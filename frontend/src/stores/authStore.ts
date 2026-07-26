import { create } from 'zustand'

interface AuthUser {
  id: string
  username: string
  email?: string
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  login: (token: string, refreshToken: string, user: AuthUser) => void
  setTokens: (token: string, refreshToken: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  login: (token, refreshToken, user) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('refresh_token', refreshToken)
    set({ user, token, refreshToken, isAuthenticated: true })
  },
  setTokens: (token, refreshToken) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('refresh_token', refreshToken)
    set({ token, refreshToken })
  },
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, token: null, refreshToken: null, isAuthenticated: false })
    window.location.href = '/login'
  },
}))
