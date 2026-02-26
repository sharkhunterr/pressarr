import { apiFetch } from './client'

export interface NotificationChannel {
  id: number
  name: string
  type: string
  enabled: boolean
  onGrab: boolean
  onDownload: boolean
  onImport: boolean
  onUpgrade: boolean
  onError: boolean
  settings: Record<string, string>
}

export const getNotifications = () =>
  apiFetch<NotificationChannel[]>('/notification')

export const createNotification = (data: Partial<NotificationChannel>) =>
  apiFetch<NotificationChannel>('/notification', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateNotification = (id: number, data: Partial<NotificationChannel>) =>
  apiFetch<NotificationChannel>(`/notification/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteNotification = (id: number) =>
  apiFetch<void>(`/notification/${id}`, { method: 'DELETE' })

export const testNotification = (data: Partial<NotificationChannel>) =>
  apiFetch<{ isValid: boolean; message: string }>('/notification/test', {
    method: 'POST',
    body: JSON.stringify(data),
  })
