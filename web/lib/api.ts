// Thin client for the Medero API. The model key never reaches the browser.
// On a phone/iPad the page is opened at the Mac's LAN address, so "localhost" would point at the
// phone itself. Default: same host and protocol as the page, port 8000.
export function apiBase(): string {
  const env = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/$/, "");
  if (typeof window === "undefined") return env || "http://localhost:8000";
  const pageHost = window.location.hostname;
  if (env && !(/localhost|127\.0\.0\.1/.test(env) && pageHost !== "localhost" && pageHost !== "127.0.0.1")) return env;
  return `${window.location.protocol}//${pageHost}:8000`;
}

export function wsUrl(path: string): string {
  return apiBase().replace(/^http/, "ws") + path;
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(apiBase() + path, init);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((body && (body.detail || body.error)) || `HTTP ${r.status}`);
  return body as T;
}

export const postJson = <T = any>(path: string, data: unknown) =>
  api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

export function postForm<T = any>(path: string, fields: Record<string, string | Blob | null | undefined>) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) if (v != null) fd.append(k, v);
  return api<T>(path, { method: "POST", body: fd });
}

// Per-tab state only (sessionStorage): session id and language. Wrapped because storage can throw.
export function save(key: string, value: string) {
  try { sessionStorage.setItem("medero." + key, value); } catch {}
}
export function load(key: string): string | null {
  try { return sessionStorage.getItem("medero." + key); } catch { return null; }
}

export type Fact = { id: string; value: string | null; source: string; approved: boolean; value_ko?: string | null };
export type CaseCard = {
  patient_language: string; alias: string; chief_complaint: Fact; symptoms: Fact[]; tried: Fact[];
  history: Fact[]; allergies: Fact; medications: Fact; insurance_type: string; may_answer: string[]; must_ask: string[];
};

export function allFacts(c: CaseCard): Fact[] {
  return [c.chief_complaint, ...c.symptoms, ...c.tried, ...c.history, c.allergies, c.medications];
}

export const FACT_LABELS: Record<string, string> = {
  cc: "cc", sym_onset: "onset", sym_duration: "duration", sym_site: "site", sym_severity: "severity",
  allergy: "allergies", meds: "medications",
};
