import api from '@/lib/axios'

export const departmentApi = {
  /**
   * Get paginated clearance approvals for officer's assigned department
   * @param {Object} params
   * @param {string} [params.status] - PENDING | APPROVED | REJECTED
   * @param {string} [params.search] - Student name or registration number
   * @param {number} [params.departmentId] - Optional department ID filter
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getQueue({ status, search, departmentId, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (status) {
      params.status = status
    }
    if (search?.trim()) {
      params.search = search.trim()
    }
    if (departmentId !== undefined && departmentId !== null && departmentId !== 'ALL') {
      params.department_id = Number(departmentId)
    }
    const response = await api.get('/department/queue', { params })
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
   * Fetch ASSIGNED_ONLY service departments directory (labs, workshops, specialized centers)
   */
  async getAssignedOnlyDepartments() {
    const response = await api.get('/departments/assigned-only')
    return response.data
  },

  /**
   * Fetch active additional facilities directory
   */
  async getAdditionalFacilities() {
    const response = await api.get('/departments/additional-facilities')
    return response.data
  },

  /**
   * Fetch university academic programmes
   */
  async getProgrammes() {
    const response = await api.get('/programmes')
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

  /**
   * Get academic officer inspection detail for a clearance request
   * @param {number} requestId
   */
  async getRequestDetail(requestId) {
    const response = await api.get(`/department/requests/${requestId}`)
    return response.data
  },

  /**
   * Academic officer adds an assigned office to student clearance request
   * @param {number} requestId
   * @param {Object} data
   * @param {number} data.departmentId
   * @param {string} data.reason
   */
  async addDepartment(requestId, { departmentId, reason }) {
    const response = await api.post(`/department/requests/${requestId}/add-department`, {
      department_id: Number(departmentId),
      reason: reason.trim(),
    })
    return response.data
  },

  /**
   * List student roster for the officer's academic department
   * @param {Object} params
   * @param {string} [params.search]
   * @param {number} [params.departmentId]
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getRoster({ search, departmentId, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (search?.trim()) {
      params.search = search.trim()
    }
    if (departmentId !== undefined && departmentId !== null && departmentId !== 'ALL') {
      params.department_id = Number(departmentId)
    }
    const response = await api.get('/department/roster', { params })
    return response.data
  },

  /**
   * Add a single student to academic roster
   * @param {Object} data
   */
  async createRosterStudent(data) {
    const response = await api.post('/department/roster', {
      registration_number: data.registration_number.trim().toUpperCase(),
      name: data.name.trim(),
      email: data.email.trim().toLowerCase(),
      mobile: data.mobile.trim(),
      programme_id: Number(data.programme_id),
      address: data.address?.trim() || null,
    })
    return response.data
  },

  /**
   * Patch student roster record (name, email, mobile, address, programme_id)
   * @param {number} id
   * @param {Object} data
   */
  async patchRosterStudent(id, data) {
    const payload = {}
    if (data.name !== undefined) payload.name = data.name.trim()
    if (data.email !== undefined) payload.email = data.email.trim().toLowerCase()
    if (data.mobile !== undefined) payload.mobile = data.mobile.trim()
    if (data.address !== undefined) payload.address = data.address.trim()
    if (data.programme_id !== undefined && data.programme_id !== null) {
      payload.programme_id = Number(data.programme_id)
    }

    const response = await api.patch(`/department/roster/${id}`, payload)
    return response.data
  },

  /**
   * Upload CSV file to batch ingest students into academic roster
   * @param {File} file
   */
  async uploadRosterCsv(file) {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/department/roster/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  /**
   * Download CSV template for academic roster upload
   */
  async downloadRosterTemplate() {
    const response = await api.get('/department/roster/template.csv', {
      responseType: 'blob',
    })
    return response.data
  },

  /**
   * List lab courses managed by the officer's academic department
   * @param {Object} params
   * @param {boolean} [params.is_active]
   * @param {number} [params.departmentId]
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   */
  async getLabCourses({ is_active, departmentId, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset }
    if (is_active !== undefined) {
      params.is_active = is_active
    }
    if (departmentId !== undefined && departmentId !== null && departmentId !== 'ALL') {
      params.department_id = Number(departmentId)
    }
    const response = await api.get('/department/lab-courses', { params })
    return response.data
  },

  /**
   * Create a new lab course mapped to an ASSIGNED_ONLY service department
   * @param {Object} data
   */
  async createLabCourse(data) {
    const payload = {
      code: data.code.trim().toUpperCase(),
      name: data.name.trim(),
      lab_department_id: Number(data.lab_department_id),
      specialization: data.specialization?.trim() || null,
    }
    if (data.academic_department_id) {
      payload.academic_department_id = Number(data.academic_department_id)
    }
    const response = await api.post('/department/lab-courses', payload)
    return response.data
  },

  /**
   * Patch a lab course (code, name, lab_department_id, specialization, is_active)
   * @param {number} id
   * @param {Object} data
   */
  async patchLabCourse(id, data) {
    const payload = {}
    if (data.code !== undefined) payload.code = data.code.trim().toUpperCase()
    if (data.name !== undefined) payload.name = data.name.trim()
    if (data.lab_department_id !== undefined) payload.lab_department_id = Number(data.lab_department_id)
    if (data.specialization !== undefined) payload.specialization = data.specialization?.trim() || null
    if (data.is_active !== undefined) payload.is_active = Boolean(data.is_active)

    const response = await api.patch(`/department/lab-courses/${id}`, payload)
    return response.data
  },

  /**
   * Upload CSV file to batch ingest lab courses
   * @param {File} file
   * @param {Object} [options]
   * @param {boolean} [options.dry_run=false]
   * @param {boolean} [options.create_missing_offices=false]
   */
  async uploadLabCoursesCsv(file, { dry_run = false, create_missing_offices = false } = {}) {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/department/lab-courses/upload', formData, {
      params: {
        dry_run: Boolean(dry_run),
        create_missing_offices: Boolean(create_missing_offices),
      },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  /**
   * Fetch lab and workshop offices manageable by the officer's academic department
   */
  async getLabWorkshops() {
    const response = await api.get('/department/lab-workshops')
    return response.data
  },

  /**
   * Create a new lab or workshop office
   * @param {Object} data
   * @param {string} data.name
   * @param {string} [data.description]
   */
  async createLabWorkshop({ name, description } = {}) {
    const payload = {
      name: name.trim(),
    }
    if (description !== undefined && description !== null) {
      payload.description = description.trim() || null
    }
    const response = await api.post('/department/lab-workshops', payload)
    return response.data
  },

  /**
   * Update lab or workshop office details or active state
   * @param {number} id
   * @param {Object} data
   */
  async patchLabWorkshop(id, { name, description, is_active } = {}) {
    const payload = {}
    if (name !== undefined) payload.name = name.trim()
    if (description !== undefined) payload.description = description?.trim() || null
    if (is_active !== undefined) payload.is_active = Boolean(is_active)
    const response = await api.patch(`/department/lab-workshops/${id}`, payload)
    return response.data
  },

  /**
   * Download CSV template for lab courses upload
   */
  async downloadLabCoursesTemplate() {
    const response = await api.get('/department/lab-courses/template.csv', {
      responseType: 'blob',
    })
    return response.data
  },

  /**
   * Academic officer cancel active clearance request
   * @param {number} requestId
   * @param {string} reason - strictly mandatory (1-1000 characters)
   */
  async cancelRequest(requestId, reason) {
    const response = await api.post(`/department/requests/${requestId}/cancel`, {
      reason: reason.trim(),
    })
    return response.data
  },
}
