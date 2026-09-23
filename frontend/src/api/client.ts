export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      /* 非 JSON 错误体 */
    }
    const d = (detail as { detail?: unknown } | null)?.detail;
    if (d && typeof d === "object" && "message" in d) {
      const obj = d as { code?: string; message: string };
      throw new ApiError(res.status, obj.code ?? "error", obj.message);
    }
    if (typeof d === "string" && d) {
      throw new ApiError(res.status, "error", d);
    }
    throw new ApiError(res.status, "error", res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
