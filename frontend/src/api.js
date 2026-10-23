const BASE = "/api";

async function handle(res) {
  if (!res.ok) {
    let detail = `${res.status}`;
    try { const b = await res.json(); if (b?.detail) detail = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail); } catch { /* json değil */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  get: (path, params) => fetch(`${BASE}${path}${qs(params)}`).then(handle),
  post: (path, body, params) => fetch(`${BASE}${path}${qs(params)}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}),
  }).then(handle),
  del: (path) => fetch(`${BASE}${path}`, { method: "DELETE" }).then(handle),
  upload: (file) => {
    const f = new FormData();
    f.append("file", file);
    return fetch(`${BASE}/upload`, { method: "POST", body: f }).then(handle);
  },
};
