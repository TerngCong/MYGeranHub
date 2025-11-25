import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'

import type { ChatMessage } from '../types/chat'
import { MessageBubble } from './MessageBubble'

interface ChatWindowProps {
  messages: ChatMessage[]
  onSend: (prompt: string) => Promise<void>
  isSending: boolean
}

export function ChatWindow({ messages, onSend, isSending }: ChatWindowProps) {
  const [draft, setDraft] = useState('')
  const viewportRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    viewportRef.current?.scrollTo({
      top: viewportRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!draft.trim()) return
    const value = draft
    setDraft('')
    await onSend(value)
  }

  return (
    <div className="chat-window">
      <div className="chat-viewport" ref={viewportRef}>
        {messages.length === 0 ? (
          <div className="chat-empty">
            <h3>Welcome to MYGeranHub</h3>
            <p>Ask anything about Malaysian grants to get started.</p>
          </div>
        ) : (
          messages.map((message) => <MessageBubble key={message.id} message={message} />)
        )}
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type your question…"
          disabled={isSending}
        />
        <button type="submit" disabled={isSending || !draft.trim()}>
          {isSending ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  )
}


