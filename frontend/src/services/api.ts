import type { AuthProfile } from '../types/auth'

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
    throw new Error(message || 'Request failed')
  }

  return (await response.json()) as T
}

export async function fetchProfile(idToken: string): Promise<AuthProfile> {
  return request<AuthProfile>('/auth/profile', { method: 'GET' }, idToken)
}
