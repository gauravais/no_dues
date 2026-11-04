import axios from 'axios'
import { toast } from 'sonner'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL,
  timeout: 90000, // 90 seconds timeout for free-tier hosting cold starts
  headers: {
    'Content-Type': 'application/json',
  },
})

// Cold-start wakeup banner management
let activeSlowRequests = 0

function showWakeupBanner() {
  if (typeof document === 'undefined') return
  let el = document.getElementById('server-wakeup-banner')
  if (!el) {
    el = document.createElement('div')
    el.id = 'server-wakeup-banner'
    el.setAttribute('role', 'status')
    el.setAttribute('aria-live', 'polite')
    el.className =
      'fixed top-0 left-0 right-0 z-[9999] bg-amber-500 text-white text-xs sm:text-sm font-medium py-2 px-4 text-center shadow-md transition-opacity duration-300 pointer-events-none'
    el.textContent = 'The server is waking up. This can take up to a minute the first time.'
    document.body.appendChild(el)
  }
  el.style.display = 'block'
}

function hideWakeupBanner() {
  if (typeof document === 'undefined') return
  const el = document.getElementById('server-wakeup-banner')
  if (el) {
    el.style.display = 'none'
  }
}

function clearRequestTimer(config) {
  if (config?._wakeupTimer) {
    clearTimeout(config._wakeupTimer)
    config._wakeupTimer = null
  }
  if (config?._didShowWakeup) {
    config._didShowWakeup = false
    activeSlowRequests = Math.max(0, activeSlowRequests - 1)
    if (activeSlowRequests === 0) {
      hideWakeupBanner()
    }
  }
}

// Request interceptor: inject token & schedule 4-second cold start banner
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('nodues_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    config._didShowWakeup = false
    config._wakeupTimer = setTimeout(() => {
      config._didShowWakeup = true
      activeSlowRequests++
      showWakeupBanner()
    }, 4000)

    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: retry GET once on network error/502/503/504; handle global errors
api.interceptors.response.use(
  (response) => {
    clearRequestTimer(response.config)
    return response
  },
  async (error) => {
    const config = error.config

    // Only retry GET requests on network errors or 502/503/504; never retry POST or other methods
    const method = (config?.method || 'get').toLowerCase()
    const status = error.response?.status
    const isNetworkOrGatewayError = !status || [502, 503, 504].includes(status)

    if (config && method === 'get' && isNetworkOrGatewayError && !config._isRetry) {
      config._isRetry = true
      return api(config)
    }

    clearRequestTimer(config)

    if (status === 401) {
      const isAuthRoute =
        window.location.pathname.startsWith('/login') ||
        window.location.pathname.startsWith('/signup')
      if (!isAuthRoute && localStorage.getItem('nodues_token')) {
        localStorage.removeItem('nodues_token')
        localStorage.removeItem('nodues_user')
        toast.error('Session expired. Please sign in again.')
        window.location.href = '/login'
      }
    } else if (status === 403) {
      if (error.response?.data?.detail === 'PASSWORD_CHANGE_REQUIRED') {
        if (window.location.pathname !== '/change-password') {
          window.location.href = '/change-password'
        }
        return Promise.reject(error)
      }
      toast.error('Access denied: You do not have permission for this action.')
    }

    return Promise.reject(error)
  }
)

export default api
