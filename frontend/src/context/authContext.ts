import type { User } from 'firebase/auth'
import { createContext } from 'react'

import type { AuthProfile } from '../types/auth'

export interface AuthContextValue {
  user: User | null
  idToken: string | null
  profile: AuthProfile | null
  loading: boolean
  refreshProfile: () => Promise<AuthProfile | null>
  loginWithGoogle: () => Promise<void>
  loginWithEmail: (email: string, password: string) => Promise<void>
  registerWithEmail: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
