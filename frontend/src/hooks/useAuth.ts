import { useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'
import { authApi } from '../api/authApi'

export function useAuth() {
  const { user, isAuthenticated, login: storeLogin, logout: storeLogout } = useAuthStore()

  const login = useCallback(async (username: string, password: string) => {
    const res: any = await authApi.login({ username, password })
    storeLogin(res.data.access_token, res.data.refresh_token, res.data.user)
    return res
  }, [storeLogin])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      storeLogout()
    }
  }, [storeLogout])

  return { user, isAuthenticated, login, logout }
}
