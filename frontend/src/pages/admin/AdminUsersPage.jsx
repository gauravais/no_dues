import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
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
import { toast } from 'sonner'
import {
  Users,
  UserPlus,
  Upload,
  Search,
  KeyRound,
  Copy,
  Check,
  ShieldAlert,
  AlertTriangle,
  UserCheck,
  UserX,
  FileSpreadsheet,
  Download,
} from 'lucide-react'

const ROLE_BADGES = {
  admin: { label: 'Administrator', className: 'bg-zinc-900 text-white border-zinc-900' },
  dept_officer: { label: 'Department Officer', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  hod: { label: 'Chairperson (HoD)', className: 'bg-purple-50 text-purple-700 border-purple-200' },
  registrar_accounts: { label: 'Registrar / Accounts', className: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  student: { label: 'Student', className: 'bg-zinc-100 text-zinc-700 border-zinc-200' },
}

export function AdminUsersPage() {
  useDocumentTitle('Staff & Users Directory | SVSU No-Dues')
  const { user: currentAdmin } = useAuth()
  const queryClient = useQueryClient()

  // Filter & Search State
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('ALL')
  const [departmentFilter, setDepartmentFilter] = useState('ALL')
  const [activeFilter, setActiveFilter] = useState('ALL')
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)

  // Modals State
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isBulkOpen, setIsBulkOpen] = useState(false)

  // Single User Create Form
  const [createForm, setCreateForm] = useState({
    full_name: '',
    email: '',
    role: 'dept_officer',
    department_id: '',
    google_only: false,
  })
  const [createError, setCreateError] = useState('')

  // Bulk Upload State
  const [bulkFile, setBulkFile] = useState(null)
  const [bulkGoogleOnly, setBulkGoogleOnly] = useState(false)
  const [bulkReport, setBulkReport] = useState(null)
  const [bulkError, setBulkError] = useState('')

  // Confirmation Alert Dialogs
  const [confirmResetTarget, setConfirmResetTarget] = useState(null) // user object
  const [confirmToggleTarget, setConfirmToggleTarget] = useState(null) // user object

  // ONE-TIME TEMPORARY PASSWORD MODAL (strictly memory-held, wiped on close)
  const [tempPasswordModal, setTempPasswordModal] = useState(null) // { title, email, password, note }
  const [hasCopiedPassword, setHasCopiedPassword] = useState(false)

  // Fetch Departments for filtering and selection
  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: () => adminApi.getDepartments(),
  })

  // Filtered academic departments specifically for HoD role
  const academicDepartments = useMemo(
    () => departments.filter((d) => d.kind === 'academic'),
    [departments]
  )

  // Fetch Users
  const {
    data: users = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      'admin',
      'users',
      searchQuery,
      roleFilter,
      departmentFilter,
      activeFilter,
      pageIndex,
      pageSize,
    ],
    queryFn: () =>
      adminApi.getUsers({
        search: searchQuery.trim() || undefined,
        role: roleFilter,
        department_id: departmentFilter,
        is_active: activeFilter,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  // Create User Mutation
  const createUserMutation = useMutation({
    mutationFn: (data) => adminApi.createStaffUser(data),
    onSuccess: (data) => {
      toast.success('User account provisioned successfully.')
      setIsCreateOpen(false)
      setCreateForm({ full_name: '', email: '', role: 'dept_officer', department_id: '', google_only: false })
      setCreateError('')
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'offices'] })

      // Open one-time credential modal ONLY if a temporary password was generated
      if (data.temporary_password) {
        setTempPasswordModal({
          title: 'New Account Provisioned',
          email: data.email,
          password: data.temporary_password,
          note: `Role: ${data.role}`,
        })
      } else {
        toast.info(`Account provisioned for ${data.email}. This user signs in with Google.`)
      }
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create user account.'
      setCreateError(msg)
      toast.error(msg)
    },
  })

  // Reset Password Mutation
  const resetPasswordMutation = useMutation({
    mutationFn: (userId) => adminApi.resetPassword(userId),
    onSuccess: (data, userId) => {
      const targetUser = users.find((u) => u.id === userId)
      toast.success('Password reset successfully.')
      setConfirmResetTarget(null)
      // Open one-time credential modal
      setTempPasswordModal({
        title: 'Password Reset Generated',
        email: data.email || targetUser?.email,
        password: data.temporary_password,
        note: 'The previous password has been invalidated immediately.',
      })
    },
    onError: (err) => {
      setConfirmResetTarget(null)
      toast.error(err.response?.data?.detail || 'Failed to reset password.')
    },
  })

  // Toggle Active Mutation
  const toggleActiveMutation = useMutation({
    mutationFn: ({ userId, isActive }) => adminApi.setUserActive(userId, isActive),
    onSuccess: (_, variables) => {
      toast.success(
        variables.isActive
          ? 'User account activated successfully.'
          : 'User account deactivated.'
      )
      setConfirmToggleTarget(null)
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'offices'] })
    },
    onError: (err) => {
      setConfirmToggleTarget(null)
      toast.error(err.response?.data?.detail || 'Failed to update user status.')
    },
  })

  // Bulk Upload Mutation
  const bulkUploadMutation = useMutation({
    mutationFn: ({ file, googleOnly }) => adminApi.bulkUploadUsers(file, { google_only: googleOnly }),
    onSuccess: (data) => {
      setBulkReport(data)
      setBulkFile(null)
      setBulkError('')
      toast.success(
        `Staff upload complete: ${data.created_count} created, ${data.rejected_count} rejected.`
      )
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'offices'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to process bulk staff CSV.'
      setBulkError(msg)
      toast.error(msg)
    },
  })

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setSearchQuery(searchInput)
    setPageIndex(0)
  }

  const handleCreateSubmit = (e) => {
    e.preventDefault()
    if (!createForm.full_name.trim() || !createForm.email.trim()) {
      setCreateError('Full name and official email are required.')
      return
    }

    if (
      (createForm.role === 'dept_officer' || createForm.role === 'hod') &&
      !createForm.department_id
    ) {
      setCreateError(`Department assignment is mandatory for ${createForm.role}.`)
      return
    }

    const payload = {
      full_name: createForm.full_name.trim(),
      email: createForm.email.trim(),
      role: createForm.role,
      google_only: Boolean(createForm.google_only),
    }
    if (createForm.department_id) {
      payload.department_id = Number(createForm.department_id)
    }

    createUserMutation.mutate(payload)
  }

  const handleCopyPassword = (pwd) => {
    navigator.clipboard.writeText(pwd)
    setHasCopiedPassword(true)
    toast.success('Password copied to clipboard.')
    setTimeout(() => setHasCopiedPassword(false), 2500)
  }

  const downloadBulkTemplate = () => {
    const csvContent =
      'email,full_name,role,department,google_only\r\n' +
      'officer.csit@svsu.ac.in,Dr. Rajesh Kumar,dept_officer,Skill Department of CS/IT,false\r\n' +
      'hod.csit@svsu.ac.in,Dr. Sunita Sharma,hod,Skill Department of CS/IT,true\r\n' +
      'accounts.staff@svsu.ac.in,Ramesh Chand,registrar_accounts,Account Section,false\r\n'
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'staff_users_template.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const downloadCredentialsCsv = (rows) => {
    const createdRows = (rows || []).filter((r) => r.status === 'created' && r.temporary_password)
    if (createdRows.length === 0) {
      toast.error('No generated credentials to download.')
      return
    }
    let csvContent = 'email,temporary_password\r\n'
    createdRows.forEach((r) => {
      csvContent += `"${r.email}","${r.temporary_password}"\r\n`
    })

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'staff_credentials_one_time.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    toast.success('Credentials CSV downloaded. Store it securely!')
  }

  // Table Columns
  const columns = useMemo(
    () => [
      {
        accessorKey: 'id',
        header: 'User ID',
        cell: ({ row }) => (
          <span className="font-mono text-xs font-semibold text-zinc-500">
            #{row.original.id}
          </span>
        ),
      },
      {
        accessorKey: 'full_name',
        header: 'Staff Member',
        cell: ({ row }) => (
          <div className="space-y-0.5 py-1">
            <span className="font-semibold text-xs text-zinc-900 block">
              {row.original.full_name}
            </span>
            <span className="text-[11px] text-zinc-500 font-mono block">
              {row.original.email}
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'role',
        header: 'Role',
        cell: ({ row }) => {
          const roleCfg = ROLE_BADGES[row.original.role] || {
            label: row.original.role,
            className: 'bg-zinc-100 text-zinc-700',
          }
          return (
            <Badge variant="outline" className={`text-[10px] py-0.5 ${roleCfg.className}`}>
              {roleCfg.label}
            </Badge>
          )
        },
      },
      {
        accessorKey: 'department_name',
        header: 'Department / Section',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-700 max-w-[220px] line-clamp-1">
            {row.original.department_name || (
              <span className="text-zinc-400 italic">None / University-Wide</span>
            )}
          </span>
        ),
      },
      {
        accessorKey: 'is_active',
        header: 'Status',
        cell: ({ row }) => {
          const isActive = row.original.is_active
          return (
            <Badge
              variant="outline"
              className={
                isActive
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200 text-[10px] gap-1'
                  : 'bg-zinc-100 text-zinc-600 border-zinc-200 text-[10px] gap-1'
              }
            >
              {isActive ? (
                <>
                  <UserCheck className="w-3 h-3 text-emerald-600" />
                  Active
                </>
              ) : (
                <>
                  <UserX className="w-3 h-3 text-zinc-500" />
                  Inactive
                </>
              )}
            </Badge>
          )
        },
      },
      {
        id: 'actions',
        header: 'Administration',
        cell: ({ row }) => {
          const target = row.original
          const isSelf = target.id === currentAdmin?.id

          return (
            <div className="flex items-center gap-1.5 flex-wrap">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfirmResetTarget(target)}
                className="h-7 text-[11px] gap-1 bg-white hover:bg-zinc-50 text-zinc-700 border-zinc-200"
              >
                <KeyRound className="w-3 h-3 text-zinc-500" />
                Reset Password
              </Button>

              <Button
                size="sm"
                variant="outline"
                disabled={isSelf}
                onClick={() => setConfirmToggleTarget(target)}
                title={isSelf ? 'You cannot deactivate your own account.' : undefined}
                className={`h-7 text-[11px] gap-1 ${
                  target.is_active
                    ? 'hover:bg-rose-50 text-zinc-700 hover:text-rose-700 border-zinc-200'
                    : 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
                }`}
              >
                {target.is_active ? (
                  <>
                    <UserX className="w-3 h-3 text-zinc-500" />
                    Deactivate
                  </>
                ) : (
                  <>
                    <UserCheck className="w-3 h-3 text-emerald-600" />
                    Activate
                  </>
                )}
              </Button>
            </div>
          )
        },
      },
    ],
    [currentAdmin]
  )

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-zinc-900" />
              <h1 className="font-heading text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
                Staff & User Directory
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Provision department officers, Chairperson (HoD) accounts, reset passwords, and toggle active credentials.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setBulkReport(null)
                setBulkFile(null)
                setBulkError('')
                setIsBulkOpen(true)
              }}
              className="text-xs h-9 gap-1.5 border-zinc-200 text-zinc-800"
            >
              <Upload className="w-3.5 h-3.5" />
              Bulk Staff Upload
            </Button>

            <Button
              size="sm"
              onClick={() => {
                setCreateError('')
                setIsCreateOpen(true)
              }}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Create User
            </Button>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 bg-zinc-50/80 p-3 rounded-xl border border-border">
          {/* Search Bar */}
          <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-sm">
            <Input
              placeholder="Search by full name or university email..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="text-xs h-9 bg-white pl-8 pr-16"
            />
            <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-3" />
            <Button
              type="submit"
              size="sm"
              variant="ghost"
              className="absolute right-1 top-1 h-7 text-[11px] px-2 text-zinc-600 hover:text-black font-semibold"
            >
              Search
            </Button>
          </form>

          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Role Filter */}
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value)
                setPageIndex(0)
              }}
              className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="ALL">All Roles</option>
              <option value="dept_officer">Department Officers</option>
              <option value="hod">Chairpersons (HoD)</option>
              <option value="registrar_accounts">Registrar / Accounts</option>
              <option value="admin">Administrators</option>
              <option value="student">Students</option>
            </select>

            {/* Department Filter */}
            <select
              value={departmentFilter}
              onChange={(e) => {
                setDepartmentFilter(e.target.value)
                setPageIndex(0)
              }}
              className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring max-w-[200px]"
            >
              <option value="ALL">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>

            {/* Active Status Filter */}
            <select
              value={activeFilter}
              onChange={(e) => {
                setActiveFilter(e.target.value)
                setPageIndex(0)
              }}
              className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="ALL">All Statuses</option>
              <option value="true">Active Only</option>
              <option value="false">Inactive Only</option>
            </select>

            {(searchQuery || roleFilter !== 'ALL' || departmentFilter !== 'ALL' || activeFilter !== 'ALL') && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearchInput('')
                  setSearchQuery('')
                  setRoleFilter('ALL')
                  setDepartmentFilter('ALL')
                  setActiveFilter('ALL')
                  setPageIndex(0)
                }}
                className="text-xs h-9 text-zinc-500 hover:text-black"
              >
                Clear Filters
              </Button>
            )}
          </div>
        </div>

        {/* Users DataTable */}
        {isError ? (
          <div className="p-6 rounded-xl border border-rose-200 bg-rose-50 text-rose-900 text-xs">
            <p className="font-semibold">Failed to load user directory.</p>
            <p className="mt-1">{error?.response?.data?.detail || error?.message || 'Server error'}</p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => refetch()}
              className="mt-3 text-xs h-8 bg-white"
            >
              Retry
            </Button>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={users}
            loading={isLoading}
            emptyMessage="No university accounts match the specified criteria."
            pageSize={pageSize}
          />
        )}
      </div>

      {/* CREATE USER MODAL */}
      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!open) {
            setIsCreateOpen(false)
            setCreateError('')
          }
        }}
      >
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleCreateSubmit}>
            <DialogHeader className="pb-3 border-b border-zinc-100">
              <DialogTitle className="font-heading font-bold text-base flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-zinc-900" />
                Provision University Staff User
              </DialogTitle>
              <DialogDescription className="text-xs">
                Creates an institutional account and returns a one-time temporary password.
              </DialogDescription>
            </DialogHeader>

            {createError && (
              <div className="p-3 my-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p>{createError}</p>
              </div>
            )}

            <div className="space-y-3.5 py-4 text-xs">
              {/* Role Selection */}
              <div className="space-y-1.5">
                <Label htmlFor="newUserRole" className="text-xs font-semibold text-zinc-800">
                  Role
                </Label>
                <select
                  id="newUserRole"
                  value={createForm.role}
                  onChange={(e) => {
                    const newRole = e.target.value
                    // If switching to HoD, reset department if not academic
                    let newDeptId = createForm.department_id
                    if (newRole === 'hod') {
                      const currentDept = departments.find((d) => d.id === Number(newDeptId))
                      if (currentDept?.kind !== 'academic') {
                        newDeptId = academicDepartments[0]?.id ? String(academicDepartments[0].id) : ''
                      }
                    }
                    setCreateForm({ ...createForm, role: newRole, department_id: newDeptId })
                  }}
                  className="w-full h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="dept_officer">Department Officer (dept_officer)</option>
                  <option value="hod">Chairperson / HoD (hod)</option>
                  <option value="registrar_accounts">Registrar / Accounts Staff</option>
                  <option value="admin">Administrator (admin)</option>
                </select>
              </div>

              {/* Department Selection (Strictly filtered for HoD to academic faculties) */}
              {(createForm.role === 'dept_officer' || createForm.role === 'hod') && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="newUserDept" className="text-xs font-semibold text-zinc-800">
                      Assigned Department
                    </Label>
                    {createForm.role === 'hod' && (
                      <span className="text-[10px] text-purple-700 font-medium">
                        Academic Faculties Only
                      </span>
                    )}
                  </div>
                  <select
                    id="newUserDept"
                    value={createForm.department_id}
                    onChange={(e) => setCreateForm({ ...createForm, department_id: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    required
                  >
                    <option value="">Select Department...</option>
                    {(createForm.role === 'hod' ? academicDepartments : departments).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} {d.kind === 'academic' ? '(Academic)' : '(Service)'}
                      </option>
                    ))}
                  </select>
                  {createForm.role === 'hod' && (
                    <p className="text-[11px] text-zinc-500">
                      Chairperson (HoD) accounts may only be provisioned for academic teaching faculties.
                    </p>
                  )}
                </div>
              )}

              {/* Full Name */}
              <div className="space-y-1.5">
                <Label htmlFor="newUserName" className="text-xs font-semibold text-zinc-800">
                  Full Name
                </Label>
                <Input
                  id="newUserName"
                  placeholder="e.g. Dr. Rajesh Kumar"
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>

              {/* Email */}
              <div className="space-y-1.5">
                <Label htmlFor="newUserEmail" className="text-xs font-semibold text-zinc-800">
                  Official Email
                </Label>
                <Input
                  id="newUserEmail"
                  type="email"
                  placeholder="e.g. rajesh.kumar@svsu.ac.in"
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  className="text-xs font-mono"
                  required
                />
                <p className="text-[11px] text-zinc-500">
                  Must end in an approved institutional domain (@svsu.ac.in).
                </p>
              </div>

              {/* Google Sign-in Only Switch */}
              <div className="flex items-start justify-between p-3 rounded-lg border border-zinc-200 bg-zinc-50/70 gap-3">
                <div className="space-y-0.5">
                  <Label htmlFor="googleOnlySwitch" className="text-xs font-semibold text-zinc-900 cursor-pointer">
                    Google sign-in only (no password)
                  </Label>
                  <p className="text-[11px] text-zinc-500 leading-snug">
                    When enabled, the user signs in with their university Google account. No temporary password will be created or displayed.
                  </p>
                </div>
                <input
                  id="googleOnlySwitch"
                  type="checkbox"
                  checked={createForm.google_only}
                  onChange={(e) => setCreateForm({ ...createForm, google_only: e.target.checked })}
                  className="h-4 w-4 mt-0.5 rounded border-zinc-300 text-black focus:ring-black cursor-pointer"
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsCreateOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={createUserMutation.isPending}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {createUserMutation.isPending ? 'Provisioning...' : 'Provision User'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* BULK STAFF UPLOAD MODAL */}
      <Dialog
        open={isBulkOpen}
        onOpenChange={(open) => {
          if (!open) {
            setIsBulkOpen(false)
            setBulkFile(null)
            setBulkReport(null)
            setBulkError('')
          }
        }}
      >
        <DialogContent className="sm:max-w-2xl bg-white p-6 max-h-[90vh] overflow-y-auto">
          <DialogHeader className="pb-3 border-b border-zinc-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 text-zinc-900 flex items-center justify-center">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
              <DialogTitle className="font-heading font-bold text-base">
                Bulk Staff Provisioning (CSV)
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Upload a comma-separated CSV with columns <code className="font-mono text-zinc-900">email, full_name, role, department</code> and optional column <code className="font-mono text-zinc-900">google_only</code> (true/false).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4 text-xs">
            {/* Optional Bulk Google-Only Override */}
            <div className="flex items-start justify-between p-3 rounded-lg border border-zinc-200 bg-zinc-50/70 gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="bulkGoogleOnly" className="text-xs font-semibold text-zinc-900 cursor-pointer">
                  Set all uploaded users to Google sign-in only
                </Label>
                <p className="text-[11px] text-zinc-500 leading-snug">
                  Overrides or defaults CSV rows: users sign in via Google and no temporary passwords are generated. Individual rows may also specify <code className="font-mono text-zinc-800">google_only</code> in the CSV.
                </p>
              </div>
              <input
                id="bulkGoogleOnly"
                type="checkbox"
                checked={bulkGoogleOnly}
                onChange={(e) => setBulkGoogleOnly(e.target.checked)}
                className="h-4 w-4 mt-0.5 rounded border-zinc-300 text-black focus:ring-black cursor-pointer"
              />
            </div>

            {/* Template Download Strip */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-50 border border-zinc-200">
              <div className="space-y-0.5">
                <span className="font-semibold text-zinc-900 block">Download Official Template</span>
                <p className="text-[11px] text-zinc-500">
                  Pre-formatted CSV with template staff rows and valid university departments.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={downloadBulkTemplate}
                className="text-xs h-8 gap-1.5 bg-white border-zinc-200 text-zinc-800 hover:text-black"
              >
                <Download className="w-3.5 h-3.5" />
                Download Template
              </Button>
            </div>

            {bulkError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p>{bulkError}</p>
              </div>
            )}

            {/* Ingestion Report if Uploaded */}
            {bulkReport ? (
              <div className="space-y-4">
                {/* Summary Strip */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-lg border border-zinc-200 bg-zinc-50 text-center">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold">Total Rows</span>
                    <span className="font-mono text-lg font-bold text-zinc-900">{bulkReport.total_rows}</span>
                  </div>
                  <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50 text-center">
                    <span className="text-[10px] text-emerald-700 uppercase tracking-wider block font-semibold">Created</span>
                    <span className="font-mono text-lg font-bold text-emerald-800">{bulkReport.created_count}</span>
                  </div>
                  <div className="p-3 rounded-lg border border-rose-200 bg-rose-50 text-center">
                    <span className="text-[10px] text-rose-700 uppercase tracking-wider block font-semibold">Rejected</span>
                    <span className="font-mono text-lg font-bold text-rose-800">{bulkReport.rejected_count}</span>
                  </div>
                </div>

                {/* Warning about One-Time Passwords */}
                {bulkReport.created_count > 0 && (
                  <div className="p-3 rounded-lg border border-amber-200 bg-amber-50/80 text-amber-950 space-y-2">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                      <span className="font-bold text-xs">Download Or Copy One-Time Passwords Now</span>
                    </div>
                    <p className="text-[11px] text-amber-900 leading-snug">
                      Temporary passwords generated below will <strong>never be shown again</strong>. Download the credentials CSV now before closing this window.
                    </p>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => downloadCredentialsCsv(bulkReport.rows)}
                      className="text-xs h-8 gap-1.5 bg-amber-800 hover:bg-amber-900 text-white font-semibold"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download Credentials CSV (This Once)
                    </Button>
                  </div>
                )}

                {/* Row breakdown */}
                <div className="border border-zinc-200 rounded-lg overflow-hidden max-h-60 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-100 text-zinc-700 border-b border-zinc-200 font-semibold">
                      <tr>
                        <th className="px-3 py-2 w-12 text-center">Row</th>
                        <th className="px-3 py-2">Email</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Details / Temp Password</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {bulkReport.rows?.map((r, i) => (
                        <tr key={i} className="hover:bg-zinc-50">
                          <td className="px-3 py-2 text-center font-mono text-zinc-500">{r.row_number}</td>
                          <td className="px-3 py-2 font-mono text-zinc-800">{r.email}</td>
                          <td className="px-3 py-2">
                            {r.status === 'created' ? (
                              <Badge variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-200 text-[10px]">
                                CREATED
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="bg-rose-50 text-rose-800 border-rose-200 text-[10px]">
                                REJECTED
                              </Badge>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            {r.temporary_password ? (
                              <div className="flex items-center gap-1.5">
                                <code className="font-mono text-xs font-semibold text-zinc-900 bg-zinc-100 px-1.5 py-0.5 rounded">
                                  {r.temporary_password}
                                </code>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleCopyPassword(r.temporary_password)}
                                  className="h-6 w-6 p-0"
                                  title="Copy password"
                                >
                                  <Copy className="w-3 h-3" />
                                </Button>
                              </div>
                            ) : (
                              <span className="text-rose-700 text-[11px]">{r.reason || 'Validation error'}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              /* File Upload Zone */
              <div className="space-y-3">
                <div className="border-2 border-dashed border-zinc-200 rounded-xl p-6 text-center hover:border-zinc-400 transition-colors bg-zinc-50/50">
                  <Upload className="w-8 h-8 text-zinc-400 mx-auto mb-2" />
                  <p className="font-semibold text-zinc-900 text-xs">Select or drop staff CSV file</p>
                  <p className="text-[11px] text-zinc-500 mt-0.5">Maximum size: 2 MB (.csv format only)</p>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) {
                        if (file.size > 2 * 1024 * 1024) {
                          setBulkError('File exceeds 2 MB maximum size limit.')
                          return
                        }
                        setBulkFile(file)
                        setBulkError('')
                      }
                    }}
                    className="mt-3 block mx-auto text-xs text-zinc-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-zinc-900 file:text-white hover:file:bg-zinc-800 cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setIsBulkOpen(false)
                setBulkFile(null)
                setBulkReport(null)
                setBulkError('')
              }}
              className="text-xs h-9"
            >
              Close
            </Button>
            {!bulkReport && (
              <Button
                type="button"
                size="sm"
                disabled={!bulkFile || bulkUploadMutation.isPending}
                onClick={() => {
                  if (bulkFile) bulkUploadMutation.mutate({ file: bulkFile, googleOnly: bulkGoogleOnly })
                }}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {bulkUploadMutation.isPending ? 'Processing CSV...' : 'Upload & Provision'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CONFIRM RESET PASSWORD DIALOG */}
      <AlertDialog
        open={Boolean(confirmResetTarget)}
        onOpenChange={(open) => {
          if (!open) setConfirmResetTarget(null)
        }}
      >
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <div className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-amber-600" />
              <AlertDialogTitle className="font-heading font-bold text-base">
                Reset User Password?
              </AlertDialogTitle>
            </div>
            <AlertDialogDescription className="text-xs text-zinc-600 leading-relaxed">
              This will immediately invalidate the current password for{' '}
              <strong className="text-zinc-900">{confirmResetTarget?.email}</strong> and generate a
              random one-time temporary password.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => resetPasswordMutation.mutate(confirmResetTarget.id)}
              disabled={resetPasswordMutation.isPending}
              className="bg-amber-600 hover:bg-amber-700 text-white text-xs h-9 font-semibold"
            >
              {resetPasswordMutation.isPending ? 'Resetting...' : 'Confirm Reset'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* CONFIRM TOGGLE ACTIVE STATUS DIALOG */}
      <AlertDialog
        open={Boolean(confirmToggleTarget)}
        onOpenChange={(open) => {
          if (!open) setConfirmToggleTarget(null)
        }}
      >
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <div className="flex items-center gap-2">
              {confirmToggleTarget?.is_active ? (
                <UserX className="w-5 h-5 text-rose-600" />
              ) : (
                <UserCheck className="w-5 h-5 text-emerald-600" />
              )}
              <AlertDialogTitle className="font-heading font-bold text-base">
                {confirmToggleTarget?.is_active ? 'Deactivate User Account?' : 'Activate User Account?'}
              </AlertDialogTitle>
            </div>
            <AlertDialogDescription className="text-xs text-zinc-600 leading-relaxed">
              {confirmToggleTarget?.is_active
                ? `Deactivating ${confirmToggleTarget?.email} will immediately revoke their ability to sign in and execute clearance actions.`
                : `Activating ${confirmToggleTarget?.email} will restore their clearance access permissions.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                toggleActiveMutation.mutate({
                  userId: confirmToggleTarget.id,
                  isActive: !confirmToggleTarget.is_active,
                })
              }
              disabled={toggleActiveMutation.isPending}
              className={`text-xs h-9 font-semibold ${
                confirmToggleTarget?.is_active
                  ? 'bg-rose-600 hover:bg-rose-700 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}
            >
              {toggleActiveMutation.isPending
                ? 'Updating...'
                : confirmToggleTarget?.is_active
                ? 'Deactivate Account'
                : 'Activate Account'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ONE-TIME TEMPORARY PASSWORD DIALOG */}
      {/* Crucial requirement: Shown ONCE in a dialog with a copy button and a clear warning; */}
      {/* it must never be stored in state beyond the dialog, URLs, console or localStorage, */}
      {/* and must disappear when the dialog closes. */}
      <Dialog
        open={Boolean(tempPasswordModal)}
        onOpenChange={(open) => {
          if (!open) {
            setTempPasswordModal(null)
            setHasCopiedPassword(false)
          }
        }}
      >
        <DialogContent className="sm:max-w-md bg-white p-6">
          <DialogHeader className="pb-3 border-b border-zinc-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center">
                <KeyRound className="w-4 h-4" />
              </div>
              <DialogTitle className="font-heading font-bold text-base">
                {tempPasswordModal?.title || 'Temporary Credentials'}
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Account credentials for <strong className="text-zinc-900">{tempPasswordModal?.email}</strong>.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4 text-xs">
            {tempPasswordModal?.note && (
              <p className="text-[11px] text-zinc-500 font-medium">
                {tempPasswordModal.note}
              </p>
            )}

            <div className="p-3 rounded-lg border border-amber-200 bg-amber-50/70 text-amber-900 flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-semibold block text-[11px] uppercase tracking-wider text-amber-950">
                  One-Time Visibility Warning
                </span>
                <p className="text-xs text-amber-900 leading-snug">
                  This temporary password is displayed <strong>strictly once</strong>. It is never stored in persistent memory, server logs, browser storage, or console. Copy it now and deliver it securely to the user.
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-lg border border-zinc-200 bg-zinc-50 space-y-2">
              <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                Generated Temporary Password
              </span>
              <div className="flex items-center justify-between gap-2 bg-white p-2.5 rounded border border-zinc-200">
                <code className="font-mono text-sm font-bold text-zinc-900 select-all">
                  {tempPasswordModal?.password}
                </code>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleCopyPassword(tempPasswordModal?.password)}
                  className="h-8 text-xs gap-1.5 shrink-0 bg-zinc-50 hover:bg-zinc-100 text-zinc-800"
                >
                  {hasCopiedPassword ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      Copy Password
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter className="pt-3 border-t border-zinc-100">
            <Button
              type="button"
              onClick={() => {
                setTempPasswordModal(null)
                setHasCopiedPassword(false)
              }}
              className="w-full bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              I Have Securely Copied This Password
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

export default AdminUsersPage
