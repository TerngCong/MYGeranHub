export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  createdAt: string
}

export interface ChatSessionResponse {
  sessionId: string
  userId: string
}

export interface ChatMessageResponse {
  sessionId: string
  reply: string
  messages: ChatMessage[]
}



