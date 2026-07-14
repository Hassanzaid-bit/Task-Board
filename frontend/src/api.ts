const TOKEN_KEY = 'taskboard_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type ErrorDetail = {
  code?: string
  message?: string
  errors?: { field: string; message: string }[]
}

function extractMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: ErrorDetail | string } | null)?.detail
  if (typeof detail === 'string') return detail
  if (detail?.errors?.length) {
    return detail.errors.map((e) => `${e.field}: ${e.message}`).join('; ')
  }
  if (detail?.message) return detail.message
  return `Request failed (${status})`
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const resp = await fetch(path, { ...options, headers })
  if (resp.status === 204) return undefined as T

  const body = await resp.json().catch(() => null)
  if (!resp.ok) throw new ApiError(resp.status, extractMessage(resp.status, body))
  return body as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(data) }),
  patch: <T>(path: string, data: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (path: string) => request<void>(path, { method: 'DELETE' }),
}
