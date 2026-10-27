import api from '@/lib/axios'

export const verifyApi = {
  /**
   * Public check of certificate validity
   */
  async checkCertificate(certificateCode) {
    const response = await api.get(`/verify/${certificateCode}`)
    return response.data
  },
}
