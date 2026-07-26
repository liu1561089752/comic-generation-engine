import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '../stores/authStore'

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 3600000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：添加 JWT Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// T8 D22: Token 刷新队列
// 多个并发请求同时收到 401 时，只发起一次 refresh，其他请求等待同一 Promise
let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise
  }
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    throw new Error('No refresh token')
  }
  refreshPromise = (async () => {
    try {
      const res: any = await axios.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
      })
      const newAccessToken: string = res.data?.data?.access_token
      const newRefreshToken: string = res.data?.data?.refresh_token
      if (!newAccessToken) {
        throw new Error('Invalid refresh response')
      }
      localStorage.setItem('access_token', newAccessToken)
      if (newRefreshToken) {
        localStorage.setItem('refresh_token', newRefreshToken)
      }
      // 同步到 zustand store（不触发 logout）
      useAuthStore.getState().setTokens(newAccessToken, newRefreshToken || refreshToken)
      return newAccessToken
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

interface RetryConfig extends InternalAxiosRequestConfig {
  _retried?: boolean
}

// 响应拦截器：统一错误处理 + 401 自动刷新
apiClient.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryConfig | undefined
    const status = error.response?.status

    // T8 D22: 401 时尝试刷新 token 并重试一次
    if (status === 401 && originalRequest) {
      const url = originalRequest.url || ''
      // 登录接口的 401 表示凭证错误，既不刷新也不能清登录态（logout 会整页跳转冲掉页面的错误提示）
      if (url.includes('/auth/login')) {
        return Promise.reject(error)
      }
      // /auth/refresh 自身失败不重试，避免死循环
      if (!originalRequest._retried && !url.includes('/auth/refresh')) {
        try {
          const newToken = await refreshAccessToken()
          originalRequest._retried = true
          originalRequest.headers!.Authorization = `Bearer ${newToken}`
          return apiClient(originalRequest)
        } catch {
          // 刷新失败：清理登录态，跳转登录页；reject 原始 401 以保留服务端 detail
          useAuthStore.getState().logout()
          return Promise.reject(error)
        }
      }
    }

    // 非 401 或刷新后仍失败：401 清理登录态
    if (status === 401) {
      useAuthStore.getState().logout()
    }

    return Promise.reject(error)
  }
)

export default apiClient
