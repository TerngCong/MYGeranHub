import type { ChatMessage } from '../types/chat'

interface MessageBubbleProps {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  return (
    <div className={`message-bubble ${isUser ? 'message-user' : 'message-bot'}`}>
      <p>{message.content}</p>
      <span>{new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
    </div>
  )
}



