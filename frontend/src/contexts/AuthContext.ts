import { createContext } from 'react'

export interface AuthContextType {
  isAuthenticated: boolean
  idToken: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => void
  loading: boolean
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)
