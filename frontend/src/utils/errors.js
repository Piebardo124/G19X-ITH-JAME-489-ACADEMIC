export function mensajeError(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail.trim() || fallback;
  if (Array.isArray(detail)) {
    return detail.map(item => typeof item?.msg === 'string' ? item.msg : '')
      .filter(Boolean).join(' ') || fallback;
  }
  return fallback;
}
