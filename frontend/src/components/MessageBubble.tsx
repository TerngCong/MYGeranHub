import { useEffect, useState } from 'react'
import type { ChatMessage } from '../types/chat'

interface MessageBubbleProps {
  message: ChatMessage
  onContentUpdate?: () => void
}

export function MessageBubble({ message, onContentUpdate }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [displayedContent, setDisplayedContent] = useState(isUser ? message.content : '')

  useEffect(() => {
    if (isUser) {
      setDisplayedContent(message.content)
      return
    }

    let currentIndex = 0
    const content = message.content
    setDisplayedContent('')

    const intervalId = setInterval(() => {
      if (currentIndex >= content.length) {
        clearInterval(intervalId)
        return
      }

      // Speed up: Add 2 chars per tick
      const chunkSize = 2
      const nextChunk = content.slice(currentIndex, currentIndex + chunkSize)
      setDisplayedContent(prev => prev + nextChunk)
      currentIndex += chunkSize

      if (onContentUpdate) {
        onContentUpdate()
      }
    }, 15)

    return () => clearInterval(intervalId)
  }, [message.content, isUser])

  return (
    <div className={`message-bubble ${isUser ? 'message-user' : 'message-bot'}`}>
      <p>{displayedContent}</p>
      <span>{new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
    </div>
  )
}