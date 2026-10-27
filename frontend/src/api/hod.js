import api from '@/lib/axios'

export const hodApi = {
  /**
   * Get all clearance requests waiting in HOD_REVIEW for HoD's academic department
   */
  async getQueue() {
    const response = await api.get('/hod/queue')
    return response.data
  },

  /**
   * Get full student clearance dossier and all department sign-offs
   * @param {number} requestId
   */
  async getRequestDetail(requestId) {
    const response = await api.get(`/hod/requests/${requestId}`)
    return response.data
  },

  /**
   * Submit final HoD decision (APPROVED: CLEARED + Cert; REJECTED: ACTION_NEEDED)
   * @param {number} requestId
   * @param {Object} data
   * @param {'APPROVED' | 'REJECTED'} data.decision
   * @param {string} [data.remarks] - mandatory on rejection
   */
  async submitDecision(requestId, { decision, remarks }) {
    const response = await api.post(`/hod/requests/${requestId}/decision`, {
      decision,
      remarks: remarks?.trim() || null,
    })
    return response.data
  },
}
