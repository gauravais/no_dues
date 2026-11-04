import api from '@/lib/axios'

export const registrarApi = {
  /**
   * Get paginated requests queue
   * @param {Object} params
   * @param {string} [params.status='CLEARED'] - CLEARED or REFUND_VERIFIED
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getQueue({ status = 'CLEARED', limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (status) {
      params.status = status
    }
    const response = await api.get('/registrar/queue', { params })
    return response.data
  },

  /**
   * Get full registrar request detail including student info, masked bank, approvals, and roster provenance
   * @param {number} requestId
   */
  async getRequestDetail(requestId) {
    const response = await api.get(`/registrar/requests/${requestId}`)
    return response.data
  },

  /**
   * Verify refund: enter deductions (0 <= deductions <= deposit_amount)
   * Transitions request status to REFUND_VERIFIED and refund status to VERIFIED
   * @param {number} requestId
   * @param {Object} data
   * @param {number|string} [data.deposit_amount]
   * @param {number|string} data.deductions
   * @param {string} data.remarks
   */
  async verifyRefund(requestId, { deposit_amount, deductions, remarks }) {
    const payload = {
      deductions: Number(deductions),
      remarks: remarks?.trim(),
    }
    if (deposit_amount != null) {
      payload.deposit_amount = String(deposit_amount)
    }
    const response = await api.post(`/registrar/requests/${requestId}/verify-refund`, payload)
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

  /**
   * Audited reveal of full plain bank details (rate limited to 10 requests/min)
   * @param {number} requestId
   */
  async revealBankDetails(requestId) {
    const response = await api.post(`/registrar/requests/${requestId}/reveal-bank-details`)
    return response.data
  },
}
