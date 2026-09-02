const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

export async function login(username, password) {
  const response = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Invalid credentials.');
  return payload.access_token;
}

export async function runAgent({ primary, comparison, query, threadId, token }) {
  const body = new FormData();
  body.append('file_1', primary);
  if (comparison) body.append('file_2', comparison);
  body.append('query', query.trim());
  body.append('include_report', 'true');
  if (threadId) body.append('thread_id', threadId);
  const response = await fetch(`${API}/agent`, { method: 'POST', body, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'The analysis could not be completed.');
  return payload;
}

export async function submitJob({ primary, comparison, query, token }) {
  const body = new FormData();
  body.append('file_1', primary);
  if (comparison) body.append('file_2', comparison);
  body.append('query', query.trim());
  body.append('include_report', 'true');
  const response = await fetch(`${API}/jobs`, { method: 'POST', body, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'The analysis job could not be created.');
  return payload;
}

export async function getJob(jobId, token) {
  const response = await fetch(`${API}/jobs/${jobId}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'The analysis job could not be read.');
  return payload;
}

export function downloadPdf(base64, filename = 'satquery-report.pdf') {
  const raw = atob(base64);
  const bytes = Uint8Array.from(raw, (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
