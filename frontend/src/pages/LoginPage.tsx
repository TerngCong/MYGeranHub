import type { FormEvent } from 'react'
import { useState } from 'react'

import { useAuth } from '../hooks/useAuth'

export default function LoginPage() {
  const { loginWithGoogle, loginWithEmail, registerWithEmail, loading } = useAuth()
  const [formState, setFormState] = useState({ email: '', password: '', mode: 'login' as 'login' | 'register' })
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!formState.email || !formState.password) return

    try {
      setPending(true)
      setError(null)
      if (formState.mode === 'login') {
        await loginWithEmail(formState.email, formState.password)
      } else {
        await registerWithEmail(formState.email, formState.password)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setPending(false)
    }
  }

  const handleGoogle = async () => {
    try {
      setPending(true)
      setError(null)
      await loginWithGoogle()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-card__hero">
          <h1>MYGeranHub</h1>
          <p>Discover Malaysian grants tailored to your company profile.</p>
        </div>
        <form className="auth-card__form" onSubmit={handleSubmit}>
          <h2>{formState.mode === 'login' ? 'Sign in' : 'Create account'}</h2>
          <label>
            Email
            <input
              type="email"
              placeholder="you@startup.my"
              value={formState.email}
              onChange={(event) => setFormState((prev) => ({ ...prev, email: event.target.value }))}
              disabled={pending || loading}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              placeholder="••••••••"
              value={formState.password}
              onChange={(event) => setFormState((prev) => ({ ...prev, password: event.target.value }))}
              disabled={pending || loading}
              required
            />
          </label>
          {error ? <span className="auth-error">{error}</span> : null}
          <button type="submit" disabled={pending || loading}>
            {pending ? 'Please wait…' : formState.mode === 'login' ? 'Sign in' : 'Register'}
          </button>

          <button type="button" className="google-btn" onClick={handleGoogle} disabled={pending || loading}>
            Continue with Google
          </button>

          <p className="auth-switch">
            {formState.mode === 'login' ? 'Need an account?' : 'Already registered?'}
            <button
              type="button"
              onClick={() =>
                setFormState((prev) => ({ ...prev, mode: prev.mode === 'login' ? 'register' : 'login' }))
              }
            >
              {formState.mode === 'login' ? 'Create one' : 'Sign in'}
            </button>
          </p>
        </form>
      </div>
    </div>
  )
}


