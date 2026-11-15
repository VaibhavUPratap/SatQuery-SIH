const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
export const API_BASE_URL = API;

export async function getBengaluruCaseStudy() {
  const response = await fetch(`${API}/nisar/bengaluru/case-study`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Failed to load the Bengaluru NISAR case study.');
  return payload;
}

export async function login(username, password) {
  const response = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Invalid credentials.');
  return payload.access_token;
}

export async function searchNisarGranules({ minLon, minLat, maxLon, maxLat, startDate, endDate, productType = 'GCOV' }) {
  const params = new URLSearchParams();
  if (minLon !== undefined && minLat !== undefined && maxLon !== undefined && maxLat !== undefined) {
    params.append('min_lon', minLon);
    params.append('min_lat', minLat);
    params.append('max_lon', maxLon);
    params.append('max_lat', maxLat);
  }
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (productType) params.append('product_type', productType);

  const response = await fetch(`${API}/nisar/search?${params.toString()}`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Failed to search NISAR granules.');
  return payload;
}

export async function validateNisarFile(file) {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch(`${API}/nisar/validate`, { method: 'POST', body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Failed to validate NISAR HDF5 product.');
  return payload;
}

export async function previewNisarProduct(file) {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch(`${API}/nisar/preview`, { method: 'POST', body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Failed to render NISAR preview.');
  return payload;
}

export async function synthesizeNisarDemo({ targetDate = '2026-07-20', withFlood = true, width = 128, height = 128 } = {}) {
  const response = await fetch(`${API}/nisar/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_date: targetDate, with_flood: withFlood, width, height }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Failed to synthesize NISAR demo data.');
  return payload;
}

export async function runAgent({ primary, comparison, query, analysisType = 'auto', threadId, token }) {
  const body = new FormData();
  body.append('file_1', primary);
  if (comparison) body.append('file_2', comparison);
  body.append('query', query.trim());
  body.append('analysis_type', analysisType);
  body.append('include_report', 'true');
  if (threadId) body.append('thread_id', threadId);

  const response = await fetch(`${API}/agent`, {
    method: 'POST',
    body,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'The analysis could not be completed.');
  return payload;
}

export async function submitJob({ primary, comparison, query, analysisType = 'auto', token }) {
  const body = new FormData();
  body.append('file_1', primary);
  if (comparison) body.append('file_2', comparison);
  body.append('query', query.trim());
  body.append('analysis_type', analysisType);
  body.append('include_report', 'true');

  const response = await fetch(`${API}/jobs`, {
    method: 'POST',
    body,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'The analysis job could not be created.');
  return payload;
}

export async function getJob(jobId, token) {
  const response = await fetch(`${API}/jobs/${jobId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'The analysis job could not be read.');
  return payload;
}

export function downloadPdf(base64, filename = 'terrapulse-nisar-report.pdf') {
  const raw = atob(base64);
  const bytes = Uint8Array.from(raw, (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
