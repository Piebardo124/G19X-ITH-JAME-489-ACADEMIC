import assert from 'node:assert/strict';
import test from 'node:test';
import {
  clearCsvImport, csvImportMessage, csvImportStorageKey, loadCsvImport, pollCsvImport, saveCsvImport,
} from '../src/utils/csvImport.js';

const IMPORT_ID = '214b8daa-20cd-467a-9f52-df115a3d89af';
const tick = () => new Promise(resolve => setImmediate(resolve));
const token = (subject, extra = {}) => `header.${Buffer.from(JSON.stringify({ sub: subject, ...extra })).toString('base64url')}.signature`;
const memoryStorage = () => {
  const entries = new Map();
  return {
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
    removeItem: key => entries.delete(key),
  };
};

function pollingHarness(requestStatus, onMissing = () => {}) {
  const scheduled = new Map();
  const progress = [], terminal = [], problems = [];
  let timerId = 0, expired = 0, missing = 0;
  const stop = pollCsvImport({
    requestStatus,
    onProgress: job => progress.push(job),
    onTerminal: job => terminal.push(job),
    onProblem: problem => problems.push(problem),
    onMissing: () => { missing++; onMissing(); },
    onSessionExpired: () => expired++,
    schedule: (callback, delay) => { const id = ++timerId; scheduled.set(id, { callback, delay }); return id; },
    unschedule: id => scheduled.delete(id),
  });
  return {
    progress, terminal, problems, scheduled, stop,
    get expired() { return expired; }, get missing() { return missing; },
    async next() {
      const [id, task] = scheduled.entries().next().value;
      scheduled.delete(id);
      await task.callback();
      await tick();
    },
  };
}

test('active import survives reload and renewed token for the same identity', () => {
  const storage = memoryStorage();
  const firstKey = csvImportStorageKey(token('hr@example.test', { exp: 10 }));
  assert.equal(saveCsvImport(firstKey, IMPORT_ID, storage), true);
  const renewedKey = csvImportStorageKey(token('hr@example.test', { exp: 20 }));
  assert.equal(loadCsvImport(renewedKey, storage), IMPORT_ID);
  assert.equal(loadCsvImport(csvImportStorageKey(token('other@example.test')), storage), null);
  clearCsvImport(renewedKey, storage);
  assert.equal(loadCsvImport(firstKey, storage), null);
});

test('storage identity supports Unicode subjects and rejects malformed tokens', () => {
  assert.ok(csvImportStorageKey(token('josé@example.test')).includes('jos%C3%A9'));
  for (const invalid of [null, '', 'garbage', 'a.%%.b', token(null), token('')]) {
    assert.equal(csvImportStorageKey(invalid), null);
  }
});

test('invalid persisted IDs and blocked storage never become requests or crash', () => {
  const storage = memoryStorage();
  storage.setItem('key', '../../other-route');
  assert.equal(loadCsvImport('key', storage), null);
  assert.equal(saveCsvImport('key', 'not-a-uuid', storage), false);
  const blocked = {
    getItem() { throw new Error('blocked'); },
    setItem() { throw new Error('blocked'); },
    removeItem() { throw new Error('blocked'); },
  };
  assert.equal(loadCsvImport('key', blocked), null);
  assert.equal(saveCsvImport('key', IMPORT_ID, blocked), false);
  assert.doesNotThrow(() => clearCsvImport('key', blocked));
});

for (const failure of [new Error('offline'), { response: { status: 503 } }, { response: { status: 429 } }]) {
  test(`polling resumes after ${failure.response?.status || 'network error'} without losing its job`, async () => {
    let calls = 0;
    const h = pollingHarness(async () => {
      if (++calls === 1) throw failure;
      return { status: 'PROCESSING', processed_rows: 2 };
    });
    await tick();
    assert.equal(h.problems.length, 1);
    assert.equal(h.problems[0].retrying, true);
    assert.equal(h.terminal.length, 0);
    assert.equal(h.missing, 0);
    assert.equal([...h.scheduled.values()][0].delay, 5000);
    await h.next();
    assert.equal(h.progress[0].processed_rows, 2);
    assert.equal([...h.scheduled.values()][0].delay, 2000);
    h.stop();
  });
}

for (const status of ['COMPLETED', 'COMPLETED_WITH_WARNINGS', 'FAILED']) {
  test(`${status} ends polling and delivers partial counts for refreshing the panel`, async () => {
    const job = { status, processed_rows: 3, failed_rows: 1, skipped_rows: 2 };
    const h = pollingHarness(async () => job);
    await tick();
    assert.deepEqual(h.terminal, [job]);
    assert.equal(h.scheduled.size, 0);
    assert.equal(h.problems.length, 0);
    h.stop();
  });
}

test('failed import explains saved partial results and duplicate risk', () => {
  const result = csvImportMessage({ status: 'FAILED', processed_rows: 3, skipped_rows: 2, failed_rows: 1, errors: 'CSV mal formado.' });
  assert.equal(result.type, 'error');
  assert.match(result.message, /3 procesadas, 2 omitidas y 1 fallidas/);
  assert.match(result.message, /ya están guardados/);
  assert.match(result.message, /duplicarlos/);
  assert.match(result.message, /CSV mal formado/);
});

test('complete, warning and pending messages preserve their intended severity', () => {
  assert.equal(csvImportMessage({ status: 'COMPLETED' }).type, 'success');
  assert.equal(csvImportMessage({ status: 'COMPLETED_WITH_WARNINGS', errors: 'Aviso' }).type, 'warning');
  assert.equal(csvImportMessage({ status: 'PROCESSING', processed_rows: 2 }).message, 'Procesando CSV: 2 filas procesadas...');
});

for (const status of [401, 403]) {
  test(`${status} pauses polling without declaring the import terminal`, async () => {
    const h = pollingHarness(async () => { throw { response: { status } }; });
    await tick();
    assert.equal(h.problems[0].retrying, false);
    assert.equal(h.terminal.length, 0);
    assert.equal(h.scheduled.size, 0);
    assert.equal(h.expired, status === 401 ? 1 : 0);
    assert.equal(h.missing, 0);
    h.stop();
  });
}

test('confirmed 404 clears stored tracking and releases upload without reporting success', async () => {
  const storage = memoryStorage();
  const storageKey = csvImportStorageKey(token('hr@example.test'));
  saveCsvImport(storageKey, IMPORT_ID, storage);
  let activeImportId = loadCsvImport(storageKey, storage);
  let messageType = 'progress';
  const h = pollingHarness(async () => { throw { response: { status: 404 } }; }, () => {
    clearCsvImport(storageKey, storage);
    activeImportId = null;
    messageType = 'warning';
  });
  await tick();
  assert.equal(loadCsvImport(storageKey, storage), null);
  assert.equal(Boolean(activeImportId), false);
  assert.equal(messageType, 'warning');
  assert.equal(h.terminal.length, 0);
  assert.equal(h.missing, 1);
  assert.equal(h.problems.length, 0);
  assert.equal(h.scheduled.size, 0);
  h.stop();
});

test('unknown response status retains tracking and retries instead of allowing another upload', async () => {
  const h = pollingHarness(async () => ({ status: 'UNEXPECTED' }));
  await tick();
  assert.equal(h.terminal.length, 0);
  assert.equal(h.problems[0].retrying, true);
  assert.equal(h.scheduled.size, 1);
  h.stop();
});

test('unmount cancels pending request and ignores its late completion', async () => {
  let resolve, signal;
  const h = pollingHarness(options => {
    signal = options.signal;
    return new Promise(done => { resolve = done; });
  });
  h.stop();
  assert.equal(signal.aborted, true);
  resolve({ status: 'FAILED', processed_rows: 1 });
  await tick();
  assert.equal(h.terminal.length, 0);
  assert.equal(h.problems.length, 0);
  assert.equal(h.scheduled.size, 0);
});

test('unmount removes scheduled retry', async () => {
  const h = pollingHarness(async () => { throw new Error('offline'); });
  await tick();
  assert.equal(h.scheduled.size, 1);
  h.stop();
  assert.equal(h.scheduled.size, 0);
});
