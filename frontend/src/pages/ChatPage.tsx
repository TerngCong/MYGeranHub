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
    return <LoadingOverlay message="Preparing your workspace..." />
  }

  return (
    <div className="chat-shell">
      <section className="chat-surface">
        <header className="chat-hero">
          <div>
            <p className="eyebrow">JamAI Copilot</p>
            <h1>Find the right Malaysian grants faster</h1>
            <p>Describe your business goals and JamAI will shortlist curated opportunities.</p>
          </div>
          <span className="session-chip">Session #{sessionId.slice(0, 8)}</span>
        </header>
        <ChatWindow messages={messages} onSend={handleSend} isSending={isSending} />
      </section>

      <aside className="account-panel">
        <div className="account-card">
          <div className="avatar">{avatarLetter}</div>
          <div className="account-details">
            <p className="account-name">{profile.displayName ?? 'MYGeranHub Member'}</p>
            <span className="account-email">{profile.email ?? 'No email available'}</span>
          </div>
        </div>
        <p className="account-hint">Keep the conversation focused on grants, eligibility, or proposal prep for the clearest answers.</p>
        <button className="secondary-btn" onClick={logout}>
          Sign out
        </button>
        {error ? <span className="chat-error">{error}</span> : null}
      </aside>
    </div>
  )
}



