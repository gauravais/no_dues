import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { adminApi } from '@/api/admin'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import {
  Building2,
  Users,
  AlertTriangle,
  UserPlus,
  Edit,
  Power,
  Trash2,
  Plus,
  Search,
  Check,
  GraduationCap,
  Briefcase,
  XCircle,
  FlaskConical,
  Home,
  Layers,
} from 'lucide-react'

const OFFICE_TABS = [
  { id: 'UNIVERSITY_OFFICE', label: 'University offices', icon: Building2 },
  { id: 'HOSTEL', label: 'Hostel', icon: Home },
  { id: 'LAB_WORKSHOP', label: 'Labs & Workshops', icon: FlaskConical },
  { id: 'ADDITIONAL_FACILITY', label: 'Additional facilities', icon: Layers },
  { id: 'ACADEMIC', label: 'Academic departments', icon: GraduationCap },
]

export function AdminOfficesPage() {
  useDocumentTitle('University Offices | SVSU No-Dues')
  const queryClient = useQueryClient()

  // Tabs & Filters
  const [activeTab, setActiveTab] = useState('UNIVERSITY_OFFICE')
  const [searchTerm, setSearchTerm] = useState('')
  const [showInactive, setShowInactive] = useState(false)

  // Selection for bulk action
  const [selectedIds, setSelectedIds] = useState([])

  // Bulk category modal
  const [bulkCategoryOpen, setBulkCategoryOpen] = useState(false)
  const [bulkTargetCategory, setBulkTargetCategory] = useState('UNIVERSITY_OFFICE')
  const [bulkError, setBulkError] = useState('')

  // Add Office modal
  const [addOfficeOpen, setAddOfficeOpen] = useState(false)
  const [addForm, setAddForm] = useState({
    name: '',
    description: '',
    category: 'UNIVERSITY_OFFICE',
  })
  const [addError, setAddError] = useState('')

  // Edit Office modal
  const [editingOffice, setEditingOffice] = useState(null)
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    category: 'UNIVERSITY_OFFICE',
  })
  const [editError, setEditError] = useState('')

  // Deactivate/Activate Confirm dialog
  const [toggleActiveOffice, setToggleActiveOffice] = useState(null)
  const [toggleActiveError, setToggleActiveError] = useState('')

  // Delete Confirm dialog
  const [deletingOffice, setDeletingOffice] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  // Create User Modal for a specific office
  const [createUserOffice, setCreateUserOffice] = useState(null)
  const [createForm, setCreateForm] = useState({
    full_name: '',
    email: '',
    role: 'dept_officer',
  })
  const [createError, setCreateError] = useState('')

  // One-time temporary password modal
  const [tempPasswordModal, setTempPasswordModal] = useState(null)
  const [hasCopiedPassword, setHasCopiedPassword] = useState(false)

  // Cancel Request modal
  const [adminCancelOpen, setAdminCancelOpen] = useState(false)
  const [adminCancelId, setAdminCancelId] = useState('')
  const [adminCancelReason, setAdminCancelReason] = useState('')
  const [adminCancelError, setAdminCancelError] = useState('')

  // 1. Fetch Staffing / Offices Directory
  const { data: officesData, isLoading: officesLoading } = useQuery({
    queryKey: ['admin', 'offices'],
    queryFn: () => adminApi.getOffices(),
  })

  // 2. Fetch Full Departments Management List
  const { data: departmentsData, isLoading: deptsLoading } = useQuery({
    queryKey: ['admin', 'departments', 'all'],
    queryFn: () => adminApi.getAdminDepartments(),
  })

  const rawOffices = useMemo(() => officesData?.items || [], [officesData?.items])
  const rawDepartments = useMemo(() => departmentsData?.items || [], [departmentsData?.items])

  // Merge departments and offices staffing
  const offices = useMemo(() => {
    const officesById = new Map()
    rawOffices.forEach((o) => officesById.set(o.id, o))

    if (rawDepartments.length > 0) {
      return rawDepartments.map((dept) => {
        const staffing = officesById.get(dept.id) || {}
        return {
          ...dept,
          active_officers: staffing.active_officers || [],
          hod: staffing.hod || null,
          missing_officer: dept.missing_officer ?? staffing.missing_officer ?? false,
          missing_hod: dept.missing_hod ?? staffing.missing_hod ?? false,
        }
      })
    }

    return rawOffices.map((o) => ({
      ...o,
      officer_count: o.active_officers?.length || 0,
      subject_count: 0,
      open_approvals_count: 0,
    }))
  }, [rawOffices, rawDepartments])

  // Mapping of users to all their assigned offices across the university
  const userOfficesMap = useMemo(() => {
    const map = new Map()
    offices.forEach((office) => {
      ;(office.active_officers || []).forEach((u) => {
        if (!map.has(u.id)) map.set(u.id, [])
        map.get(u.id).push({ id: office.id, name: office.name })
      })
      if (office.hod) {
        const u = office.hod
        if (!map.has(u.id)) map.set(u.id, [])
        map.get(u.id).push({ id: office.id, name: office.name })
      }
    })
    return map
  }, [offices])

  // Summary Metrics Banner
  const summary = useMemo(() => {
    let missingOfficers = 0
    let missingHods = 0
    let totalOpenApprovals = 0

    offices.forEach((o) => {
      if (o.missing_officer) missingOfficers++
      if (o.missing_hod) missingHods++
      if (o.open_approvals_count) totalOpenApprovals += o.open_approvals_count
    })

    return {
      total: offices.length,
      missingOfficers,
      missingHods,
      totalNeedsStaff: offices.filter((o) => o.missing_officer || o.missing_hod).length,
      totalOpenApprovals,
    }
  }, [offices])

  // Filtered offices for current tab
  const filteredOffices = useMemo(() => {
    return offices.filter((o) => {
      // Tab filter by category
      if (o.category !== activeTab) return false

      // Inactive toggle
      if (!showInactive && o.is_active === false) return false

      // Search term
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase()
        const matchesName = o.name?.toLowerCase().includes(q)
        const matchesDesc = o.description?.toLowerCase().includes(q)
        const matchesOfficers = o.active_officers?.some(
          (u) => u.name?.toLowerCase().includes(q) || u.email?.toLowerCase().includes(q)
        )
        const matchesHod =
          o.hod &&
          (o.hod.name?.toLowerCase().includes(q) || o.hod.email?.toLowerCase().includes(q))
        return matchesName || matchesDesc || matchesOfficers || matchesHod
      }

      return true
    })
  }, [offices, activeTab, showInactive, searchTerm])

  // Bulk Selection handling
  const allCurrentTabIds = useMemo(() => filteredOffices.map((o) => o.id), [filteredOffices])
  const isAllSelected = allCurrentTabIds.length > 0 && allCurrentTabIds.every((id) => selectedIds.includes(id))

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds((prev) => prev.filter((id) => !allCurrentTabIds.includes(id)))
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...allCurrentTabIds])))
    }
  }

  const toggleSelectRow = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  // Refetch helper
  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'offices'] })
    queryClient.invalidateQueries({ queryKey: ['admin', 'departments'] })
  }

  // Create Department Mutation
  const createDeptMutation = useMutation({
    mutationFn: (data) => adminApi.createDepartment(data),
    onSuccess: (newDept) => {
      toast.success(`Office "${newDept.name}" created successfully.`)
      setAddOfficeOpen(false)
      setAddForm({ name: '', description: '', category: activeTab })
      setAddError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create office.'
      setAddError(msg)
      toast.error(msg)
    },
  })

  // Patch Department Mutation (Edit)
  const patchDeptMutation = useMutation({
    mutationFn: ({ id, data }) => adminApi.patchDepartment(id, data),
    onSuccess: (updated) => {
      toast.success(`Office "${updated.name}" updated successfully.`)
      setEditingOffice(null)
      setEditError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update office.'
      setEditError(msg)
      toast.error(msg)
    },
  })

  // Toggle Active Mutation
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }) => adminApi.patchDepartment(id, { is_active, confirm: true }),
    onSuccess: (updated) => {
      toast.success(`Office "${updated.name}" is now ${updated.is_active ? 'active' : 'inactive'}.`)
      setToggleActiveOffice(null)
      setToggleActiveError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to change office active status.'
      setToggleActiveError(msg)
      toast.error(msg)
    },
  })

  // Delete Department Mutation
  const deleteDeptMutation = useMutation({
    mutationFn: (id) => adminApi.deleteDepartment(id),
    onSuccess: () => {
      toast.success('Office deleted successfully.')
      setDeletingOffice(null)
      setDeleteError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg =
        err.response?.status === 409
          ? 'Cannot delete this office because records (approvals, subjects, or memberships) refer to it. Deactivate it instead.'
          : err.response?.data?.detail || 'Failed to delete office.'
      setDeleteError(msg)
      toast.error(msg)
    },
  })

  // Bulk Category Mutation
  const bulkCategoryMutation = useMutation({
    mutationFn: (data) => adminApi.bulkCategory(data),
    onSuccess: (res) => {
      toast.success(res.message || 'Updated office categories successfully.')
      setBulkCategoryOpen(false)
      setSelectedIds([])
      setBulkError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update office categories.'
      setBulkError(msg)
      toast.error(msg)
    },
  })

  // Create Staff User Mutation
  const createUserMutation = useMutation({
    mutationFn: (data) => adminApi.createStaffUser(data),
    onSuccess: (data) => {
      toast.success('Staff account provisioned successfully.')
      const assignedDept = offices.find((d) => d.id === createUserOffice?.office?.id)
      setTempPasswordModal({
        email: data.email,
        password: data.temporary_password,
        role: data.role,
        departmentName: assignedDept?.name || 'Department',
      })
      setCreateUserOffice(null)
      setCreateForm({ full_name: '', email: '', role: 'dept_officer' })
      setCreateError('')
      invalidateAll()
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to provision staff account.'
      setCreateError(msg)
      toast.error(msg)
    },
  })

  // Admin Cancel Request Mutation
  const adminCancelMutation = useMutation({
    mutationFn: ({ requestId, reason }) => adminApi.cancelRequest(requestId, reason),
    onSuccess: (_, variables) => {
      toast.success(`Clearance request #${variables.requestId} has been cancelled.`)
      setAdminCancelOpen(false)
      setAdminCancelId('')
      setAdminCancelReason('')
      setAdminCancelError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to cancel clearance request.'
      setAdminCancelError(msg)
      toast.error(msg)
    },
  })

  const openEditDialog = (office) => {
    setEditError('')
    setEditingOffice(office)
    setEditForm({
      name: office.name,
      description: office.description || '',
      category: office.category || 'UNIVERSITY_OFFICE',
    })
  }

  const openCreateDialog = (office, defaultRole = 'dept_officer') => {
    setCreateError('')
    setCreateForm({
      full_name: '',
      email: '',
      role: defaultRole,
    })
    setCreateUserOffice({ office, defaultRole })
  }

  const handleCopyPassword = () => {
    if (!tempPasswordModal?.password) return
    navigator.clipboard.writeText(tempPasswordModal.password)
    setHasCopiedPassword(true)
    toast.success('Temporary password copied to clipboard.')
    setTimeout(() => setHasCopiedPassword(false), 2500)
  }

  const isLoading = officesLoading || deptsLoading

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-16">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
              University Offices & Categories
            </h1>
            <p className="text-xs sm:text-sm text-zinc-500 mt-1">
              Manage university clearance offices, staffing assignments, and categories across Shri Vishwakarma Skill University.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAdminCancelOpen(true)}
              className="text-xs text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 h-9 gap-1.5"
            >
              <XCircle className="w-3.5 h-3.5" />
              Cancel Request
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setAddError('')
                setAddForm({
                  name: '',
                  description: '',
                  category: activeTab !== 'ACADEMIC' ? activeTab : 'UNIVERSITY_OFFICE',
                })
                setAddOfficeOpen(true)
              }}
              className="bg-black text-white hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Office
            </Button>
          </div>
        </div>

        {/* Staffing Summary Banner */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
                Total Offices
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-zinc-950">{summary.total}</span>
                <Building2 className="w-4 h-4 text-zinc-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
                Offices Needing Staff
              </span>
              <div className="flex items-baseline justify-between">
                <span className={`text-2xl font-bold font-mono ${summary.totalNeedsStaff > 0 ? 'text-amber-600' : 'text-zinc-950'}`}>
                  {summary.totalNeedsStaff}
                </span>
                <AlertTriangle className="w-4 h-4 text-amber-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
                Missing Dealing Officer
              </span>
              <div className="flex items-baseline justify-between">
                <span className={`text-2xl font-bold font-mono ${summary.missingOfficers > 0 ? 'text-rose-600' : 'text-zinc-950'}`}>
                  {summary.missingOfficers}
                </span>
                <Users className="w-4 h-4 text-rose-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
                Open Requests
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-zinc-950">
                  {summary.totalOpenApprovals}
                </span>
                <Briefcase className="w-4 h-4 text-zinc-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Category Navigation Tabs */}
        <div className="border-b border-border">
          <div className="flex items-center gap-1 overflow-x-auto pb-px">
            {OFFICE_TABS.map((tab) => {
              const TabIcon = tab.icon
              const count = offices.filter((o) => o.category === tab.id).length
              const isActive = activeTab === tab.id

              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id)
                    setSelectedIds([])
                  }}
                  className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors ${
                    isActive
                      ? 'border-black text-black bg-zinc-50/50'
                      : 'border-transparent text-zinc-500 hover:text-zinc-900 hover:border-zinc-300'
                  }`}
                >
                  <TabIcon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                  <Badge
                    variant="outline"
                    className={`text-[10px] py-0 px-1.5 font-mono ${
                      isActive ? 'bg-black text-white border-black' : 'bg-zinc-100 text-zinc-600 border-zinc-200'
                    }`}
                  >
                    {count}
                  </Badge>
                </button>
              )
            })}
          </div>
        </div>

        {/* Search, Filter & Bulk Actions Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-400" />
              <Input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search offices by name, description or staff..."
                className="pl-8 text-xs h-9"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer text-xs select-none shrink-0 text-zinc-700 font-medium">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="rounded border-zinc-300 text-black focus:ring-black h-3.5 w-3.5"
              />
              <span>Show inactive</span>
            </label>
          </div>

          {/* Bulk Action Trigger */}
          {selectedIds.length > 0 && (
            <div className="flex items-center gap-2 bg-zinc-50 border border-zinc-200 px-3 py-1.5 rounded-lg text-xs">
              <span className="font-semibold text-zinc-900">
                {selectedIds.length} {selectedIds.length === 1 ? 'office' : 'offices'} selected
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setBulkError('')
                  setBulkTargetCategory(activeTab !== 'ACADEMIC' ? activeTab : 'UNIVERSITY_OFFICE')
                  setBulkCategoryOpen(true)
                }}
                className="text-xs h-7 bg-white font-medium gap-1"
              >
                Change type
              </Button>
            </div>
          )}
        </div>

        {/* Offices Table */}
        <div className="border border-border rounded-xl bg-white overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50/75 border-b border-border text-zinc-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="p-3 w-10">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={toggleSelectAll}
                      className="rounded border-zinc-300 text-black focus:ring-black h-3.5 w-3.5"
                      aria-label="Select all rows"
                    />
                  </th>
                  <th className="p-3">Office Name & Description</th>
                  <th className="p-3">Staff / Dealing Officers</th>
                  {activeTab === 'LAB_WORKSHOP' && <th className="p-3">Subjects</th>}
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {isLoading ? (
                  <tr>
                    <td colSpan={activeTab === 'LAB_WORKSHOP' ? 6 : 5} className="p-8 text-center text-zinc-500">
                      Loading offices...
                    </td>
                  </tr>
                ) : filteredOffices.length === 0 ? (
                  <tr>
                    <td colSpan={activeTab === 'LAB_WORKSHOP' ? 6 : 5} className="p-8 text-center text-zinc-500">
                      {searchTerm
                        ? `No offices matching "${searchTerm}".`
                        : `No offices found in this category.`}
                    </td>
                  </tr>
                ) : (
                  filteredOffices.map((office) => {
                    const isChecked = selectedIds.includes(office.id)
                    const officers = office.active_officers || []

                    return (
                      <tr
                        key={office.id}
                        className={`hover:bg-zinc-50/50 transition-colors ${
                          isChecked ? 'bg-zinc-50/80' : ''
                        }`}
                      >
                        <td className="p-3">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleSelectRow(office.id)}
                            className="rounded border-zinc-300 text-black focus:ring-black h-3.5 w-3.5"
                            aria-label={`Select ${office.name}`}
                          />
                        </td>
                        <td className="p-3 max-w-[280px]">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-zinc-950 text-xs">
                                {office.name}
                              </span>
                              {office.open_approvals_count > 0 && (
                                <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-900 border-amber-200">
                                  {office.open_approvals_count} open requests
                                </Badge>
                              )}
                            </div>
                            {office.description && (
                              <p className="text-[11px] text-zinc-500 line-clamp-2 leading-relaxed">
                                {office.description}
                              </p>
                            )}
                            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                              <Badge variant="outline" className="text-[10px] bg-zinc-100 text-zinc-700 border-zinc-200">
                                {office.label || office.category?.replace(/_/g, ' ')}
                              </Badge>
                              {office.missing_officer && (
                                <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-800 border-amber-300 gap-1">
                                  <AlertTriangle className="w-2.5 h-2.5 text-amber-600" />
                                  Missing Officer
                                </Badge>
                              )}
                              {office.missing_hod && (
                                <Badge variant="outline" className="text-[10px] bg-rose-50 text-rose-800 border-rose-300 gap-1">
                                  <AlertTriangle className="w-2.5 h-2.5 text-rose-600" />
                                  Missing HoD
                                </Badge>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="p-3 max-w-[260px]">
                          <div className="space-y-1.5">
                            {officers.length === 0 ? (
                              <span className="text-zinc-400 italic text-[11px]">No active dealing officers</span>
                            ) : (
                              officers.map((off) => {
                                const otherOffices = (userOfficesMap.get(off.id) || []).filter(
                                  (o) => o.id !== office.id
                                )
                                return (
                                  <div key={off.id} className="text-xs space-y-0.5">
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                      <span className="font-medium text-zinc-900">{off.name}</span>
                                      {otherOffices.length > 0 && (
                                        <Badge
                                          variant="outline"
                                          className="text-[9px] px-1 py-0 bg-zinc-50 text-zinc-600 border-zinc-200"
                                          title={`Also assigned to: ${otherOffices.map((o) => o.name).join(', ')}`}
                                        >
                                          +{otherOffices.length} other
                                        </Badge>
                                      )}
                                    </div>
                                    <span className="text-[11px] text-zinc-500 font-mono block">
                                      {off.email}
                                    </span>
                                  </div>
                                )
                              })
                            )}

                            {office.hod && (
                              <div className="pt-1 border-t border-zinc-100 text-xs">
                                <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block">
                                  Chairperson / HoD:
                                </span>
                                <span className="font-medium text-zinc-900">{office.hod.name}</span>
                                <span className="text-[11px] text-zinc-500 font-mono block">
                                  {office.hod.email}
                                </span>
                              </div>
                            )}
                          </div>
                        </td>
                        {activeTab === 'LAB_WORKSHOP' && (
                          <td className="p-3">
                            <Link
                              to="/admin/lab-courses"
                              className="text-xs font-mono font-medium text-zinc-800 hover:text-black hover:underline"
                            >
                              {office.subject_count || 0} subjects
                            </Link>
                          </td>
                        )}
                        <td className="p-3">
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-medium ${
                              office.is_active
                                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                : 'bg-zinc-100 text-zinc-600 border-zinc-300'
                            }`}
                          >
                            {office.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditDialog(office)}
                              className="h-8 px-2 text-xs text-zinc-700 hover:bg-zinc-100"
                              title="Edit office details and category"
                            >
                              <Edit className="w-3.5 h-3.5" />
                              <span className="hidden lg:inline ml-1">Edit</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openCreateDialog(office, 'dept_officer')}
                              className="h-8 px-2 text-xs text-zinc-700 hover:bg-zinc-100"
                              title="Assign new officer"
                            >
                              <UserPlus className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setToggleActiveError('')
                                setToggleActiveOffice(office)
                              }}
                              className={`h-8 px-2 text-xs ${
                                office.is_active
                                  ? 'text-amber-700 hover:bg-amber-50'
                                  : 'text-emerald-700 hover:bg-emerald-50'
                              }`}
                              title={office.is_active ? 'Deactivate office' : 'Activate office'}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setDeleteError('')
                                setDeletingOffice(office)
                              }}
                              className="h-8 px-2 text-xs text-red-600 hover:bg-red-50"
                              title="Delete office"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Dialog: Add Office */}
        <Dialog open={addOfficeOpen} onOpenChange={setAddOfficeOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!addForm.name.trim()) {
                  setAddError('Office name is required.')
                  return
                }
                createDeptMutation.mutate({
                  name: addForm.name.trim(),
                  description: addForm.description.trim() || null,
                  category: addForm.category,
                })
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  Add University Office
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Create a new university clearance office under the appropriate category.
                </DialogDescription>
              </DialogHeader>

              {addError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {addError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="add-name" className="text-xs font-semibold text-zinc-800">
                    Office Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="add-name"
                    value={addForm.name}
                    onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                    placeholder="e.g. Robotics Center, Central Workshop"
                    required
                    maxLength={80}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="add-category" className="text-xs font-semibold text-zinc-800">
                    Category <span className="text-rose-500">*</span>
                  </Label>
                  <Select
                    value={addForm.category}
                    onValueChange={(val) => setAddForm({ ...addForm, category: val })}
                  >
                    <SelectTrigger id="add-category" className="text-xs">
                      <SelectValue placeholder="Select category..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UNIVERSITY_OFFICE">University office</SelectItem>
                      <SelectItem value="HOSTEL">Hostel</SelectItem>
                      <SelectItem value="LAB_WORKSHOP">Lab / Workshop</SelectItem>
                      <SelectItem value="ADDITIONAL_FACILITY">Additional facility</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="add-description" className="text-xs font-semibold text-zinc-800">
                    Description (Optional)
                  </Label>
                  <Textarea
                    id="add-description"
                    value={addForm.description}
                    onChange={(e) => setAddForm({ ...addForm, description: e.target.value })}
                    placeholder="Brief description of the facility and clearance scope..."
                    className="text-xs min-h-[70px]"
                    maxLength={500}
                  />
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAddOfficeOpen(false)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createDeptMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {createDeptMutation.isPending ? 'Creating...' : 'Create Office'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Dialog: Edit Office */}
        <Dialog open={Boolean(editingOffice)} onOpenChange={(open) => !open && setEditingOffice(null)}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!editForm.name.trim()) {
                  setEditError('Office name is required.')
                  return
                }
                patchDeptMutation.mutate({
                  id: editingOffice.id,
                  data: {
                    name: editForm.name.trim(),
                    description: editForm.description.trim() || null,
                    category: editForm.category,
                  },
                })
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  Edit Office Details
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Update office name, description, or category.
                </DialogDescription>
              </DialogHeader>

              {editingOffice?.open_approvals_count > 0 && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-900 mb-3 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                  <p className="leading-snug">
                    <span className="font-semibold">Notice:</span> This office currently has{' '}
                    {editingOffice.open_approvals_count} open clearance requests. Changing category will be refused by the system until active requests conclude.
                  </p>
                </div>
              )}

              {editError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {editError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="edit-name" className="text-xs font-semibold text-zinc-800">
                    Office Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="edit-name"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    required
                    maxLength={80}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="edit-category" className="text-xs font-semibold text-zinc-800">
                    Category <span className="text-rose-500">*</span>
                  </Label>
                  <Select
                    value={editForm.category}
                    onValueChange={(val) => setEditForm({ ...editForm, category: val })}
                  >
                    <SelectTrigger id="edit-category" className="text-xs">
                      <SelectValue placeholder="Select category..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UNIVERSITY_OFFICE">University office</SelectItem>
                      <SelectItem value="HOSTEL">Hostel</SelectItem>
                      <SelectItem value="LAB_WORKSHOP">Lab / Workshop</SelectItem>
                      <SelectItem value="ADDITIONAL_FACILITY">Additional facility</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="edit-description" className="text-xs font-semibold text-zinc-800">
                    Description
                  </Label>
                  <Textarea
                    id="edit-description"
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    placeholder="Brief description..."
                    className="text-xs min-h-[70px]"
                    maxLength={500}
                  />
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditingOffice(null)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={patchDeptMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {patchDeptMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Dialog: Bulk Category Update */}
        <Dialog open={bulkCategoryOpen} onOpenChange={setBulkCategoryOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                bulkCategoryMutation.mutate({
                  department_ids: selectedIds,
                  category: bulkTargetCategory,
                })
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  Change Office Category (Bulk)
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Update the category for {selectedIds.length} selected offices simultaneously.
                </DialogDescription>
              </DialogHeader>

              {bulkError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {bulkError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="bulk-cat" className="text-xs font-semibold text-zinc-800">
                    Target Category
                  </Label>
                  <Select
                    value={bulkTargetCategory}
                    onValueChange={setBulkTargetCategory}
                  >
                    <SelectTrigger id="bulk-cat" className="text-xs">
                      <SelectValue placeholder="Select target category..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UNIVERSITY_OFFICE">University office</SelectItem>
                      <SelectItem value="HOSTEL">Hostel</SelectItem>
                      <SelectItem value="LAB_WORKSHOP">Lab / Workshop</SelectItem>
                      <SelectItem value="ADDITIONAL_FACILITY">Additional facility</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <p className="text-[11px] text-zinc-500 leading-relaxed">
                  Notice: The system will refuse this change if any selected office has active clearance reviews pending student decisions.
                </p>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setBulkCategoryOpen(false)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={bulkCategoryMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {bulkCategoryMutation.isPending ? 'Updating...' : `Update ${selectedIds.length} Offices`}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Dialog: Toggle Active / Inactive Confirm */}
        <AlertDialog open={Boolean(toggleActiveOffice)} onOpenChange={(open) => !open && setToggleActiveOffice(null)}>
          <AlertDialogContent className="bg-white max-w-md">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-heading font-bold text-base">
                {toggleActiveOffice?.is_active ? 'Deactivate Office' : 'Activate Office'}
              </AlertDialogTitle>
              <AlertDialogDescription className="text-xs text-zinc-600 space-y-2">
                <span>
                  Are you sure you want to {toggleActiveOffice?.is_active ? 'deactivate' : 'activate'}{' '}
                  <strong>"{toggleActiveOffice?.name}"</strong>?
                </span>
                {toggleActiveOffice?.is_active && (
                  <span className="block text-[11px] text-zinc-500">
                    Deactivated offices cannot be chosen by students for clearance and will not be dispatched on new requests. Existing completed records remain preserved.
                  </span>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>

            {toggleActiveError && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900">
                {toggleActiveError}
              </div>
            )}

            <AlertDialogFooter>
              <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault()
                  toggleActiveMutation.mutate({
                    id: toggleActiveOffice.id,
                    is_active: !toggleActiveOffice.is_active,
                  })
                }}
                disabled={toggleActiveMutation.isPending}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {toggleActiveMutation.isPending ? 'Processing...' : 'Confirm'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Dialog: Delete Office Confirm */}
        <AlertDialog open={Boolean(deletingOffice)} onOpenChange={(open) => !open && setDeletingOffice(null)}>
          <AlertDialogContent className="bg-white max-w-md">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-heading font-bold text-base text-rose-600">
                Delete Office
              </AlertDialogTitle>
              <AlertDialogDescription className="text-xs text-zinc-600 space-y-2">
                <span>
                  Are you sure you want to permanently delete <strong>"{deletingOffice?.name}"</strong>?
                </span>
                <span className="block text-[11px] text-zinc-500">
                  Offices can only be deleted if no historical clearances, courses, or member records refer to them. If references exist, the system requires you to deactivate it instead.
                </span>
              </AlertDialogDescription>
            </AlertDialogHeader>

            {deleteError && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900">
                {deleteError}
              </div>
            )}

            <AlertDialogFooter>
              <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault()
                  deleteDeptMutation.mutate(deletingOffice.id)
                }}
                disabled={deleteDeptMutation.isPending}
                className="bg-rose-600 text-white hover:bg-rose-700 text-xs h-9 font-semibold"
              >
                {deleteDeptMutation.isPending ? 'Deleting...' : 'Delete Permanently'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Dialog: Provision Staff Account for this Office */}
        <Dialog open={Boolean(createUserOffice)} onOpenChange={(open) => !open && setCreateUserOffice(null)}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!createForm.full_name.trim() || !createForm.email.trim()) {
                  setCreateError('Full name and official university email are required.')
                  return
                }
                createUserMutation.mutate({
                  full_name: createForm.full_name.trim(),
                  email: createForm.email.trim(),
                  role: createForm.role,
                  department_id: createUserOffice.office.id,
                })
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  Provision Staff Account
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Create and assign a staff member for {createUserOffice?.office?.name}.
                </DialogDescription>
              </DialogHeader>

              {createError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {createError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="staff-name" className="text-xs font-semibold text-zinc-800">
                    Full Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="staff-name"
                    value={createForm.full_name}
                    onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                    placeholder="e.g. Dr. Ramesh Kumar"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="staff-email" className="text-xs font-semibold text-zinc-800">
                    University Email <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="staff-email"
                    type="email"
                    value={createForm.email}
                    onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                    placeholder="official email @svsu.ac.in"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="staff-role" className="text-xs font-semibold text-zinc-800">
                    Staff Role
                  </Label>
                  <Select
                    value={createForm.role}
                    onValueChange={(val) => setCreateForm({ ...createForm, role: val })}
                  >
                    <SelectTrigger id="staff-role" className="text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="dept_officer">Dealing Officer</SelectItem>
                      <SelectItem value="hod">Chairperson / HoD</SelectItem>
                      <SelectItem value="registrar_accounts">Accounts Officer</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCreateUserOffice(null)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createUserMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {createUserMutation.isPending ? 'Provisioning...' : 'Provision Account'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Dialog: Temporary One-Time Password */}
        <Dialog open={Boolean(tempPasswordModal)} onOpenChange={(open) => !open && setTempPasswordModal(null)}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base text-zinc-950">
                Staff Account Provisioned
              </DialogTitle>
              <DialogDescription className="text-xs">
                Copy and deliver these credentials to the staff officer. This password will not be shown again.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-2 text-xs">
              <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 space-y-1">
                <div className="text-[11px] text-zinc-500">Official Email</div>
                <div className="font-mono font-semibold text-zinc-900">{tempPasswordModal?.email}</div>
              </div>

              <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 space-y-1">
                <div className="text-[11px] text-zinc-500">One-Time Password</div>
                <div className="flex items-center justify-between">
                  <div className="font-mono font-bold text-base text-zinc-950">
                    {tempPasswordModal?.password}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyPassword}
                    className="h-8 text-xs gap-1 font-medium bg-white"
                  >
                    {hasCopiedPassword ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : 'Copy'}
                  </Button>
                </div>
              </div>
            </div>

            <DialogFooter className="pt-3 border-t border-zinc-100">
              <Button
                type="button"
                onClick={() => setTempPasswordModal(null)}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold w-full"
              >
                Done
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Dialog: Cancel Active Clearance Request */}
        <Dialog open={adminCancelOpen} onOpenChange={setAdminCancelOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const reqId = parseInt(adminCancelId, 10)
                if (!reqId || isNaN(reqId)) {
                  setAdminCancelError('A valid numeric Request ID is required.')
                  return
                }
                if (!adminCancelReason.trim()) {
                  setAdminCancelError('Cancellation reason is strictly mandatory.')
                  return
                }
                adminCancelMutation.mutate({ requestId: reqId, reason: adminCancelReason.trim() })
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base text-red-600">
                  Cancel Clearance Request (Admin)
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Administrative override to cancel an active request before decisions are finalized.
                </DialogDescription>
              </DialogHeader>

              {adminCancelError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {adminCancelError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="cancel-req-id" className="text-xs font-semibold text-zinc-800">
                    Clearance Request ID <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="cancel-req-id"
                    type="number"
                    value={adminCancelId}
                    onChange={(e) => setAdminCancelId(e.target.value)}
                    placeholder="e.g. 101"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="cancel-reason" className="text-xs font-semibold text-zinc-800">
                    Mandatory Reason for Cancellation <span className="text-rose-500">*</span>
                  </Label>
                  <Textarea
                    id="cancel-reason"
                    value={adminCancelReason}
                    onChange={(e) => setAdminCancelReason(e.target.value)}
                    placeholder="State administrative justification for cancellation..."
                    className="text-xs min-h-[80px]"
                    required
                    maxLength={1000}
                  />
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAdminCancelOpen(false)}
                  className="text-xs h-9"
                >
                  Close
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={adminCancelMutation.isPending}
                  className="bg-red-600 text-white hover:bg-red-700 text-xs h-9 font-semibold"
                >
                  {adminCancelMutation.isPending ? 'Cancelling...' : 'Cancel Clearance Request'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}

export default AdminOfficesPage
