import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { adminApi } from '@/api/admin'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
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
import { toast } from 'sonner'
import {
  Building2,
  Users,
  AlertTriangle,
  UserPlus,
  KeyRound,
  Copy,
  Check,
  ShieldAlert,
  GraduationCap,
  Briefcase,
  ArrowRight,
  XCircle,
} from 'lucide-react'

export function AdminOfficesPage() {
  useDocumentTitle('University Offices & Staffing | SVSU No-Dues')
  const queryClient = useQueryClient()

  // Search & filter
  const [searchTerm, setSearchTerm] = useState('')
  const [kindFilter, setKindFilter] = useState('ALL') // ALL, academic, service
  const [missingFilter, setMissingFilter] = useState('ALL') // ALL, missing_any, missing_officer, missing_hod

  // Create User Modal for a specific office
  const [createUserOffice, setCreateUserOffice] = useState(null) // { office, defaultRole }
  const [createForm, setCreateForm] = useState({
    full_name: '',
    email: '',
    role: 'dept_officer',
  })
  const [createError, setCreateError] = useState('')

  // One-Time Temporary Password Dialog
  // CRITICAL: Shown once, never stored beyond this dialog, disappears on close
  const [tempPasswordModal, setTempPasswordModal] = useState(null) // { email, password, role, departmentName }
  const [hasCopiedPassword, setHasCopiedPassword] = useState(false)

  // Admin Cancel Request State
  const [adminCancelOpen, setAdminCancelOpen] = useState(false)
  const [adminCancelId, setAdminCancelId] = useState('')
  const [adminCancelReason, setAdminCancelReason] = useState('')
  const [adminCancelError, setAdminCancelError] = useState('')

  const adminCancelMutation = useMutation({
    mutationFn: ({ requestId, reason }) => adminApi.cancelRequest(requestId, reason),
    onSuccess: (_, variables) => {
      toast.success(`Clearance request #${variables.requestId} has been cancelled.`)
      setAdminCancelOpen(false)
      setAdminCancelId('')
      setAdminCancelReason('')
      setAdminCancelError('')
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to cancel clearance request.'
      setAdminCancelError(msg)
      toast.error(msg)
    },
  })

  // Fetch offices
  const {
    data: officesData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin', 'offices'],
    queryFn: () => adminApi.getOffices(),
  })

  const offices = useMemo(() => officesData?.items || [], [officesData?.items])

  // Summary Metrics
  const summary = useMemo(() => {
    let missingOfficers = 0
    let missingHods = 0
    let academicCount = 0
    let serviceCount = 0

    offices.forEach((o) => {
      if (o.kind === 'academic') academicCount++
      if (o.kind === 'service') serviceCount++
      if (o.missing_officer) missingOfficers++
      if (o.missing_hod) missingHods++
    })

    return {
      total: offices.length,
      academicCount,
      serviceCount,
      missingOfficers,
      missingHods,
      totalNeedsStaff: offices.filter((o) => o.missing_officer || o.missing_hod).length,
    }
  }, [offices])

  // Filtered Offices
  const filteredOffices = useMemo(() => {
    return offices.filter((o) => {
      if (kindFilter !== 'ALL' && o.kind !== kindFilter) return false
      if (missingFilter === 'missing_any' && !o.missing_officer && !o.missing_hod) return false
      if (missingFilter === 'missing_officer' && !o.missing_officer) return false
      if (missingFilter === 'missing_hod' && !o.missing_hod) return false

      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase()
        const matchesName = o.name.toLowerCase().includes(q)
        const matchesOfficers = o.active_officers?.some(
          (u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
        )
        const matchesHod =
          o.hod &&
          (o.hod.name.toLowerCase().includes(q) || o.hod.email.toLowerCase().includes(q))
        return matchesName || matchesOfficers || matchesHod
      }
      return true
    })
  }, [offices, kindFilter, missingFilter, searchTerm])

  // Create User Mutation
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
      queryClient.invalidateQueries({ queryKey: ['admin', 'offices'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to provision staff account.'
      setCreateError(msg)
      toast.error(msg)
    },
  })

  const openCreateDialog = (office, defaultRole = 'dept_officer') => {
    setCreateError('')
    setCreateForm({
      full_name: '',
      email: '',
      role: defaultRole,
    })
    setCreateUserOffice({ office, defaultRole })
  }

  const handleCreateSubmit = (e) => {
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
  }

  const handleCopyPassword = () => {
    if (!tempPasswordModal?.password) return
    navigator.clipboard.writeText(tempPasswordModal.password)
    setHasCopiedPassword(true)
    toast.success('Temporary password copied to clipboard.')
    setTimeout(() => setHasCopiedPassword(false), 2500)
  }

  // Table Columns
  const columns = useMemo(
    () => [
      {
        accessorKey: 'id',
        header: 'ID',
        cell: ({ row }) => (
          <span className="font-mono text-xs font-semibold text-zinc-500">
            #{row.original.id}
          </span>
        ),
      },
      {
        accessorKey: 'name',
        header: 'Office / Department',
        cell: ({ row }) => {
          const item = row.original
          return (
            <div className="space-y-1 py-1 max-w-[280px]">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-xs text-zinc-900 leading-tight">
                  {item.name}
                </span>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                <Badge
                  variant="outline"
                  className={
                    item.kind === 'academic'
                      ? 'bg-indigo-50/70 text-indigo-700 border-indigo-200 text-[10px]'
                      : 'bg-zinc-100 text-zinc-700 border-zinc-200 text-[10px]'
                  }
                >
                  {item.kind === 'academic' ? 'Academic Department' : 'Service Branch'}
                </Badge>
                {item.applicability && (
                  <Badge
                    variant="outline"
                    className="bg-white text-zinc-500 border-zinc-200 text-[9px] font-mono"
                  >
                    {item.applicability}
                  </Badge>
                )}
              </div>
            </div>
          )
        },
      },
      {
        accessorKey: 'active_officers',
        header: 'Active Officers',
        cell: ({ row }) => {
          const item = row.original
          const officersList = item.active_officers || []

          if (officersList.length === 0) {
            return (
              <Badge
                variant="outline"
                className="bg-amber-50 text-amber-800 border-amber-300 text-[11px] font-medium gap-1 py-0.5"
              >
                <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
                Needs Officer
              </Badge>
            )
          }

          return (
            <div className="space-y-1">
              {officersList.map((off) => (
                <div key={off.id} className="text-xs">
                  <span className="font-medium text-zinc-900 block leading-tight">
                    {off.name}
                  </span>
                  <span className="text-[11px] text-zinc-500 font-mono">
                    {off.email}
                  </span>
                </div>
              ))}
            </div>
          )
        },
      },
      {
        accessorKey: 'hod',
        header: 'Chairperson / HoD',
        cell: ({ row }) => {
          const item = row.original
          if (item.kind !== 'academic') {
            return <span className="text-xs text-zinc-400 italic">Not Applicable</span>
          }

          if (item.missing_hod || !item.hod) {
            return (
              <Badge
                variant="outline"
                className="bg-rose-50 text-rose-800 border-rose-300 text-[11px] font-medium gap-1 py-0.5"
              >
                <AlertTriangle className="w-3 h-3 text-rose-600 shrink-0" />
                Needs HoD
              </Badge>
            )
          }

          return (
            <div className="text-xs">
              <span className="font-semibold text-zinc-900 block leading-tight">
                {item.hod.name}
              </span>
              <span className="text-[11px] text-zinc-500 font-mono">
                {item.hod.email}
              </span>
            </div>
          )
        },
      },
      {
        id: 'actions',
        header: 'Staffing Action',
        cell: ({ row }) => {
          const item = row.original
          const needsOfficer = item.missing_officer
          const needsHod = item.missing_hod

          return (
            <div className="flex items-center gap-1.5 flex-wrap">
              {needsOfficer && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openCreateDialog(item, 'dept_officer')}
                  className="h-7 text-[11px] gap-1 bg-amber-50 hover:bg-amber-100 text-amber-900 border-amber-200"
                >
                  <UserPlus className="w-3 h-3" />
                  Assign Officer
                </Button>
              )}
              {needsHod && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openCreateDialog(item, 'hod')}
                  className="h-7 text-[11px] gap-1 bg-rose-50 hover:bg-rose-100 text-rose-900 border-rose-200"
                >
                  <UserPlus className="w-3 h-3" />
                  Assign HoD
                </Button>
              )}
              {!needsOfficer && !needsHod && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => openCreateDialog(item, 'dept_officer')}
                  className="h-7 text-[11px] text-zinc-600 hover:text-black gap-1"
                >
                  <UserPlus className="w-3 h-3" />
                  Add Officer
                </Button>
              )}
            </div>
          )
        },
      },
    ],
    []
  )

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-zinc-900" />
              <h1 className="font-heading text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
                Offices & Staffing Dashboard
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Master registry of university academic faculties, service sections, and their designated clearance staff.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              asChild
              variant="outline"
              size="sm"
              className="text-xs h-9 gap-1.5 border-zinc-200 text-zinc-700"
            >
              <Link to="/admin/users">
                <Users className="w-3.5 h-3.5" />
                User Directory
                <ArrowRight className="w-3 h-3 ml-0.5" />
              </Link>
            </Button>
          </div>
        </div>

        {/* Staffing Health Summary KPI Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                  Total Offices
                </span>
                <span className="font-mono text-2xl font-bold text-zinc-900">
                  {summary.total}
                </span>
              </div>
              <div className="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-700">
                <Building2 className="w-4 h-4" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                  Academic Faculties
                </span>
                <span className="font-mono text-2xl font-bold text-indigo-900">
                  {summary.academicCount}
                </span>
              </div>
              <div className="w-9 h-9 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-700">
                <GraduationCap className="w-4 h-4" />
              </div>
            </CardContent>
          </Card>

          <Card
            className={`border shadow-2xs transition-colors ${
              summary.missingOfficers > 0
                ? 'border-amber-300 bg-amber-50/40'
                : 'border-border bg-white'
            }`}
          >
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-[11px] font-medium text-zinc-600 uppercase tracking-wider block">
                  Needs Officer
                </span>
                <span
                  className={`font-mono text-2xl font-bold ${
                    summary.missingOfficers > 0 ? 'text-amber-800' : 'text-zinc-900'
                  }`}
                >
                  {summary.missingOfficers}
                </span>
              </div>
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                  summary.missingOfficers > 0
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-zinc-100 text-zinc-600'
                }`}
              >
                <Briefcase className="w-4 h-4" />
              </div>
            </CardContent>
          </Card>

          <Card
            className={`border shadow-2xs transition-colors ${
              summary.missingHods > 0
                ? 'border-rose-300 bg-rose-50/40'
                : 'border-border bg-white'
            }`}
          >
            <CardContent className="p-4 flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-[11px] font-medium text-zinc-600 uppercase tracking-wider block">
                  Needs HoD
                </span>
                <span
                  className={`font-mono text-2xl font-bold ${
                    summary.missingHods > 0 ? 'text-rose-800' : 'text-zinc-900'
                  }`}
                >
                  {summary.missingHods}
                </span>
              </div>
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                  summary.missingHods > 0
                    ? 'bg-rose-100 text-rose-800'
                    : 'bg-zinc-100 text-zinc-600'
                }`}
              >
                <AlertTriangle className="w-4 h-4" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Warning Notification if Staffing Gaps Exist */}
        {summary.totalNeedsStaff > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="text-xs font-bold text-amber-900">
                Staffing Attention Required: {summary.missingOfficers} office{summary.missingOfficers !== 1 ? 's' : ''} still need an officer
                {summary.missingHods > 0 && ` and ${summary.missingHods} academic department${summary.missingHods !== 1 ? 's' : ''} require an HoD`}.
              </h2>
              <p className="text-xs text-amber-800 leading-relaxed">
                Clearance workflows will be blocked for students whose applications touch unstaffed offices. Use the shortcut buttons in the table below to provision dedicated officers.
              </p>
            </div>
          </div>
        )}

        {/* Controls: Search & Filters */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-zinc-50/80 p-3 rounded-xl border border-border">
          <div className="relative flex-1 max-w-sm">
            <Input
              placeholder="Search office name, officer, or HoD..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="text-xs h-9 bg-white pl-8"
            />
            <Building2 className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-3" />
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Kind Filter */}
            <select
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
              className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="ALL">All Office Kinds</option>
              <option value="academic">Academic Departments</option>
              <option value="service">Service Branches</option>
            </select>

            {/* Missing Filter */}
            <select
              value={missingFilter}
              onChange={(e) => setMissingFilter(e.target.value)}
              className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="ALL">All Staffing Statuses</option>
              <option value="missing_any">Needs Staffing (Any)</option>
              <option value="missing_officer">Missing Officer</option>
              <option value="missing_hod">Missing HoD</option>
            </select>
          </div>
        </div>

        {/* Offices DataTable */}
        {isError ? (
          <div className="p-6 rounded-xl border border-rose-200 bg-rose-50 text-rose-900 text-xs">
            <p className="font-semibold">Failed to load university offices directory.</p>
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
            data={filteredOffices}
            loading={isLoading}
            emptyMessage="No university offices match the active filters."
            pageSize={35}
          />
        )}

        {/* Administrative Action Panel: Cancel a Clearance Request by ID */}
        <div className="rounded-xl border border-border bg-white p-6 shadow-card space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-zinc-900" />
                <h3 className="font-heading text-sm font-bold text-zinc-900">
                  Cancel Clearance Request by ID
                </h3>
              </div>
              <p className="text-xs text-zinc-600 leading-relaxed max-w-2xl">
                Administrators can terminate an active clearance request by specifying its database ID and an audit reason.
                <span className="block text-[11px] text-zinc-400 mt-0.5">
                  (Note: Searching clearance requests by student registration number or name is currently pending backend API support).
                </span>
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setAdminCancelId('')
                setAdminCancelReason('')
                setAdminCancelError('')
                setAdminCancelOpen(true)
              }}
              className="text-xs text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 h-8 gap-1.5 shrink-0"
            >
              <XCircle className="w-3.5 h-3.5" />
              Cancel a Request by ID
            </Button>
          </div>
        </div>
      </div>

      {/* Admin Cancel Request Modal */}
      <Dialog
        open={adminCancelOpen}
        onOpenChange={(open) => {
          if (!open) {
            setAdminCancelOpen(false)
            setAdminCancelId('')
            setAdminCancelReason('')
            setAdminCancelError('')
          }
        }}
      >
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!adminCancelId.trim()) {
                setAdminCancelError('Clearance request ID is required.')
                return
              }
              if (!adminCancelReason.trim()) {
                setAdminCancelError('A mandatory cancellation reason is required.')
                return
              }
              adminCancelMutation.mutate({
                requestId: Number(adminCancelId),
                reason: adminCancelReason.trim(),
              })
            }}
          >
            <DialogHeader className="pb-3 border-b border-zinc-100">
              <DialogTitle className="font-heading font-bold text-base flex items-center gap-2 text-zinc-950">
                <ShieldAlert className="w-4 h-4 text-red-600" />
                Administrative Request Cancellation
              </DialogTitle>
              <DialogDescription className="text-xs text-zinc-500">
                Permanently cancel an active student clearance request. This action is recorded in the university audit log.
              </DialogDescription>
            </DialogHeader>

            {adminCancelError && (
              <div className="p-3 my-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p>{adminCancelError}</p>
              </div>
            )}

            <div className="py-4 space-y-4 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="adminRequestId" className="text-xs font-semibold text-zinc-800">
                  Clearance Request ID <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="adminRequestId"
                  type="number"
                  placeholder="e.g. 1"
                  min="1"
                  value={adminCancelId}
                  onChange={(e) => {
                    setAdminCancelId(e.target.value)
                    if (adminCancelError) setAdminCancelError('')
                  }}
                  className="text-xs font-mono"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="adminCancelReason" className="text-xs font-semibold text-zinc-800">
                  Mandatory Cancellation Reason <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="adminCancelReason"
                  rows={3}
                  maxLength={1000}
                  placeholder="Explain why this request is being cancelled administratively..."
                  value={adminCancelReason}
                  onChange={(e) => {
                    setAdminCancelReason(e.target.value)
                    if (adminCancelError) setAdminCancelError('')
                  }}
                  className="text-xs resize-none"
                  required
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setAdminCancelOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={adminCancelMutation.isPending || !adminCancelId || !adminCancelReason.trim()}
                className="bg-red-600 text-white hover:bg-red-700 text-xs h-9 font-semibold"
              >
                {adminCancelMutation.isPending ? 'Cancelling...' : 'Confirm Cancellation'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Provision User Shortcut Modal */}
      <Dialog
        open={Boolean(createUserOffice)}
        onOpenChange={(open) => {
          if (!open) {
            setCreateUserOffice(null)
            setCreateError('')
          }
        }}
      >
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleCreateSubmit}>
            <DialogHeader className="pb-3 border-b border-zinc-100">
              <DialogTitle className="font-heading font-bold text-base flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-zinc-900" />
                Assign Staff to {createUserOffice?.office?.name}
              </DialogTitle>
              <DialogDescription className="text-xs">
                Provision a university dealing account. A random one-time temporary password will be generated.
              </DialogDescription>
            </DialogHeader>

            {createError && (
              <div className="p-3 my-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p>{createError}</p>
              </div>
            )}

            <div className="space-y-3.5 py-4 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="staffRole" className="text-xs font-semibold text-zinc-800">
                  Role Assignment
                </Label>
                <select
                  id="staffRole"
                  value={createForm.role}
                  onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                  className="w-full h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="dept_officer">Department Dealing Officer</option>
                  {createUserOffice?.office?.kind === 'academic' && (
                    <option value="hod">Chairperson / HoD (Academic Department)</option>
                  )}
                </select>
                {createUserOffice?.office?.kind !== 'academic' && (
                  <p className="text-[11px] text-zinc-500">
                    Note: Chairperson (HoD) role is strictly restricted to academic faculties.
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="staffName" className="text-xs font-semibold text-zinc-800">
                  Staff Full Name
                </Label>
                <Input
                  id="staffName"
                  placeholder="e.g. Dr. Rajesh Kumar"
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="staffEmail" className="text-xs font-semibold text-zinc-800">
                  Official University Email
                </Label>
                <Input
                  id="staffEmail"
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
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
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
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {createUserMutation.isPending ? 'Provisioning...' : 'Provision Account'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ONE-TIME TEMPORARY PASSWORD DIALOG */}
      {/* Crucial: Transient memory only, disappears on close, copy feedback */}
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
                Temporary Credentials Generated
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Account provisioned for <strong className="text-zinc-900">{tempPasswordModal?.email}</strong> in {tempPasswordModal?.departmentName}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4 text-xs">
            <div className="p-3 rounded-lg border border-amber-200 bg-amber-50/70 text-amber-900 flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-semibold block text-[11px] uppercase tracking-wider text-amber-950">
                  One-Time Visibility Notice
                </span>
                <p className="text-xs text-amber-900 leading-snug">
                  This temporary password is displayed <strong>strictly once</strong>. It is never stored in persistent memory, logs, or local storage. Please copy and deliver it securely to the officer.
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
                  onClick={handleCopyPassword}
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

export default AdminOfficesPage
