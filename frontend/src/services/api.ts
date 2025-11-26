import type { AuthProfile } from '../types/auth'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message || 'Request failed')
    this.name = 'ApiError'
    this.status = status
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(
  path: string,
  options: RequestInit,
  idToken: string,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${idToken}`,
      ...(options.headers ?? {}),
    },
  })

  if (!response.ok) {
    const message = await response.text()
    throw new ApiError(response.status, message || response.statusText || 'Request failed')
  }

  return (await response.json()) as T
}

export async function fetchProfile(idToken: string): Promise<AuthProfile> {
  return request<AuthProfile>('/auth/profile', { method: 'GET' }, idToken)
}

export interface ChatResponse {
  status?: string
  message?: string[]
  payload?: string
  response?: string // for backward compatibility
}

export async function sendChatMessage(idToken: string, message: string): Promise<ChatResponse> {
  return request<ChatResponse>('/jamai/message', {
    method: 'POST',
    body: JSON.stringify({ message }),
  }, idToken)
}

export async function resetChatSession(idToken: string): Promise<void> {
  await request('/jamai/reset', {
    method: 'POST',
  }, idToken)
}
