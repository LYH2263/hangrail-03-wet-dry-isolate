export class ApiError extends Error {
  status: number;
  code?: string;
  body: unknown;
  constructor(status: number, raw: string) {
    let body: unknown = undefined;
    let message = raw || `HTTP ${status}`;
    let code: string | undefined;
    try {
      body = raw ? JSON.parse(raw) : undefined;
    } catch {
      body = undefined;
    }
    const detail = (body as { detail?: unknown })?.detail;
    if (detail && typeof detail === "object") {
      const d = detail as { code?: string; message?: string };
      if (d.message) message = d.message;
      code = d.code;
    } else if (typeof detail === "string") {
      message = detail;
    }
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.body = body;
  }
  get isIsolationConflict() {
    return this.status === 409 && this.code === "isolation_conflict";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const STATE_LABEL: Record<string, string> = { dry: "干衣", wet: "湿衣" };
