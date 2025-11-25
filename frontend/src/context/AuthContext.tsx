import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from 'firebase/auth'
import type { User } from 'firebase/auth'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'

import { ApiError, fetchProfile } from '../services/api'
import { firebaseAuth, googleProvider } from '../services/firebase'
import type { AuthProfile } from '../types/auth'
import { AuthContext } from './authContext'
import type { AuthContextValue } from './authContext'

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null)
  const [idToken, setIdToken] = useState<string | null>(null)
  const [profile, setProfile] = useState<AuthProfile | null>(null)
  const [loading, setLoading] = useState(true)

  const syncProfile = useCallback(async (forceRefresh = false): Promise<AuthProfile | null> => {
    const currentUser = firebaseAuth.currentUser
    if (!currentUser) {
      setProfile(null)
      setIdToken(null)
      return null
    }

    const loadProfile = async (refreshToken: boolean): Promise<AuthProfile> => {
      const token = await currentUser.getIdToken(refreshToken)
      const apiProfile = await fetchProfile(token)
      setIdToken(token)
      setProfile(apiProfile)
      return apiProfile
    }

    try {
      return await loadProfile(forceRefresh)
    } catch (error) {
      const shouldRetry = !forceRefresh && error instanceof ApiError && error.status === 401
      if (shouldRetry) {
        try {
          return await loadProfile(true)
        } catch (retryError) {
          setProfile(null)
          setIdToken(null)
          throw retryError
        }
      }

      setProfile(null)
      setIdToken(null)
      throw error
    }
  }, [])

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (firebaseUser) => {
      setUser(firebaseUser)
      if (!firebaseUser) {
        setProfile(null)
        setIdToken(null)
        setLoading(false)
        return
      }

      try {
        await syncProfile()
      } catch (error) {
        console.error('Unable to sync Firebase profile', error)
        if (error instanceof ApiError && error.status === 401) {
          try {
            await signOut(firebaseAuth)
          } catch (signOutError) {
            console.error('Unable to sign out after auth failure', signOutError)
          }
        }
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
    setIdToken(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      idToken,
      profile,
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
