import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { api, clearToken, getToken, setToken } from './api'
import type { User } from './types'

const USER_KEY = 'taskboard_user'

type TokenResponse = { access_token: string; user: User }

type AuthContextValue = {
  user: User | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, displayName: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function loadStoredUser(): User | null {
  if (!getToken()) return null
  const raw = localStorage.getItem(USER_KEY)
  return raw ? (JSON.parse(raw) as User) : null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(loadStoredUser)

  const applySession = useCallback((resp: TokenResponse) => {
    setToken(resp.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(resp.user))
    setUser(resp.user)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      applySession(await api.post<TokenResponse>('/api/v1/auth/login', { email, password }))
    },
    [applySession],
  )

  const register = useCallback(
    async (email: string, displayName: string, password: string) => {
      applySession(
        await api.post<TokenResponse>('/api/v1/auth/register', {
          email,
          display_name: displayName,
          password,
        }),
      )
    },
    [applySession],
  )

  const logout = useCallback(() => {
    clearToken()
    localStorage.removeItem(USER_KEY)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: user !== null, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
