import api from '@/lib/axios'

export const registrarApi = {
  /**
   * Get paginated requests in CLEARED status awaiting refund verification
   * @param {Object} params
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getQueue({ limit = 50, offset = 0 } = {}) {
    const response = await api.get('/registrar/queue', {
      params: { limit, offset },
    })
    return response.data
  },

  /**
   * Verify refund: enter deductions (0 <= deductions <= deposit_amount)
   * Transitions request status to REFUND_VERIFIED and refund status to VERIFIED
   * @param {number} requestId
   * @param {Object} data
   * @param {number} data.deductions
   * @param {string} [data.remarks]
   */
  async verifyRefund(requestId, { deductions, remarks }) {
    const response = await api.post(`/registrar/requests/${requestId}/verify-refund`, {
      deductions: Number(deductions),
      remarks: remarks?.trim() || null,
    })
    return response.data
  },

  /**
   * Mark refund processed / disbursed with bank transaction UTR/NEFT reference
   * Requires refund to already be in VERIFIED status
   * Transitions refund status to PROCESSED
   * @param {number} requestId
   * @param {Object} data
   * @param {string} data.payment_reference
   */
  async markProcessed(requestId, { payment_reference }) {
    const response = await api.post(`/registrar/requests/${requestId}/mark-processed`, {
      payment_reference: payment_reference?.trim(),
    })
    return response.data
  },
}
