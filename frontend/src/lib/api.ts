export type Role = "admin" | "issuer" | "owner" | "verifier";
export interface User { id: number; email: string; name: string; role: Role; status: string; organization?: string | null }

const TOKEN_KEY = "sv_token";
export const getToken = () => (typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY));
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function parseError(r: Response): Promise<ApiError> {
  let msg = r.statusText;
  try {
    const j = await r.json();
    msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: { msg: string }) => d.msg).join("; ") : msg;
  } catch {}
  return new ApiError(r.status, msg);
}

export async function api<T = unknown>(path: string, opts: { method?: string; json?: unknown; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  if (opts.form) body = opts.form;
  const r = await fetch(`/api${path}`, { method: opts.method || (body ? "POST" : "GET"), headers, body });
  if (r.status === 401 && t && !path.startsWith("/auth/login")) { setToken(null); if (typeof window !== "undefined") window.location.href = "/login"; }
  if (!r.ok) throw await parseError(r);
  return r.json() as Promise<T>;
}

export async function fetchBlob(path: string): Promise<Blob> {
  const r = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!r.ok) throw await parseError(r);
  return r.blob();
}

// ---- types ----
export interface Reason { source: string; text: string; feature?: string; rule?: string; score?: number }
export interface FraudReport {
  id: number; risk_level: "Low" | "Medium" | "High"; risk_score: number; document_score: number | null; activity_score: number | null;
  reasons: Reason[]; features: Record<string, unknown>; model_info: Record<string, unknown>; created_at: string;
}
export interface Tx { tx_hash: string; kind: string; block_number: number; timestamp: string; status: string }
export interface Doc {
  id: number; title: string; doc_type: string; filename: string; mime_type: string; size_bytes: number; sha256: string;
  status: "stored" | "registered" | "revoked"; ipfs_cid: string | null; created_at: string; owner: { id: number; name: string };
  issuer: { name: string; address: string } | null; is_owner: boolean; risk_level?: string | null;
  transactions?: Tx[]; fraud_report?: FraudReport | null;
  shares?: { id: number; user: { id: number; name: string; email: string }; expires_at: string | null }[];
}
export type VStatus = "Verified" | "Modified" | "Unknown" | "Revoked";
export interface Verification {
  id: number; filename: string; file_sha256: string; status: VStatus; document_id: number | null; similarity: number | null;
  issuer_address: string | null; issuer_authorized: boolean | null; chain_timestamp: string | null; created_at: string;
  details: { notes: string[]; issuer_name?: string; document_title?: string; registered_hash?: string; revocation_reason?: string };
  verifier: { id: number; name: string }; fraud_report: FraudReport | null;
}
