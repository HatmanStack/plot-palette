import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import * as authService from '../services/auth'
import { AuthContext } from './AuthContext'
import type { AuthContextType } from './AuthContext'

export type { AuthContextType }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [idToken, setIdToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  async function checkAuth() {
    try {
      const token = await authService.getIdToken()
      if (token) {
        setIdToken(token)
        setIsAuthenticated(true)
      }
    } catch (error) {
      console.error('Auth check failed:', error)
    } finally {
      setLoading(false)
    }
  }

  async function login(email: string, password: string) {
    const token = await authService.signIn(email, password)
    setIdToken(token)
    setIsAuthenticated(true)
  }

  async function signup(email: string, password: string) {
    await authService.signUp(email, password)
    // Note: Cognito requires email verification before login
  }

  function logout() {
    authService.signOut()
    setIdToken(null)
    setIsAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, idToken, login, signup, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}
