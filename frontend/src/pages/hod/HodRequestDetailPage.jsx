import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { hodApi } from '@/api/hod'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
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
  CheckCircle2,
  XCircle,
  RotateCw,
  Home,
  Calendar,
  AlertTriangle,
  History,
  ShieldCheck,
  Award,
  ExternalLink,
  Copy,
} from 'lucide-react'

export function HodRequestDetailPage() {
  useDocumentTitle('HoD Clearance Review')
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [decision, setDecision] = useState('APPROVED')
  const [remarks, setRemarks] = useState('')
  const [remarksError, setRemarksError] = useState('')
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [approvedSuccessData, setApprovedSuccessData] = useState(null)

  // Fetch full request detail
  const {
    data: detail,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['hod', 'request', id],
    queryFn: async () => {
      return await hodApi.getRequestDetail(Number(id))
    },
    enabled: Boolean(id),
  })

  const departmentName = user?.department_name || 'Academic Department'

  const handleOpenConfirm = () => {
    if (decision === 'REJECTED' && !remarks.trim()) {
      setRemarksError('Remarks are strictly mandatory when rejecting a clearance request.')
      return
    }
    if (remarks.length > 500) {
      setRemarksError('Remarks cannot exceed 500 characters.')
      return
    }
    setRemarksError('')
    setConfirmDialogOpen(true)
  }

  const handleExecuteDecision = async () => {
    setIsSubmitting(true)
    try {
      const res = await hodApi.submitDecision(Number(id), {
        decision,
        remarks: remarks.trim() || null,
      })

      if (decision === 'APPROVED') {
        toast.success('Clearance approved! Certificate generated successfully.')
        setApprovedSuccessData(res)
      } else {
        toast.success('Clearance returned to student with remarks.')
      }

      setConfirmDialogOpen(false)
      refetch()
    } catch (err) {
      const status = err.response?.status
      const msg = err.response?.data?.detail

      if (status === 409) {
        toast.error('Conflict: Request is no longer in HOD_REVIEW status.')
      } else if (status === 404) {
        toast.error('Request not found or does not belong to your academic department.')
      } else if (status === 400) {
        setRemarksError(msg || 'Mandatory remarks missing.')
        toast.error(msg || 'Validation error.')
      } else {
        toast.error(msg || 'Failed to submit decision.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="max-w-6xl mx-auto space-y-6">
          <Skeleton className="h-6 w-32 bg-zinc-100" />
          <Skeleton className="h-28 w-full rounded-xl bg-zinc-100" />
          <Skeleton className="h-64 w-full rounded-xl bg-zinc-100" />
        </div>
      </AppShell>
    )
  }

  if (isError || !detail) {
    return (
      <AppShell>
        <div className="max-w-xl mx-auto py-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h2 className="font-heading text-xl font-bold text-zinc-900">
            Dossier Not Accessible
          </h2>
          <p className="text-xs text-zinc-500 leading-relaxed">
            {error?.response?.data?.detail ||
              'This clearance request could not be found or does not belong to your assigned academic department.'}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/hod')}
            className="text-xs gap-1.5 border-border"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            Return to HoD Queue
          </Button>
        </div>
      </AppShell>
    )
  }

  const approvals = detail.approvals || []
  const canDecide = detail.status === 'HOD_REVIEW'

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <Link
            to="/hod"
            className="flex items-center gap-1 hover:text-zinc-900 transition-colors font-medium"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            HoD Clearance Queue
          </Link>
          <span>/</span>
          <span className="text-zinc-900 font-mono">Dossier #{detail.request_id}</span>
        </div>

        {/* Student Dossier Header Card */}
        <div className="rounded-xl border border-border bg-white p-6 shadow-card space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-heading text-2xl font-bold text-zinc-950">
                  {detail.student_name}
                </span>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-zinc-100 text-zinc-700 border border-zinc-200">
                  {detail.registration_number}
                </span>
              </div>
              <p className="text-xs sm:text-sm text-zinc-600">
                {detail.programme_name}
              </p>
            </div>

            <div className="flex flex-col sm:items-end gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                Clearance Lifecycle
              </span>
              <StatusBadge status={detail.status} />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-3 border-t border-zinc-100 text-xs">
            <div>
              <span className="text-zinc-400 block text-[11px]">Covered Academic Department</span>
              <span className="font-semibold text-zinc-800">{departmentName}</span>
            </div>
            <div>
              <span className="text-zinc-400 block text-[11px]">Campus Enrollment</span>
              <span className="font-medium text-zinc-800 flex items-center gap-1">
                {detail.is_hosteller ? (
                  <>
                    <Home className="w-3 h-3 text-indigo-600" />
                    Residential Student (Hosteller)
                  </>
                ) : (
                  'Day Scholar'
                )}
              </span>
            </div>
            <div>
              <span className="text-zinc-400 block text-[11px]">Application Submitted</span>
              <span className="font-medium text-zinc-800 flex items-center gap-1">
                <Calendar className="w-3 h-3 text-zinc-400" />
                {detail.submitted_at ? new Date(detail.submitted_at).toLocaleString() : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Previous HoD Remarks Banner */}
        {detail.hod_remarks && (
          <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/80 text-xs text-amber-950 space-y-1">
            <div className="flex items-center gap-1.5 font-semibold text-amber-900">
              <AlertTriangle className="w-4 h-4 text-amber-700" />
              <span>Prior Chairperson Rejection Remarks</span>
            </div>
            <p className="leading-relaxed pl-5 text-amber-900/90 font-mono text-[11px]">
              "{detail.hod_remarks}"
            </p>
          </div>
        )}

        {/* Approved Success Banner with Certificate Info */}
        {(approvedSuccessData || detail.status === 'CLEARED' || detail.status === 'REFUND_VERIFIED') && (
          <div className="p-5 rounded-xl border border-emerald-200 bg-emerald-50/70 text-xs text-emerald-950 space-y-3">
            <div className="flex items-center gap-2 font-semibold text-emerald-900 text-sm">
              <Award className="w-5 h-5 text-emerald-600" />
              <span>Clearance Formally Approved & Certificate Issued</span>
            </div>
            <p className="leading-relaxed text-emerald-900/90 text-xs">
              All departmental obligations have been cleared. The official university certificate has been generated and is available for tamper-proof public verification.
            </p>

            {(detail.certificate_code || approvedSuccessData?.certificate_code) && (
              <div className="p-3.5 rounded-lg bg-white border border-emerald-300 shadow-2xs space-y-1.5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 block">
                      Certificate Verification Code
                    </span>
                    <span className="font-mono text-xs sm:text-sm font-bold text-zinc-900 select-all">
                      {detail.certificate_code || approvedSuccessData?.certificate_code}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const code = detail.certificate_code || approvedSuccessData?.certificate_code
                        navigator.clipboard.writeText(code)
                        toast.success('Certificate code copied to clipboard!')
                      }}
                      className="h-7 px-2.5 text-[11px] gap-1 border-emerald-200 text-emerald-800 hover:bg-emerald-50"
                    >
                      <Copy className="w-3 h-3" />
                      Copy Code
                    </Button>
                    <Link
                      to={`/verify/${detail.certificate_code || approvedSuccessData?.certificate_code}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 hover:text-emerald-900 underline underline-offset-2 ml-1"
                    >
                      Verify Publicly
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              </div>
            )}

            <div className="p-2.5 rounded-lg bg-white/80 border border-emerald-200 text-[11px] text-zinc-600 flex items-center justify-between">
              <span>Workflow Stage: <strong>{detail.status}</strong></span>
              <span className="text-emerald-700 font-mono text-[10px]">Security Deposit Ready for Refund</span>
            </div>
          </div>
        )}

        {/* Full Department Sign-off Table */}
        <div className="rounded-xl border border-border bg-white shadow-card overflow-hidden space-y-3">
          <div className="px-6 py-4 border-b border-border bg-zinc-50/60 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-base font-bold text-zinc-950">
                Department Sign-off Matrix
              </h2>
              <p className="text-xs text-zinc-500">
                Complete parallel clearance audit trail across all applicable university offices.
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
                    Category
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Decision Status
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Officer Remarks
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Decision Timestamp
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600 text-right pr-6">
                    Decided By
                  </TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {approvals.map((app) => (
                  <TableRow key={app.id} className="border-border hover:bg-zinc-50/60 transition-colors">
                    <TableCell className="px-6 py-3.5">
                      <span className="font-semibold text-xs sm:text-sm text-zinc-900 block">
                        {app.department_name}
                      </span>
                      {app.resubmission_count > 0 && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-amber-700 font-medium">
                          <History className="w-2.5 h-2.5" />
                          Resubmission #{app.resubmission_count}
                        </span>
                      )}
                    </TableCell>

                    <TableCell className="py-3.5">
                      <Badge variant="outline" className="text-[10px] uppercase font-mono bg-zinc-50 text-zinc-600">
                        {app.department_kind}
                      </Badge>
                    </TableCell>

                    <TableCell className="py-3.5">
                      <StatusBadge status={app.status} />
                    </TableCell>

                    <TableCell className="py-3.5 text-xs text-zinc-700 max-w-xs">
                      {app.remarks ? (
                        <span className="font-medium text-zinc-900">{app.remarks}</span>
                      ) : (
                        <span className="text-zinc-400 italic">No remarks recorded</span>
                      )}
                      {app.previous_remarks && (
                        <div className="mt-1 text-[11px] text-zinc-500 font-mono bg-zinc-50 p-1.5 rounded border border-zinc-200">
                          <span className="font-semibold text-zinc-600 block text-[10px]">Previous Reason:</span>
                          "{app.previous_remarks}"
                        </div>
                      )}
                    </TableCell>

                    <TableCell className="py-3.5 text-xs text-zinc-600 font-mono">
                      {app.decided_at ? new Date(app.decided_at).toLocaleString() : '—'}
                    </TableCell>

                    <TableCell className="py-3.5 text-right pr-6 text-xs">
                      {app.decided_by_name ? (
                        <span className="font-semibold text-zinc-900 block">
                          {app.decided_by_name}
                        </span>
                      ) : (
                        <span className="text-zinc-400 italic">
                          {app.status === 'PENDING' ? 'Pending Review' : 'Department Officer'}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>

        {/* Chairperson Final Decision Panel (Visible when HOD_REVIEW) */}
        {canDecide && (
          <div className="rounded-xl border border-zinc-900 bg-white p-6 shadow-card space-y-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-zinc-900" />
              <h2 className="font-heading text-lg font-bold text-zinc-950">
                Chairperson Final Determination
              </h2>
            </div>
            <p className="text-xs text-zinc-500">
              Granting final approval moves the clearance to <strong>CLEARED</strong> and creates the digital Certificate record. Rejection returns the application to <strong>ACTION_NEEDED</strong>.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setDecision('APPROVED')
                  setRemarksError('')
                }}
                className={`flex items-center justify-center gap-2.5 p-3.5 rounded-xl border text-xs font-semibold transition-all ${
                  decision === 'APPROVED'
                    ? 'border-emerald-600 bg-emerald-50/50 text-emerald-950 ring-1 ring-emerald-600'
                    : 'border-border bg-white text-zinc-600 hover:bg-zinc-50'
                }`}
              >
                <CheckCircle2 className={`w-4 h-4 ${decision === 'APPROVED' ? 'text-emerald-600' : 'text-zinc-400'}`} />
                Grant Final Clearance (Issue Certificate)
              </button>

              <button
                type="button"
                onClick={() => {
                  setDecision('REJECTED')
                }}
                className={`flex items-center justify-center gap-2.5 p-3.5 rounded-xl border text-xs font-semibold transition-all ${
                  decision === 'REJECTED'
                    ? 'border-rose-600 bg-rose-50/50 text-rose-950 ring-1 ring-rose-600'
                    : 'border-border bg-white text-zinc-600 hover:bg-zinc-50'
                }`}
              >
                <XCircle className={`w-4 h-4 ${decision === 'REJECTED' ? 'text-rose-600' : 'text-zinc-400'}`} />
                Reject Clearance (Mandatory Remarks)
              </button>
            </div>

            <div className="space-y-1.5 pt-2">
              <div className="flex justify-between items-center text-xs">
                <Label htmlFor="hod-remarks" className="font-semibold text-zinc-900">
                  {decision === 'REJECTED' ? (
                    <span className="text-rose-700">Chairperson Remarks (Mandatory for Rejection) *</span>
                  ) : (
                    <span>Chairperson Clearance Note (Optional)</span>
                  )}
                </Label>
                <span className={`text-[11px] font-mono ${remarks.length > 500 ? 'text-rose-600 font-bold' : 'text-zinc-400'}`}>
                  {remarks.length} / 500
                </span>
              </div>

              <Textarea
                id="hod-remarks"
                rows={3}
                placeholder={
                  decision === 'REJECTED'
                    ? 'Specify reason for withholding final clearance (e.g. Major project submission incomplete or academic disciplinary hold)...'
                    : 'Optional final approval endorsement notes...'
                }
                value={remarks}
                onChange={(e) => {
                  setRemarks(e.target.value)
                  if (remarksError) setRemarksError('')
                }}
                className={`text-xs bg-white resize-none ${remarksError ? 'border-rose-500 focus-visible:ring-rose-500' : 'border-border'}`}
              />

              {remarksError && (
                <p className="text-[11px] text-rose-600 font-medium">{remarksError}</p>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <Button
                size="sm"
                onClick={handleOpenConfirm}
                className={`h-9 px-5 text-xs gap-2 text-white font-medium ${
                  decision === 'APPROVED'
                    ? 'bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-600'
                    : 'bg-rose-600 hover:bg-rose-700 focus-visible:ring-rose-600'
                }`}
              >
                {decision === 'APPROVED' ? (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Proceed with Final Approval
                  </>
                ) : (
                  <>
                    <XCircle className="w-4 h-4" />
                    Proceed with Rejection
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Confirmation AlertDialog */}
        <AlertDialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
          <AlertDialogContent className="bg-white border-border">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-heading text-lg font-bold text-zinc-950">
                {decision === 'APPROVED'
                  ? 'Confirm Final Clearance Approval'
                  : 'Confirm Clearance Rejection'}
              </AlertDialogTitle>
              <AlertDialogDescription className="text-xs text-zinc-600 leading-relaxed">
                {decision === 'APPROVED'
                  ? `Are you sure you want to approve the final No-Dues clearance for ${detail.student_name} (${detail.registration_number})? This action issues an official university certificate and transmits the dossier to Accounts for security deposit refund.`
                  : `Are you sure you want to reject this application? The student will be notified with your remarks and required to resolve the issue before resubmitting.`}
              </AlertDialogDescription>
            </AlertDialogHeader>

            <AlertDialogFooter className="pt-2 border-t border-border gap-2">
              <AlertDialogCancel disabled={isSubmitting} className="text-xs h-9 border-border">
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleExecuteDecision}
                disabled={isSubmitting}
                className={`text-xs h-9 text-white ${
                  decision === 'APPROVED'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                {isSubmitting ? (
                  <>
                    <RotateCw className="w-3.5 h-3.5 animate-spin mr-1.5" />
                    Submitting...
                  </>
                ) : (
                  'Confirm & Submit'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AppShell>
  )
}

export default HodRequestDetailPage
