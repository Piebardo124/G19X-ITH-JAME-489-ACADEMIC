const ACTIVE_STATUSES = new Set(['QUEUED', 'PROCESSING']);
const TERMINAL_STATUSES = new Set(['COMPLETED', 'COMPLETED_WITH_WARNINGS', 'FAILED']);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// The subject only partitions browser state. API authorization still validates the JWT.
export function csvImportStorageKey(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const bytes = Uint8Array.from(atob(payload), character => character.charCodeAt(0));
    const { sub } = JSON.parse(new TextDecoder().decode(bytes));
    return typeof sub === 'string' && sub.trim()
      ? `plurione:csv-import:${encodeURIComponent(sub)}`
      : null;
  } catch {
    return null;
  }
}

export function loadCsvImport(storageKey, storage) {
  if (!storageKey) return null;
  try {
    const importId = (storage ?? globalThis.sessionStorage)?.getItem(storageKey);
    return UUID_PATTERN.test(importId || '') ? importId : null;
  } catch {
    return null;
  }
}

export function saveCsvImport(storageKey, importId, storage) {
  if (!storageKey || !UUID_PATTERN.test(importId || '')) return false;
  try {
    const target = storage ?? globalThis.sessionStorage;
    if (!target) return false;
    target.setItem(storageKey, importId);
    return true;
  } catch {
    return false;
  }
}

export function clearCsvImport(storageKey, storage) {
  if (!storageKey) return;
  try {
    (storage ?? globalThis.sessionStorage)?.removeItem(storageKey);
  } catch {
    // Storage may be unavailable; completing an import must still update the UI.
  }
}

export function csvImportMessage(job) {
  const count = field => Number.isInteger(job[field]) && job[field] >= 0 ? job[field] : 0;
  const processed = count('processed_rows');
  const summary = `${processed} procesadas, ${count('skipped_rows')} omitidas y ${count('failed_rows')} fallidas.`;
  const details = typeof job.errors === 'string' && job.errors.trim() ? ` ${job.errors.trim()}` : '';
  if (job.status === 'FAILED') {
    const partial = processed > 0
      ? ' Los comentarios procesados ya están guardados; volver a enviar el archivo puede duplicarlos.'
      : '';
    return { message: `Carga fallida: ${summary}${partial}${details}`, type: 'error' };
  }
  if (job.status === 'COMPLETED_WITH_WARNINGS') {
    return { message: `Carga terminada con observaciones: ${summary}${details}`, type: 'warning' };
  }
  if (job.status === 'COMPLETED') {
    return { message: `Carga completada: ${summary}`, type: 'success' };
  }
  return { message: `Procesando CSV: ${processed} filas procesadas...`, type: 'progress' };
}

export function pollCsvImport({
  requestStatus,
  onProgress,
  onTerminal,
  onProblem,
  onMissing,
  onSessionExpired,
  schedule = setTimeout,
  unschedule = clearTimeout,
  interval = 2000,
  retryInterval = 5000,
}) {
  let stopped = false;
  let timer;
  const controller = new AbortController();

  const poll = async () => {
    let job;
    try {
      job = await requestStatus({ signal: controller.signal });
    } catch (error) {
      if (stopped) return;
      const status = error.response?.status;
      if (status === 404) {
        onMissing();
        return;
      }
      const retrying = !status || status >= 500 || [408, 425, 429].includes(status);
      onProblem({ error, retrying });
      if (status === 401) onSessionExpired?.();
      if (retrying) timer = schedule(poll, retryInterval);
      return;
    }
    if (stopped) return;
    if (TERMINAL_STATUSES.has(job?.status)) {
      onTerminal(job);
    } else if (ACTIVE_STATUSES.has(job?.status)) {
      onProgress(job);
      timer = schedule(poll, interval);
    } else {
      onProblem({ error: new Error('Estado de importación desconocido'), retrying: true });
      timer = schedule(poll, retryInterval);
    }
  };

  void poll();
  return () => {
    stopped = true;
    unschedule(timer);
    controller.abort();
  };
}
