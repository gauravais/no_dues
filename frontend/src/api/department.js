import api from '@/lib/axios'

export const departmentApi = {
  /**
   * Get paginated clearance approvals for officer's assigned department
   * @param {Object} params
   * @param {string} [params.status] - PENDING | APPROVED | REJECTED
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getQueue({ status, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (status) {
      params.status = status
    }
    const response = await api.get('/department/queue', { params })
    return response.data
  },

  /**
   * Submit decision (APPROVED or REJECTED) on an approval row
   * @param {number} approvalId
   * @param {Object} data
   * @param {'APPROVED' | 'REJECTED'} data.decision
   * @param {string} [data.remarks] - strictly mandatory when decision is REJECTED
   */
  async submitDecision(approvalId, { decision, remarks }) {
    const response = await api.post(`/department/approvals/${approvalId}/decision`, {
      decision,
      remarks: remarks?.trim() || null,
    })
    return response.data
  },
}
