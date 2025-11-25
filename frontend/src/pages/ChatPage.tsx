import { useMemo } from 'react'

import { LoadingOverlay } from '../components/LoadingOverlay'
import { useAuth } from '../hooks/useAuth'

export default function ChatPage() {
  const { profile, logout } = useAuth()

  const avatarLetter = useMemo(() => profile?.displayName?.[0]?.toUpperCase() ?? profile?.email?.[0]?.toUpperCase() ?? 'U', [profile])

  if (!profile) {
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
        </header>
        <div className="chat-window chat-placeholder">
          <div className="chat-empty">
            <h3>Live chat is getting an upgrade</h3>
            <p>JamAI Copilot is temporarily offline while we refactor the experience. Check back soon for the new flow.</p>
          </div>
        </div>
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
      </aside>
    </div>
  )
}
