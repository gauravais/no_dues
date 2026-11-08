import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { studentApi } from '@/api/student'
import { departmentApi } from '@/api/department'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { StatusBadge } from '@/components/StatusBadge'
import { StepTimeline } from '@/components/StepTimeline'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
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
  Landmark,
  FileCheck2,
  Download,
  RotateCw,
  Send,
  AlertTriangle,
  History,
  ShieldAlert,
  PlusCircle,
  Building2,
  FlaskConical,
  ArrowRight,
  Info,
  CheckCircle2,
  XCircle,
} from 'lucide-react'

export function StudentDashboard() {
  useDocumentTitle('Student Clearance')
  const { user } = useAuth()
  const navigate = useNavigate()

  // State for Bank Details modal
  const [bankModalOpen, setBankModalOpen] = useState(false)
  const [bankForm, setBankForm] = useState({
    accountNumber: '',
    ifscCode: '',
    accountHolderName: user?.full_name || '',
    bankAddress: '',
  })
  const [bankSubmitting, setBankSubmitting] = useState(false)

  // State for Department Resubmit modal
  const [resubmitTarget, setResubmitTarget] = useState(null)
  const [resubmitSubmitting, setResubmitSubmitting] = useState(false)

  // State for HoD Resubmit modal
  const [hodResubmitOpen, setHodResubmitOpen] = useState(false)
  const [hodResubmitSubmitting, setHodResubmitSubmitting] = useState(false)

  // State for "Add More" modals
  const [addOfficeOpen, setAddOfficeOpen] = useState(false)
  const [selectedOfficeId, setSelectedOfficeId] = useState('')
  const [addOfficeSubmitting, setAddOfficeSubmitting] = useState(false)

  const [addLabsOpen, setAddLabsOpen] = useState(false)
  const [selectedLabIds, setSelectedLabIds] = useState([])
  const [addLabsSubmitting, setAddLabsSubmitting] = useState(false)

  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState(new Date())

  // State for Cancel Request dialog
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [cancelSubmitting, setCancelSubmitting] = useState(false)

  // 1. Fetch Bank Details
  const {
    data: bankDetails,
    isLoading: bankLoading,
    isError: bankError,
    error: bankErrorObj,
    refetch: refetchBank,
  } = useQuery({
    queryKey: ['student', 'bank-details'],
    queryFn: async () => {
      try {
        return await studentApi.getBankDetails()
      } catch (err) {
        if (err.response?.status === 404) return null
        throw err
      }
    },
    staleTime: 60000,
  })

  // 2. Fetch Active Clearance Request with 30s auto-refresh
  const {
    data: currentRequest,
    isLoading: requestLoading,
    isError: requestError,
    error: requestErrorObj,
    isRefetching: requestRefetching,
    refetch: refetchRequest,
  } = useQuery({
    queryKey: ['student', 'current-request'],
    queryFn: async () => {
      try {
        const res = await studentApi.getCurrentRequest()
        setLastRefreshed(new Date())
        return res
      } catch (err) {
        if (err.response?.status === 404) return null
        throw err
      }
    },
    refetchInterval: 30000,
  })

  // 3. Fetch Additional Facilities for "Add an additional facility"
  const { data: assignedOnlyDepts = [] } = useQuery({
    queryKey: ['departments', 'additional-facilities'],
    queryFn: () => departmentApi.getAdditionalFacilities(),
    enabled: addOfficeOpen,
  })

  // 4. Fetch Lab Catalog for "Add Lab Subjects"
  const { data: labCatalogData } = useQuery({
    queryKey: ['student', 'lab-catalog'],
    queryFn: () => studentApi.getLabCatalog(),
    enabled: addLabsOpen,
  })

  // Pre-fill holder name when bank details dialog opens
  useEffect(() => {
    if (bankDetails) {
      setBankForm({
        accountHolderName: bankDetails.account_holder_name || user?.full_name || '',
        ifscCode: bankDetails.ifsc_code || '',
        bankAddress: bankDetails.bank_address || '',
        accountNumber: '',
      })
    } else if (user?.full_name) {
      setBankForm((prev) => ({ ...prev, accountHolderName: user.full_name }))
    }
  }, [bankDetails, user])

  // Bank Details submission
  const handleBankSubmit = async (e) => {
    e.preventDefault()
    const { accountNumber, ifscCode, accountHolderName, bankAddress } = bankForm

    const cleanAccount = accountNumber.trim()
    const cleanIfsc = ifscCode.trim().toUpperCase()
    const cleanHolder = accountHolderName.trim()
    const cleanAddress = bankAddress.trim()

    if (!/^\d{9,18}$/.test(cleanAccount)) {
      toast.error('Account number must be digits only, between 9 and 18 characters.')
      return
    }

    if (!/^[A-Z]{4}0[A-Z0-9]{6}$/.test(cleanIfsc)) {
      toast.error('IFSC code must match standard format: 4 letters, 0, then 6 alphanumeric characters.')
      return
    }

    if (!cleanHolder) {
      toast.error('Account holder name is required.')
      return
    }

    if (!cleanAddress) {
      toast.error('Bank branch address is required.')
      return
    }

    setBankSubmitting(true)
    try {
      await studentApi.updateBankDetails({
        accountNumber: cleanAccount,
        ifscCode: cleanIfsc,
        accountHolderName: cleanHolder,
        bankAddress: cleanAddress,
      })
      toast.success('Bank details saved securely.')
      setBankModalOpen(false)
      refetchBank()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to update bank details.'
      toast.error(msg)
    } finally {
      setBankSubmitting(false)
    }
  }

  // Handle Department Resubmission
  const handleConfirmResubmitDepartment = async () => {
    if (!resubmitTarget || !currentRequest) return

    setResubmitSubmitting(true)
    try {
      await studentApi.resubmitDepartment(currentRequest.id, resubmitTarget.department_id)
      toast.success(`Resubmitted review to ${resubmitTarget.department_name}.`)
      setResubmitTarget(null)
      refetchRequest()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to resubmit to department.'
      toast.error(msg)
    } finally {
      setResubmitSubmitting(false)
    }
  }

  // Handle HoD Resubmission
  const handleConfirmResubmitHod = async () => {
    if (!currentRequest) return

    setHodResubmitSubmitting(true)
    try {
      await studentApi.resubmitToHod(currentRequest.id)
      toast.success('Resubmitted clearance for Chairperson / HoD review.')
      setHodResubmitOpen(false)
      refetchRequest()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to resubmit to HoD.'
      toast.error(msg)
    } finally {
      setHodResubmitSubmitting(false)
    }
  }

  // Handle Add Department
  const handleConfirmAddDepartment = async () => {
    if (!selectedOfficeId || !currentRequest) return

    setAddOfficeSubmitting(true)
    try {
      await studentApi.addDepartment(currentRequest.id, Number(selectedOfficeId))
      toast.success('Office added to clearance dossier successfully.')
      setAddOfficeOpen(false)
      setSelectedOfficeId('')
      refetchRequest()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to add office to request.'
      toast.error(msg)
    } finally {
      setAddOfficeSubmitting(false)
    }
  }

  // Handle Add Lab Courses
  const handleConfirmAddLabs = async () => {
    if (!selectedLabIds.length || !currentRequest) return

    setAddLabsSubmitting(true)
    try {
      await studentApi.declareLabCourses(currentRequest.id, selectedLabIds)
      toast.success('Lab subjects added successfully.')
      setAddLabsOpen(false)
      setSelectedLabIds([])
      refetchRequest()
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        (err.response?.status === 404 || err.response?.status === 405
          ? 'Backend endpoint POST /student/requests/{id}/lab-courses is not available (reported as API gap).'
          : 'Failed to add lab courses.')
      toast.error(msg)
    } finally {
      setAddLabsSubmitting(false)
    }
  }

  // Handle PDF Certificate Download as Blob with Bearer token
  const handleDownloadCertificate = async () => {
    if (!currentRequest) return

    setDownloadingPdf(true)
    try {
      const blob = await studentApi.downloadCertificatePdf(currentRequest.id)
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `SVSU_NoDues_Certificate_${currentRequest.id}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Clearance certificate downloaded successfully.')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to download certificate PDF.'
      toast.error(msg)
    } finally {
      setDownloadingPdf(false)
    }
  }

  const handleCancelRequest = async (e) => {
    e?.preventDefault?.()
    if (!cancelReason.trim()) {
      toast.error('A reason for cancellation is mandatory.')
      return
    }
    if (!currentRequest) return

    setCancelSubmitting(true)
    try {
      await studentApi.cancelRequest(currentRequest.id, cancelReason.trim())
      toast.success('Clearance request cancelled successfully.')
      setCancelDialogOpen(false)
      setCancelReason('')
      refetchRequest()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to cancel request.'
      toast.error(msg)
    } finally {
      setCancelSubmitting(false)
    }
  }

  // Progress calculations
  const approvals = currentRequest?.approvals || []
  const approvedCount = approvals.filter((a) => a.status === 'APPROVED').length
  const totalDepts = approvals.length
  const progressPercent = totalDepts > 0 ? Math.round((approvedCount / totalDepts) * 100) : 0
  const hasRejectedDepts = approvals.some((a) => a.status === 'REJECTED')

  // Student can cancel ONLY while every approval is still PENDING
  const canCancel =
    currentRequest &&
    currentRequest.status !== 'CANCELLED' &&
    currentRequest.status !== 'CLEARED' &&
    currentRequest.status !== 'REFUND_VERIFIED' &&
    approvals.length > 0 &&
    approvals.every((a) => a.status === 'PENDING')

  // HoD rejection banner condition: ACTION_NEEDED + hod_remarks + no department is rejected
  const showHodBanner =
    currentRequest?.status === 'ACTION_NEEDED' &&
    currentRequest?.hod_remarks &&
    !hasRejectedDepts

  // Can show "Add more" panel: when request is active and not CLEARED or REFUND_VERIFIED or CANCELLED
  const canAddMore =
    currentRequest &&
    currentRequest.status !== 'CLEARED' &&
    currentRequest.status !== 'REFUND_VERIFIED' &&
    currentRequest.status !== 'CANCELLED'

  // Filter out departments already on the request for the "Add Office" select
  const existingDeptIds = new Set(approvals.map((a) => a.department_id))
  const availableToAddOffices = assignedOnlyDepts.filter(
    (dept) => !existingDeptIds.has(dept.id)
  )

  return (
    <AppShell>
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
                Student Clearance Dossier
              </h1>
              {requestRefetching && (
                <RotateCw className="w-4 h-4 text-zinc-400 animate-spin" />
              )}
            </div>
            <p className="text-xs sm:text-sm text-zinc-500">
              {user?.full_name || 'Student'} • {user?.roster?.registration_number || 'Enrolled Student'} •{' '}
              {user?.roster?.programme_name || 'Undergraduate Programme'}
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-zinc-400 hidden sm:inline">
              Refreshed: {lastRefreshed.toLocaleTimeString()}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetchRequest()
                refetchBank()
                toast.info('Status refreshed.')
              }}
              className="text-xs gap-1.5 h-8 border-border hover:bg-zinc-100"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Sync Now
            </Button>
          </div>
        </div>

        {/* API Error State with Retry Button */}
        {(bankError || requestError) && (
          <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-destructive">
            <div className="flex items-center gap-2.5 text-sm">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-semibold text-zinc-900 text-xs sm:text-sm">Unable to load clearance data</p>
                <p className="text-xs text-zinc-600 mt-0.5">
                  {requestErrorObj?.response?.data?.detail ||
                    bankErrorObj?.response?.data?.detail ||
                    'Could not communicate with the university clearance service.'}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (bankError) refetchBank()
                if (requestError) refetchRequest()
              }}
              className="border-destructive/30 hover:bg-destructive/10 text-xs text-destructive shrink-0"
            >
              <RotateCw className="w-3.5 h-3.5 mr-1.5" />
              Retry Connection
            </Button>
          </div>
        )}

        {/* Loading Skeletons */}
        {requestLoading && bankLoading ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((n) => (
                <Skeleton key={n} className="h-28 rounded-xl bg-zinc-100" />
              ))}
            </div>
            <Skeleton className="h-64 rounded-xl bg-zinc-100" />
          </div>
        ) : (
          <>
            {/* Stat Strip / Summary Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Stat 1: Lifecycle Status */}
              <div className="rounded-xl border border-border bg-white p-4 shadow-2xs space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 block">
                  Clearance Status
                </span>
                <div className="pt-1">
                  {currentRequest ? (
                    <StatusBadge status={currentRequest.status} />
                  ) : (
                    <Badge variant="outline" className="bg-zinc-50 text-zinc-600 border-zinc-200 text-xs">
                      Not Applied
                    </Badge>
                  )}
                </div>
                <p className="text-[11px] text-zinc-500 pt-1 leading-snug">
                  {currentRequest
                    ? `Request #${currentRequest.id} active`
                    : 'Submit application to begin review'}
                </p>
              </div>

              {/* Stat 2: Department Clearances Ratio */}
              <div className="rounded-xl border border-border bg-white p-4 shadow-2xs space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 block">
                  Department Progress
                </span>
                <div className="text-lg font-bold font-mono text-zinc-900 pt-0.5">
                  {approvedCount} / {totalDepts || 0} Approved
                </div>
                <Progress value={progressPercent} className="h-1.5 bg-zinc-100 mt-1" />
              </div>

              {/* Stat 3: Refund Bank Status */}
              <div className="rounded-xl border border-border bg-white p-4 shadow-2xs space-y-1 flex flex-col justify-between">
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 block">
                    Security Deposit Refund
                  </span>
                  <div className="text-sm font-semibold font-mono text-zinc-900 pt-0.5 truncate">
                    {bankDetails ? bankDetails.account_number_masked : 'No Bank Registered'}
                  </div>
                </div>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-[11px] text-zinc-500">
                    {bankDetails ? bankDetails.ifsc_code : 'Required for apply'}
                  </span>
                  <button
                    onClick={() => setBankModalOpen(true)}
                    className="text-[11px] font-semibold text-black hover:underline"
                  >
                    {bankDetails ? 'Edit' : 'Register'}
                  </button>
                </div>
              </div>

              {/* Stat 4: Fast Action Card */}
              <div className="rounded-xl border border-border bg-white p-4 shadow-2xs space-y-1 flex flex-col justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 block">
                  Next Step
                </span>
                <div className="text-xs font-medium text-zinc-800 leading-snug">
                  {!bankDetails
                    ? 'Register bank details or start application'
                    : !currentRequest
                    ? 'Submit your clearance declarations'
                    : hasRejectedDepts
                    ? 'Resolve dues with flagged department'
                    : showHodBanner
                    ? 'Address Chairperson requirement'
                    : currentRequest.status === 'CLEARED' || currentRequest.status === 'REFUND_VERIFIED'
                    ? 'Official certificate ready for download'
                    : 'Awaiting departmental sign-offs'}
                </div>
                <div className="pt-1">
                  <span className="text-[10px] font-mono text-zinc-400">
                    SVSU Clearance Protocol
                  </span>
                </div>
              </div>
            </div>

            {/* HoD Action Banner (When HoD rejected with remarks & all departments cleared) */}
            {showHodBanner && (
              <Alert className="bg-amber-50/90 border-amber-300 text-amber-950 p-4">
                <ShieldAlert className="h-5 w-5 text-amber-700 mt-0.5" />
                <div className="flex-1 ml-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <AlertTitle className="text-sm font-semibold tracking-tight">
                        Action Required by Academic Chairperson (HoD)
                      </AlertTitle>
                      <AlertDescription className="text-xs mt-1 text-amber-900 leading-relaxed">
                        The Chairperson reviewed your clearance dossier and flagged:{' '}
                        <span className="font-semibold underline underline-offset-2">
                          "{currentRequest.hod_remarks}"
                        </span>
                        . Once addressed, resubmit directly for Chairperson sign-off.
                      </AlertDescription>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => setHodResubmitOpen(true)}
                      className="bg-amber-900 hover:bg-amber-950 text-white text-xs shrink-0"
                    >
                      Resubmit to HoD
                    </Button>
                  </div>
                </div>
              </Alert>
            )}

            {/* Refund Summary (when provided by API) */}
            {Boolean(
              currentRequest?.refund_status ||
              (currentRequest?.deposit_amount !== null && currentRequest?.deposit_amount !== undefined) ||
              currentRequest?.refund
            ) && (
              <Card className="border-border bg-white shadow-2xs">
                <CardHeader className="p-5 pb-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Landmark className="w-4 h-4 text-zinc-700" />
                      <CardTitle className="text-sm font-bold text-zinc-950">
                        Security Deposit Refund Summary
                      </CardTitle>
                    </div>
                    {currentRequest.refund_status && (
                      <Badge
                        variant="outline"
                        className={`text-[10px] uppercase font-mono tracking-wider ${
                          currentRequest.refund_status === 'PROCESSED'
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                            : currentRequest.refund_status === 'VERIFIED'
                            ? 'bg-blue-50 text-blue-800 border-blue-200'
                            : 'bg-amber-50 text-amber-800 border-amber-200'
                        }`}
                      >
                        Refund: {currentRequest.refund_status.replace(/_/g, ' ')}
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="p-5 pt-0 space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                    <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200">
                      <span className="text-[11px] text-zinc-500 block">Original Deposit</span>
                      <span className="text-sm font-bold font-mono text-zinc-900">
                        ₹{currentRequest.deposit_amount ?? currentRequest.refund?.security_deposit_amount ?? '0.00'}
                      </span>
                    </div>
                    <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200">
                      <span className="text-[11px] text-zinc-500 block">Deductions Applied</span>
                      <span className="text-sm font-bold font-mono text-rose-600">
                        -₹{currentRequest.deductions ?? currentRequest.refund?.deductions ?? '0.00'}
                      </span>
                    </div>
                    <div className="p-3 rounded-lg bg-emerald-50/60 border border-emerald-200">
                      <span className="text-[11px] text-emerald-800 font-semibold block">Net Refund Amount</span>
                      <span className="text-sm font-bold font-mono text-emerald-700">
                        ₹{currentRequest.final_amount ?? currentRequest.refund?.final_amount ?? '0.00'}
                      </span>
                    </div>
                  </div>

                  {currentRequest.payment_reference && (
                    <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        <div>
                          <span className="font-semibold text-zinc-900 block">
                            Bank Disbursement Processed
                          </span>
                          <span className="text-[11px] text-zinc-500">
                            Transferred to registered bank account {bankDetails?.account_number ? `(${bankDetails.account_number})` : ''}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 font-mono text-xs bg-white px-2.5 py-1 rounded border border-zinc-200 text-zinc-800">
                        <span className="text-zinc-400 font-sans text-[10px] uppercase font-semibold">UTR / Ref:</span>
                        <span className="font-bold">{currentRequest.payment_reference}</span>
                      </div>
                    </div>
                  )}

                  {!currentRequest.payment_reference && currentRequest.refund_status === 'VERIFIED' && (
                    <p className="text-[11px] text-zinc-500 italic">
                      Deductions verified by Accounts Branch. Electronic bank transfer is queued for disbursement.
                    </p>
                  )}

                  {!currentRequest.payment_reference && currentRequest.refund_status === 'PENDING_VERIFICATION' && (
                    <p className="text-[11px] text-zinc-500 italic">
                      Clearance complete. Accounts Branch is currently auditing library/hostel records against deposit ledger.
                    </p>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Application Card (When Not Submitted) OR Step Timeline (When Submitted) */}
            {!currentRequest ? (
              <Card className="border-border bg-white shadow-card">
                <CardHeader className="p-6 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-black text-white flex items-center justify-center">
                      <FileCheck2 className="w-5 h-5" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-bold">
                        Apply for Digital No-Dues Clearance
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Declare your residence status, lab subjects, and applicable offices using the step-by-step wizard.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="p-6 pt-0 space-y-4 text-xs text-zinc-600">
                  <p className="leading-relaxed">
                    Under the updated university clearance workflow, your clearance reviews are determined by your own declarations:
                    hostel status, specific lab subjects used in your academic department, and any additional facilities.
                  </p>

                  {!bankDetails && (
                    <Alert className="bg-amber-50 border-amber-200 text-amber-900 py-3">
                      <AlertTriangle className="h-4 w-4 text-amber-800" />
                      <AlertTitle className="text-xs font-semibold">Bank Details Prerequisite</AlertTitle>
                      <AlertDescription className="text-xs mt-0.5">
                        You can register your bank account directly in Step 1 of the application wizard, or register it now.
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>

                <CardFooter className="p-6 pt-0 border-t border-zinc-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <span className="text-xs text-zinc-400">
                    Shri Vishwakarma Skill University • Digital Clearance
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => navigate('/student/apply')}
                      className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-2 font-semibold shadow-xs"
                    >
                      <Send className="w-3.5 h-3.5" />
                      Apply for Clearance
                      <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
                    </Button>
                  </div>
                </CardFooter>
              </Card>
            ) : (
              /* Clearance Progress & Pipeline Card */
              <Card className="border-border bg-white shadow-card">
                <CardHeader className="p-6 pb-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base font-bold">
                        Clearance Application Progress
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Request ID #{currentRequest.id} • Submitted on{' '}
                        {new Date(currentRequest.submitted_at).toLocaleDateString()}
                      </CardDescription>
                    </div>

                    <div className="flex items-center gap-2">
                      {canCancel && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCancelDialogOpen(true)}
                          className="text-xs text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 h-8 gap-1.5"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          Cancel Request
                        </Button>
                      )}

                      {(currentRequest.status === 'CLEARED' ||
                        currentRequest.status === 'REFUND_VERIFIED') && (
                        <Button
                          onClick={handleDownloadCertificate}
                          disabled={downloadingPdf}
                          className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-1.5 h-9 font-semibold shadow-xs"
                        >
                          <Download className="w-3.5 h-3.5" />
                          {downloadingPdf ? 'Generating PDF...' : 'Download Certificate (PDF)'}
                        </Button>
                      )}
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="p-6 pt-0 space-y-4">
                  {currentRequest.status === 'CANCELLED' && (
                    <div className="p-4 rounded-xl border border-zinc-200 bg-zinc-50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <StatusBadge status="CANCELLED" />
                          <span className="text-xs font-semibold text-zinc-900">Application Cancelled</span>
                        </div>
                        <p className="text-xs text-zinc-600 leading-relaxed">
                          This clearance application was cancelled before any office decided. You can apply again anytime with updated declarations.
                        </p>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => navigate('/student/apply')}
                        className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold h-8 gap-1.5 shrink-0"
                      >
                        Apply Again
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  )}

                  <StepTimeline
                    status={currentRequest.status}
                    approvals={currentRequest.approvals}
                    hodRemarks={currentRequest.hod_remarks}
                  />
                </CardContent>
              </Card>
            )}

            {/* "Add More" Panel (When request is active and not CLEARED/REFUND_VERIFIED) */}
            {canAddMore && (
              <Card className="border-border bg-zinc-50/50 shadow-2xs">
                <CardHeader className="p-5 pb-3">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <PlusCircle className="w-4 h-4 text-zinc-900" />
                        <CardTitle className="text-sm font-bold text-zinc-950">
                          Add Further Facilities or Labs
                        </CardTitle>
                      </div>
                      <CardDescription className="text-xs mt-1 text-zinc-600">
                        Adding an office asks only that office; a request already with the HoD returns to department review.
                      </CardDescription>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setAddLabsOpen(true)}
                        className="text-xs gap-1.5 h-8 bg-white border-zinc-200 text-zinc-800 hover:bg-zinc-100"
                      >
                        <FlaskConical className="w-3.5 h-3.5" />
                        Add a lab or workshop
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setAddOfficeOpen(true)}
                        className="text-xs gap-1.5 h-8 bg-white border-zinc-200 text-zinc-800 hover:bg-zinc-100"
                      >
                        <Building2 className="w-3.5 h-3.5" />
                        Add an additional facility
                      </Button>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            )}

            {/* Department Approvals Grid */}
            {currentRequest && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h2 className="font-heading text-lg font-bold tracking-tight text-zinc-950">
                      Department Clearance Reviews
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Reviews are evaluated in parallel. Rejections require specific dues resolution and individual resubmission.
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs font-mono bg-zinc-50 py-1 self-start sm:self-auto">
                    {approvedCount} of {totalDepts} Cleared
                  </Badge>
                </div>

                {approvals.length === 0 ? (
                  <EmptyState
                    title="No department reviews assigned"
                    description="No departmental reviews have been linked to this clearance request."
                  />
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {approvals.map((item) => {
                      const isRejected = item.status === 'REJECTED'
                      const isApproved = item.status === 'APPROVED'

                      return (
                        <Card
                          key={item.id}
                          className={`border bg-white transition-all shadow-2xs hover:shadow-card ${
                            isRejected
                              ? 'border-rose-300 ring-1 ring-rose-200'
                              : isApproved
                              ? 'border-border'
                              : 'border-border'
                          }`}
                        >
                          <CardHeader className="p-5 pb-3">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <CardTitle className="text-sm font-bold text-zinc-900 leading-tight">
                                  {item.department_name}
                                </CardTitle>
                                <div className="mt-1">
                                  <Badge variant="outline" className="text-[10px] font-medium bg-zinc-50 border-zinc-200 text-zinc-700">
                                    {item.department_label || (item.department_category ? item.department_category.replace(/_/g, ' ') : 'Department')}
                                  </Badge>
                                </div>
                              </div>
                              <StatusBadge status={item.status} size="sm" />
                            </div>
                          </CardHeader>

                          <CardContent className="p-5 pt-0 space-y-3 text-xs">
                            {/* Department Added Notice (e.g. Added by your department: reason) */}
                            {item.added_reason && (
                              <div className="rounded-md bg-amber-50/80 border border-amber-200 p-2 text-[11px] text-amber-950">
                                <span className="font-semibold">Added by your department:</span>{' '}
                                {item.added_reason}
                              </div>
                            )}

                            {/* Declared Subjects if returned by API */}
                            {item.declared_subjects && item.declared_subjects.length > 0 && (
                              <div className="space-y-1">
                                <span className="text-[11px] font-semibold text-zinc-600 block">
                                  Declared Subjects:
                                </span>
                                <div className="flex flex-wrap gap-1">
                                  {item.declared_subjects.map((sub, i) => (
                                    <Badge
                                      key={i}
                                      variant="outline"
                                      className="text-[10px] font-mono bg-zinc-50 border-zinc-200 text-zinc-700"
                                    >
                                      {typeof sub === 'string' ? sub : sub.course_code || sub.course_name}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Current Remarks */}
                            {item.remarks && (
                              <div
                                className={`rounded-lg p-2.5 text-xs ${
                                  isRejected
                                    ? 'bg-rose-50 border border-rose-200 text-rose-900 font-medium'
                                    : 'bg-zinc-50 border border-zinc-200 text-zinc-700'
                                }`}
                              >
                                <div className="font-semibold text-[11px] mb-0.5">
                                  {isRejected ? 'Action Required / Pending Due:' : 'Remarks:'}
                                </div>
                                <p className="leading-snug">{item.remarks}</p>
                              </div>
                            )}

                            {/* Visually Separate Previous Rejection Reason Callout */}
                            {item.previous_remarks && (
                              <div className="rounded-lg p-2.5 bg-zinc-50 border border-zinc-200/80 text-zinc-600 text-xs space-y-1">
                                <div className="flex items-center gap-1.5 font-semibold text-[11px] text-zinc-700">
                                  <History className="w-3.5 h-3.5 text-zinc-400" />
                                  <span>Previous Rejection Reason:</span>
                                </div>
                                <p className="text-[11px] italic leading-snug">
                                  "{item.previous_remarks}"
                                </p>
                              </div>
                            )}

                            {/* Metadata Strip */}
                            <div className="flex flex-col gap-1 text-[11px] text-muted-foreground pt-1 border-t border-zinc-100">
                              <div className="flex items-center justify-between">
                                <span>
                                  {item.decided_at
                                    ? `Decided: ${new Date(item.decided_at).toLocaleDateString()}`
                                    : 'Awaiting officer sign-off'}
                                </span>
                                {item.resubmission_count > 0 && (
                                  <Badge variant="outline" className="text-[10px] bg-zinc-50 font-mono py-0">
                                    Resubmitted {item.resubmission_count}x
                                  </Badge>
                                )}
                              </div>
                              {item.decided_by_name && (
                                <div className="text-[11px] text-zinc-600 font-medium">
                                  Officer: <span className="text-zinc-900">{item.decided_by_name}</span>
                                </div>
                              )}
                            </div>
                          </CardContent>

                          {/* Resubmit button: ONLY for REJECTED items per requirement */}
                          {isRejected && (
                            <CardFooter className="p-5 pt-0">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setResubmitTarget(item)}
                                className="w-full text-xs text-rose-800 border-rose-300 hover:bg-rose-50 hover:text-rose-900 gap-1.5 font-medium h-9"
                              >
                                <RotateCw className="w-3.5 h-3.5" />
                                Resubmit to this Department
                              </Button>
                            </CardFooter>
                          )}
                        </Card>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Dialog: Add an Additional Facility */}
      <Dialog open={addOfficeOpen} onOpenChange={setAddOfficeOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <DialogHeader className="pb-3">
            <DialogTitle className="font-heading font-bold text-base">
              Add an Additional Facility
            </DialogTitle>
            <DialogDescription className="text-xs">
              Select an additional facility or center to add to your clearance reviews.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="officeSelect" className="text-xs font-semibold text-zinc-800">
                Facility / Center
              </Label>
              {availableToAddOffices.length === 0 ? (
                <p className="text-xs text-zinc-500 italic py-2">
                  All available additional facilities have already been added to your request.
                </p>
              ) : (
                <Select value={selectedOfficeId} onValueChange={setSelectedOfficeId}>
                  <SelectTrigger id="officeSelect" className="text-xs">
                    <SelectValue placeholder="Select a facility to add..." />
                  </SelectTrigger>
                  <SelectContent>
                    {availableToAddOffices.map((dept) => {
                      const isAvailable = dept.has_active_officer !== false
                      return (
                        <SelectItem
                          key={dept.id}
                          value={String(dept.id)}
                          disabled={!isAvailable}
                          className="text-xs"
                        >
                          {dept.name} {dept.code ? `(${dept.code})` : ''}
                          {!isAvailable ? ' (Not available yet)' : ''}
                        </SelectItem>
                      )
                    })}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="rounded-lg bg-zinc-50 border border-zinc-200 p-2.5 text-xs text-zinc-600 flex items-start gap-2">
              <Info className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                Adding a facility asks only that office; a request already with the HoD returns to department review.
              </p>
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
              type="button"
              size="sm"
              disabled={!selectedOfficeId || addOfficeSubmitting}
              onClick={handleConfirmAddDepartment}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              {addOfficeSubmitting ? 'Adding...' : 'Add Facility'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Add a Lab or Workshop */}
      <Dialog open={addLabsOpen} onOpenChange={setAddLabsOpen}>
        <DialogContent className="sm:max-w-lg bg-white p-6 max-h-[85vh] flex flex-col">
          <DialogHeader className="pb-3">
            <DialogTitle className="font-heading font-bold text-base">
              Add a Lab or Workshop
            </DialogTitle>
            <DialogDescription className="text-xs">
              Select additional laboratory subjects or workshops to add to your clearance declarations.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 overflow-y-auto flex-1 pr-1 text-xs">
            <div className="rounded-lg bg-zinc-50 border border-zinc-200 p-2.5 text-zinc-600 flex items-start gap-2">
              <Info className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                Adding lab subjects links them to your academic department review.
              </p>
            </div>

            {(!labCatalogData || !(labCatalogData.lab_courses || labCatalogData.courses) || (labCatalogData.lab_courses || labCatalogData.courses).length === 0) ? (
              <p className="text-xs text-zinc-500 italic py-4 text-center">
                No lab courses cataloged for your academic programme.
              </p>
            ) : (
              <div className="space-y-2">
                {(labCatalogData.lab_courses || labCatalogData.courses).map((course) => {
                  const isChecked = selectedLabIds.includes(course.id)
                  const code = course.code || course.course_code
                  const name = course.name || course.course_name
                  const signingOffice = course.lab_department_name || course.signing_department_name
                  return (
                    <label
                      key={course.id}
                      className={`flex items-start gap-2.5 p-2.5 rounded-lg border transition-all cursor-pointer ${
                        isChecked
                          ? 'border-zinc-950 bg-zinc-50'
                          : 'border-zinc-200 hover:border-zinc-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedLabIds([...selectedLabIds, course.id])
                          } else {
                            setSelectedLabIds(selectedLabIds.filter((id) => id !== course.id))
                          }
                        }}
                        className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-black focus:ring-black accent-zinc-900 cursor-pointer"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-zinc-900">
                            {code}
                          </span>
                          <span className="font-medium text-zinc-800 truncate">
                            {name}
                          </span>
                        </div>
                        {signingOffice && (
                          <div className="text-[11px] text-zinc-500 mt-0.5">
                            Signing Office: {signingOffice}
                          </div>
                        )}
                      </div>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100 shrink-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAddLabsOpen(false)}
              className="text-xs h-9"
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={selectedLabIds.length === 0 || addLabsSubmitting}
              onClick={handleConfirmAddLabs}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              {addLabsSubmitting ? 'Adding...' : `Add Selected (${selectedLabIds.length})`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Register / Update Bank Details */}
      <Dialog open={bankModalOpen} onOpenChange={setBankModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleBankSubmit}>
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                {bankDetails ? 'Update Security Deposit Refund Account' : 'Register Refund Bank Account'}
              </DialogTitle>
              <DialogDescription className="text-xs">
                Provide valid Indian banking details. Account numbers are securely masked in all public views.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="accountHolderName" className="text-xs font-semibold text-zinc-800">
                  Beneficiary Account Holder Name
                </Label>
                <Input
                  id="accountHolderName"
                  value={bankForm.accountHolderName}
                  onChange={(e) => setBankForm({ ...bankForm, accountHolderName: e.target.value })}
                  placeholder="Official name matching bank passbook"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="accountNumber" className="text-xs font-semibold text-zinc-800">
                  Bank Account Number (digits only, 9 to 18 digits)
                </Label>
                <Input
                  id="accountNumber"
                  value={bankForm.accountNumber}
                  onChange={(e) => setBankForm({ ...bankForm, accountNumber: e.target.value })}
                  placeholder="e.g. 123456789012"
                  pattern="^\d{9,18}$"
                  required
                  autoComplete="off"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ifscCode" className="text-xs font-semibold text-zinc-800">
                  Bank IFSC Code (e.g. SBIN0001234)
                </Label>
                <Input
                  id="ifscCode"
                  value={bankForm.ifscCode}
                  onChange={(e) => setBankForm({ ...bankForm, ifscCode: e.target.value.toUpperCase() })}
                  placeholder="e.g. SBIN0001234"
                  pattern="^[A-Z]{4}0[A-Z0-9]{6}$"
                  className="uppercase font-mono"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="bankAddress" className="text-xs font-semibold text-zinc-800">
                  Bank Branch Name & Address
                </Label>
                <Input
                  id="bankAddress"
                  value={bankForm.bankAddress}
                  onChange={(e) => setBankForm({ ...bankForm, bankAddress: e.target.value })}
                  placeholder="e.g. State Bank of India, SVSU Campus Branch, Palwal"
                  required
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setBankModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={bankSubmitting}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {bankSubmitting ? 'Saving Details...' : 'Save Bank Details'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* AlertDialog: Confirm Resubmission to Department */}
      <AlertDialog
        open={Boolean(resubmitTarget)}
        onOpenChange={(open) => !open && setResubmitTarget(null)}
      >
        <AlertDialogContent className="bg-white p-6">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
              Confirm Resubmission to {resubmitTarget?.department_name}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs space-y-2 text-zinc-600">
              <p>
                Have you resolved the flagged due or requirement with{' '}
                <strong>{resubmitTarget?.department_name}</strong>?
              </p>
              {resubmitTarget?.remarks && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs font-medium">
                  Reported issue: "{resubmitTarget.remarks}"
                </div>
              )}
              <p>
                Resubmitting marks this department as <strong>PENDING</strong> and alerts the officer for re-evaluation.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmResubmitDepartment}
              disabled={resubmitSubmitting}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              {resubmitSubmitting ? 'Resubmitting...' : 'Yes, Resubmit'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* AlertDialog: Confirm Resubmission to HoD */}
      <AlertDialog
        open={hodResubmitOpen}
        onOpenChange={setHodResubmitOpen}
      >
        <AlertDialogContent className="bg-white p-6">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
              Resubmit for Chairperson (HoD) Final Review
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs space-y-2 text-zinc-600">
              <p>
                Have you satisfied the Chairperson's required action?
              </p>
              {currentRequest?.hod_remarks && (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium">
                  Chairperson requirement: "{currentRequest.hod_remarks}"
                </div>
              )}
              <p>
                This will move your application back into the Chairperson's active review queue (<strong>HOD_REVIEW</strong>).
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmResubmitHod}
              disabled={hodResubmitSubmitting}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              {hodResubmitSubmitting ? 'Resubmitting...' : 'Confirm Resubmission to HoD'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {/* AlertDialog: Cancel Clearance Application */}
      <AlertDialog
        open={cancelDialogOpen}
        onOpenChange={setCancelDialogOpen}
      >
        <AlertDialogContent className="bg-white p-6 max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
              Cancel Clearance Application?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs space-y-2 text-zinc-600">
              <p>
                You can cancel only before any office has decided. Once cancelled, this application is closed.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-2 space-y-1.5">
            <Label htmlFor="studentCancelReason" className="text-xs font-semibold text-zinc-800">
              Reason for Cancellation <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="studentCancelReason"
              placeholder="e.g. Need to re-declare lab subjects or correct declarations"
              rows={3}
              className="text-xs resize-none"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              required
            />
          </div>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel
              disabled={cancelSubmitting}
              onClick={() => {
                setCancelDialogOpen(false)
                setCancelReason('')
              }}
              className="text-xs h-9"
            >
              Keep Application
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelRequest}
              disabled={cancelSubmitting || !cancelReason.trim()}
              className="bg-red-600 text-white hover:bg-red-700 text-xs h-9 font-semibold"
            >
              {cancelSubmitting ? 'Cancelling...' : 'Confirm Cancellation'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  )
}

export default StudentDashboard
