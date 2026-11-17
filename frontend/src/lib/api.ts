declare global {
  interface Window {
    __AIRWIN_TOKEN__?: string
  }
}

export const token: string =
  window.__AIRWIN_TOKEN__ ??
  new URLSearchParams(window.location.search).get("t") ??
  (import.meta.env.VITE_AIRWIN_TOKEN as string | undefined) ??
  ""

export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    method,
    headers: { "X-Token": token, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    /* sin cuerpo */
  }
  if (!res.ok) {
    const msg = (data as { error?: string } | null)?.error ?? `Error ${res.status}`
    throw new ApiError(msg)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T = { ok: boolean }>(path: string, body: unknown = {}) => request<T>("POST", path, body),
}

export function eventsUrl() {
  return `/api/events?t=${encodeURIComponent(token)}`
}
