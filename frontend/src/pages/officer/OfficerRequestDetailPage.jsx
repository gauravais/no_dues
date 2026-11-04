import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { departmentApi } from '@/api/department'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
  ChevronLeft,
  Building2,
  PlusCircle,
  Home,
  Calendar,
  AlertTriangle,
  History,
  FileText,
  Info,
  XCircle,
} from 'lucide-react'

export function OfficerRequestDetailPage() {
  useDocumentTitle('Student Clearance Dossier')
  const { id } = useParams()
  const { user } = useAuth()
  const queryClient = useQueryClient()

  // Add Office Dialog State
  const [addOfficeOpen, setAddOfficeOpen] = useState(false)
  const [selectedDeptId, setSelectedDeptId] = useState('')
  const [addReason, setAddReason] = useState('')
  const [addReasonError, setAddReasonError] = useState('')

  // Officer Cancel Request State
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [cancelReasonError, setCancelReasonError] = useState('')

  // Fetch full academic dossier
  const {
    data: detail,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['department', 'request', id],
    queryFn: () => departmentApi.getRequestDetail(Number(id)),
    enabled: Boolean(id),
  })

  // Cancel Request Mutation
  const cancelMutation = useMutation({
    mutationFn: (reason) => departmentApi.cancelRequest(Number(id), reason),
    onSuccess: () => {
      toast.success('Clearance request has been cancelled.')
      setCancelDialogOpen(false)
      setCancelReason('')
      setCancelReasonError('')
      queryClient.invalidateQueries({ queryKey: ['department', 'request', id] })
      queryClient.invalidateQueries({ queryKey: ['department', 'queue'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to cancel clearance request.'
      toast.error(msg)
    },
  })

  // Add Department Mutation
  const addDeptMutation = useMutation({
    mutationFn: ({ departmentId, reason }) =>
      departmentApi.addDepartment(Number(id), { departmentId, reason }),
    onSuccess: (newItem) => {
      toast.success(`Added ${newItem.department_name} to clearance dossier.`)
      setAddOfficeOpen(false)
      setSelectedDeptId('')
      setAddReason('')
      setAddReasonError('')
      queryClient.invalidateQueries({ queryKey: ['department', 'request', id] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to add office to request.'
      toast.error(msg)
    },
  })

  const handleOpenAddOffice = () => {
    setSelectedDeptId(detail?.can_add_departments?.[0]?.id ? String(detail.can_add_departments[0].id) : '')
    setAddReason('')
    setAddReasonError('')
    setAddOfficeOpen(true)
  }

  const handleAddOfficeSubmit = (e) => {
    e.preventDefault()
    if (!selectedDeptId) {
      toast.error('Please select an office to add.')
      return
    }
    if (!addReason.trim()) {
      setAddReasonError('A valid operational reason is strictly mandatory when adding an office.')
      return
    }
    addDeptMutation.mutate({
      departmentId: Number(selectedDeptId),
      reason: addReason.trim(),
    })
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="max-w-7xl mx-auto space-y-6">
          <Skeleton className="h-10 w-48 bg-zinc-100" />
          <Skeleton className="h-44 w-full rounded-xl bg-zinc-100" />
          <Skeleton className="h-96 w-full rounded-xl bg-zinc-100" />
        </div>
      </AppShell>
    )
  }

  if (isError || !detail) {
    return (
      <AppShell>
        <div className="max-w-7xl mx-auto space-y-4">
          <Link
            to="/officer"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-black font-medium"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Queue
          </Link>
          <div className="p-6 rounded-xl border border-destructive/20 bg-destructive/5 text-destructive text-sm flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-zinc-950">
                Failed to load student clearance dossier
              </p>
              <p className="text-xs text-zinc-600 mt-1">
                {error?.response?.data?.detail ||
                  'The requested clearance record could not be found or does not involve your department.'}
              </p>
            </div>
          </div>
        </div>
      </AppShell>
    )
  }

  const approvals = detail.approvals || []
  const canAddDepts = detail.can_add_departments || []
  const canOfficerCancel =
    !detail.is_limited_view &&
    detail.status !== 'CLEARED' &&
    detail.status !== 'REFUND_VERIFIED' &&
    detail.status !== 'CANCELLED'

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between">
          <Link
            to="/officer"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-black font-medium"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Department Queue
          </Link>

          <div className="flex items-center gap-2">
            {canOfficerCancel && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setCancelReason('')
                  setCancelReasonError('')
                  setCancelDialogOpen(true)
                }}
                className="text-xs text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 gap-1.5 h-8 font-medium"
              >
                <XCircle className="w-3.5 h-3.5" />
                Cancel Request
              </Button>
            )}

            {canAddDepts.length > 0 && (
              <Button
                size="sm"
                onClick={handleOpenAddOffice}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-1.5 h-8 font-semibold shadow-xs"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                Add Office
              </Button>
            )}
          </div>
        </div>

        {/* Student Dossier Header Card */}
        <div className="p-6 rounded-xl border border-border bg-white shadow-card space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h1 className="font-heading text-xl sm:text-2xl font-extrabold tracking-tight text-zinc-950">
                  {detail.student_name}
                </h1>
                <Badge variant="outline" className="font-mono text-xs bg-zinc-50 border-zinc-200">
                  {detail.registration_number}
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-zinc-600">
                {detail.programme_name} • Clearance Request #{detail.request_id}
              </p>
            </div>

            <div className="flex flex-col sm:items-end gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                Overall Lifecycle Status
              </span>
              <StatusBadge status={detail.status} />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-zinc-100 text-xs">
            <div>
              <span className="text-zinc-400 block text-[11px]">Academic Department</span>
              <span className="font-semibold text-zinc-800">
                {detail.academic_department || user?.department_name || 'Academic Dept'}
              </span>
            </div>
            <div>
              <span className="text-zinc-400 block text-[11px]">Declared Residency</span>
              <span className="font-medium text-zinc-800 flex items-center gap-1">
                {detail.declared_is_hosteller !== null && detail.declared_is_hosteller !== undefined ? (
                  detail.declared_is_hosteller || detail.is_hosteller ? (
                    <>
                      <Home className="w-3.5 h-3.5 text-indigo-600" />
                      Residential Student (Hosteller)
                    </>
                  ) : (
                    'Day Scholar'
                  )
                ) : (
                  <span className="text-zinc-400 italic">Hostel Office Review</span>
                )}
              </span>
            </div>
            <div>
              <span className="text-zinc-400 block text-[11px]">Submission Date</span>
              <span className="font-medium text-zinc-800 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                {detail.submitted_at ? new Date(detail.submitted_at).toLocaleString() : '—'}
              </span>
            </div>
          </div>

          {/* Student Declarations Section */}
          <div className="pt-4 border-t border-zinc-100 space-y-3">
            <div>
              <span className="text-[11px] font-semibold text-zinc-900 block mb-1">
                Declared Laboratory & Workshop Subjects:
              </span>
              {detail.declared_subjects && detail.declared_subjects.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {detail.declared_subjects.map((sub, i) => (
                    <Badge
                      key={i}
                      variant="outline"
                      className="font-mono text-xs bg-zinc-50 border-zinc-200 text-zinc-800 py-1"
                    >
                      {sub}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-400 italic">
                  Student declared zero specific laboratory subjects for this clearance.
                </p>
              )}
            </div>

            {detail.others_note && (
              <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-xs text-zinc-700 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-zinc-900 text-[11px]">
                  <FileText className="w-3.5 h-3.5 text-zinc-500" />
                  <span>Student Declaration Note (Special Facilities / Notes):</span>
                </div>
                <p className="leading-relaxed font-mono text-[11px]">{detail.others_note}</p>
              </div>
            )}
          </div>
        </div>

        {/* Prior Chairperson Remarks Banner if present */}
        {detail.hod_remarks && (
          <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/80 text-xs text-amber-950 space-y-1">
            <div className="flex items-center gap-1.5 font-semibold text-amber-900">
              <AlertTriangle className="w-4 h-4 text-amber-700" />
              <span>Chairperson (HoD) Action Requirement</span>
            </div>
            <p className="leading-relaxed pl-5 font-mono text-[11px]">
              "{detail.hod_remarks}"
            </p>
          </div>
        )}

        {/* Department Approvals Table */}
        <div className="rounded-xl border border-border bg-white shadow-card overflow-hidden space-y-3">
          <div className="px-6 py-4 border-b border-border bg-zinc-50/60 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-base font-bold text-zinc-950">
                {approvals.length === 1 ? 'Department Clearance Review' : 'Department Clearance Matrix'}
              </h2>
              <p className="text-xs text-zinc-500">
                {approvals.length === 1
                  ? 'Review status and decision record for your department.'
                  : 'Full parallel review status, officer sign-offs, and department additions.'}
              </p>
            </div>
            <Badge variant="outline" className="font-mono text-xs bg-white">
              {approvals.filter((a) => a.status === 'APPROVED').length} of {approvals.length} Approved
            </Badge>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader className="border-b border-border bg-zinc-50/40">
                <TableRow className="border-border">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600 px-6">
                    Department Office
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Kind
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Status
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Remarks & Rejection History
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Officer Sign-off
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600 pr-6">
                    Added By / Reason
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="divide-y divide-zinc-100">
                {approvals.map((app) => (
                  <TableRow key={app.id} className="hover:bg-zinc-50/60 transition-colors">
                    <TableCell className="px-6 py-3.5">
                      <span className="font-bold text-xs text-zinc-900 block">
                        {app.department_name}
                      </span>
                      {app.resubmission_count > 0 && (
                        <span className="text-[10px] text-amber-700 font-mono">
                          Resubmitted {app.resubmission_count}x
                        </span>
                      )}
                    </TableCell>

                    <TableCell className="py-3.5">
                      <Badge variant="outline" className="text-[10px] uppercase font-mono bg-zinc-50">
                        {app.department_kind}
                      </Badge>
                    </TableCell>

                    <TableCell className="py-3.5">
                      <StatusBadge status={app.status} size="sm" />
                    </TableCell>

                    <TableCell className="py-3.5 max-w-xs text-xs space-y-1">
                      {app.remarks ? (
                        <p className={`leading-snug ${app.status === 'REJECTED' ? 'text-rose-900 font-medium' : 'text-zinc-700'}`}>
                          {app.remarks}
                        </p>
                      ) : (
                        <span className="text-zinc-400 italic text-[11px]">—</span>
                      )}
                      {app.previous_remarks && (
                        <div className="flex items-center gap-1 text-[11px] text-zinc-500 italic">
                          <History className="w-3 h-3 text-zinc-400 shrink-0" />
                          <span>Prev: "{app.previous_remarks}"</span>
                        </div>
                      )}
                    </TableCell>

                    <TableCell className="py-3.5 text-xs text-zinc-600">
                      <div>
                        {app.decided_by_name ? (
                          <span className="font-medium text-zinc-900 block">{app.decided_by_name}</span>
                        ) : (
                          <span className="text-zinc-400 italic">Pending officer</span>
                        )}
                        <span className="text-[10px] text-zinc-400 font-mono">
                          {app.decided_at ? new Date(app.decided_at).toLocaleDateString() : '—'}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell className="py-3.5 pr-6 text-xs text-zinc-600">
                      {app.added_reason || app.added_by_name ? (
                        <div className="p-2 rounded bg-amber-50/80 border border-amber-200/80 text-[11px] text-amber-950">
                          <span className="font-semibold block">
                            Added by {app.added_by_name || 'Academic Dept'}:
                          </span>
                          <span className="italic">"{app.added_reason}"</span>
                        </div>
                      ) : (
                        <span className="text-zinc-400 text-[11px]">System standard</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>

      {/* Dialog: Add Office */}
      <Dialog open={addOfficeOpen} onOpenChange={setAddOfficeOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleAddOfficeSubmit}>
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base flex items-center gap-2">
                <Building2 className="w-4 h-4 text-zinc-900" />
                Add Clearance Office
              </DialogTitle>
              <DialogDescription className="text-xs">
                Add an additional service or lab facility to this student's clearance dossier.
              </DialogDescription>
            </DialogHeader>

            <div className="p-3 mb-3 rounded-lg bg-zinc-50 border border-zinc-200 text-xs text-zinc-600 flex items-start gap-2">
              <Info className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                Adding an office asks only that office; a request already with the HoD returns to department review.
              </p>
            </div>

            <div className="space-y-3.5 py-1 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="addOfficeSelect" className="text-xs font-semibold text-zinc-800">
                  Select University Facility / Office *
                </Label>
                <select
                  id="addOfficeSelect"
                  value={selectedDeptId}
                  onChange={(e) => setSelectedDeptId(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  required
                >
                  {canAddDepts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.kind})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="addReason" className="text-xs font-semibold text-zinc-800">
                  Operational Reason for Addition *
                </Label>
                <Textarea
                  id="addReason"
                  rows={3}
                  placeholder="Explain why this student requires review from this facility..."
                  value={addReason}
                  onChange={(e) => {
                    setAddReason(e.target.value)
                    if (addReasonError) setAddReasonError('')
                  }}
                  className={`text-xs resize-none ${addReasonError ? 'border-rose-500' : ''}`}
                  required
                />
                {addReasonError && (
                  <p className="text-[11px] text-rose-600 font-medium">{addReasonError}</p>
                )}
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
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
                disabled={addDeptMutation.isPending || !selectedDeptId}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {addDeptMutation.isPending ? 'Adding Office...' : 'Confirm Addition'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      {/* Officer Cancel Request Dialog */}
      <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <AlertDialogContent className="bg-white p-6 max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
              Cancel Student Clearance Request?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs space-y-2 text-zinc-600">
              <p>
                Cancelling this clearance request immediately terminates the active workflow for this student. A detailed operational reason is strictly required for the institutional audit trail.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-2 space-y-1.5">
            <Label htmlFor="officerCancelReason" className="text-xs font-semibold text-zinc-800">
              Reason for Cancellation <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="officerCancelReason"
              placeholder="e.g. Student withdrew application or transferred to another institution"
              rows={3}
              maxLength={1000}
              className={`text-xs resize-none ${cancelReasonError ? 'border-destructive ring-1 ring-destructive' : ''}`}
              value={cancelReason}
              onChange={(e) => {
                setCancelReason(e.target.value)
                if (cancelReasonError) setCancelReasonError('')
              }}
              required
            />
            {cancelReasonError && (
              <p className="text-[11px] text-destructive font-medium">{cancelReasonError}</p>
            )}
          </div>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel
              disabled={cancelMutation.isPending}
              onClick={() => {
                setCancelDialogOpen(false)
                setCancelReason('')
                setCancelReasonError('')
              }}
              className="text-xs h-9"
            >
              Keep Active
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={cancelMutation.isPending || !cancelReason.trim()}
              onClick={(e) => {
                e.preventDefault()
                if (!cancelReason.trim()) {
                  setCancelReasonError('A valid reason is strictly required to cancel.')
                  return
                }
                cancelMutation.mutate(cancelReason.trim())
              }}
              className="bg-red-600 text-white hover:bg-red-700 text-xs h-9 font-semibold"
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Confirm Cancellation'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  )
}

export default OfficerRequestDetailPage
