import api from '@/lib/axios'

export const authApi = {
  /**
   * Fetch public authentication configuration
   */
  async getConfig() {
    const response = await api.get('/auth/config')
    return response.data
  },

  /**
   * Google OAuth2 login
   */
  async googleLogin(credential) {
    const response = await api.post('/auth/google', { credential })
    return response.data
  },

  /**
   * OAuth2 password login (form-urlencoded)
   */
  async login(email, password) {
    const normalizedEmail = (email || '').trim().toLowerCase()
    const formData = new URLSearchParams()
    formData.append('username', normalizedEmail)
    formData.append('password', password)

    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
    return response.data
  },

  /**
   * Fetch current authenticated user profile
   */
  async me() {
    const response = await api.get('/auth/me')
    return response.data
  },

  /**
   * Step 1: Request 6-digit OTP for student signup
   */
  async requestOtp(registrationNumber, email) {
    const response = await api.post('/auth/signup/request-otp', {
      registration_number: registrationNumber,
      email,
    })
    return response.data
  },

  /**
   * Step 2: Verify OTP and create password
   */
  async verifyOtp({ registrationNumber, otp, password }) {
    const response = await api.post('/auth/signup/verify', {
      registration_number: registrationNumber,
      otp,
      password,
    })
    return response.data
  },

  /**
   * Change user password (forced or voluntary)
   */
  async changePassword(currentPassword, newPassword) {
    const response = await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return response.data
  },
}
