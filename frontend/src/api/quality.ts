import { apiFetch } from './client'

export interface QualityProfileItem {
  id?: number
  quality: string
  allowed: boolean
  sortOrder: number
}

export interface QualityProfile {
  id: number
  name: string
  cutoff: string
  isDefault: boolean
  items: QualityProfileItem[]
}

export const getProfiles = () =>
  apiFetch<QualityProfile[]>('/qualityprofile')

export const getProfile = (id: number) =>
  apiFetch<QualityProfile>(`/qualityprofile/${id}`)

export const createProfile = (data: Partial<QualityProfile>) =>
  apiFetch<QualityProfile>('/qualityprofile', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateProfile = (id: number, data: Partial<QualityProfile>) =>
  apiFetch<QualityProfile>(`/qualityprofile/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteProfile = (id: number) =>
  apiFetch<void>(`/qualityprofile/${id}`, { method: 'DELETE' })
