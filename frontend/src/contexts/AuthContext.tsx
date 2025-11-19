import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

interface AuthContextType {
  isAuthenticated: boolean
  idToken: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [idToken, setIdToken] = useState<string | null>(null)
  const [loading] = useState(false)

  async function login(email: string, _password: string) {
    // TODO: Implement Cognito login in Task 2
    console.log('Login:', email)
    setIsAuthenticated(true)
    setIdToken('mock-token')
  }

  async function signup(email: string, _password: string) {
    // TODO: Implement Cognito signup in Task 2
    console.log('Signup:', email)
  }

  function logout() {
    setIdToken(null)
    setIsAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, idToken, login, signup, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
