import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { studentApi } from '@/api/student'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { StatusBadge } from '@/components/StatusBadge'
import { StepTimeline } from '@/components/StepTimeline'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
} from 'lucide-react'

const MOCK_BANK_DETAILS = {
  account_number_masked: '••••••••4192',
  ifsc_code: 'SBIN0001234',
  account_holder_name: 'Aarav Sharma',
  bank_address: 'State Bank of India, SVSU Campus Branch',
}

const MOCK_ACTIVE_REQUEST = {
  id: 104,
  status: 'SUBMITTED',
  created_at: '2026-10-24T10:00:00Z',
  remarks: 'Final semester clearance for B.Tech Degree Conferment',
  hod_remarks: null,
  approvals: [
    {
      id: 1,
      department_id: 1,
      department_name: 'Central Library',
      status: 'APPROVED',
      remarks: 'All 4 borrowed textbooks returned, no outstanding overdue fines.',
      updated_at: '2026-10-24T11:20:00Z',
    },
    {
      id: 2,
      department_id: 2,
      department_name: 'Sports Office',
      status: 'APPROVED',
      remarks: 'Badminton equipment and gym locker cleared.',
      updated_at: '2026-10-24T11:45:00Z',
    },
    {
      id: 3,
      department_id: 3,
      department_name: 'Hostel Office',
      status: 'PENDING',
      remarks: null,
      updated_at: null,
    },
    {
      id: 4,
      department_id: 4,
      department_name: 'Mess / Cafeteria',
      status: 'APPROVED',
      remarks: 'Mess bill for October 2026 reconciled and settled.',
      updated_at: '2026-10-24T12:05:00Z',
    },
    {
      id: 5,
      department_id: 5,
      department_name: 'Laboratories',
      status: 'APPROVED',
      remarks: 'Hardware lab kit and keys handed over to lab assistant.',
      updated_at: '2026-10-24T13:10:00Z',
    },
    {
      id: 6,
      department_id: 6,
      department_name: 'Computer Centre & IT',
      status: 'APPROVED',
      remarks: 'Campus email archive initiated, VPN account suspended.',
      updated_at: '2026-10-24T14:30:00Z',
    },
    {
      id: 7,
      department_id: 7,
      department_name: 'Transport Department',
      status: 'APPROVED',
      remarks: 'Bus pass surrendered.',
      updated_at: '2026-10-24T14:55:00Z',
    },
    {
      id: 8,
      department_id: 8,
      department_name: 'Training & Placement Cell',
      status: 'APPROVED',
      remarks: 'Mandatory graduate exit survey submitted.',
      updated_at: '2026-10-24T15:20:00Z',
    },
    {
      id: 9,
      department_id: 9,
      department_name: 'Alumni Association',
      status: 'APPROVED',
      remarks: 'Life membership registration confirmed.',
      updated_at: '2026-10-24T16:00:00Z',
    },
    {
      id: 10,
      department_id: 10,
      department_name: 'Scholarship Section',
      status: 'PENDING',
      remarks: null,
      updated_at: null,
    },
  ],
}

export function StudentDashboard() {
  useDocumentTitle('Student Clearance')
  const { user, token } = useAuth()
  const isMock = token === 'dev-preview-token' || (typeof window !== 'undefined' && window.location.search.includes('mock=student'))

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

  // State for Apply submitting
  const [applySubmitting, setApplySubmitting] = useState(false)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState(new Date())

  // 1. Fetch Bank Details
  const {
    data: bankDetails,
    isLoading: bankLoading,
    refetch: refetchBank,
  } = useQuery({
    queryKey: ['student', 'bank-details'],
    queryFn: async () => {
      if (isMock) return MOCK_BANK_DETAILS
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
    isRefetching: requestRefetching,
    refetch: refetchRequest,
  } = useQuery({
    queryKey: ['student', 'current-request'],
    queryFn: async () => {
      if (isMock) return MOCK_ACTIVE_REQUEST
      try {
        const res = await studentApi.getCurrentRequest()
        setLastRefreshed(new Date())
        return res
      } catch (err) {
        if (err.response?.status === 404) return null
        throw err
      }
    },
    refetchInterval: isMock ? false : 30000, // 30s live polling (disabled in mock/preview)
  })

  // Pre-fill holder name when bank details dialog opens
  useEffect(() => {
    if (bankDetails) {
      setBankForm({
        accountHolderName: bankDetails.account_holder_name || user?.full_name || '',
        ifscCode: bankDetails.ifsc_code || '',
        bankAddress: bankDetails.bank_address || '',
        accountNumber: '', // never echo full account number
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
      toast.error('IFSC code must match standard format: 4 letters, 0, then 6 alphanumeric characters (e.g. SBIN0001234).')
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

  // Handle Apply for Clearance
  const handleApply = async () => {
    if (!bankDetails) {
      toast.error('Bank details are required before applying for clearance.')
      return
    }

    setApplySubmitting(true)
    try {
      await studentApi.createRequest()
      toast.success('Clearance application submitted! Departmental reviews dispatched.')
      refetchRequest()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to submit clearance application.'
      toast.error(msg)
    } finally {
      setApplySubmitting(false)
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

  // Progress calculations
  const approvals = currentRequest?.approvals || []
  const approvedCount = approvals.filter((a) => a.status === 'APPROVED').length
  const totalDepts = approvals.length
  const progressPercent = totalDepts > 0 ? Math.round((approvedCount / totalDepts) * 100) : 0
  const hasRejectedDepts = approvals.some((a) => a.status === 'REJECTED')

  // HoD rejection banner condition: ACTION_NEEDED + hod_remarks + no department is rejected
  const showHodBanner =
    currentRequest?.status === 'ACTION_NEEDED' &&
    currentRequest?.hod_remarks &&
    !hasRejectedDepts

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
                  {approvedCount} / {totalDepts || 10} Approved
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
                    ? 'Register your bank account'
                    : !currentRequest
                    ? 'Ready to submit application'
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
                        Initiate concurrent departmental reviews across all 10 university service and academic offices.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="p-6 pt-0 space-y-4 text-xs text-zinc-600">
                  <p className="leading-relaxed">
                    By submitting, your request is instantly delivered to the <strong>Central Library</strong>,{' '}
                    <strong>Sports Department</strong>, <strong>Hostel Office</strong>,{' '}
                    <strong>Computer Centre</strong>, <strong>General Branch</strong>,{' '}
                    <strong>Dean Student Welfare</strong>, <strong>N.S.S.</strong>,{' '}
                    <strong>R&S Branch</strong>, <strong>IIC</strong>, and your <strong>Academic Department</strong>.
                  </p>

                  {!bankDetails && (
                    <Alert className="bg-amber-50 border-amber-200 text-amber-900 py-3">
                      <AlertTriangle className="h-4 w-4 text-amber-800" />
                      <AlertTitle className="text-xs font-semibold">Prerequisite Required</AlertTitle>
                      <AlertDescription className="text-xs mt-0.5">
                        You must register your bank account details before applying so that security deposit refunds can be processed.
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>

                <CardFooter className="p-6 pt-0 border-t border-zinc-100 flex items-center justify-between">
                  <span className="text-xs text-zinc-400">
                    Shri Vishwakarma Skill University
                  </span>
                  <div className="flex items-center gap-2">
                    {!bankDetails ? (
                      <Button
                        size="sm"
                        onClick={() => setBankModalOpen(true)}
                        className="bg-primary text-primary-foreground text-xs gap-1.5"
                      >
                        <Landmark className="w-3.5 h-3.5" />
                        Register Bank Details First
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={handleApply}
                        disabled={applySubmitting}
                        className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-2 font-semibold shadow-xs"
                      >
                        <Send className="w-3.5 h-3.5" />
                        {applySubmitting ? 'Submitting Application...' : 'Apply for Clearance'}
                      </Button>
                    )}
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
                </CardHeader>

                <CardContent className="p-6 pt-0 space-y-4">
                  <StepTimeline
                    status={currentRequest.status}
                    approvals={currentRequest.approvals}
                    hodRemarks={currentRequest.hod_remarks}
                  />
                </CardContent>
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
                                <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground block mt-0.5">
                                  {item.department_kind} office
                                </span>
                              </div>
                              <StatusBadge status={item.status} size="sm" />
                            </div>
                          </CardHeader>

                          <CardContent className="p-5 pt-0 space-y-3 text-xs">
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
                            <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-zinc-100">
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
    </AppShell>
  )
}

export default StudentDashboard
