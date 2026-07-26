import apiClient from './client'
import type { ApiResponse } from '../types'

export interface LoginParams {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  token_type: string
  user: {
    id: string
    username: string
    email?: string
  }
}

export interface RefreshResult {
  access_token: string
  refresh_token: string
  token_type: string
}

export const authApi = {
  login: (params: LoginParams) =>
    apiClient.post<ApiResponse<LoginResult>>('/auth/login', params),

  /** T8 D22: Refresh access token using refresh_token */
  refresh: (refreshToken: string) =>
    apiClient.post<ApiResponse<RefreshResult>>('/auth/refresh', { refresh_token: refreshToken }),

  logout: () =>
    apiClient.post<ApiResponse<null>>('/auth/logout'),

  getProfile: () =>
    apiClient.get<ApiResponse<{ id: string; username: string; email?: string }>>('/auth/me'),
}
