import api from '@/lib/axios'

export const studentApi = {
  /**
   * Get student's registered bank details (masked account number)
   */
  async getBankDetails() {
    const response = await api.get('/student/bank-details')
    return response.data
  },

  /**
   * Create or update student's bank details
   */
  async updateBankDetails({ accountNumber, ifscCode, accountHolderName, bankAddress }) {
    const response = await api.put('/student/bank-details', {
      account_number: accountNumber,
      ifsc_code: ifscCode,
      account_holder_name: accountHolderName,
      bank_address: bankAddress,
    })
    return response.data
  },

  /**
   * Apply for No-Dues clearance
   */
  async createRequest() {
    const response = await api.post('/student/requests')
    return response.data
  },

  /**
   * Fetch current active clearance request with department approvals
   */
  async getCurrentRequest() {
    const response = await api.get('/student/requests/current')
    return response.data
  },

  /**
   * Resubmit rejected department approval
   */
  async resubmitDepartment(requestId, departmentId) {
    const response = await api.post(
      `/student/requests/${requestId}/departments/${departmentId}/resubmit`
    )
    return response.data
  },

  /**
   * Resubmit to HoD after HoD rejection
   */
  async resubmitToHod(requestId) {
    const response = await api.post(`/student/requests/${requestId}/resubmit-to-hod`)
    return response.data
  },

  /**
   * Download official clearance certificate as binary PDF blob
   */
  async downloadCertificatePdf(requestId) {
    const response = await api.get(`/student/requests/${requestId}/certificate.pdf`, {
      responseType: 'blob',
    })
    return response.data
  },
}
