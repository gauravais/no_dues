import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  Upload,
  UserPlus,
  Search,
  RefreshCw,
  FileSpreadsheet,
  Download,
  KeyRound,
  Copy,
  Check,
  ShieldAlert,
  Edit,
  Sliders,
  CheckCircle2,
  XCircle,
  AlertCircle,
  UserX,
  UserCheck,
  Info,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

export function AdminDashboardPage() {
  useDocumentTitle('Institutional Admin')
  const { user: currentAdmin } = useAuth()
  const queryClient = useQueryClient()

  // Tab State
  const [activeTab, setActiveTab] = useState('roster')

  // Roster Tab Query State
  const [searchTerm, setSearchTerm] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [pageSize] = useState(25)
  const [offset, setOffset] = useState(0)

  // Modals State
  const [editRosterTarget, setEditRosterTarget] = useState(null)
  const [assignDeptsTarget, setAssignDeptsTarget] = useState(null)
  const [selectedDeptIds, setSelectedDeptIds] = useState([])

  // Temporary Password Dialog State
  const [tempPasswordModal, setTempPasswordModal] = useState(null) // { title, email, password }
  const [hasCopiedPassword, setHasCopiedPassword] = useState(false)

  // User Actions State
  const [confirmResetUser, setConfirmResetUser] = useState(null) // { id, email }
  const [confirmToggleActive, setConfirmToggleActive] = useState(null) // { id, active }

  // Users Directory Query & Filter State (built on GET /admin/users)
  const [userSearchTerm, setUserSearchTerm] = useState('')
  const [userSearchQuery, setUserSearchQuery] = useState('')
  const [userRoleFilter, setUserRoleFilter] = useState('ALL')
  const [userPageSize] = useState(25)
  const [userOffset, setUserOffset] = useState(0)

  // CSV Ingestion State
  const [csvFile, setCsvFile] = useState(null)
  const [csvDragActive, setCsvDragActive] = useState(false)
  const [uploadReport, setUploadReport] = useState(null)

  // New Staff Form State
  const [newStaffForm, setNewStaffForm] = useState({
    full_name: '',
    email: '',
    role: 'dept_officer',
    department_id: '',
  })

  // Edit Roster Form State
  const [editRosterForm, setEditRosterForm] = useState({
    is_hosteller: false,
    security_deposit_amount: '',
    address: '',
    mobile: '',
  })

  // -------------------------------------------------------------
  // Queries
  // -------------------------------------------------------------

  // Fetch active departments from GET /departments
  const {
    data: departments = [],
    isLoading: departmentsLoading,
  } = useQuery({
    queryKey: ['departments'],
    queryFn: adminApi.getDepartments,
    staleTime: 5 * 60 * 1000,
  })

  const academicDepartments = useMemo(
    () => departments.filter((d) => d.kind === 'academic' || d.applicability === 'OWN_ACADEMIC'),
    [departments]
  )
  const assignableDepartments = useMemo(
    () => departments.filter((d) => d.applicability === 'ASSIGNED_ONLY'),
    [departments]
  )

  // Fetch student roster
  const {
    data: rosterData,
    isLoading: rosterLoading,
    isFetching: rosterFetching,
    isError: rosterError,
    error: rosterErrorObj,
    refetch: refetchRoster,
  } = useQuery({
    queryKey: ['admin-roster', { search: searchQuery, limit: pageSize, offset }],
    queryFn: () => adminApi.getRoster({ search: searchQuery, limit: pageSize, offset }),
    enabled: activeTab === 'roster',
  })

  // Fetch institutional user directory from GET /admin/users
  const {
    data: usersList = [],
    isLoading: usersLoading,
    isFetching: usersFetching,
    isError: usersError,
    error: usersErrorObj,
    refetch: refetchUsers,
  } = useQuery({
    queryKey: [
      'admin-users',
      { search: userSearchQuery, role: userRoleFilter, limit: userPageSize, offset: userOffset },
    ],
    queryFn: () =>
      adminApi.getUsers({
        search: userSearchQuery,
        role: userRoleFilter,
        limit: userPageSize,
        offset: userOffset,
      }),
    enabled: activeTab === 'users',
  })

  // -------------------------------------------------------------
  // Mutations
  // -------------------------------------------------------------
  const uploadCsvMutation = useMutation({
    mutationFn: (file) => adminApi.uploadRosterCsv(file),
    onSuccess: (data) => {
      setUploadReport(data)
      setCsvFile(null)
      toast.success(
        `CSV processed: ${data.created_count} created, ${data.updated_count} updated, ${data.rejected_count} rejected.`
      )
      queryClient.invalidateQueries({ queryKey: ['admin-roster'] })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to upload CSV file.')
    },
  })

  const updateRosterMutation = useMutation({
    mutationFn: ({ id, data }) => adminApi.updateRosterEntry(id, data),
    onSuccess: () => {
      toast.success('Student roster record updated successfully.')
      setEditRosterTarget(null)
      queryClient.invalidateQueries({ queryKey: ['admin-roster'] })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to update roster entry.')
    },
  })

  const updateDeptsMutation = useMutation({
    mutationFn: ({ id, departmentIds }) => adminApi.updateAssignedDepartments(id, departmentIds),
    onSuccess: () => {
      toast.success('Assigned laboratories and workshops updated.')
      setAssignDeptsTarget(null)
      queryClient.invalidateQueries({ queryKey: ['admin-roster'] })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to update assigned departments.')
    },
  })

  const createStaffMutation = useMutation({
    mutationFn: (payload) => adminApi.createStaffUser(payload),
    onSuccess: (data) => {
      // Invalidate users directory query
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      // Reset form
      setNewStaffForm({
        full_name: '',
        email: '',
        role: 'dept_officer',
        department_id: '',
      })
      // Open one-time temporary password dialog
      setTempPasswordModal({
        title: 'New Staff Account Provisioned',
        email: data.email,
        password: data.temporary_password,
        role: data.role,
        name: data.full_name,
      })
      setHasCopiedPassword(false)
      toast.success(`Account for ${data.email} provisioned successfully.`)
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to provision staff account.')
    },
  })

  const resetPasswordMutation = useMutation({
    mutationFn: (userId) => adminApi.resetPassword(userId),
    onSuccess: (data) => {
      setConfirmResetUser(null)
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setTempPasswordModal({
        title: 'Temporary Password Reset Complete',
        email: data.email,
        password: data.temporary_password,
      })
      setHasCopiedPassword(false)
      toast.success(`Password reset for ${data.email}.`)
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to reset password.')
    },
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ userId, isActive }) => adminApi.setUserActive(userId, isActive),
    onSuccess: (data) => {
      setConfirmToggleActive(null)
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success(
        `User ${data.email} is now ${data.is_active ? 'Active' : 'Deactivated'}.`
      )
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to update user active status.')
    },
  })

  // -------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------
  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setSearchQuery(searchTerm)
    setOffset(0)
  }

  const handleUserSearchSubmit = (e) => {
    e.preventDefault()
    setUserSearchQuery(userSearchTerm)
    setUserOffset(0)
  }

  const handleOpenEditRoster = (student) => {
    setEditRosterTarget(student)
    setEditRosterForm({
      is_hosteller: !!student.is_hosteller,
      security_deposit_amount: student.security_deposit_amount ?? '',
      address: student.address || '',
      mobile: student.mobile || '',
    })
  }

  const handleSaveEditRoster = (e) => {
    e.preventDefault()
    if (!editRosterTarget) return
    const payload = {
      is_hosteller: editRosterForm.is_hosteller,
      security_deposit_amount: parseFloat(editRosterForm.security_deposit_amount) || 0,
      address: editRosterForm.address.trim(),
      mobile: editRosterForm.mobile.trim(),
    }
    updateRosterMutation.mutate({ id: editRosterTarget.id, data: payload })
  }

  const handleOpenAssignDepts = (student) => {
    setAssignDeptsTarget(student)
    setSelectedDeptIds(student.assigned_department_ids || [])
  }

  const toggleDeptId = (id) => {
    setSelectedDeptIds((prev) =>
      prev.includes(id) ? prev.filter((dId) => dId !== id) : [...prev, id]
    )
  }

  const handleSaveAssignedDepts = () => {
    if (!assignDeptsTarget) return
    updateDeptsMutation.mutate({
      id: assignDeptsTarget.id,
      departmentIds: selectedDeptIds,
    })
  }

  const handleStaffFormSubmit = (e) => {
    e.preventDefault()
    const payload = {
      full_name: newStaffForm.full_name.trim(),
      email: newStaffForm.email.trim(),
      role: newStaffForm.role,
    }
    if (newStaffForm.role === 'dept_officer' || newStaffForm.role === 'hod') {
      if (!newStaffForm.department_id) {
        toast.error('Department selection is required for Department Officers and HoDs.')
        return
      }
      payload.department_id = Number(newStaffForm.department_id)
    }
    createStaffMutation.mutate(payload)
  }

  const handleCopyPassword = () => {
    if (!tempPasswordModal?.password) return
    navigator.clipboard.writeText(tempPasswordModal.password)
    setHasCopiedPassword(true)
    toast.success('Password copied to clipboard.')
  }

  const handleDownloadSampleCsv = () => {
    const csvContent =
      'registration_number,name,email,mobile,address,programme,is_hosteller,security_deposit_amount\n' +
      'SAMPLE001,Sample Student A,student.sample1@svsu.ac.in,9876543210,"H.No 12, Sector 14, Gurugram",B.Tech Robotics and Automation,true,5000\n' +
      'SAMPLE002,Sample Student B,student.sample2@svsu.ac.in,9876543211,"Flat 402, Green Valley, Palwal",B.Tech Industry 4.0,false,3000\n' +
      'SAMPLE003,Sample Student C,student.sample3@svsu.ac.in,9876543212,"Vill. Dudhola, Palwal, Haryana",B.Voc Automotive Studies,true,5000\n'

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'svsu_roster_sample.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // -------------------------------------------------------------
  // Table Columns Definition
  // -------------------------------------------------------------
  const rosterColumns = [
    {
      accessorKey: 'registration_number',
      header: 'Reg. Number',
      cell: ({ row }) => (
        <span className="font-mono font-bold text-xs text-zinc-900">
          {row.getValue('registration_number')}
        </span>
      ),
    },
    {
      accessorKey: 'name',
      header: 'Student Name',
      cell: ({ row }) => (
        <div>
          <div className="font-semibold text-xs text-zinc-900">{row.getValue('name')}</div>
          <div className="font-mono text-[11px] text-muted-foreground">{row.original.email}</div>
        </div>
      ),
    },
    {
      accessorKey: 'programme_name',
      header: 'Programme',
      cell: ({ row }) => (
        <span className="text-xs text-zinc-700 max-w-[200px] truncate block">
          {row.getValue('programme_name') || 'N/A'}
        </span>
      ),
    },
    {
      accessorKey: 'is_hosteller',
      header: 'Resident Status',
      cell: ({ row }) => {
        const isHosteller = row.getValue('is_hosteller')
        return (
          <Badge
            variant="outline"
            className={
              isHosteller
                ? 'bg-amber-50 text-amber-800 border-amber-200 text-[10px]'
                : 'bg-zinc-50 text-zinc-600 border-zinc-200 text-[10px]'
            }
          >
            {isHosteller ? 'Hosteller' : 'Day Scholar'}
          </Badge>
        )
      },
    },
    {
      accessorKey: 'security_deposit_amount',
      header: 'Security Deposit',
      cell: ({ row }) => {
        const amount = Number(row.getValue('security_deposit_amount') || 0)
        return (
          <span className="font-mono text-xs font-semibold text-zinc-900">
            ₹{amount.toLocaleString('en-IN')}
          </span>
        )
      },
    },
    {
      accessorKey: 'assigned_department_ids',
      header: 'Assigned Labs',
      cell: ({ row }) => {
        const ids = row.getValue('assigned_department_ids') || []
        return (
          <span className="text-xs text-muted-foreground">
            {ids.length === 0 ? 'None' : `${ids.length} dept${ids.length > 1 ? 's' : ''}`}
          </span>
        )
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const student = row.original
        return (
          <div className="flex items-center gap-1.5 justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleOpenEditRoster(student)}
              className="h-7 px-2 text-[11px] gap-1 text-zinc-700 hover:text-black"
            >
              <Edit className="w-3 h-3" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleOpenAssignDepts(student)}
              className="h-7 px-2 text-[11px] gap-1 text-zinc-700 hover:text-black"
            >
              <Sliders className="w-3 h-3" />
              Depts
            </Button>
          </div>
        )
      },
    },
  ]

  const totalRoster = rosterData?.total || 0
  const rosterItems = rosterData?.items || []

  // Department options based on selected role in staff form (dynamic from GET /departments)
  const availableDepartments =
    newStaffForm.role === 'hod' ? academicDepartments : departments

  const isRoleDeptDisabled = newStaffForm.role === 'registrar_accounts'

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-zinc-900 text-white tracking-wide uppercase">
                System Administration
              </span>
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground mt-2">
              Institutional Administration
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1 max-w-2xl">
              Manage the master student roster, ingest batch CSV records, assign departmental obligations, and provision staff credentials.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetchRoster()
                toast.info('Refreshed roster data.')
              }}
              disabled={rosterFetching}
              className="h-9 gap-1.5 text-xs text-zinc-700"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${rosterFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-zinc-100 p-1 border border-border">
            <TabsTrigger value="roster" className="gap-2 text-xs font-semibold">
              <Users className="w-3.5 h-3.5" />
              Student Roster ({totalRoster})
            </TabsTrigger>
            <TabsTrigger value="upload" className="gap-2 text-xs font-semibold">
              <Upload className="w-3.5 h-3.5" />
              CSV Bulk Ingestion
            </TabsTrigger>
            <TabsTrigger value="staff" className="gap-2 text-xs font-semibold">
              <UserPlus className="w-3.5 h-3.5" />
              Staff & Credentials
            </TabsTrigger>
          </TabsList>

          {/* ========================================================= */}
          {/* TAB 1: STUDENT ROSTER                                     */}
          {/* ========================================================= */}
          <TabsContent value="roster" className="space-y-4">
            {rosterError && (
              <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-destructive">
                <div className="flex items-center gap-2 text-sm">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Failed to load student roster: {rosterErrorObj?.response?.data?.detail || rosterErrorObj?.message || 'Server error'}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchRoster()}
                  className="border-destructive/30 hover:bg-destructive/10 text-xs shrink-0"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                  Retry
                </Button>
              </div>
            )}
            <Card className="border-border bg-white shadow-card">
              <CardHeader className="p-4 sm:p-6 pb-4 border-b border-border/60">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <CardTitle className="font-heading text-lg font-bold">
                      Master Student Roster
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Official directory of graduating students eligible for No-Dues Clearance.
                    </CardDescription>
                  </div>

                  {/* Search Form */}
                  <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 w-full sm:w-auto">
                    <Input
                      placeholder="Search Reg No, Name, or Email..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="text-xs h-9 w-full sm:w-72"
                    />
                    <Button
                      type="submit"
                      size="sm"
                      className="h-9 px-3 bg-primary text-primary-foreground hover:bg-zinc-800 text-xs shrink-0 gap-1.5 font-semibold"
                    >
                      <Search className="w-3.5 h-3.5" />
                      Search
                    </Button>
                    {searchQuery && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSearchTerm('')
                          setSearchQuery('')
                          setOffset(0)
                        }}
                        className="h-9 px-2 text-xs text-muted-foreground"
                      >
                        Clear
                      </Button>
                    )}
                  </form>
                </div>
              </CardHeader>

              <CardContent className="p-0">
                {rosterLoading ? (
                  <div className="p-12 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin text-zinc-400" />
                    <span>Loading student records from database...</span>
                  </div>
                ) : rosterItems.length === 0 ? (
                  <div className="p-8">
                    <EmptyState
                      icon={Users}
                      title="No student records found"
                      description={
                        searchQuery
                          ? `No student records match "${searchQuery}". Try a different keyword.`
                          : 'The roster is currently empty. Upload a CSV batch file to populate students.'
                      }
                    />
                  </div>
                ) : (
                  <>
                    <DataTable
                      columns={rosterColumns}
                      data={rosterItems}
                      pageSize={pageSize}
                    />

                    {/* Server-side Pagination Bar */}
                    <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground bg-zinc-50/50">
                      <div>
                        Showing <span className="font-semibold text-zinc-900">{offset + 1}</span> to{' '}
                        <span className="font-semibold text-zinc-900">
                          {Math.min(offset + pageSize, totalRoster)}
                        </span>{' '}
                        of <span className="font-semibold text-zinc-900">{totalRoster}</span> students
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={offset === 0 || rosterFetching}
                          onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
                          className="h-8 text-xs px-2.5"
                        >
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={offset + pageSize >= totalRoster || rosterFetching}
                          onClick={() => setOffset((prev) => prev + pageSize)}
                          className="h-8 text-xs px-2.5"
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ========================================================= */}
          {/* TAB 2: CSV BULK INGESTION                                 */}
          {/* ========================================================= */}
          <TabsContent value="upload" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Upload Dropzone Card */}
              <div className="lg:col-span-2 space-y-4">
                <Card className="border-border bg-white shadow-card">
                  <CardHeader className="p-6 pb-4">
                    <CardTitle className="font-heading text-lg font-bold">
                      Upload Roster CSV Batch
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Ingest or update student records in bulk. Records are matched and upserted by registration number.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-6 pt-0 space-y-4">
                    {/* Drag and Drop Box */}
                    <div
                      onDragOver={(e) => {
                        e.preventDefault()
                        setCsvDragActive(true)
                      }}
                      onDragLeave={() => setCsvDragActive(false)}
                      onDrop={(e) => {
                        e.preventDefault()
                        setCsvDragActive(false)
                        if (e.dataTransfer.files?.[0]) {
                          setCsvFile(e.dataTransfer.files[0])
                        }
                      }}
                      className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer flex flex-col items-center justify-center gap-3 ${
                        csvDragActive
                          ? 'border-black bg-zinc-50'
                          : 'border-zinc-200 hover:border-zinc-400 bg-white'
                      }`}
                      onClick={() => document.getElementById('csvFileInput')?.click()}
                    >
                      <input
                        id="csvFileInput"
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files?.[0]) {
                            setCsvFile(e.target.files[0])
                          }
                        }}
                      />
                      <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-800">
                        <FileSpreadsheet className="w-6 h-6" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-zinc-900">
                          {csvFile ? csvFile.name : 'Choose a CSV file or drag & drop here'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {csvFile
                            ? `${(csvFile.size / 1024).toFixed(1)} KB — ready to upload`
                            : 'Accepts standard UTF-8 encoded .csv files up to 10MB'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleDownloadSampleCsv}
                        className="text-xs gap-1.5 h-9 text-zinc-700"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download Sample CSV Template
                      </Button>

                      <Button
                        size="sm"
                        disabled={!csvFile || uploadCsvMutation.isPending}
                        onClick={() => {
                          if (csvFile) uploadCsvMutation.mutate(csvFile)
                        }}
                        className="h-9 px-4 bg-primary text-primary-foreground hover:bg-zinc-800 text-xs font-semibold gap-1.5"
                      >
                        {uploadCsvMutation.isPending ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            Processing Batch...
                          </>
                        ) : (
                          <>
                            <Upload className="w-3.5 h-3.5" />
                            Ingest Records
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Upload Results Report */}
                {uploadReport && (
                  <Card className="border-border bg-white shadow-card">
                    <CardHeader className="p-6 pb-4 border-b border-border/60">
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="font-heading text-base font-bold">
                            Ingestion Execution Report
                          </CardTitle>
                          <CardDescription className="text-xs">
                            Row-level summary of processed CSV entries.
                          </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="bg-zinc-50 text-zinc-800 text-xs">
                            Total: {uploadReport.total_rows}
                          </Badge>
                          <Badge variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-200 text-xs">
                            Created: {uploadReport.created_count}
                          </Badge>
                          <Badge variant="outline" className="bg-sky-50 text-sky-800 border-sky-200 text-xs">
                            Updated: {uploadReport.updated_count}
                          </Badge>
                          {uploadReport.rejected_count > 0 && (
                            <Badge variant="outline" className="bg-rose-50 text-rose-800 border-rose-200 text-xs">
                              Rejected: {uploadReport.rejected_count}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="p-0">
                      <div className="max-h-96 overflow-y-auto">
                        <table className="w-full text-xs text-left">
                          <thead className="bg-zinc-50 border-b border-border text-zinc-600 font-medium">
                            <tr>
                              <th className="p-3 w-16 text-center">Row</th>
                              <th className="p-3">Registration No</th>
                              <th className="p-3">Status</th>
                              <th className="p-3">Diagnostic Message</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border">
                            {uploadReport.rows.map((r, i) => (
                              <tr key={i} className="hover:bg-zinc-50/60 font-sans">
                                <td className="p-3 text-center font-mono text-muted-foreground">
                                  {r.row_number}
                                </td>
                                <td className="p-3 font-mono font-semibold text-zinc-900">
                                  {r.registration_number || 'N/A'}
                                </td>
                                <td className="p-3">
                                  {r.status === 'created' && (
                                    <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 text-[10px] gap-1 font-semibold">
                                      <CheckCircle2 className="w-3 h-3" />
                                      Created
                                    </Badge>
                                  )}
                                  {r.status === 'updated' && (
                                    <Badge className="bg-sky-100 text-sky-800 border-sky-200 text-[10px] gap-1 font-semibold">
                                      <RefreshCw className="w-3 h-3" />
                                      Updated
                                    </Badge>
                                  )}
                                  {r.status === 'rejected' && (
                                    <Badge className="bg-rose-100 text-rose-800 border-rose-200 text-[10px] gap-1 font-semibold">
                                      <XCircle className="w-3 h-3" />
                                      Rejected
                                    </Badge>
                                  )}
                                </td>
                                <td className="p-3 text-zinc-600 text-[11px]">
                                  {r.reason || 'Successfully processed and validated.'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* CSV Specifications Hint Card */}
              <div className="space-y-4">
                <Card className="border-border bg-white shadow-card">
                  <CardHeader className="p-5 pb-3">
                    <CardTitle className="font-heading text-sm font-bold flex items-center gap-2">
                      <Info className="w-4 h-4 text-zinc-500" />
                      Required CSV Schema
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-5 pt-0 space-y-3 text-xs text-zinc-700">
                    <p className="text-muted-foreground leading-relaxed">
                      The file header must contain exactly the following 8 column names (case-insensitive):
                    </p>
                    <div className="p-2.5 bg-zinc-50 rounded-lg border border-border font-mono text-[11px] text-zinc-800 break-all leading-relaxed">
                      registration_number, name, email, mobile, address, programme, is_hosteller, security_deposit_amount
                    </div>

                    <div className="space-y-2 pt-2 border-t border-border">
                      <div className="text-[11px]">
                        <span className="font-bold text-zinc-900">programme:</span> Must match an accredited SVSU programme name exactly (e.g. &apos;B.Tech Robotics and Automation&apos;, &apos;B.Voc Automotive Studies&apos;).
                      </div>
                      <div className="text-[11px]">
                        <span className="font-bold text-zinc-900">is_hosteller:</span> Boolean true/false, 1/0, or yes/no.
                      </div>
                      <div className="text-[11px]">
                        <span className="font-bold text-zinc-900">security_deposit_amount:</span> Non-negative integer or decimal amount in INR.
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* ========================================================= */}
          {/* TAB 3: STAFF PROVISIONING & CREDENTIALS                   */}
          {/* ========================================================= */}
          <TabsContent value="staff" className="space-y-6">
            {usersError && (
              <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-destructive">
                <div className="flex items-center gap-2 text-sm">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Failed to load institutional user directory: {usersErrorObj?.response?.data?.detail || usersErrorObj?.message || 'Server error'}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchUsers()}
                  className="border-destructive/30 hover:bg-destructive/10 text-xs shrink-0"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                  Retry
                </Button>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Provision Form */}
              <Card className="border-border bg-white shadow-card">
                <CardHeader className="p-6 pb-4 border-b border-border/60">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900">
                      <UserPlus className="w-4 h-4" />
                    </div>
                    <div>
                      <CardTitle className="font-heading text-base font-bold">
                        Provision Staff Account
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Create an institutional staff login for officers, department chairpersons (HoD), or accounts officers.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="p-6 pt-4">
                  <form onSubmit={handleStaffFormSubmit} className="space-y-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="staffFullName" className="text-xs font-semibold">
                        Full Name <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        id="staffFullName"
                        placeholder="e.g. Dr. Meenakshi Sharma"
                        value={newStaffForm.full_name}
                        onChange={(e) =>
                          setNewStaffForm({ ...newStaffForm, full_name: e.target.value })
                        }
                        className="text-xs h-9"
                        required
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="staffEmail" className="text-xs font-semibold">
                        Institutional Email <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        id="staffEmail"
                        type="email"
                        placeholder="e.g. officer.lab1@svsu.ac.in"
                        value={newStaffForm.email}
                        onChange={(e) =>
                          setNewStaffForm({ ...newStaffForm, email: e.target.value })
                        }
                        className="text-xs h-9"
                        required
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="staffRole" className="text-xs font-semibold">
                          Staff Role <span className="text-red-500">*</span>
                        </Label>
                        <select
                          id="staffRole"
                          value={newStaffForm.role}
                          onChange={(e) => {
                            const newRole = e.target.value
                            setNewStaffForm({
                              ...newStaffForm,
                              role: newRole,
                              department_id: newRole === 'registrar_accounts' ? '' : newStaffForm.department_id,
                            })
                          }}
                          className="w-full text-xs h-9 rounded-md border border-input bg-background px-3 py-1 font-sans focus:outline-none focus:ring-1 focus:ring-ring"
                        >
                          <option value="dept_officer">Department Officer</option>
                          <option value="hod">Chairperson / HoD</option>
                          <option value="registrar_accounts">Registrar / Accounts Officer</option>
                        </select>
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="staffDepartment" className="text-xs font-semibold">
                          Assigned Department {isRoleDeptDisabled ? '(N/A)' : <span className="text-red-500">*</span>}
                        </Label>
                        <select
                          id="staffDepartment"
                          disabled={isRoleDeptDisabled}
                          value={newStaffForm.department_id}
                          onChange={(e) =>
                            setNewStaffForm({ ...newStaffForm, department_id: e.target.value })
                          }
                          className="w-full text-xs h-9 rounded-md border border-input bg-background px-3 py-1 font-sans focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
                        >
                          <option value="">
                            {isRoleDeptDisabled ? 'No department required' : 'Select department...'}
                          </option>
                          {availableDepartments.map((dept) => (
                            <option key={dept.id} value={dept.id}>
                              {dept.name} ({dept.kind})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {newStaffForm.role === 'hod' && (
                      <p className="text-[11px] text-zinc-500 italic">
                        Note: Chairpersons (HoD) can only be assigned to Academic Departments.
                      </p>
                    )}

                    <div className="pt-2 flex justify-end">
                      <Button
                        type="submit"
                        disabled={createStaffMutation.isPending}
                        className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs font-semibold h-9 px-4 gap-1.5"
                      >
                        {createStaffMutation.isPending ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            Provisioning...
                          </>
                        ) : (
                          <>
                            <UserPlus className="w-3.5 h-3.5" />
                            Create Staff Account
                          </>
                        )}
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>

              {/* Institutional Users Directory Card (Live from GET /admin/users) */}
              <div className="space-y-4">
                <Card className="border-border bg-white shadow-card">
                  <CardHeader className="p-6 pb-4 border-b border-border/60">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900">
                          <Users className="w-4 h-4" />
                        </div>
                        <div>
                          <CardTitle className="font-heading text-base font-bold">
                            University Users Directory
                          </CardTitle>
                          <CardDescription className="text-xs">
                            Manage user accounts, roles, credentials, and access permissions.
                          </CardDescription>
                        </div>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetchUsers()}
                        disabled={usersFetching}
                        className="text-xs h-8 gap-1.5 border-border bg-white"
                      >
                        <RefreshCw className={`w-3 h-3 ${usersFetching ? 'animate-spin' : ''}`} />
                        Refresh
                      </Button>
                    </div>

                    {/* Filter and Search Bar */}
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 pt-4">
                      <form onSubmit={handleUserSearchSubmit} className="relative flex-1">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                        <Input
                          type="text"
                          placeholder="Search users by name or email..."
                          value={userSearchTerm}
                          onChange={(e) => setUserSearchTerm(e.target.value)}
                          className="pl-8 text-xs h-8 bg-zinc-50 border-border"
                        />
                      </form>

                      <div className="w-full sm:w-48">
                        <select
                          value={userRoleFilter}
                          onChange={(e) => {
                            setUserRoleFilter(e.target.value)
                            setUserOffset(0)
                          }}
                          className="w-full text-xs h-8 rounded-md border border-input bg-zinc-50 px-2.5 py-1 font-sans focus:outline-none focus:ring-1 focus:ring-ring"
                        >
                          <option value="ALL">All Roles</option>
                          <option value="student">Student</option>
                          <option value="dept_officer">Department Officer</option>
                          <option value="hod">Chairperson (HoD)</option>
                          <option value="registrar_accounts">Registrar / Accounts</option>
                          <option value="admin">Administrator</option>
                        </select>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="p-0">
                    {usersLoading ? (
                      <div className="p-8 text-center text-xs text-muted-foreground">
                        <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-zinc-400" />
                        Loading user directory...
                      </div>
                    ) : usersList.length === 0 ? (
                      <div className="p-8 text-center text-xs text-muted-foreground">
                        No users found matching query criteria.
                      </div>
                    ) : (
                      <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
                        {usersList.map((usr) => {
                          const isSelf = usr.id === currentAdmin?.id
                          return (
                            <div
                              key={usr.id}
                              className="p-3.5 sm:px-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs hover:bg-zinc-50/60 transition-colors"
                            >
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-semibold text-zinc-950 text-sm">
                                    {usr.full_name || usr.email}
                                  </span>
                                  <span className="font-mono text-[10px] text-zinc-400">
                                    #{usr.id}
                                  </span>
                                  <Badge
                                    variant="outline"
                                    className={`text-[10px] font-mono py-0 ${
                                      usr.is_active
                                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                        : 'bg-rose-50 text-rose-800 border-rose-200'
                                    }`}
                                  >
                                    {usr.is_active ? 'Active' : 'Deactivated'}
                                  </Badge>
                                </div>
                                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                                  <span className="font-mono">{usr.email}</span>
                                  <span>•</span>
                                  <Badge variant="outline" className="text-[10px] bg-zinc-50 font-mono py-0">
                                    {usr.role}
                                  </Badge>
                                  {(usr.department_name || usr.department) && (
                                    <>
                                      <span>•</span>
                                      <span className="text-zinc-600 font-medium">
                                        {usr.department_name || usr.department}
                                      </span>
                                    </>
                                  )}
                                </div>
                              </div>

                              <div className="flex items-center gap-1.5 self-end sm:self-center shrink-0">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => {
                                    setConfirmResetUser({ id: usr.id, email: usr.email })
                                  }}
                                  className="h-7 px-2.5 text-[11px] gap-1 text-zinc-700 hover:text-black border-border bg-white"
                                >
                                  <KeyRound className="w-3 h-3 text-amber-600" />
                                  Reset
                                </Button>

                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={isSelf}
                                  onClick={() => {
                                    if (isSelf) {
                                      toast.error('You cannot deactivate your own account.')
                                      return
                                    }
                                    setConfirmToggleActive({ id: usr.id, active: !usr.is_active })
                                  }}
                                  className={`h-7 px-2.5 text-[11px] gap-1 border-border bg-white ${
                                    usr.is_active
                                      ? 'text-rose-700 hover:text-rose-800 hover:bg-rose-50'
                                      : 'text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50'
                                  }`}
                                  title={isSelf ? 'Cannot deactivate your own account' : undefined}
                                >
                                  {usr.is_active ? (
                                    <>
                                      <UserX className="w-3 h-3" />
                                      Deactivate
                                    </>
                                  ) : (
                                    <>
                                      <UserCheck className="w-3 h-3" />
                                      Activate
                                    </>
                                  )}
                                </Button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}

                    {/* Pagination Bar */}
                    <div className="p-3 border-t border-border bg-zinc-50/60 flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        Showing <strong className="text-zinc-800">{userOffset + 1}</strong> -{' '}
                        <strong className="text-zinc-800">{userOffset + usersList.length}</strong> users
                      </span>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={userOffset === 0 || usersLoading}
                          onClick={() => setUserOffset((prev) => Math.max(0, prev - userPageSize))}
                          className="h-7 px-2 text-[11px] gap-1 border-border bg-white"
                        >
                          <ChevronLeft className="w-3 h-3" />
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={usersList.length < userPageSize || usersLoading}
                          onClick={() => setUserOffset((prev) => prev + userPageSize)}
                          className="h-7 px-2 text-[11px] gap-1 border-border bg-white"
                        >
                          Next
                          <ChevronRight className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* ========================================================= */}
      {/* MODAL: EDIT ROSTER RECORD                                 */}
      {/* ========================================================= */}
      <Dialog
        open={!!editRosterTarget}
        onOpenChange={(open) => !open && setEditRosterTarget(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading text-base font-bold">
              Edit Roster Record: {editRosterTarget?.registration_number}
            </DialogTitle>
            <DialogDescription className="text-xs">
              Update resident hosteller status, security deposit obligation, and contact details.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSaveEditRoster} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="editStudentMobile" className="text-xs font-semibold">Mobile Number</Label>
              <Input
                id="editStudentMobile"
                value={editRosterForm.mobile}
                onChange={(e) => setEditRosterForm({ ...editRosterForm, mobile: e.target.value })}
                className="text-xs h-9 font-mono"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="editStudentAddress" className="text-xs font-semibold">Address</Label>
              <Input
                id="editStudentAddress"
                value={editRosterForm.address}
                onChange={(e) => setEditRosterForm({ ...editRosterForm, address: e.target.value })}
                className="text-xs h-9"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="editSecurityDeposit" className="text-xs font-semibold">Security Deposit Amount (₹ INR)</Label>
              <Input
                id="editSecurityDeposit"
                type="number"
                min="0"
                step="100"
                value={editRosterForm.security_deposit_amount}
                onChange={(e) =>
                  setEditRosterForm({
                    ...editRosterForm,
                    security_deposit_amount: e.target.value,
                  })
                }
                className="text-xs h-9 font-mono"
                required
              />
            </div>

            <div className="flex items-center gap-2 pt-1">
              <input
                id="hostellerCheckbox"
                type="checkbox"
                checked={editRosterForm.is_hosteller}
                onChange={(e) =>
                  setEditRosterForm({ ...editRosterForm, is_hosteller: e.target.checked })
                }
                className="h-4 w-4 rounded border-gray-300 text-black focus:ring-black"
              />
              <Label htmlFor="hostellerCheckbox" className="text-xs font-medium cursor-pointer">
                Student is a University Hosteller (Requires Hostel clearance branch)
              </Label>
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEditRosterTarget(null)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={updateRosterMutation.isPending}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs font-semibold"
              >
                {updateRosterMutation.isPending ? 'Saving...' : 'Save Changes'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ========================================================= */}
      {/* MODAL: ASSIGN SERVICE DEPARTMENTS / LABS                  */}
      {/* ========================================================= */}
      <Dialog
        open={!!assignDeptsTarget}
        onOpenChange={(open) => !open && setAssignDeptsTarget(null)}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-heading text-base font-bold">
              Assigned Laboratories & Workshops
            </DialogTitle>
            <DialogDescription className="text-xs">
              Assign specialized labs and workshops for student {assignDeptsTarget?.registration_number}. General service departments (Library, Sports, Hostel) are assigned automatically.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto p-1 border rounded-lg">
              {departmentsLoading ? (
                <div className="col-span-2 p-6 text-center text-xs text-muted-foreground">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-zinc-400" />
                  Loading departments...
                </div>
              ) : assignableDepartments.length === 0 ? (
                <div className="col-span-2 p-6 text-center text-xs text-muted-foreground">
                  No assignable laboratories or workshops configured.
                </div>
              ) : (
                assignableDepartments.map((dept) => {
                  const isChecked = selectedDeptIds.includes(dept.id)
                  return (
                    <label
                      key={dept.id}
                      className={`flex items-center gap-2 p-2 rounded text-xs cursor-pointer border transition-colors ${
                        isChecked
                          ? 'bg-zinc-100 border-zinc-400 font-semibold text-black'
                          : 'bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleDeptId(dept.id)}
                        className="rounded border-zinc-300 text-black focus:ring-black"
                      />
                      <span>{dept.name}</span>
                    </label>
                  )
                })
              )}
            </div>

            <p className="text-[11px] text-muted-foreground">
              Selected: {selectedDeptIds.length} assignable department{selectedDeptIds.length !== 1 ? 's' : ''}.
            </p>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAssignDeptsTarget(null)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={updateDeptsMutation.isPending}
              onClick={handleSaveAssignedDepts}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs font-semibold"
            >
              {updateDeptsMutation.isPending ? 'Updating...' : 'Save Assignments'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ========================================================= */}
      {/* MODAL: ONE-TIME TEMPORARY PASSWORD DIALOG                 */}
      {/* ========================================================= */}
      <Dialog
        open={!!tempPasswordModal}
        onOpenChange={(open) => {
          if (!open) {
            setTempPasswordModal(null)
            setHasCopiedPassword(false)
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-2 text-amber-600 mb-1">
              <ShieldAlert className="w-5 h-5 shrink-0" />
              <span className="text-xs font-bold uppercase tracking-wider">
                Critical Security Notice
              </span>
            </div>
            <DialogTitle className="font-heading text-lg font-bold">
              {tempPasswordModal?.title || 'One-Time Temporary Password'}
            </DialogTitle>
            <DialogDescription className="text-xs leading-relaxed text-zinc-600">
              This credential is generated once by the server and will <strong className="text-zinc-900">never be displayed again</strong>. It is not saved in your browser or retrievable. Copy it immediately.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-3">
            <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-3 space-y-1">
              <span className="text-[10px] uppercase font-bold text-muted-foreground block">
                Account Email
              </span>
              <p className="text-xs font-mono font-semibold text-zinc-900">
                {tempPasswordModal?.email}
              </p>
            </div>

            <div className="space-y-1.5">
              <span className="text-xs font-semibold text-zinc-900 block">
                Temporary Password
              </span>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-zinc-900 text-emerald-400 font-mono text-sm px-3 py-2 rounded-md tracking-wider font-bold select-all">
                  {tempPasswordModal?.password}
                </div>
                <Button
                  size="sm"
                  onClick={handleCopyPassword}
                  className="h-10 px-3 bg-zinc-100 hover:bg-zinc-200 text-zinc-900 border border-zinc-300 shrink-0 gap-1.5 text-xs font-semibold"
                >
                  {hasCopiedPassword ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      Copy
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button
              className="w-full bg-primary text-primary-foreground hover:bg-zinc-800 text-xs font-semibold"
              onClick={() => {
                setTempPasswordModal(null)
                setHasCopiedPassword(false)
              }}
            >
              I Have Securely Copied This Password
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ========================================================= */}
      {/* ALERT DIALOG: CONFIRM RESET PASSWORD                      */}
      {/* ========================================================= */}
      <AlertDialog
        open={!!confirmResetUser}
        onOpenChange={(open) => !open && setConfirmResetUser(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold">
              Reset Password for {confirmResetUser?.email}?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-muted-foreground leading-relaxed">
              This action invalidates any active sessions for this account and generates a new one-time temporary password. The user must use the new credentials on next sign-in.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="text-xs">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmResetUser) {
                  resetPasswordMutation.mutate(confirmResetUser.id)
                }
              }}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs font-semibold"
            >
              {resetPasswordMutation.isPending ? 'Resetting...' : 'Confirm Reset'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ========================================================= */}
      {/* ALERT DIALOG: CONFIRM TOGGLE ACTIVE STATUS                */}
      {/* ========================================================= */}
      <AlertDialog
        open={!!confirmToggleActive}
        onOpenChange={(open) => !open && setConfirmToggleActive(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold">
              {confirmToggleActive?.active ? 'Activate' : 'Deactivate'} User #{confirmToggleActive?.id}?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-muted-foreground leading-relaxed">
              {confirmToggleActive?.active
                ? 'The account will be enabled and permitted to sign in to the university clearance portal.'
                : 'The account will be locked out immediately and cannot authenticate until re-enabled by an administrator.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="text-xs">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmToggleActive) {
                  toggleActiveMutation.mutate({
                    userId: confirmToggleActive.id,
                    isActive: confirmToggleActive.active,
                  })
                }
              }}
              className={
                confirmToggleActive?.active
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold'
                  : 'bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold'
              }
            >
              {toggleActiveMutation.isPending ? 'Updating...' : 'Confirm'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  )
}

export default AdminDashboardPage
