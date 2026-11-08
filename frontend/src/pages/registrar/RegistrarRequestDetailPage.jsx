import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { registrarApi } from '@/api/registrar'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import {
  ChevronLeft,
  Landmark,
  ShieldAlert,
  CreditCard,
  FileCheck2,
  Eye,
  EyeOff,
  AlertTriangle,
  RotateCw,
  Check,
  History,
  AlertCircle,
} from 'lucide-react'

export function RegistrarRequestDetailPage() {
  useDocumentTitle('Audit & Disburse Clearance Refund')
  const { id } = useParams()
  const queryClient = useQueryClient()

  // Verify Refund Dialog & Form State
  const [verifyModalOpen, setVerifyModalOpen] = useState(false)
  const [confirmVerifyOpen, setConfirmVerifyOpen] = useState(false)
  const [depositInput, setDepositInput] = useState('')
  const [deductionsInput, setDeductionsInput] = useState('0')
  const [verifyRemarks, setVerifyRemarks] = useState('')
  const [verifyError, setVerifyError] = useState('')

  // Mark Processed Dialog & Form State
  const [processModalOpen, setProcessModalOpen] = useState(false)
  const [confirmProcessOpen, setConfirmProcessOpen] = useState(false)
  const [paymentRef, setPaymentRef] = useState('')
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10))
  const [paymentMode, setPaymentMode] = useState('NEFT')
  const [processError, setProcessError] = useState('')

  // Reopen Verification Dialog State
  const [reopenModalOpen, setReopenModalOpen] = useState(false)
  const [reopenReason, setReopenReason] = useState('')

  // Mark Failed Dialog State
  const [markFailedModalOpen, setMarkFailedModalOpen] = useState(false)
  const [failedReason, setFailedReason] = useState('')

  // Retry Payment Dialog State
  const [confirmRetryOpen, setConfirmRetryOpen] = useState(false)

  // Resolve Student Issue Dialog State
  const [resolveModalOpen, setResolveModalOpen] = useState(false)
  const [resolveNote, setResolveNote] = useState('')

  // Reveal Bank Details State (never stored in query cache, never stored in localStorage)
  const [revealConfirmOpen, setRevealConfirmOpen] = useState(false)
  const [revealedBank, setRevealedBank] = useState(null)
  const [revealCountdown, setRevealCountdown] = useState(0)
  const countdownTimerRef = useRef(null)

  // Fetch full registrar request detail
  const {
    data: detail,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['registrar', 'request', id],
    queryFn: () => registrarApi.getRequestDetail(Number(id)),
    enabled: Boolean(id),
  })

  // Reveal Bank Details Mutation (gcTime: 0 per security requirements)
  const revealMutation = useMutation({
    mutationFn: () => registrarApi.revealBankDetails(Number(id)),
    gcTime: 0,
    onSuccess: (data) => {
      setRevealedBank(data)
      setRevealCountdown(30)
      toast.success('Audited bank account revealed. Auto-hiding in 30 seconds.')
    },
    onError: (err) => {
      const status = err.response?.status
      if (status === 429) {
        toast.error('Rate limit exceeded (maximum 10 calls/min). Please wait before requesting bank details again.')
      } else {
        toast.error(err.response?.data?.detail || 'Failed to reveal bank account details.')
      }
    },
  })

  // 30-second live countdown timer for revealed bank details
  useEffect(() => {
    if (revealCountdown > 0) {
      countdownTimerRef.current = setTimeout(() => {
        setRevealCountdown((prev) => prev - 1)
      }, 1000)
    } else if (revealCountdown === 0 && revealedBank) {
      setRevealedBank(null)
      toast.info('Revealed bank details hidden automatically.')
    }
    return () => {
      if (countdownTimerRef.current) clearTimeout(countdownTimerRef.current)
    }
  }, [revealCountdown, revealedBank])

  // Wipe revealed data on unmount
  useEffect(() => {
    return () => {
      setRevealedBank(null)
      if (countdownTimerRef.current) clearTimeout(countdownTimerRef.current)
    }
  }, [])

  // 1. Verify Refund Mutation
  const verifyMutation = useMutation({
    mutationFn: ({ deposit_amount, deductions, remarks }) =>
      registrarApi.verifyRefund(Number(id), { deposit_amount, deductions, remarks }),
    onSuccess: () => {
      toast.success('Security deposit refund verified successfully.')
      setConfirmVerifyOpen(false)
      setVerifyModalOpen(false)
      queryClient.invalidateQueries({ queryKey: ['registrar', 'request', id] })
      queryClient.invalidateQueries({ queryKey: ['registrar', 'queue'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to verify refund.'
      setVerifyError(msg)
      toast.error(msg)
    },
  })

  // 2. Reopen Verification Mutation
  const reopenMutation = useMutation({
    mutationFn: ({ reason }) => registrarApi.reopenVerification(Number(id), { reason }),
    onSuccess: () => {
      toast.success('Verification reopened. Refund returned to TO_VERIFY queue.')
      setReopenModalOpen(false)
      setReopenReason('')
      queryClient.invalidateQueries({ queryKey: ['registrar', 'request', id] })
      queryClient.invalidateQueries({ queryKey: ['registrar', 'queue'] })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to reopen verification.')
    },
  })

  // 3. Mark Processed Mutation
  const processMutation = useMutation({
    mutationFn: ({ payment_reference, paid_on, payment_mode }) =>
      registrarApi.markProcessed(Number(id), { payment_reference, paid_on, payment_mode }),
    onSuccess: () => {
      toast.success('Disbursement recorded! Refund marked as processed.')
      setProcessModalOpen(false)
      setConfirmProcessOpen(false)
      setPaymentRef('')
      setProcessError('')
      queryClient.invalidateQueries({ queryKey: ['registrar', 'request', id] })
      queryClient.invalidateQueries({ queryKey: ['registrar', 'queue'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to record disbursement.'
      setProcessError(msg)
      toast.error(msg)
    },
  })

  // 4. Mark Failed Mutation
  const markFailedMutation = useMutation({
    mutationFn: ({ reason }) => registrarApi.markFailed(Number(id), { reason }),
    onSuccess: () => {
      toast.success('Disbursement marked as failed.')
      setMarkFailedModalOpen(false)
      setFailedReason('')
      queryClient.invalidateQueries({ queryKey: ['registrar', 'request', id] })
      queryClient.invalidateQueries({ queryKey: ['registrar', 'queue'] })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to mark payment as failed.')
    },
  })

  // 5. Retry Payment Mutation
  const retryMutation = useMutation({
    mutationFn: () => registrarApi.retryPayment(Number(id)),
    onSuccess: () => {
      toast.success('Payment reset to VERIFIED. Ready for retry.')
      setConfirmRetryOpen(false)
      queryClient.invalidateQueries({ queryKey: ['registrar', 'request', id] })
      queryClient.invalidateQueries({ queryKey: ['registrar', 'queue'] })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to retry payment.')
    },
  })

  // 6. Resolve Student Issue Mutation
  const resolveIssueMutation = useMutation({
    mutationFn: ({ note }) => registrarApi.resolveIssue(Number(id), { note }),
    onSuccess: () => {
      toast.success('Student issue marked as resolved.')
      setResolveModalOpen(false)
      setResolveNote('')
      queryClient.invalidateQueries({ queryKey: ['registrar', 'request', id] })
      queryClient.invalidateQueries({ queryKey: ['registrar', 'queue'] })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to resolve issue.')
    },
  })

  const handleOpenVerifyModal = () => {
    setDepositInput(detail?.deposit_amount || '5000.00')
    setDeductionsInput(detail?.deductions != null ? String(detail.deductions) : '0')
    setVerifyRemarks('')
    setVerifyError('')
    setVerifyModalOpen(true)
  }

  const handleCalculateFinal = () => {
    const dep = parseFloat(depositInput) || 0
    const ded = parseFloat(deductionsInput) || 0
    return Math.max(0, dep - ded).toFixed(2)
  }

  const handleVerifyStep1Submit = (e) => {
    e.preventDefault()
    const dep = parseFloat(depositInput)
    const ded = parseFloat(deductionsInput)

    if (isNaN(dep) || dep < 0) {
      setVerifyError('Please enter a valid deposit amount (greater than or equal to 0).')
      return
    }
    if (isNaN(ded) || ded < 0) {
      setVerifyError('Deductions cannot be negative.')
      return
    }
    if (ded > dep) {
      setVerifyError('Deductions cannot exceed the total security deposit amount.')
      return
    }
    if (!verifyRemarks.trim()) {
      setVerifyError('Audit remarks are mandatory when verifying refund calculations.')
      return
    }

    setVerifyError('')
    setConfirmVerifyOpen(true)
  }

  const handleConfirmVerifySubmit = () => {
    verifyMutation.mutate({
      deposit_amount: depositInput,
      deductions: deductionsInput,
      remarks: verifyRemarks.trim(),
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
            to="/registrar"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-black font-medium"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Refunds Queue
          </Link>
          <div className="p-6 rounded-xl border border-destructive/20 bg-destructive/5 text-destructive text-sm flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-zinc-950">
                Failed to load clearance refund record
              </p>
              <p className="text-xs text-zinc-600 mt-1">
                {error?.response?.data?.detail ||
                  'The requested clearance record could not be found or has not reached CLEARED status.'}
              </p>
            </div>
          </div>
        </div>
      </AppShell>
    )
  }

  const approvals = detail.approvals || []
  const isClearanceDone = detail.status === 'CLEARED' || detail.status === 'REFUND_VERIFIED'
  const isAccountsVerified =
    detail.refund_status === 'VERIFIED' ||
    detail.refund_status === 'PROCESSED' ||
    detail.refund_status === 'PAYMENT_FAILED'
  const isProcessed = detail.refund_status === 'PROCESSED'
  const isPaymentFailed = detail.refund_status === 'PAYMENT_FAILED'
  const isStudentConfirmed = Boolean(detail.student_confirmed_at)

  const stepperStages = [
    {
      num: 1,
      title: 'Clearance Complete',
      done: isClearanceDone,
      active: !isClearanceDone,
      date: detail.cleared_date,
    },
    {
      num: 2,
      title: 'Accounts Verification',
      done: isAccountsVerified,
      active: isClearanceDone && !isAccountsVerified,
      date: detail.verified_at,
    },
    {
      num: 3,
      title: 'Payment Disbursed',
      done: isProcessed,
      failed: isPaymentFailed,
      active: detail.refund_status === 'VERIFIED',
      date: detail.paid_on || detail.paid_at,
    },
    {
      num: 4,
      title: 'Receipt Confirmed',
      done: isStudentConfirmed,
      active: isProcessed && !isStudentConfirmed,
      date: detail.student_confirmed_at,
    },
  ]

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Navigation Breadcrumb & Lifecycle Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <Link
            to="/registrar"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-black font-medium"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Accounts & Refunds Queue
          </Link>

          {/* Actions valid ONLY for current state */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* When PENDING_VERIFICATION */}
            {detail.refund_status === 'PENDING_VERIFICATION' && (
              <Button
                size="sm"
                onClick={handleOpenVerifyModal}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-1.5 h-8 font-semibold shadow-xs"
              >
                <FileCheck2 className="w-3.5 h-3.5" />
                Verify Refund Calculation
              </Button>
            )}

            {/* When VERIFIED */}
            {detail.refund_status === 'VERIFIED' && (
              <>
                <Button
                  size="sm"
                  onClick={() => {
                    setPaymentRef('')
                    setPaidOn(new Date().toISOString().slice(0, 10))
                    setPaymentMode('NEFT')
                    setProcessError('')
                    setProcessModalOpen(true)
                  }}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs gap-1.5 h-8 font-semibold shadow-xs"
                >
                  <CreditCard className="w-3.5 h-3.5" />
                  Mark as Paid
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setReopenReason('')
                    setReopenModalOpen(true)
                  }}
                  className="text-xs gap-1.5 h-8 border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                  Reopen Verification
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setFailedReason('')
                    setMarkFailedModalOpen(true)
                  }}
                  className="text-xs gap-1.5 h-8 border-rose-200 text-rose-700 hover:bg-rose-50"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Mark as Failed
                </Button>
              </>
            )}

            {/* When PAYMENT_FAILED */}
            {detail.refund_status === 'PAYMENT_FAILED' && (
              <>
                <Button
                  size="sm"
                  onClick={() => setConfirmRetryOpen(true)}
                  className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-1.5 h-8 font-semibold shadow-xs"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                  Retry Payment
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setFailedReason('')
                    setMarkFailedModalOpen(true)
                  }}
                  className="text-xs gap-1.5 h-8 border-rose-200 text-rose-700 hover:bg-rose-50"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Mark as Failed
                </Button>
              </>
            )}

            {/* When PROCESSED */}
            {detail.refund_status === 'PROCESSED' && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setFailedReason('')
                  setMarkFailedModalOpen(true)
                }}
                className="text-xs gap-1.5 h-8 border-rose-200 text-rose-700 hover:bg-rose-50"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                Mark as Failed
              </Button>
            )}

            {/* When student issue is open */}
            {detail.student_issue_note && !detail.student_issue_resolved_at && (
              <Button
                size="sm"
                onClick={() => {
                  setResolveNote('')
                  setResolveModalOpen(true)
                }}
                className="bg-amber-800 hover:bg-amber-900 text-white text-xs gap-1.5 h-8 font-semibold shadow-xs"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                Resolve Student Issue
              </Button>
            )}
          </div>
        </div>

        {/* Stepper at the top showing current lifecycle stage */}
        <div className="p-4 rounded-xl border border-border bg-white shadow-2xs">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {stepperStages.map((st) => (
              <div key={st.num} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-50 border border-zinc-100">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold font-mono shrink-0 ${
                    st.done
                      ? 'bg-emerald-600 text-white'
                      : st.failed
                      ? 'bg-red-600 text-white'
                      : st.active
                      ? 'bg-zinc-950 text-white ring-2 ring-zinc-200'
                      : 'bg-zinc-200 text-zinc-500'
                  }`}
                >
                  {st.done ? (
                    <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                  ) : st.failed ? (
                    <AlertCircle className="w-3.5 h-3.5" />
                  ) : (
                    st.num
                  )}
                </div>
                <div className="min-w-0">
                  <span
                    className={`text-xs block font-semibold truncate ${
                      st.done
                        ? 'text-emerald-900'
                        : st.failed
                        ? 'text-red-900'
                        : st.active
                        ? 'text-zinc-950'
                        : 'text-zinc-400'
                    }`}
                  >
                    {st.title}
                  </span>
                  <span className="text-[10px] text-zinc-400 block truncate">
                    {st.date
                      ? new Date(st.date).toLocaleDateString()
                      : st.done
                      ? 'Done'
                      : st.active
                      ? 'In progress'
                      : 'Pending'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Student & Dossier Summary Card */}
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
                {detail.programme} • Clearance Request #{detail.request_id}
              </p>
            </div>

            <div className="flex flex-col sm:items-end gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                Disbursement Stage
              </span>
              <div className="flex items-center gap-1.5">
                <StatusBadge status={detail.status} />
                <Badge
                  variant="outline"
                  className={`text-[10px] uppercase font-mono ${
                    isProcessed
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                      : detail.refund_status === 'PAYMENT_FAILED'
                      ? 'bg-red-50 text-red-800 border-red-300'
                      : isAccountsVerified
                      ? 'bg-blue-50 text-blue-800 border-blue-300'
                      : 'bg-zinc-50 text-zinc-700 border-zinc-300'
                  }`}
                >
                  Refund: {detail.refund_status || 'PENDING'}
                </Badge>
              </div>
            </div>
          </div>

          {/* Roster Provenance Warning Box (Shown ONLY on registrar detail page per requirement) */}
          <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-amber-950 space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-amber-900">
              <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0" />
              <span>Roster Record Provenance & Institutional Audit Verification</span>
            </div>
            <p className="text-[11px] text-amber-900 leading-relaxed font-medium">
              Hint: Check that the roster entry was created by the student's own department.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-[11px] border-t border-amber-200/80">
              <div>
                <span className="text-amber-800/80 block">Ingestion Source / Mode:</span>
                <span className="font-mono font-bold text-amber-950 uppercase">
                  {detail.roster_source || 'ADMIN_IMPORT'}
                </span>
              </div>
              <div>
                <span className="text-amber-800/80 block">Created / Enrolled By Officer:</span>
                <span className="font-semibold text-amber-950">
                  {detail.roster_created_by_name ||
                    (detail.roster_created_by_user_id
                      ? `Staff User #${detail.roster_created_by_user_id}`
                      : 'Central Academic Administration')}
                </span>
              </div>
            </div>
          </div>

          {/* Financial Calculation Strip */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-3 border-t border-zinc-100 text-xs">
            <div className="p-3.5 rounded-lg bg-zinc-50 border border-zinc-200">
              <span className="text-zinc-500 block text-[11px]">Security Deposit Amount</span>
              <span className="text-base font-bold font-mono text-zinc-950">
                ₹{detail.deposit_amount || '0.00'}
              </span>
            </div>
            <div className="p-3.5 rounded-lg bg-zinc-50 border border-zinc-200">
              <span className="text-zinc-500 block text-[11px]">Assessed Deductions / Dues</span>
              <span className="text-base font-bold font-mono text-rose-600">
                -₹{detail.deductions || '0.00'}
              </span>
            </div>
            <div className="p-3.5 rounded-lg bg-emerald-50/70 border border-emerald-200">
              <span className="text-emerald-800 font-semibold block text-[11px]">Net Disbursable Refund</span>
              <span className="text-base font-bold font-mono text-emerald-700">
                ₹{detail.final_amount || detail.deposit_amount || '0.00'}
              </span>
            </div>
          </div>
        </div>

        {/* Bank Details & Audited Reveal Section (Positioned near payment form) */}
        <div className="p-6 rounded-xl border border-border bg-white shadow-card space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="font-heading text-base font-bold text-zinc-950 flex items-center gap-2">
                <Landmark className="w-4 h-4 text-zinc-800" />
                Registered Indian Bank Account (Beneficiary Details)
              </h2>
              <p className="text-xs text-zinc-500 mt-0.5">
                Bank account provided by student for direct NEFT/RTGS deposit credit.
              </p>
              <p className="text-[11px] text-amber-800 font-medium mt-1">
                Hint: Reveal only when you are about to pay.
              </p>
            </div>

            {revealedBank ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setRevealedBank(null)
                  setRevealCountdown(0)
                  toast.info('Bank details hidden.')
                }}
                className="text-xs gap-1.5 h-8 border-amber-300 text-amber-900 bg-amber-50 hover:bg-amber-100"
              >
                <EyeOff className="w-3.5 h-3.5" />
                Hide Now ({revealCountdown}s left)
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRevealConfirmOpen(true)}
                className="text-xs gap-1.5 h-8 border-border bg-white text-zinc-900 hover:bg-zinc-50"
              >
                <Eye className="w-3.5 h-3.5" />
                Audited Reveal Bank Account
              </Button>
            )}
          </div>

          {/* Masked vs Revealed Presentation */}
          {!revealedBank ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-4 rounded-xl bg-zinc-50 border border-zinc-200 text-xs">
              <div>
                <span className="text-zinc-400 block text-[11px]">Account Number (Masked)</span>
                <span className="font-mono font-bold text-zinc-900 text-sm">
                  {detail.account_number_masked}
                </span>
              </div>
              <div>
                <span className="text-zinc-400 block text-[11px]">IFSC Code</span>
                <span className="font-mono font-semibold text-zinc-800 text-sm">
                  {detail.ifsc_code}
                </span>
              </div>
              <div>
                <span className="text-zinc-400 block text-[11px]">Account Holder Name</span>
                <span className="font-medium text-zinc-900">
                  {detail.account_holder_name}
                </span>
              </div>
              <div>
                <span className="text-zinc-400 block text-[11px]">Branch Address</span>
                <span className="text-zinc-700 truncate block">
                  {detail.bank_address}
                </span>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-amber-50/90 border border-amber-300 text-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-amber-950">
                  <ShieldAlert className="w-4 h-4 text-amber-800" />
                  <span>Audited Bank Account Information (Auto-hiding in {revealCountdown} seconds)</span>
                </div>
                <Badge variant="outline" className="font-mono bg-white text-amber-900 border-amber-300">
                  {revealCountdown}s
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2 border-t border-amber-200">
                <div>
                  <span className="text-amber-800/80 block text-[11px]">Full Bank Account Number</span>
                  <span className="font-mono font-bold text-zinc-950 text-base select-all tracking-wider">
                    {revealedBank.account_number}
                  </span>
                </div>
                <div>
                  <span className="text-amber-800/80 block text-[11px]">IFSC Code</span>
                  <span className="font-mono font-bold text-zinc-950 text-base select-all">
                    {revealedBank.ifsc_code}
                  </span>
                </div>
                <div>
                  <span className="text-amber-800/80 block text-[11px]">Beneficiary Name</span>
                  <span className="font-semibold text-zinc-900 text-sm">
                    {revealedBank.account_holder_name}
                  </span>
                </div>
                <div>
                  <span className="text-amber-800/80 block text-[11px]">Bank & Branch Address</span>
                  <span className="text-zinc-800 text-xs">
                    {revealedBank.bank_address}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Refund Lifecycle & Audit Timeline */}
        <div className="rounded-xl border border-border bg-white shadow-card overflow-hidden">
          <div className="px-6 py-4 border-b border-border bg-zinc-50/60 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-zinc-700" />
              <h2 className="font-heading text-base font-bold text-zinc-950">
                Refund Lifecycle & Audit Timeline
              </h2>
            </div>
            <span className="text-[11px] text-zinc-400 font-mono">
              Audited event log
            </span>
          </div>

          <div className="p-6 space-y-4">
            {/* Student reported issue banner if exists */}
            {detail.student_issue_note && (
              <div
                className={`p-4 rounded-lg border text-xs space-y-1.5 ${
                  detail.student_issue_resolved_at
                    ? 'bg-zinc-50 border-zinc-200 text-zinc-700'
                    : 'bg-amber-50 border-amber-300 text-amber-950'
                }`}
              >
                <div className="flex items-center justify-between font-semibold">
                  <div className="flex items-center gap-1.5">
                    <AlertTriangle
                      className={`w-3.5 h-3.5 ${
                        detail.student_issue_resolved_at ? 'text-zinc-500' : 'text-amber-700'
                      }`}
                    />
                    <span>Student Problem Report</span>
                  </div>
                  <span className="text-[10px] font-mono">
                    {detail.student_issue_at ? new Date(detail.student_issue_at).toLocaleString() : ''}
                  </span>
                </div>
                <p className="font-mono p-2 rounded bg-white/80 border border-amber-200">
                  "{detail.student_issue_note}"
                </p>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-[11px]">
                    {detail.student_issue_resolved_at ? (
                      <span className="text-emerald-700 font-medium">
                        Resolved on {new Date(detail.student_issue_resolved_at).toLocaleString()}
                      </span>
                    ) : (
                      <span className="text-amber-800 font-medium">
                        Open — requires Accounts resolution
                      </span>
                    )}
                  </span>
                  {!detail.student_issue_resolved_at && (
                    <Button
                      size="sm"
                      onClick={() => {
                        setResolveNote('')
                        setResolveModalOpen(true)
                      }}
                      className="h-7 px-2.5 text-xs bg-amber-900 hover:bg-amber-950 text-white"
                    >
                      Resolve Issue
                    </Button>
                  )}
                </div>
              </div>
            )}

            {/* Timeline Events List */}
            <div className="space-y-3">
              {/* 1. Verification Event */}
              {detail.verified_at && (
                <div className="p-3.5 rounded-lg bg-zinc-50 border border-zinc-200 text-xs flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-zinc-900">Verified by Accounts</span>
                      <Badge
                        variant="outline"
                        className="text-[10px] bg-blue-50 text-blue-800 border-blue-200 font-mono"
                      >
                        VERIFIED
                      </Badge>
                    </div>
                    <p className="text-[11px] text-zinc-600">
                      Verified by:{' '}
                      <span className="font-medium text-zinc-900">
                        {detail.verified_by_name || 'Accounts Officer'}
                      </span>
                    </p>
                    {detail.accounts_note && (
                      <div className="text-xs text-zinc-700 bg-white p-2 rounded border border-zinc-200 mt-1">
                        <span className="font-semibold text-[10px] text-zinc-500 uppercase block mb-0.5">
                          Accounts Note
                        </span>
                        {detail.accounts_note}
                      </div>
                    )}
                  </div>
                  <span className="text-[11px] font-mono text-zinc-400 shrink-0">
                    {new Date(detail.verified_at).toLocaleString()}
                  </span>
                </div>
              )}

              {/* 2. Paid / Processed Event */}
              {(detail.paid_at || detail.paid_on || detail.payment_reference) && (
                <div className="p-3.5 rounded-lg bg-emerald-50/50 border border-emerald-200 text-xs flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-emerald-950">Payment Processed</span>
                      <Badge
                        variant="outline"
                        className="text-[10px] bg-emerald-100 text-emerald-900 border-emerald-300 font-mono"
                      >
                        PROCESSED
                      </Badge>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-0.5 text-[11px] text-zinc-700 pt-0.5">
                      <span>
                        Disbursed By: <strong>{detail.paid_by_name || 'Accounts Officer'}</strong>
                      </span>
                      <span>
                        Paid On:{' '}
                        <strong>
                          {detail.paid_on ? new Date(detail.paid_on).toLocaleDateString() : 'N/A'}
                        </strong>
                      </span>
                      <span>
                        Payment Mode: <strong>{detail.payment_mode || 'NEFT'}</strong>
                      </span>
                      <span>
                        Payment Reference:{' '}
                        <strong className="font-mono">{detail.payment_reference || 'N/A'}</strong>
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-emerald-800 shrink-0">
                    {detail.paid_at ? new Date(detail.paid_at).toLocaleString() : ''}
                  </span>
                </div>
              )}

              {/* 3. Payment Failed Event */}
              {(detail.failed_at || detail.failure_reason) && (
                <div className="p-3.5 rounded-lg bg-red-50/50 border border-red-200 text-xs flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-red-950">Payment Failed</span>
                      <Badge
                        variant="outline"
                        className="text-[10px] bg-red-100 text-red-900 border-red-300 font-mono"
                      >
                        FAILED
                      </Badge>
                    </div>
                    <div className="text-xs text-red-900 bg-white p-2 rounded border border-red-200 mt-1">
                      <span className="font-semibold text-[10px] text-red-600 uppercase block mb-0.5">
                        Failure Reason
                      </span>
                      {detail.failure_reason}
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-red-800 shrink-0">
                    {detail.failed_at ? new Date(detail.failed_at).toLocaleString() : ''}
                  </span>
                </div>
              )}

              {/* 4. Student Confirmed Event */}
              {detail.student_confirmed_at && (
                <div className="p-3.5 rounded-lg bg-emerald-50/50 border border-emerald-200 text-xs flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-emerald-950">Student Receipt Confirmed</span>
                      <Badge
                        variant="outline"
                        className="text-[10px] bg-emerald-100 text-emerald-900 border-emerald-300 font-mono"
                      >
                        CONFIRMED
                      </Badge>
                    </div>
                    <p className="text-[11px] text-zinc-600">
                      Student confirmed receipt of net refund payout in registered bank account.
                    </p>
                  </div>
                  <span className="text-[11px] font-mono text-emerald-800 shrink-0">
                    {new Date(detail.student_confirmed_at).toLocaleString()}
                  </span>
                </div>
              )}

              {!detail.verified_at && !detail.paid_at && !detail.failed_at && !detail.student_confirmed_at && (
                <p className="text-xs text-zinc-400 italic py-2">
                  No refund events recorded yet. Awaiting initial Accounts verification.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Approvals Summary Matrix */}
        <div className="rounded-xl border border-border bg-white shadow-card overflow-hidden space-y-3">
          <div className="px-6 py-4 border-b border-border bg-zinc-50/60 flex items-center justify-between">
            <div>
              <h2 className="font-heading text-base font-bold text-zinc-950">
                Department Approvals Summary
              </h2>
              <p className="text-xs text-zinc-500">
                Verification sign-offs recorded across all parallel university offices.
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
                    Decision Status
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Officer Remarks
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                    Decided By
                  </TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-zinc-600 pr-6">
                    Timestamp
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="divide-y divide-zinc-100">
                {approvals.map((app) => (
                  <TableRow key={app.id} className="hover:bg-zinc-50/60 transition-colors">
                    <TableCell className="px-6 py-3 font-semibold text-xs text-zinc-900">
                      {app.department_name}
                    </TableCell>
                    <TableCell className="py-3">
                      <Badge variant="outline" className="text-[10px] font-mono uppercase bg-zinc-50">
                        {app.department_kind}
                      </Badge>
                    </TableCell>
                    <TableCell className="py-3">
                      <StatusBadge status={app.status} size="sm" />
                    </TableCell>
                    <TableCell className="py-3 text-xs text-zinc-600 max-w-xs">
                      {app.remarks || <span className="text-zinc-400 italic">—</span>}
                    </TableCell>
                    <TableCell className="py-3 text-xs font-medium text-zinc-800">
                      {app.decided_by_name || <span className="text-zinc-400 italic">Officer</span>}
                    </TableCell>
                    <TableCell className="py-3 pr-6 text-xs text-zinc-500 font-mono">
                      {app.decided_at ? new Date(app.decided_at).toLocaleDateString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>

      {/* AlertDialog: Audited Reveal Confirmation */}
      <AlertDialog open={revealConfirmOpen} onOpenChange={setRevealConfirmOpen}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-600" />
              Audited Bank Account Reveal
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-zinc-600 space-y-2">
              <p className="font-semibold text-zinc-900">
                This action is recorded in the audit log.
              </p>
              <p>
                Access to full unmasked student bank details is monitored and rate-limited. The revealed account details will automatically vanish after 30 seconds.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setRevealConfirmOpen(false)
                revealMutation.mutate()
              }}
              disabled={revealMutation.isPending}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              {revealMutation.isPending ? 'Accessing...' : 'Confirm & Reveal'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog: Verify Refund Step 1 */}
      <Dialog open={verifyModalOpen} onOpenChange={setVerifyModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleVerifyStep1Submit}>
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Audit & Verify Security Deposit Refund
              </DialogTitle>
              <DialogDescription className="text-xs">
                Assess deductions (fines, missing items) and compute net refund payout for {detail.student_name}.
              </DialogDescription>
            </DialogHeader>

            {verifyError && (
              <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p className="leading-snug">{verifyError}</p>
              </div>
            )}

            <div className="space-y-4 py-1 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="depAmount" className="text-xs font-semibold text-zinc-800">
                  Total Security Deposit Collected (₹) *
                </Label>
                <Input
                  id="depAmount"
                  type="number"
                  step="0.01"
                  min="0"
                  value={depositInput}
                  onChange={(e) => setDepositInput(e.target.value)}
                  className="font-mono text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="dedAmount" className="text-xs font-semibold text-zinc-800">
                  Assessed Deductions / Dues (₹) * (0 ≤ Deductions ≤ Deposit)
                </Label>
                <Input
                  id="dedAmount"
                  type="number"
                  step="0.01"
                  min="0"
                  value={deductionsInput}
                  onChange={(e) => setDeductionsInput(e.target.value)}
                  className="font-mono text-xs"
                  required
                />
              </div>

              {/* Live Preview of Final Amount */}
              <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 flex items-center justify-between">
                <span className="text-[11px] font-semibold text-zinc-700">
                  Live Net Payout Calculation:
                </span>
                <span className="font-mono font-bold text-sm text-emerald-700">
                  ₹{handleCalculateFinal()}
                </span>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="verifyRemarks" className="text-xs font-semibold text-zinc-800">
                  Audit / Calculation Remarks *
                </Label>
                <Textarea
                  id="verifyRemarks"
                  rows={3}
                  placeholder="e.g. All university property accounted for, no library or lab damages assessed."
                  value={verifyRemarks}
                  onChange={(e) => setVerifyRemarks(e.target.value)}
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
                onClick={() => setVerifyModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                Proceed to Confirmation
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* AlertDialog: Confirm Verify Refund */}
      <AlertDialog open={confirmVerifyOpen} onOpenChange={setConfirmVerifyOpen}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
              Confirm Refund Verification
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-zinc-600 space-y-2">
              <p>
                Are you sure you want to verify refund of <strong>₹{handleCalculateFinal()}</strong> for{' '}
                <strong>{detail.student_name}</strong> ({detail.registration_number})?
              </p>
              <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-zinc-800 text-xs font-mono space-y-1">
                <div>Original Deposit: ₹{depositInput}</div>
                <div>Deductions: -₹{deductionsInput}</div>
                <div className="font-bold text-emerald-700 pt-1 border-t border-zinc-200">
                  Net Disbursable: ₹{handleCalculateFinal()}
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmVerifySubmit}
              disabled={verifyMutation.isPending}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              {verifyMutation.isPending ? 'Verifying...' : 'Yes, Confirm & Verify'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog: Mark as Paid */}
      <Dialog open={processModalOpen} onOpenChange={setProcessModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              const cleanRef = paymentRef.trim()
              if (!/^[a-zA-Z0-9\-_]{6,40}$/.test(cleanRef)) {
                setProcessError('Payment reference must be 6 to 40 characters (alphanumeric, hyphens, and underscores only).')
                return
              }
              setProcessError('')
              setConfirmProcessOpen(true)
            }}
          >
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Record Bank Disbursement (Mark as Paid)
              </DialogTitle>
              <DialogDescription className="text-xs">
                Provide bank transaction reference, disbursement date, and payment mode.
              </DialogDescription>
            </DialogHeader>

            {processError && (
              <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p className="leading-snug">{processError}</p>
              </div>
            )}

            <div className="space-y-4 py-1 text-xs">
              <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200 text-emerald-950 space-y-1">
                <span className="text-[11px] font-semibold block text-emerald-800">
                  Disbursing Net Refund Payout:
                </span>
                <span className="text-base font-bold font-mono">
                  ₹{detail.final_amount || detail.deposit_amount}
                </span>
                <span className="text-[11px] text-emerald-700 block">
                  Beneficiary: {detail.account_holder_name} ({detail.account_number_masked})
                </span>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="payRef" className="text-xs font-semibold text-zinc-800">
                  Bank Payment Transaction Reference / UTR Number *
                </Label>
                <Input
                  id="payRef"
                  placeholder="e.g. UTR123456789012 or CMS-NEFT-0029"
                  value={paymentRef}
                  onChange={(e) => setPaymentRef(e.target.value)}
                  className="font-mono text-xs uppercase"
                  required
                />
                <p className="text-[11px] text-zinc-500">
                  6-40 alphanumeric characters, hyphens, and underscores.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="paidOn" className="text-xs font-semibold text-zinc-800">
                  Disbursement Date *
                </Label>
                <Input
                  id="paidOn"
                  type="date"
                  value={paidOn}
                  onChange={(e) => setPaidOn(e.target.value)}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="payMode" className="text-xs font-semibold text-zinc-800">
                  Payment Mode *
                </Label>
                <select
                  id="payMode"
                  value={paymentMode}
                  onChange={(e) => setPaymentMode(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="NEFT">NEFT</option>
                  <option value="IMPS">IMPS</option>
                  <option value="UPI">UPI</option>
                  <option value="CHEQUE">CHEQUE</option>
                  <option value="OTHER">OTHER</option>
                </select>
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setProcessModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-9 font-semibold"
              >
                Proceed to Confirmation
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* AlertDialog: Confirm Mark as Paid */}
      <AlertDialog open={confirmProcessOpen} onOpenChange={setConfirmProcessOpen}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
              Confirm Bank Disbursement
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-zinc-600 space-y-2">
              <p>
                Confirm recording payment disbursement of{' '}
                <strong>₹{detail.final_amount || detail.deposit_amount}</strong> for{' '}
                <strong>{detail.student_name}</strong>:
              </p>
              <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-zinc-800 text-xs font-mono space-y-1">
                <div>Reference: {paymentRef}</div>
                <div>Date: {paidOn}</div>
                <div>Mode: {paymentMode}</div>
                <div>Beneficiary: {detail.account_holder_name}</div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                processMutation.mutate({
                  payment_reference: paymentRef.trim(),
                  paid_on: paidOn,
                  payment_mode: paymentMode,
                })
              }}
              disabled={processMutation.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-9 font-semibold"
            >
              {processMutation.isPending ? 'Recording...' : 'Yes, Confirm & Record Payment'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog: Reopen Verification */}
      <Dialog open={reopenModalOpen} onOpenChange={setReopenModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!reopenReason.trim()) {
                toast.error('Reason for reopening verification is mandatory.')
                return
              }
              reopenMutation.mutate({ reason: reopenReason.trim() })
            }}
          >
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Reopen Refund Verification
              </DialogTitle>
              <DialogDescription className="text-xs">
                Reopen verification to re-calculate deductions or update security deposit details.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-1 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="reopenReason" className="text-xs font-semibold text-zinc-800">
                  Reason for Reopening *
                </Label>
                <Textarea
                  id="reopenReason"
                  rows={3}
                  placeholder="e.g. Revised deduction assessed by department, mistake in calculation..."
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
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
                onClick={() => setReopenModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={reopenMutation.isPending || !reopenReason.trim()}
                className="bg-zinc-950 text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {reopenMutation.isPending ? 'Reopening...' : 'Confirm Reopen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Dialog: Mark Failed */}
      <Dialog open={markFailedModalOpen} onOpenChange={setMarkFailedModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!failedReason.trim()) {
                toast.error('Failure reason is mandatory.')
                return
              }
              markFailedMutation.mutate({ reason: failedReason.trim() })
            }}
          >
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Mark Disbursement as Failed
              </DialogTitle>
              <DialogDescription className="text-xs">
                Record bank disbursement failure reason so the student and office can rectify bank information.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-1 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="failedReason" className="text-xs font-semibold text-zinc-800">
                  Disbursement Failure Reason *
                </Label>
                <Textarea
                  id="failedReason"
                  rows={3}
                  placeholder="e.g. Bank rejected transfer: Invalid account number / IFSC code mismatch / Beneficiary name mismatch..."
                  value={failedReason}
                  onChange={(e) => setFailedReason(e.target.value)}
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
                onClick={() => setMarkFailedModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={markFailedMutation.isPending || !failedReason.trim()}
                className="bg-rose-700 hover:bg-rose-800 text-white text-xs h-9 font-semibold"
              >
                {markFailedMutation.isPending ? 'Recording...' : 'Confirm Failure'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* AlertDialog: Confirm Retry Payment */}
      <AlertDialog open={confirmRetryOpen} onOpenChange={setConfirmRetryOpen}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
              Retry Payment Disbursement?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-zinc-600 leading-relaxed">
              This will transition the refund status from <strong>PAYMENT_FAILED</strong> back to{' '}
              <strong>VERIFIED</strong>, allowing you to record a new payment transaction reference.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="pt-2">
            <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => retryMutation.mutate()}
              disabled={retryMutation.isPending}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
            >
              {retryMutation.isPending ? 'Retrying...' : 'Confirm Retry'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog: Resolve Student Issue */}
      <Dialog open={resolveModalOpen} onOpenChange={setResolveModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              resolveIssueMutation.mutate({ note: resolveNote.trim() || undefined })
            }}
          >
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Resolve Student Issue
              </DialogTitle>
              <DialogDescription className="text-xs">
                Mark the student-reported issue as resolved with optional resolution notes.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-1 text-xs">
              {detail.student_issue_note && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-950">
                  <span className="font-semibold block text-[11px] text-amber-800 mb-0.5">
                    Student Issue Description:
                  </span>
                  <p className="font-mono text-xs">"{detail.student_issue_note}"</p>
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="resolveNote" className="text-xs font-semibold text-zinc-800">
                  Resolution Remarks (Optional)
                </Label>
                <Textarea
                  id="resolveNote"
                  rows={3}
                  placeholder="e.g. Contacted bank, clarified deduction with student, or re-initiated transfer..."
                  value={resolveNote}
                  onChange={(e) => setResolveNote(e.target.value)}
                  className="text-xs resize-none"
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setResolveModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={resolveIssueMutation.isPending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-9 font-semibold"
              >
                {resolveIssueMutation.isPending ? 'Resolving...' : 'Mark as Resolved'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

export default RegistrarRequestDetailPage
