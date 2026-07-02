// Same-site with the frontend (localhost) so the httpOnly auth cookie is sent.
export const API_BASE_URL = 'http://localhost:8000';

/**
 * fetch wrapper: always sends the auth cookie, JSON-encodes bodies, and
 * returns the parsed JSON plus ok/status. Pass { form } for multipart uploads.
 */
export async function api(path, { method = 'GET', body, form } = {}) {
  const opts = { method, credentials: 'include', headers: {} };
  if (form) {
    opts.body = form; // FormData sets its own Content-Type
  } else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE_URL}${path}`, opts);
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty/non-JSON body */
  }
  return { ok: res.ok, status: res.status, data };
}
