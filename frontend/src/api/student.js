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
   * Apply for No-Dues clearance with optional student declarations
   * @param {Object} [declarations]
   * @param {boolean} [declarations.isHosteller]
   * @param {number[]} [declarations.labCourseIds]
   * @param {string} [declarations.othersNote]
   * @param {Object} [declarations.bank]
   */
  async createRequest(declarations = {}) {
    const payload = {}
    if (typeof declarations.isHosteller === 'boolean') {
      payload.is_hosteller = declarations.isHosteller
    }
    if (Array.isArray(declarations.labCourseIds)) {
      payload.lab_course_ids = declarations.labCourseIds
    }
    if (Array.isArray(declarations.labWorkshopDepartmentIds)) {
      payload.lab_workshop_department_ids = declarations.labWorkshopDepartmentIds
    }
    if (declarations.othersNote !== undefined && declarations.othersNote !== null) {
      payload.others_note = declarations.othersNote.trim() || null
    }
    if (Array.isArray(declarations.otherOfficeIds || declarations.otherDepartmentIds)) {
      payload.other_office_ids = declarations.otherOfficeIds || declarations.otherDepartmentIds
    }
    if (declarations.bank) {
      payload.bank = {
        account_number: declarations.bank.accountNumber?.trim(),
        ifsc_code: declarations.bank.ifscCode?.trim().toUpperCase(),
        account_holder_name: declarations.bank.accountHolderName?.trim(),
        bank_address: declarations.bank.bankAddress?.trim(),
      }
    }

    const response = await api.post(
      '/student/requests',
      Object.keys(payload).length > 0 ? payload : undefined
    )
    return response.data
  },

  /**
   * Get lab courses catalog and fallback offices for student's programme
   */
  async getLabCatalog() {
    const response = await api.get('/student/lab-catalog')
    return response.data
  },

  /**
   * Get additional facilities list (optional ASSIGNED_ONLY offices)
   */
  async getAdditionalFacilities() {
    const response = await api.get('/departments/additional-facilities')
    return response.data
  },

  /**
   * Add an ASSIGNED_ONLY or applicable department to an active clearance request
   * @param {number} requestId
   * @param {number} departmentId
   */
  async addDepartment(requestId, departmentId) {
    const response = await api.post(`/student/requests/${requestId}/departments`, {
      department_id: departmentId,
    })
    return response.data
  },

  /**
   * Declare additional lab subjects mid-clearance
   * @param {number} requestId
   * @param {number[]} labCourseIds
   */
  async declareLabCourses(requestId, labCourseIds) {
    const response = await api.post(`/student/requests/${requestId}/lab-courses`, {
      lab_course_ids: labCourseIds,
    })
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

  /**
   * Cancel active clearance request before any office has decided
   * @param {number} requestId
   * @param {string} [reason]
   */
  async cancelRequest(requestId, reason) {
    const response = await api.post(`/student/requests/${requestId}/cancel`, {
      reason: reason?.trim() || null,
    })
    return response.data
  },

  /**
   * Confirm refund receipt or report an issue
   * @param {number} requestId
   * @param {Object} data
   * @param {boolean} data.received
   * @param {string} [data.note]
   */
  async confirmRefund(requestId, { received, note }) {
    const payload = { received }
    if (note !== undefined && note !== null) {
      payload.note = note.trim()
    }
    const response = await api.post(`/student/requests/${requestId}/refund/confirm`, payload)
    return response.data
  },
}
