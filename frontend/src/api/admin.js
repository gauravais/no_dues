import api from '@/lib/axios'

export const adminApi = {
  /**
   * List student roster with pagination and search
   * @param {Object} params
   * @param {string} [params.search] - Search by reg no, name, or email
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getRoster({ search, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (search?.trim()) {
      params.search = search.trim()
    }
    const response = await api.get('/admin/roster', { params })
    return response.data
  },

  /**
   * Upload student roster CSV file
   * @param {File} file
   */
  async uploadRosterCsv(file) {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/admin/roster/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  /**
   * Update student roster profile (hosteller, deposit, address, mobile)
   * @param {number} id - Roster ID
   * @param {Object} data
   */
  async updateRosterEntry(id, { address, mobile, is_hosteller, security_deposit_amount } = {}) {
    const payload = {}
    if (address !== undefined) payload.address = address
    if (mobile !== undefined) payload.mobile = mobile
    if (is_hosteller !== undefined) payload.is_hosteller = is_hosteller
    if (security_deposit_amount !== undefined) payload.security_deposit_amount = security_deposit_amount

    const response = await api.patch(`/admin/roster/${id}`, payload)
    return response.data
  },

  /**
   * Replace assigned laboratory and workshop departments for a student
   * @param {number} id - Roster ID
   * @param {number[]} departmentIds
   */
  async updateAssignedDepartments(id, departmentIds) {
    const response = await api.put(`/admin/roster/${id}/assigned-departments`, {
      department_ids: departmentIds,
    })
    return response.data
  },

  /**
   * Fetch active university departments directory
   */
  async getDepartments() {
    const response = await api.get('/departments')
    return response.data
  },

  /**
   * Fetch university offices and staffing status
   */
  async getOffices() {
    const response = await api.get('/admin/offices')
    return response.data
  },

  /**
   * Fetch university user directory with role, department, active status and search filters
   * @param {Object} params
   * @param {string} [params.search]
   * @param {string} [params.role]
   * @param {number} [params.department_id]
   * @param {boolean} [params.is_active]
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getUsers({ search, role, department_id, is_active, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (search?.trim()) {
      params.search = search.trim()
    }
    if (role && role !== 'ALL') {
      params.role = role
    }
    if (department_id !== undefined && department_id !== null && department_id !== '' && department_id !== 'ALL') {
      params.department_id = Number(department_id)
    }
    if (is_active !== undefined && is_active !== null && is_active !== '' && is_active !== 'ALL') {
      params.is_active = is_active === 'true' || is_active === true
    }
    const response = await api.get('/admin/users', { params })
    return response.data
  },

  /**
   * Provision new staff user (dept_officer, hod, registrar_accounts)
   * @param {Object} data
   * @param {string} data.email
   * @param {string} data.full_name
   * @param {'dept_officer' | 'hod' | 'registrar_accounts'} data.role
   * @param {number} [data.department_id]
   * @param {boolean} [data.google_only]
   */
  async createStaffUser({ email, full_name, role, department_id, google_only } = {}) {
    const payload = {
      email,
      full_name,
      role,
    }
    if (department_id) {
      payload.department_id = Number(department_id)
    }
    if (google_only !== undefined) {
      payload.google_only = Boolean(google_only)
    }
    const response = await api.post('/admin/users', payload)
    return response.data
  },

  /**
   * Bulk provision staff accounts from CSV file
   * @param {File} file
   * @param {Object} [options]
   * @param {boolean} [options.google_only]
   */
  async bulkUploadUsers(file, { google_only } = {}) {
    const formData = new FormData()
    formData.append('file', file)
    const config = {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
    if (google_only !== undefined) {
      config.params = { google_only: Boolean(google_only) }
    }
    const response = await api.post('/admin/users/bulk-upload', formData, config)
    return response.data
  },

  /**
   * Reset user password (generates one-time random password)
   * @param {number} userId
   */
  async resetPassword(userId) {
    const response = await api.post(`/admin/users/${userId}/reset-password`)
    return response.data
  },

  /**
   * Toggle user active/inactive status
   * @param {number} userId
   * @param {boolean} isActive
   */
  async setUserActive(userId, isActive) {
    const response = await api.patch(`/admin/users/${userId}/active`, {
      is_active: isActive,
    })
    return response.data
  },

  /**
   * List global lab courses with department and active filters
   * @param {Object} params
   * @param {number} [params.academic_department_id]
   * @param {boolean} [params.is_active]
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getLabCourses({ academic_department_id, is_active, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (academic_department_id !== undefined && academic_department_id !== null && academic_department_id !== '' && academic_department_id !== 'ALL') {
      params.academic_department_id = Number(academic_department_id)
    }
    if (is_active !== undefined && is_active !== null && is_active !== '' && is_active !== 'ALL') {
      params.is_active = is_active === 'true' || is_active === true
    }
    const response = await api.get('/admin/lab-courses', { params })
    return response.data
  },

  /**
   * Create lab course mapped to an academic department and an ASSIGNED_ONLY service lab
   * @param {Object} data
   */
  async createLabCourse({ code, name, lab_department_id, academic_department_id, specialization } = {}) {
    const payload = {
      code,
      name,
      lab_department_id: Number(lab_department_id),
    }
    if (academic_department_id) {
      payload.academic_department_id = Number(academic_department_id)
    }
    if (specialization) {
      payload.specialization = specialization
    }
    const response = await api.post('/admin/lab-courses', payload)
    return response.data
  },

  /**
   * Update lab course metadata
   * @param {number} id
   * @param {Object} data
   */
  async patchLabCourse(id, { name, specialization, is_active } = {}) {
    const payload = {}
    if (name !== undefined) payload.name = name
    if (specialization !== undefined) payload.specialization = specialization
    if (is_active !== undefined) payload.is_active = is_active
    const response = await api.patch(`/admin/lab-courses/${id}`, payload)
    return response.data
  },

  /**
   * Download admin lab courses CSV template
   */
  async downloadLabCoursesTemplate() {
    const response = await api.get('/admin/lab-courses/template.csv', {
      responseType: 'blob',
    })
    return response.data
  },

  /**
   * Admin cancel active clearance request by ID
   * @param {number} requestId
   * @param {string} reason - strictly mandatory (1-1000 characters)
   */
  async cancelRequest(requestId, reason) {
    const response = await api.post(`/admin/requests/${requestId}/cancel`, {
      reason: reason.trim(),
    })
    return response.data
  },
}
