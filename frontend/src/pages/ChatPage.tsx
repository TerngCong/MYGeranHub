import { useEffect, useMemo, useState } from 'react'

import { LoadingOverlay } from '../components/LoadingOverlay'
import { ChatWindow } from '../components/ChatWindow'
import { useAuth } from '../hooks/useAuth'
import { sendChatMessage } from '../services/api'
import type { ChatMessage } from '../types/chat'

export default function ChatPage() {
  const { profile, idToken, sessionId, logout } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const avatarLetter = useMemo(() => profile?.displayName?.[0]?.toUpperCase() ?? profile?.email?.[0]?.toUpperCase() ?? 'U', [profile])

  useEffect(() => {
    setMessages([])
  }, [sessionId])

  const handleSend = async (prompt: string) => {
    if (!idToken) return
    setIsSending(true)
    setError(null)
    try {
      const response = await sendChatMessage(idToken, { prompt, sessionId: sessionId ?? undefined })
      setMessages(response.messages)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send message')
    } finally {
      setIsSending(false)
    }
  }

  if (!profile || !sessionId) {
    return <LoadingOverlay message="Preparing your workspace…" />
  }

  return (
    <div className="chat-layout">
      <aside>
        <div className="user-card">
          <div className="avatar">{avatarLetter}</div>
          <div>
            <strong>{profile.displayName ?? 'MYGeranHub Member'}</strong>
            <p>{profile.email ?? 'No email'}</p>
          </div>
        </div>
        <p className="user-card__hint">Ask anything about available Malaysian government grants.</p>
        <button className="secondary-btn" onClick={logout}>
          Sign out
        </button>
        {error ? <span className="chat-error">{error}</span> : null}
      </aside>

      <section>
        <header>
          <div>
            <h1>Grant Copilot</h1>
            <p>Chat with JamAI to explore curated grant opportunities.</p>
          </div>
          <span className="session-pill">Session #{sessionId.slice(0, 8)}</span>
        </header>

        <ChatWindow messages={messages} onSend={handleSend} isSending={isSending} />
      </section>
    </div>
  )
}



