import type { AuthProfile } from '../types/auth'
import type { ChatMessageResponse, ChatSessionResponse } from '../types/chat'

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

export async function ensureChatSession(idToken: string): Promise<ChatSessionResponse> {
  return request<ChatSessionResponse>('/chat/session', { method: 'POST' }, idToken)
}

interface SendMessagePayload {
  sessionId?: string
  prompt: string
}

export async function sendChatMessage(
  idToken: string,
  payload: SendMessagePayload,
): Promise<ChatMessageResponse> {
  return request<ChatMessageResponse>(
    '/chat/message',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    idToken,
  )
}

