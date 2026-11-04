/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi } from '@/api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    return localStorage.getItem('nodues_token') || null
  })
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('nodues_user')
      if (saved) return JSON.parse(saved)
    } catch {
      // ignore JSON errors
    }
    return null
  })
  const [isLoading, setIsLoading] = useState(false)

  const fetchProfile = useCallback(async () => {
    if (!token) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      const profile = await authApi.me()
      setUser(profile)
      localStorage.setItem('nodues_user', JSON.stringify(profile))
    } catch {
      localStorage.removeItem('nodues_token')
      localStorage.removeItem('nodues_user')
      setToken(null)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [token])

  useEffect(() => {
    let isMounted = true
    if (token) {
      authApi.me().then((profile) => {
        if (isMounted) {
          setUser(profile)
          localStorage.setItem('nodues_user', JSON.stringify(profile))
          setIsLoading(false)
        }
      }).catch(() => {
        if (isMounted) {
          localStorage.removeItem('nodues_token')
          localStorage.removeItem('nodues_user')
          setToken(null)
          setUser(null)
          setIsLoading(false)
        }
      })
    } else {
      setIsLoading(false)
    }
    return () => {
      isMounted = false
    }
  }, [token])

  const login = (accessToken, userData = null) => {
    localStorage.setItem('nodues_token', accessToken)
    setToken(accessToken)
    if (userData) {
      localStorage.setItem('nodues_user', JSON.stringify(userData))
      setUser(userData)
    }
    authApi.me().then((fresh) => {
      setUser(fresh)
      localStorage.setItem('nodues_user', JSON.stringify(fresh))
    }).catch(() => {})
  }

  const logout = () => {
    localStorage.removeItem('nodues_token')
    localStorage.removeItem('nodues_user')
    setToken(null)
    setUser(null)
    window.location.href = '/login'
  }

  const value = {
    token,
    user,
    isLoading,
    isAuthenticated: Boolean(token && user),
    login,
    logout,
    refreshProfile: fetchProfile,
    role: user?.role,
    mustChangePassword: Boolean(user?.must_change_password),
    isStudent: user?.role === 'student',
    isOfficer: user?.role === 'dept_officer',
    isHod: user?.role === 'hod',
    isRegistrar: user?.role === 'registrar_accounts',
    isAdmin: user?.role === 'admin',
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
