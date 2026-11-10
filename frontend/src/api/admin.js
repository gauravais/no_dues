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
   * Update student roster profile (address, mobile)
   * @param {number} id - Roster ID
   * @param {Object} data
   */
  async updateRosterEntry(id, { address, mobile } = {}) {
    const payload = {}
    if (address !== undefined) payload.address = address
    if (mobile !== undefined) payload.mobile = mobile

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
   * @param {number[]} [data.department_ids]
   * @param {boolean} [data.google_only]
   */
  async createStaffUser({ email, full_name, role, department_id, department_ids, google_only } = {}) {
    const payload = {
      email,
      full_name,
      role,
    }
    if (department_ids && department_ids.length > 0) {
      payload.department_ids = department_ids.map(Number)
    } else if (department_id) {
      payload.department_id = Number(department_id)
    }
    if (google_only !== undefined) {
      payload.google_only = Boolean(google_only)
    }
    const response = await api.post('/admin/users', payload)
    return response.data
  },

  /**
   * Get user detail including full departments membership list
   * @param {number} id
   */
  async getUser(id) {
    const response = await api.get(`/admin/users/${id}`)
    return response.data
  },

  /**
   * Add department membership to user
   * @param {number} userId
   * @param {number} departmentId
   */
  async addUserDepartment(userId, departmentId) {
    const response = await api.post(`/admin/users/${userId}/departments`, {
      department_id: Number(departmentId),
    })
    return response.data
  },

  /**
   * Remove department membership from user
   * @param {number} userId
   * @param {number} departmentId
   */
  async removeUserDepartment(userId, departmentId) {
    const response = await api.delete(`/admin/users/${userId}/departments/${departmentId}`)
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
  async patchLabCourse(id, { code, name, lab_department_id, specialization, is_active } = {}) {
    const payload = {}
    if (code !== undefined) payload.code = code.trim().toUpperCase()
    if (name !== undefined) payload.name = name.trim()
    if (lab_department_id !== undefined) payload.lab_department_id = Number(lab_department_id)
    if (specialization !== undefined) payload.specialization = specialization?.trim() || null
    if (is_active !== undefined) payload.is_active = Boolean(is_active)
    const response = await api.patch(`/admin/lab-courses/${id}`, payload)
    return response.data
  },

  /**
   * Upload CSV file to batch ingest lab courses across university
   * @param {File} file
   * @param {Object} [options]
   * @param {boolean} [options.dry_run=false]
   * @param {boolean} [options.create_missing_offices=false]
   */
  async uploadLabCoursesCsv(file, { dry_run = false, create_missing_offices = false } = {}) {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/admin/lab-courses/upload', formData, {
      params: {
        dry_run: Boolean(dry_run),
        create_missing_offices: Boolean(create_missing_offices),
      },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  /**
   * List university departments with category metrics and active status
   * @param {Object} [params]
   * @param {string} [params.category]
   * @param {boolean} [params.is_active]
   * @param {string} [params.search]
   */
  async getAdminDepartments({ category, is_active, search } = {}) {
    const params = {}
    if (category && category !== 'ALL') params.category = category
    if (is_active !== undefined && is_active !== null && is_active !== '' && is_active !== 'ALL') {
      params.is_active = is_active === 'true' || is_active === true
    }
    if (search?.trim()) params.search = search.trim()
    const response = await api.get('/admin/departments', { params })
    return response.data
  },

  /**
   * Create university service department
   * @param {Object} data
   * @param {string} data.name
   * @param {string} [data.description]
   * @param {string} data.category
   */
  async createDepartment({ name, description, category } = {}) {
    const payload = {
      name: name.trim(),
      category,
    }
    if (description !== undefined && description !== null) {
      payload.description = description.trim() || null
    }
    const response = await api.post('/admin/departments', payload)
    return response.data
  },

  /**
   * Update department name, description, category, or active status
   * @param {number} id
   * @param {Object} data
   */
  async patchDepartment(id, { name, description, category, is_active, confirm = false } = {}) {
    const payload = {}
    if (name !== undefined) payload.name = name.trim()
    if (description !== undefined) payload.description = description?.trim() || null
    if (category !== undefined) payload.category = category
    if (is_active !== undefined) payload.is_active = Boolean(is_active)
    if (confirm !== undefined) payload.confirm = Boolean(confirm)
    const response = await api.patch(`/admin/departments/${id}`, payload, {
      params: { confirm: Boolean(confirm) },
    })
    return response.data
  },

  /**
   * Delete department when no records refer to it
   * @param {number} id
   */
  async deleteDepartment(id) {
    const response = await api.delete(`/admin/departments/${id}`)
    return response.data
  },

  /**
   * Bulk update department categories
   * @param {Object} data
   * @param {number[]} data.department_ids
   * @param {string} data.category
   */
  async bulkCategory({ department_ids, category } = {}) {
    const payload = {
      department_ids: department_ids.map(Number),
      category,
    }
    const response = await api.post('/admin/departments/bulk-category', payload)
    return response.data
  },

  /**
   * Update staff user details (name, email, and unlink_google)
   * @param {number} id
   * @param {Object} data
   */
  async patchUser(id, { full_name, email, unlink_google = false } = {}) {
    const payload = {}
    if (full_name !== undefined) payload.full_name = full_name.trim()
    if (email !== undefined) payload.email = email.trim().toLowerCase()
    if (unlink_google !== undefined) payload.unlink_google = Boolean(unlink_google)
    const response = await api.patch(`/admin/users/${id}`, payload)
    return response.data
  },

  /**
   * List university faculties
   */
  async getFaculties() {
    const response = await api.get('/admin/faculties')
    return response.data
  },

  /**
   * Create new faculty
   * @param {Object} data
   */
  async createFaculty({ name, short_code } = {}) {
    const payload = {
      name: name.trim(),
      short_code: short_code.trim().toUpperCase(),
    }
    const response = await api.post('/admin/faculties', payload)
    return response.data
  },

  /**
   * Update faculty name or short code
   * @param {number} id
   * @param {Object} data
   */
  async patchFaculty(id, { name, short_code } = {}) {
    const payload = {}
    if (name !== undefined) payload.name = name.trim()
    if (short_code !== undefined) payload.short_code = short_code.trim().toUpperCase()
    const response = await api.patch(`/admin/faculties/${id}`, payload)
    return response.data
  },

  /**
   * List academic departments
   * @param {Object} [params]
   */
  async getAcademicDepartments({ faculty_id, is_active } = {}) {
    const params = {}
    if (faculty_id !== undefined && faculty_id !== null && faculty_id !== '' && faculty_id !== 'ALL') {
      params.faculty_id = Number(faculty_id)
    }
    if (is_active !== undefined && is_active !== null && is_active !== '' && is_active !== 'ALL') {
      params.is_active = is_active === 'true' || is_active === true
    }
    const response = await api.get('/admin/academic-departments', { params })
    return response.data
  },

  /**
   * Create academic department
   * @param {Object} data
   */
  async createAcademicDepartment({ name, faculty_id, is_active = true } = {}) {
    const payload = {
      name: name.trim(),
      faculty_id: Number(faculty_id),
      is_active: Boolean(is_active),
    }
    const response = await api.post('/admin/academic-departments', payload)
    return response.data
  },

  /**
   * Update academic department
   * @param {number} id
   * @param {Object} data
   */
  async patchAcademicDepartment(id, { name, faculty_id, is_active } = {}) {
    const payload = {}
    if (name !== undefined) payload.name = name.trim()
    if (faculty_id !== undefined && faculty_id !== null) payload.faculty_id = Number(faculty_id)
    if (is_active !== undefined) payload.is_active = Boolean(is_active)
    const response = await api.patch(`/admin/academic-departments/${id}`, payload)
    return response.data
  },

  /**
   * List academic programmes
   * @param {Object} [params]
   */
  async getProgrammes({ academic_department_id, is_active } = {}) {
    const params = {}
    if (academic_department_id !== undefined && academic_department_id !== null && academic_department_id !== '' && academic_department_id !== 'ALL') {
      params.academic_department_id = Number(academic_department_id)
    }
    if (is_active !== undefined && is_active !== null && is_active !== '' && is_active !== 'ALL') {
      params.is_active = is_active === 'true' || is_active === true
    }
    const response = await api.get('/admin/programmes', { params })
    return response.data
  },

  /**
   * Create academic programme
   * @param {Object} data
   */
  async createProgramme({ name, academic_department_id, is_active = true } = {}) {
    const payload = {
      name: name.trim(),
      academic_department_id: Number(academic_department_id),
      is_active: Boolean(is_active),
    }
    const response = await api.post('/admin/programmes', payload)
    return response.data
  },

  /**
   * Update academic programme
   * @param {number} id
   * @param {Object} data
   */
  async patchProgramme(id, { name, academic_department_id, is_active } = {}) {
    const payload = {}
    if (name !== undefined) payload.name = name.trim()
    if (academic_department_id !== undefined && academic_department_id !== null) {
      payload.academic_department_id = Number(academic_department_id)
    }
    if (is_active !== undefined) payload.is_active = Boolean(is_active)
    const response = await api.patch(`/admin/programmes/${id}`, payload)
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
