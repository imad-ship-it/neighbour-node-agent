import axios from 'axios'
import { getAccessToken } from './tokenStore'

const client = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
})

// DRF authenticates before it checks permissions, so a stale token sent to an
// AllowAny endpoint still 401s. Keep the header off the endpoints that mint it.
const PUBLIC_PATHS = ['/auth/register/', '/auth/login/']

client.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token && !PUBLIC_PATHS.includes(config.url)) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Pull the first human-readable message out of a DRF error response.
export function apiError(error, fallback) {
  const data = error?.response?.data
  if (!data) return error?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const first = Object.entries(data)[0]
  if (!first) return fallback
  const [field, value] = first
  const message = Array.isArray(value) ? value[0] : value
  return field === 'detail' ? message : `${field}: ${message}`
}

export default client
