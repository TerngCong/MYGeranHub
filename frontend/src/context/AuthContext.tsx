import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from 'firebase/auth'
import type { User } from 'firebase/auth'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { PropsWithChildren } from 'react'

import { ensureChatSession, fetchProfile } from '../services/api'
import { firebaseAuth, googleProvider } from '../services/firebase'
import type { AuthProfile } from '../types/auth'

interface AuthContextValue {
  user: User | null
  idToken: string | null
  profile: AuthProfile | null
  loading: boolean
  sessionId: string | null
  refreshProfile: () => Promise<AuthProfile | null>
  loginWithGoogle: () => Promise<void>
  loginWithEmail: (email: string, password: string) => Promise<void>
  registerWithEmail: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null)
  const [idToken, setIdToken] = useState<string | null>(null)
  const [profile, setProfile] = useState<AuthProfile | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const syncProfile = useCallback(async (): Promise<AuthProfile | null> => {
    const currentUser = firebaseAuth.currentUser
    if (!currentUser) {
      setProfile(null)
      setIdToken(null)
      setSessionId(null)
      return null
    }

    const token = await currentUser.getIdToken()
    setIdToken(token)
    const apiProfile = await fetchProfile(token)
    setProfile(apiProfile)
    const session = await ensureChatSession(token)
    setSessionId(session.sessionId)
    return apiProfile
  }, [])

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (firebaseUser) => {
      setUser(firebaseUser)
      if (!firebaseUser) {
        setProfile(null)
        setIdToken(null)
        setSessionId(null)
        setLoading(false)
        return
      }

      try {
        await syncProfile()
      } catch (error) {
        console.error('Unable to sync Firebase profile', error)
      } finally {
        setLoading(false)
      }
    })

    return () => unsubscribe()
  }, [syncProfile])

  const loginWithGoogle = useCallback(async () => {
    await signInWithPopup(firebaseAuth, googleProvider)
    await syncProfile()
  }, [syncProfile])

  const loginWithEmail = useCallback(
    async (email: string, password: string) => {
      await signInWithEmailAndPassword(firebaseAuth, email, password)
      await syncProfile()
    },
    [syncProfile],
  )

  const registerWithEmail = useCallback(
    async (email: string, password: string) => {
      await createUserWithEmailAndPassword(firebaseAuth, email, password)
      await syncProfile()
    },
    [syncProfile],
  )

  const logout = useCallback(async () => {
    await signOut(firebaseAuth)
    setProfile(null)
    setSessionId(null)
    setIdToken(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      idToken,
      profile,
      sessionId,
      loading,
      refreshProfile: syncProfile,
      loginWithGoogle,
      loginWithEmail,
      registerWithEmail,
      logout,
    }),
    [
      user,
      idToken,
      profile,
      sessionId,
      loading,
      syncProfile,
      loginWithGoogle,
      loginWithEmail,
      registerWithEmail,
      logout,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider')
  }

  return context
}

