import axios from 'axios'
import { toast } from 'sonner'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to inject Bearer token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('nodues_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor to handle global errors (401, 403)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status

    if (status === 401) {
      const isAuthRoute = window.location.pathname.startsWith('/login') || window.location.pathname.startsWith('/signup')
      if (!isAuthRoute && localStorage.getItem('nodues_token')) {
        localStorage.removeItem('nodues_token')
        localStorage.removeItem('nodues_user')
        toast.error('Session expired. Please sign in again.')
        window.location.href = '/login'
      }
    } else if (status === 403) {
      toast.error('Access denied: You do not have permission for this action.')
    }

    return Promise.reject(error)
  }
)

export default api
