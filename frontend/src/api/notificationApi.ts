import apiClient from './client'
import type { ApiResponse } from '../types'

export interface NotificationItem {
  id: string
  type: string
  title: string
  description: string | null
  related_url: string | null
  is_read: boolean
  priority: string
  created_at: string
}

export interface NotificationsMeta {
  page: number
  page_size: number
  total: number
  unread_count: number
}

export interface NotificationsListResponse {
  items: NotificationItem[]
  meta: NotificationsMeta
}

export const notificationApi = {
  list: (params?: { page?: number; page_size?: number; unread_only?: boolean }) =>
    apiClient.get<ApiResponse<NotificationsListResponse>>('/notifications', { params }),

  unreadCount: () =>
    apiClient.get<ApiResponse<{ unread_count: number }>>('/notifications/unread-count'),

  markAsRead: (id: string) =>
    apiClient.post<ApiResponse<{ id: string; is_read: boolean }>>(`/notifications/${id}/read`),

  markAllAsRead: () =>
    apiClient.post<ApiResponse<{ message: string }>>('/notifications/read-all'),
}
