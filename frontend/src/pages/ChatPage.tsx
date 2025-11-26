import { useMemo, useState } from 'react'
import { ChatWindow } from '../components/ChatWindow'
import { LoadingOverlay } from '../components/LoadingOverlay'
import { useAuth } from '../hooks/useAuth'
import { sendChatMessage, resetChatSession } from '../services/api'
import type { ChatMessage } from '../types/chat'

export default function ChatPage() {
  const { profile, idToken, logout } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [language, setLanguage] = useState<'en' | 'ms'>('en')
  const [isMenuOpen, setIsMenuOpen] = useState(false)

  const avatarLetter = useMemo(() => profile?.displayName?.[0]?.toUpperCase() ?? profile?.email?.[0]?.toUpperCase() ?? 'U', [profile])

  const handleReset = async () => {
    if (!idToken) return
    if (!confirm(language === 'en' ? 'Are you sure you want to clear the chat?' : 'Adakah anda pasti mahu memadamkan perbualan?')) return

    try {
      await resetChatSession(idToken)
      setMessages([])
    } catch (err) {
      console.error("Failed to reset session:", err)
      setError("Failed to reset chat")
    }
  }

  const handleSend = async (prompt: string) => {
    if (!idToken) return
    setIsSending(true)
    setError(null)

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: prompt,
      createdAt: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMsg])

    try {
      const response = await sendChatMessage(idToken, prompt)

      // Handle new response structure
      // response is now { status: "reply" | "trigger_judge", message: string[], payload?: string }

      let content = ""
      if (response.status === "reply" && response.message && response.message.length > 0) {
        content = response.message[0]
      } else if (response.status === "trigger_judge") {
        content = "Grant search triggered! (This is a placeholder for the judge logic)"
      } else if (response.response) {
        // Fallback for old structure if any
        content = response.response
      }

      if (!content) {
        throw new Error("Received empty response from AI")
      }

      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: content,
        createdAt: new Date().toISOString()
      }
      setMessages(prev => [...prev, aiMsg])
      setIsSending(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send message')
      setIsSending(false)
    }
  }

  if (!profile) {
    return <LoadingOverlay message="Preparing your workspace..." />
  }

  return (
    <div className="chat-shell">
      <section className="chat-surface">
        <header className="chat-hero">
          <div className="hero-brand">
            <h1 className="app-brand">MYGeranHub</h1>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              className="lang-toggle"
              onClick={handleReset}
              title="Reset Chat"
              style={{ backgroundColor: '#dc3545', borderColor: '#dc3545', padding: '0.5rem' }}
            >
              🗑️
            </button>

            <button
              className="lang-toggle"
              onClick={() => setLanguage(prev => prev === 'en' ? 'ms' : 'en')}
            >
              {language === 'en' ? 'BM' : 'EN'}
            </button>
          </div>

          <div className="user-menu-container">
            <button
              className="avatar-btn"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              title="Account"
            >
              {avatarLetter}
            </button>

            {isMenuOpen && (
              <div className="user-dropdown">
                <div className="user-info">
                  <p className="name">{profile.displayName ?? 'Member'}</p>
                  <p className="email">{profile.email}</p>
                </div>
                <button
                  className="signout-btn"
                  onClick={() => {
                    if (confirm(language === 'en' ? 'Are you sure you want to sign out?' : 'Adakah anda pasti mahu log keluar?')) {
                      logout()
                    }
                  }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </header>

        <ChatWindow messages={messages} onSend={handleSend} isSending={isSending} language={language} />
        {error && <div className="toast-error">{error}</div>}
      </section>
    </div>
  )
}



