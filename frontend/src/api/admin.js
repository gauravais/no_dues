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
  async updateRosterEntry(id, data) {
    const response = await api.patch(`/admin/roster/${id}`, data)
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
   * Provision new staff user (dept_officer, hod, registrar_accounts)
   * @param {Object} data
   * @param {string} data.email
   * @param {string} data.full_name
   * @param {'dept_officer' | 'hod' | 'registrar_accounts'} data.role
   * @param {number} [data.department_id]
   */
  async createStaffUser(data) {
    const response = await api.post('/admin/users', data)
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
}
