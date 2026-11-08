import api from '@/lib/axios'

export const registrarApi = {
  /**
   * Get paginated requests queue filtered by tab or status
   * @param {Object} params
   * @param {string} [params.tab] - TO_VERIFY, TO_PAY, PAID, FAILED, ALL
   * @param {string} [params.status] - Legacy status: CLEARED or REFUND_VERIFIED
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getQueue({ tab, status, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (tab) {
      params.tab = tab
    } else if (status) {
      params.status = status
    }
    const response = await api.get('/registrar/queue', { params })
    return response.data
  },

  /**
   * Get full registrar request detail including student info, masked bank, approvals, roster provenance, and timeline
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
   * Reopen verified refund back to PENDING_VERIFICATION
   * @param {number} requestId
   * @param {Object} data
   * @param {string} data.reason
   */
  async reopenVerification(requestId, { reason }) {
    const response = await api.post(`/registrar/requests/${requestId}/reopen-verification`, {
      reason: reason?.trim(),
    })
    return response.data
  },

  /**
   * Mark refund processed / disbursed with bank transaction reference
   * Requires refund to already be in VERIFIED status
   * @param {number} requestId
   * @param {Object} data
   * @param {string} data.payment_reference
   * @param {string} [data.paid_on]
   * @param {string} [data.payment_mode]
   */
  async markProcessed(requestId, { payment_reference, paid_on, payment_mode }) {
    const payload = {
      payment_reference: payment_reference?.trim(),
    }
    if (paid_on) {
      payload.paid_on = paid_on
    }
    if (payment_mode) {
      payload.payment_mode = payment_mode
    }
    const response = await api.post(`/registrar/requests/${requestId}/mark-processed`, payload)
    return response.data
  },

  /**
   * Mark disbursement as failed
   * @param {number} requestId
   * @param {Object} data
   * @param {string} data.reason
   */
  async markFailed(requestId, { reason }) {
    const response = await api.post(`/registrar/requests/${requestId}/mark-failed`, {
      reason: reason?.trim(),
    })
    return response.data
  },

  /**
   * Retry failed refund payment (transitions PAYMENT_FAILED -> VERIFIED)
   * @param {number} requestId
   */
  async retryPayment(requestId) {
    const response = await api.post(`/registrar/requests/${requestId}/retry-payment`)
    return response.data
  },

  /**
   * Resolve student-reported refund issue
   * @param {number} requestId
   * @param {Object} [data]
   * @param {string} [data.note]
   */
  async resolveIssue(requestId, { note } = {}) {
    const payload = {}
    if (note) {
      payload.note = note.trim()
    }
    const response = await api.post(`/registrar/requests/${requestId}/resolve-issue`, payload)
    return response.data
  },

  /**
   * Export refunds list as CSV blob
   * @param {string} [tab='ALL']
   */
  async exportCsv(tab = 'ALL') {
    const response = await api.get('/registrar/refunds/export.csv', {
      params: { tab },
      responseType: 'blob',
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

  /**
   * Download deposit ledger CSV template
   */
  async getDepositLedgerTemplate() {
    const response = await api.get('/registrar/deposit-ledger/template.csv', {
      responseType: 'blob',
    })
    return response.data
  },

  /**
   * Bulk upload security deposit ledger CSV
   * @param {File} file
   * @param {Object} [options]
   * @param {boolean} [options.dry_run=false]
   */
  async uploadDepositLedger(file, { dry_run = false } = {}) {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/registrar/deposit-ledger/upload', formData, {
      params: { dry_run },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  /**
   * Update single student security deposit ledger amount
   * @param {number} rosterId
   * @param {Object} data
   * @param {number|string} data.deposit_amount
   */
  async updateRosterDeposit(rosterId, { deposit_amount }) {
    const response = await api.patch(`/registrar/roster/${rosterId}/deposit`, {
      deposit_amount: Number(deposit_amount),
    })
    return response.data
  },
}
