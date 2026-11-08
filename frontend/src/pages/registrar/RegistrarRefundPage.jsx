import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { registrarApi } from '@/api/registrar'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  RotateCw,
  Search,
  CheckCircle2,
  CreditCard,
  Receipt,
  FileCheck2,
  AlertCircle,
  Download,
  AlertTriangle,
  Upload,
  FileSpreadsheet,
  Edit,
} from 'lucide-react'

export function RegistrarRefundPage() {
  useDocumentTitle('Refunds & Disbursements')
  const { user } = useAuth()

  const [activeTab, setActiveTab] = useState('TO_VERIFY')
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)
  const [searchTerm, setSearchTerm] = useState('')
  const [isExporting, setIsExporting] = useState(false)

  // Deposit Ledger State
  const [ledgerUploadOpen, setLedgerUploadOpen] = useState(false)
  const [ledgerFile, setLedgerFile] = useState(null)
  const [isCheckingFile, setIsCheckingFile] = useState(false)
  const [isUploadingLedger, setIsUploadingLedger] = useState(false)
  const [ledgerReport, setLedgerReport] = useState(null)

  // Single Student Deposit Edit State
  const [editStudentModalOpen, setEditStudentModalOpen] = useState(false)
  const [editStudentRosterId, setEditStudentRosterId] = useState('')
  const [editStudentReg, setEditStudentReg] = useState('')
  const [editStudentName, setEditStudentName] = useState('')
  const [editStudentDeposit, setEditStudentDeposit] = useState('')
  const [isSavingStudentDeposit, setIsSavingStudentDeposit] = useState(false)
  const [editStudentError, setEditStudentError] = useState('')

  // Refund Modal Flow State
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedRequest, setSelectedRequest] = useState(null)
  const [activeStep, setActiveStep] = useState(1) // 1: verify-refund, 2: mark-processed

  // Step 1 Form: Verify Refund
  const [depositInput, setDepositInput] = useState('')
  const [deductions, setDeductions] = useState('0')
  const [noDepositChecked, setNoDepositChecked] = useState(false)
  const [remarks, setRemarks] = useState('')
  const [depositError, setDepositError] = useState('')
  const [deductionsError, setDeductionsError] = useState('')
  const [isVerifying, setIsVerifying] = useState(false)
  const [confirmVerifyOpen, setConfirmVerifyOpen] = useState(false)

  // Step 2 Form: Mark Processed
  const [paymentRef, setPaymentRef] = useState('')
  const [paymentRefError, setPaymentRefError] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [verifiedResult, setVerifiedResult] = useState(null)

  const formatInr = (val) => {
    const num = Number(val)
    if (isNaN(num)) return '₹0.00'
    return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const isValidDecimal = (val) => /^\d+(\.\d{1,2})?$/.test(val.trim())

  // Fetch Requests Queue based on active tab
  const {
    data: queueResponse,
    isLoading,
    isError,
    error,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['registrar', 'queue', activeTab, pageIndex, pageSize],
    queryFn: async () => {
      return await registrarApi.getQueue({
        tab: activeTab,
        limit: pageSize,
        offset: pageIndex * pageSize,
      })
    },
  })

  const rawItems = useMemo(() => queueResponse?.items || [], [queueResponse?.items])
  const totalItems = queueResponse?.total || 0

  // Client-side quick filter
  const filteredItems = useMemo(() => {
    if (!searchTerm.trim()) return rawItems
    const term = searchTerm.toLowerCase().trim()
    return rawItems.filter(
      (item) =>
        item.student_name?.toLowerCase().includes(term) ||
        item.registration_number?.toLowerCase().includes(term) ||
        item.programme?.toLowerCase().includes(term)
    )
  }, [rawItems, searchTerm])

  const openRefundModal = (req, step = 1) => {
    setSelectedRequest(req)
    setActiveStep(step)
    const ledgerVal =
      req.ledger_deposit_amount && Number(req.ledger_deposit_amount) > 0
        ? String(req.ledger_deposit_amount)
        : req.deposit_amount && Number(req.deposit_amount) > 0
        ? String(req.deposit_amount)
        : ''
    const existingDeductions = req.deductions != null && Number(req.deductions) >= 0 ? String(req.deductions) : '0'
    setDepositInput(ledgerVal)
    setDeductions(existingDeductions)
    setNoDepositChecked(ledgerVal !== '' && Number(ledgerVal) === 0)
    setRemarks(req.accounts_note || '')
    setDepositError('')
    setDeductionsError('')
    setConfirmVerifyOpen(false)
    setPaymentRef('')
    setPaymentRefError('')
    setVerifiedResult(
      req.final_amount != null
        ? {
            final_amount: Number(req.final_amount),
            deductions: Number(req.deductions || 0),
          }
        : null
    )
    setModalOpen(true)
  }

  const openEditStudentDeposit = (studentInfo = null) => {
    if (studentInfo) {
      setEditStudentRosterId(studentInfo.roster_id || '')
      setEditStudentReg(studentInfo.registration_number || '')
      setEditStudentName(studentInfo.student_name || '')
      setEditStudentDeposit(
        studentInfo.ledger_deposit_amount != null
          ? String(studentInfo.ledger_deposit_amount)
          : studentInfo.deposit_amount && Number(studentInfo.deposit_amount) > 0
          ? String(studentInfo.deposit_amount)
          : ''
      )
    } else {
      setEditStudentRosterId('')
      setEditStudentReg('')
      setEditStudentName('')
      setEditStudentDeposit('')
    }
    setEditStudentError('')
    setEditStudentModalOpen(true)
  }

  const handleDownloadTemplate = async () => {
    try {
      const blob = await registrarApi.getDepositLedgerTemplate()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'deposit_ledger_template.csv'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      toast.success('Deposit ledger template downloaded.')
    } catch (err) {
      toast.error('Failed to download template: ' + (err?.response?.data?.detail || err.message))
    }
  }

  const handleCheckLedgerFile = async () => {
    if (!ledgerFile) {
      toast.error('Please select a CSV file first.')
      return
    }
    setIsCheckingFile(true)
    try {
      const res = await registrarApi.uploadDepositLedger(ledgerFile, { dry_run: true })
      setLedgerReport(res)
      toast.info(`Dry run complete: ${res.updated_count} valid, ${res.rejected_count} rejected.`)
    } catch (err) {
      toast.error('File check failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setIsCheckingFile(false)
    }
  }

  const handleApplyLedgerUpload = async () => {
    if (!ledgerFile) {
      toast.error('Please select a CSV file first.')
      return
    }
    setIsUploadingLedger(true)
    try {
      const res = await registrarApi.uploadDepositLedger(ledgerFile, { dry_run: false })
      setLedgerReport(res)
      refetch()
      toast.success(`Ledger uploaded: ${res.updated_count} updated, ${res.rejected_count} rejected.`)
    } catch (err) {
      toast.error('Upload failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setIsUploadingLedger(false)
    }
  }

  const handleSaveStudentDeposit = async (e) => {
    e.preventDefault()
    if (!editStudentRosterId) {
      setEditStudentError('Please select or specify a student record.')
      return
    }
    const trimmed = editStudentDeposit.trim()
    if (!trimmed || !isValidDecimal(trimmed)) {
      setEditStudentError('Enter a valid deposit amount with up to 2 decimal places.')
      return
    }
    const num = Number(trimmed)
    if (isNaN(num) || num < 0 || num > 99999999.99) {
      setEditStudentError('Deposit amount must be between 0 and 99,999,999.99.')
      return
    }
    setIsSavingStudentDeposit(true)
    setEditStudentError('')
    try {
      await registrarApi.updateRosterDeposit(Number(editStudentRosterId), {
        deposit_amount: num,
      })
      toast.success(`Deposit updated to ${formatInr(num)} for ${editStudentReg || 'student'}.`)
      setEditStudentModalOpen(false)
      refetch()
    } catch (err) {
      const msg = err?.response?.data?.detail || err.message || 'Failed to update deposit'
      setEditStudentError(msg)
    } finally {
      setIsSavingStudentDeposit(false)
    }
  }

  // Step 1 Validation & Proceed to Confirmation
  const handleVerifyRefundStep1 = (e) => {
    e.preventDefault()
    if (!selectedRequest) return

    setDepositError('')
    setDeductionsError('')

    const trimmedDep = depositInput.trim()
    const trimmedDed = deductions.trim()

    if (!trimmedDep) {
      setDepositError('Security deposit paid by student is required.')
      return
    }
    if (!isValidDecimal(trimmedDep)) {
      setDepositError('Deposit amount must be a valid number with at most two decimal places.')
      return
    }
    const numDeposit = Number(trimmedDep)
    if (isNaN(numDeposit) || numDeposit < 0 || numDeposit > 99999999.99) {
      setDepositError('Deposit amount must be between 0 and 99,999,999.99.')
      return
    }

    if (!trimmedDed) {
      setDeductionsError('Deductions amount is required (enter 0 if no deductions).')
      return
    }
    if (!isValidDecimal(trimmedDed)) {
      setDeductionsError('Deductions must be a valid number with at most two decimal places.')
      return
    }
    const numDeductions = Number(trimmedDed)
    if (isNaN(numDeductions) || numDeductions < 0) {
      setDeductionsError('Deductions must be a valid number greater than or equal to 0.')
      return
    }

    if (numDeductions > numDeposit) {
      setDeductionsError(`Deductions cannot exceed the security deposit (${formatInr(numDeposit)}).`)
      return
    }

    if (numDeposit === 0 && !noDepositChecked) {
      setDepositError('Please confirm by ticking the checkbox that this student has no deposit to refund.')
      return
    }

    if (!remarks.trim()) {
      toast.error('Audit remarks are mandatory when verifying refund calculations.')
      return
    }
    if (remarks.trim().length > 500) {
      toast.error('Remarks cannot exceed 500 characters.')
      return
    }

    setConfirmVerifyOpen(true)
  }

  // Confirmed Submission to API
  const handleConfirmVerifySubmit = async () => {
    if (!selectedRequest) return
    const numDeposit = Number(depositInput.trim())
    const numDeductions = Number(deductions.trim())

    setIsVerifying(true)
    try {
      const res = await registrarApi.verifyRefund(selectedRequest.request_id, {
        deposit_amount: numDeposit,
        deductions: numDeductions,
        remarks: remarks.trim(),
      })

      setVerifiedResult(res)
      setConfirmVerifyOpen(false)
      toast.success(`Security deposit refund verified for ${formatInr(res.final_amount)}.`)
      // Advance immediately to Step 2 so the registrar can record bank payment reference without losing context
      setActiveStep(2)
      refetch()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to verify refund deductions.'
      toast.error(msg)
      setDeductionsError(msg)
      setConfirmVerifyOpen(false)
    } finally {
      setIsVerifying(false)
    }
  }

  // Handle Step 2: Mark Processed
  const handleMarkProcessed = async (e) => {
    e.preventDefault()
    if (!selectedRequest) return

    const cleanRef = paymentRef.trim()
    if (!cleanRef) {
      setPaymentRefError('Payment transaction reference (UTR / NEFT number) is required.')
      return
    }

    setPaymentRefError('')
    setIsProcessing(true)

    try {
      await registrarApi.markProcessed(selectedRequest.request_id, {
        payment_reference: cleanRef,
      })

      toast.success(`Disbursement reference ${cleanRef} recorded. Refund marked PROCESSED.`)
      setModalOpen(false)
      refetch()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to record payment reference.'
      toast.error(msg)
      setPaymentRefError(msg)
    } finally {
      setIsProcessing(false)
    }
  }

  // Export refunds CSV
  const handleExportCsv = async () => {
    setIsExporting(true)
    try {
      const blob = await registrarApi.exportCsv(activeTab)
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/csv;charset=utf-8;' }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `svsu_refunds_${activeTab.toLowerCase()}_${new Date().toISOString().slice(0, 10)}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success(`Exported ${activeTab} refunds list to CSV.`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to export CSV.')
    } finally {
      setIsExporting(false)
    }
  }

  // Column definitions
  const columns = useMemo(() => {
    const baseCols = [
      {
        id: 'student',
        header: 'Student',
        cell: ({ row }) => {
          const item = row.original
          return (
            <div className="space-y-1">
              <span className="font-semibold text-zinc-900 block text-xs sm:text-sm">
                {item.student_name}
              </span>
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-mono text-[11px] text-zinc-500">
                  {item.registration_number}
                </span>
                {item.student_issue_open && (
                  <Badge
                    variant="outline"
                    className="bg-amber-50 text-amber-900 border-amber-300 text-[10px] gap-1 font-medium"
                  >
                    <AlertTriangle className="w-2.5 h-2.5 text-amber-700" />
                    Student reported a problem
                  </Badge>
                )}
              </div>
            </div>
          )
        },
      },
      {
        accessorKey: 'programme',
        header: 'Programme',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-600 line-clamp-2 max-w-[220px]">
            {row.original.programme}
          </span>
        ),
      },
      {
        accessorKey: 'deposit_amount',
        header: 'Security Deposit',
        cell: ({ row }) => {
          const item = row.original
          if (item.refund_status === 'PENDING_VERIFICATION') {
            if (item.ledger_deposit_amount && Number(item.ledger_deposit_amount) > 0) {
              return (
                <div className="space-y-0.5">
                  <span className="font-mono font-bold text-xs sm:text-sm text-zinc-900 block">
                    {formatInr(item.ledger_deposit_amount)}
                  </span>
                  <span className="inline-flex items-center text-[10px] text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded font-medium border border-blue-200">
                    From ledger
                  </span>
                </div>
              )
            }
            return <span className="text-zinc-400 font-mono text-xs">—</span>
          }
          const amt = item.deposit_amount
          return (
            <span className="font-mono font-bold text-xs sm:text-sm text-zinc-900">
              {formatInr(amt || 0)}
            </span>
          )
        },
      },
      {
        accessorKey: 'deductions',
        header: 'Deductions',
        cell: ({ row }) => {
          const item = row.original
          if (item.refund_status === 'PENDING_VERIFICATION' || item.deductions == null) {
            return <span className="text-zinc-400 font-mono">—</span>
          }
          return (
            <span className="font-mono text-xs text-rose-700 font-medium">
              {formatInr(item.deductions)}
            </span>
          )
        },
      },
      {
        accessorKey: 'final_amount',
        header: 'Final Refund',
        cell: ({ row }) => {
          const item = row.original
          if (item.refund_status === 'PENDING_VERIFICATION' || item.final_amount == null) {
            return <span className="text-zinc-400 font-mono">—</span>
          }
          return (
            <span className="font-mono font-bold text-xs sm:text-sm text-emerald-800">
              {formatInr(item.final_amount)}
            </span>
          )
        },
      },
      {
        accessorKey: 'cleared_date',
        header: 'Cleared On',
        cell: ({ row }) => {
          const d = row.original.cleared_date
          return d ? (
            <span className="text-xs text-zinc-600">
              {new Date(d).toLocaleDateString()}
            </span>
          ) : (
            <span className="text-zinc-400">—</span>
          )
        },
      },
      {
        accessorKey: 'refund_status',
        header: 'Refund Status',
        cell: ({ row }) => {
          const st = row.original.refund_status
          return (
            <Badge
              variant="outline"
              className={`text-[10px] uppercase font-mono ${
                st === 'PROCESSED'
                  ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
                  : st === 'VERIFIED'
                  ? 'bg-indigo-50 text-indigo-900 border-indigo-200'
                  : st === 'PAYMENT_FAILED'
                  ? 'bg-red-50 text-red-900 border-red-200'
                  : 'bg-amber-50 text-amber-900 border-amber-200'
              }`}
            >
              {st}
            </Badge>
          )
        },
      },
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) => {
          const item = row.original
          return (
            <div className="flex items-center gap-1.5">
              {item.refund_status === 'PENDING_VERIFICATION' && (
                <Button
                  size="sm"
                  onClick={() => openRefundModal(item, 1)}
                  className="h-8 px-2.5 text-xs gap-1 bg-zinc-950 text-white hover:bg-zinc-800"
                >
                  <CreditCard className="w-3.5 h-3.5" />
                  Verify
                </Button>
              )}
              {item.roster_id && item.refund_status === 'PENDING_VERIFICATION' && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => openEditStudentDeposit(item)}
                  title="Update deposit in ledger"
                  className="h-8 px-2 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                >
                  <Edit className="w-3.5 h-3.5" />
                </Button>
              )}
              {item.refund_status === 'VERIFIED' && (
                <Button
                  size="sm"
                  onClick={() => openRefundModal(item, 2)}
                  className="h-8 px-2.5 text-xs gap-1 bg-emerald-700 text-white hover:bg-emerald-800"
                >
                  <FileCheck2 className="w-3.5 h-3.5" />
                  Record UTR
                </Button>
              )}
              <Link to={`/registrar/requests/${item.request_id}`}>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 px-2.5 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                >
                  Inspect
                </Button>
              </Link>
            </div>
          )
        },
      },
    ]

    return baseCols
  }, [])

  const renderMobileCard = (item) => (
    <div className="p-4 rounded-xl border border-border bg-white shadow-2xs space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-semibold text-zinc-900 block text-sm">
            {item.student_name}
          </span>
          <span className="font-mono text-xs text-zinc-500">
            {item.registration_number}
          </span>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant="outline" className="text-[10px] font-mono bg-zinc-50">
            {item.refund_status}
          </Badge>
          {item.student_issue_open && (
            <Badge
              variant="outline"
              className="bg-amber-50 text-amber-900 border-amber-300 text-[10px] gap-1 font-medium"
            >
              <AlertTriangle className="w-2.5 h-2.5 text-amber-700" />
              Student reported a problem
            </Badge>
          )}
        </div>
      </div>

      <div className="text-xs text-zinc-600">
        {item.programme}
      </div>

      <div className="space-y-1 text-xs text-zinc-500 pt-1 border-t border-zinc-100">
        <div className="flex items-center justify-between">
          <span>Security Deposit:</span>
          <span className="font-mono font-bold text-zinc-900">
            {item.refund_status === 'PENDING_VERIFICATION'
              ? item.ledger_deposit_amount && Number(item.ledger_deposit_amount) > 0
                ? `${formatInr(item.ledger_deposit_amount)} (Ledger)`
                : '—'
              : formatInr(item.deposit_amount || 0)}
          </span>
        </div>
        <div className="flex items-center justify-between text-rose-700">
          <span>Deductions:</span>
          <span className="font-mono font-medium">
            {item.refund_status === 'PENDING_VERIFICATION' || item.deductions == null
              ? '—'
              : formatInr(item.deductions)}
          </span>
        </div>
        <div className="flex items-center justify-between text-emerald-800 font-bold">
          <span>Net Refund:</span>
          <span className="font-mono">
            {item.refund_status === 'PENDING_VERIFICATION' || item.final_amount == null
              ? '—'
              : formatInr(item.final_amount)}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 pt-2">
        {item.refund_status === 'PENDING_VERIFICATION' && (
          <Button
            size="sm"
            onClick={() => openRefundModal(item, 1)}
            className="flex-1 h-8 text-xs gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
          >
            <CreditCard className="w-3.5 h-3.5" />
            Verify
          </Button>
        )}
        {item.roster_id && item.refund_status === 'PENDING_VERIFICATION' && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => openEditStudentDeposit(item)}
            title="Update deposit in ledger"
            className="h-8 px-2.5 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-50"
          >
            <Edit className="w-3.5 h-3.5" />
          </Button>
        )}
        {item.refund_status === 'VERIFIED' && (
          <Button
            size="sm"
            onClick={() => openRefundModal(item, 2)}
            className="flex-1 h-8 text-xs gap-1.5 bg-emerald-700 text-white hover:bg-emerald-800"
          >
            <FileCheck2 className="w-3.5 h-3.5" />
            Record UTR
          </Button>
        )}
        <Link to={`/registrar/requests/${item.request_id}`} className="flex-1">
          <Button
            variant="outline"
            size="sm"
            className="w-full h-8 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-50"
          >
            Inspect
          </Button>
        </Link>
      </div>
    </div>
  )

  const depositNum = depositInput !== '' && !isNaN(Number(depositInput)) ? Number(depositInput) : 0
  const deductionsNum = deductions !== '' && !isNaN(Number(deductions)) ? Number(deductions) : 0
  const finalRefundNum = Math.max(0, depositNum - deductionsNum)
  const isDepositZero = depositInput.trim() !== '' && Number(depositInput) === 0
  const isVerifyDisabled =
    isVerifying ||
    depositInput.trim() === '' ||
    (isDepositZero && !noDepositChecked) ||
    Number(deductions) > Number(depositInput)

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 border border-border flex items-center justify-center text-zinc-900">
                <Landmark className="w-4 h-4" />
              </div>
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
                Security Deposit Refund Queue
              </h1>
              {isRefetching && (
                <RotateCw className="w-4 h-4 text-zinc-400 animate-spin" />
              )}
            </div>
            <p className="text-xs sm:text-sm text-zinc-500">
              Accounts Officer: <span className="font-semibold text-zinc-900">{user?.full_name || user?.email}</span> • Security Deposit Reconciliation & Bank Disbursement
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={isExporting}
              onClick={handleExportCsv}
              className="text-xs gap-1.5 h-8 border-border bg-white hover:bg-zinc-100"
              title="Export currently selected tab to CSV (bank account numbers masked)"
            >
              <Download className="w-3.5 h-3.5" />
              {isExporting ? 'Exporting...' : 'Export list (CSV)'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetch()
                toast.info('Refund queue updated.')
              }}
              className="text-xs gap-1.5 h-8 border-border bg-white hover:bg-zinc-100"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Sync Queue
            </Button>
          </div>
        </div>

        {/* API Error State with Retry Button */}
        {isError && (
          <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-destructive">
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Failed to load refund queue: {error?.response?.data?.detail || error?.message || 'Server connection error'}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="border-destructive/30 hover:bg-destructive/10 text-xs shrink-0"
            >
              <RotateCw className="w-3.5 h-3.5 mr-1.5" />
              Retry
            </Button>
          </div>
        )}

        {/* Workflow Advisory Banner */}
        <div className="rounded-xl border border-border bg-zinc-50/70 p-4 text-xs text-zinc-600 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-semibold text-zinc-900">
              <Receipt className="w-4 h-4 text-zinc-700" />
              <span>Post-Clearance Refund Procedure</span>
            </div>
            <p className="leading-relaxed text-[11px] text-zinc-500">
              Audit applicable dues/deductions against student security deposits, confirm the final payable refund amount, and record official bank payment transaction identifiers.
            </p>
          </div>
          <span className="text-[11px] text-zinc-400 font-mono shrink-0">
            Account numbers in CSV export are masked for security
          </span>
        </div>

        {/* Security Deposit Ledger Section */}
        <div className="rounded-xl border border-border bg-white p-5 shadow-2xs space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-zinc-700" />
                <h2 className="text-sm font-bold text-zinc-950 font-heading">
                  Security Deposit Ledger
                </h2>
              </div>
              <p className="text-xs text-zinc-500">
                Official student security deposit ledger records maintained by Accounts. Pre-fills into refund verification.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadTemplate}
                className="text-xs gap-1.5 h-8 bg-white border-border hover:bg-zinc-100"
                title="Download CSV template formatted for deposit ledger upload"
              >
                <Download className="w-3.5 h-3.5" />
                Download template (CSV)
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setLedgerUploadOpen(true)
                  setLedgerReport(null)
                  setLedgerFile(null)
                }}
                className="text-xs gap-1.5 h-8 bg-white border-border hover:bg-zinc-100"
              >
                <Upload className="w-3.5 h-3.5" />
                Upload ledger (CSV)
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => openEditStudentDeposit(null)}
                className="text-xs gap-1.5 h-8 bg-white border-border hover:bg-zinc-100"
              >
                <Edit className="w-3.5 h-3.5" />
                Update student deposit
              </Button>
            </div>
          </div>
        </div>

        {/* Summary Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-xl border border-border bg-white p-4 shadow-2xs space-y-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 block">
              Awaiting Bank Payment (To Pay)
            </span>
            <div className="flex items-baseline justify-between pt-0.5">
              <div className="text-xl font-bold font-mono text-zinc-900">
                ₹{Number(queueResponse?.total_to_pay_amount || 0).toLocaleString('en-IN')}
              </div>
              <Badge variant="outline" className="text-xs font-mono bg-blue-50 text-blue-800 border-blue-200">
                {queueResponse?.counts?.TO_PAY ?? 0} {queueResponse?.counts?.TO_PAY === 1 ? 'request' : 'requests'}
              </Badge>
            </div>
            <span className="text-[11px] text-zinc-500 block">
              Verified by Accounts Branch, queued for disbursement
            </span>
          </div>

          <div className="rounded-xl border border-border bg-white p-4 shadow-2xs space-y-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 block">
              Disbursed Refunds (Paid)
            </span>
            <div className="flex items-baseline justify-between pt-0.5">
              <div className="text-xl font-bold font-mono text-emerald-700">
                ₹{Number(queueResponse?.total_paid_amount || 0).toLocaleString('en-IN')}
              </div>
              <Badge variant="outline" className="text-xs font-mono bg-emerald-50 text-emerald-800 border-emerald-200">
                {queueResponse?.counts?.PAID ?? 0} completed
              </Badge>
            </div>
            <span className="text-[11px] text-zinc-500 block">
              Payment reference recorded and credit processed
            </span>
          </div>
        </div>

        {/* Lifecycle Status Tabs */}
        <Tabs
          value={activeTab}
          onValueChange={(val) => {
            setActiveTab(val)
            setPageIndex(0)
          }}
          className="w-full"
        >
          <TabsList className="bg-zinc-100 p-1 border border-border flex flex-wrap h-auto gap-1">
            <TabsTrigger
              value="TO_VERIFY"
              className="text-xs font-semibold data-[state=active]:bg-white data-[state=active]:text-zinc-950"
            >
              To verify ({queueResponse?.counts?.TO_VERIFY ?? 0})
            </TabsTrigger>
            <TabsTrigger
              value="TO_PAY"
              className="text-xs font-semibold data-[state=active]:bg-white data-[state=active]:text-zinc-950"
            >
              To pay ({queueResponse?.counts?.TO_PAY ?? 0})
            </TabsTrigger>
            <TabsTrigger
              value="PAID"
              className="text-xs font-semibold data-[state=active]:bg-white data-[state=active]:text-zinc-950"
            >
              Paid ({queueResponse?.counts?.PAID ?? 0})
            </TabsTrigger>
            <TabsTrigger
              value="FAILED"
              className="text-xs font-semibold data-[state=active]:bg-white data-[state=active]:text-zinc-950"
            >
              Failed ({queueResponse?.counts?.FAILED ?? 0})
            </TabsTrigger>
            <TabsTrigger
              value="ALL"
              className="text-xs font-semibold data-[state=active]:bg-white data-[state=active]:text-zinc-950"
            >
              All ({queueResponse?.counts?.ALL ?? 0})
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Search Toolbar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
            <Input
              type="text"
              placeholder="Search by student or registration..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 h-9 text-xs bg-white border-border"
            />
          </div>
          {searchTerm && (
            <span className="text-[11px] text-zinc-500 self-center">
              Filtered <span className="font-mono font-medium text-zinc-800">{filteredItems.length}</span> of {rawItems.length} loaded records
            </span>
          )}
        </div>

        {/* DataTable */}
        <DataTable
          columns={columns}
          data={filteredItems}
          isLoading={isLoading}
          manualPagination={true}
          totalItems={totalItems}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          renderMobileCard={renderMobileCard}
          emptyTitle={
            activeTab === 'CLEARED'
              ? 'No cleared requests awaiting verification'
              : 'No verified refunds awaiting disbursement'
          }
          emptyDescription={
            activeTab === 'CLEARED'
              ? 'There are currently no students in CLEARED status awaiting security deposit deduction audit.'
              : 'There are currently no students in REFUND_VERIFIED status awaiting bank payment recording.'
          }
        />

        {/* Refund Processing Modal (Chained Workflow) */}
        <Dialog open={modalOpen} onOpenChange={setModalOpen}>
          <DialogContent className="sm:max-w-lg bg-white border-border">
            <DialogHeader>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono text-[10px] bg-zinc-100">
                  Step {activeStep} of 2
                </Badge>
                <DialogTitle className="font-heading text-lg font-bold text-zinc-950">
                  {activeStep === 1 ? 'Verify Security Deposit Deductions' : 'Record Disbursement Payment Reference'}
                </DialogTitle>
              </div>
              <DialogDescription className="text-xs text-zinc-500">
                {activeStep === 1
                  ? 'Audit applicable dues/deductions against the security deposit before approving net payout.'
                  : 'Record the official banking transaction reference (UTR / NEFT) to complete the disbursement.'}
              </DialogDescription>
            </DialogHeader>

            {selectedRequest && (
              <div className="space-y-4 py-2">
                {/* Student Summary Strip */}
                <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-xs space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-zinc-900">{selectedRequest.student_name}</span>
                    <span className="font-mono text-zinc-600">{selectedRequest.registration_number}</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-zinc-500">
                    <span className="line-clamp-1 max-w-[260px]">{selectedRequest.programme}</span>
                    <span className="font-mono font-semibold text-zinc-800">
                      Deposit Status: {selectedRequest.refund_status === 'PENDING_VERIFICATION' ? 'Awaiting verification' : formatInr(selectedRequest.deposit_amount || 0)}
                    </span>
                  </div>
                </div>

                {/* Step 1: Verify Deductions Form */}
                {activeStep === 1 && (
                  <form onSubmit={handleVerifyRefundStep1} className="space-y-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="deposit-input" className="text-xs font-semibold text-zinc-900">
                        Security deposit paid by the student (₹) *
                      </Label>
                      <Input
                        id="deposit-input"
                        type="number"
                        min="0"
                        max="99999999.99"
                        step="0.01"
                        value={depositInput}
                        onChange={(e) => {
                          setDepositInput(e.target.value)
                          if (depositError) setDepositError('')
                          if (e.target.value !== '' && Number(e.target.value) !== 0) {
                            setNoDepositChecked(false)
                          }
                        }}
                        className={`font-mono text-xs bg-white ${depositError ? 'border-rose-500' : 'border-border'}`}
                        placeholder="Enter amount from ledger/receipt"
                        required
                      />
                      {selectedRequest?.ledger_deposit_amount && Number(selectedRequest.ledger_deposit_amount) > 0 ? (
                        <div className="flex items-center gap-1.5 p-2 rounded-md bg-blue-50/80 border border-blue-200 text-blue-900 text-[11px] font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-600 inline-block" />
                          From the deposit ledger. Confirm or correct it.
                        </div>
                      ) : (
                        <p className="text-[11px] text-zinc-500">
                          Enter the amount from the university's deposit receipt or ledger. It is not stored anywhere else.
                        </p>
                      )}
                      {depositError && (
                        <p className="text-[11px] text-rose-600 font-medium">{depositError}</p>
                      )}
                    </div>

                    {/* Checkbox if deposit is 0 */}
                    {depositInput.trim() !== '' && Number(depositInput) === 0 && (
                      <div className="flex items-center space-x-2 p-2.5 rounded-lg bg-zinc-50 border border-zinc-200">
                        <input
                          id="no-deposit-checkbox"
                          type="checkbox"
                          checked={noDepositChecked}
                          onChange={(e) => {
                            setNoDepositChecked(e.target.checked)
                            if (depositError) setDepositError('')
                          }}
                          className="h-4 w-4 rounded border-zinc-300 text-zinc-950 focus:ring-zinc-950 cursor-pointer"
                        />
                        <Label htmlFor="no-deposit-checkbox" className="text-xs font-medium text-zinc-900 cursor-pointer">
                          This student has no deposit to refund
                        </Label>
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <Label htmlFor="deductions-input" className="text-xs font-semibold text-zinc-900">
                        Deductions Amount (₹) *
                      </Label>
                      <Input
                        id="deductions-input"
                        type="number"
                        min="0"
                        max={depositInput ? Math.max(0, Number(depositInput)) : 99999999.99}
                        step="0.01"
                        value={deductions}
                        onChange={(e) => {
                          setDeductions(e.target.value)
                          if (deductionsError) setDeductionsError('')
                        }}
                        className={`font-mono text-xs bg-white ${deductionsError ? 'border-rose-500' : 'border-border'}`}
                        placeholder="0.00"
                        required
                      />
                      {deductionsError && (
                        <p className="text-[11px] text-rose-600 font-medium">{deductionsError}</p>
                      )}
                      <p className="text-[10px] text-zinc-400">
                        Enter 0 if no outstanding breakage, library loss, or hosteller dues apply.
                      </p>
                    </div>

                    {/* Live Preview Calculation Card */}
                    {(() => {
                      const typedDep = depositInput.trim() !== '' && !isNaN(Number(depositInput)) ? Number(depositInput) : null
                      const typedDed = deductions.trim() !== '' && !isNaN(Number(deductions)) ? Number(deductions) : 0
                      const netRefund = typedDep !== null ? Math.max(0, typedDep - typedDed) : 0
                      const isNetZero = typedDep !== null && netRefund === 0

                      return (
                        <div className="space-y-3">
                          <div className="p-4 rounded-xl border border-border bg-zinc-50/80 space-y-2 text-xs">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 block">
                              Live Calculation Breakdown
                            </span>
                            <div className="flex justify-between text-zinc-600">
                              <span>Original Security Deposit:</span>
                              <span className="font-mono font-medium">
                                {typedDep !== null ? formatInr(typedDep) : '—'}
                              </span>
                            </div>
                            <div className="flex justify-between text-rose-700">
                              <span>Less Verified Deductions:</span>
                              <span className="font-mono font-medium">
                                - {formatInr(typedDed)}
                              </span>
                            </div>
                            <div className="pt-2 border-t border-zinc-200 flex justify-between items-center text-sm font-bold text-zinc-950">
                              <span className="text-xs">Net Refund Payable to Student:</span>
                              <span className="font-mono text-emerald-800 text-base">
                                {typedDep !== null ? formatInr(netRefund) : '—'}
                              </span>
                            </div>
                          </div>

                          {/* Clear warning when net refund is 0 */}
                          {isNetZero && (
                            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2">
                              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                              <div className="leading-snug">
                                <strong className="font-semibold">Notice:</strong> Net refund payable to student is {formatInr(0)}.
                                {typedDep === 0
                                  ? ' This student has zero security deposit recorded.'
                                  : ' Total assessed deductions match the full security deposit.'}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })()}

                    <div className="space-y-1.5">
                      <Label htmlFor="refund-remarks" className="text-xs font-semibold text-zinc-900">
                        Reconciliation Notes / Remarks (Mandatory) *
                      </Label>
                      <Textarea
                        id="refund-remarks"
                        rows={2}
                        placeholder="e.g. Cleared with full refund, zero deductions."
                        value={remarks}
                        onChange={(e) => setRemarks(e.target.value)}
                        className="text-xs bg-white border-border resize-none"
                        required
                      />
                    </div>

                    <DialogFooter className="gap-2 sm:gap-0 pt-2 border-t border-border">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setModalOpen(false)}
                        disabled={isVerifying}
                        className="text-xs h-9 border-border"
                      >
                        Cancel
                      </Button>
                      <Button
                        type="submit"
                        size="sm"
                        disabled={isVerifyDisabled}
                        className="text-xs h-9 gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
                      >
                        {isVerifying ? (
                          <>
                            <RotateCw className="w-3.5 h-3.5 animate-spin" />
                            Verifying...
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Verify & Approve Refund
                          </>
                        )}
                      </Button>
                    </DialogFooter>
                  </form>
                )}

                {/* Step 2: Mark Processed Form (Chained) */}
                {activeStep === 2 && (
                  <form onSubmit={handleMarkProcessed} className="space-y-4">
                    {/* Success notification banner from Step 1 */}
                    <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/70 text-xs text-emerald-950 space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-semibold text-emerald-900">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          <span>Security Deposit Verified</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setActiveStep(1)}
                          className="text-[11px] text-emerald-800 hover:text-emerald-950 underline font-medium"
                        >
                          Modify Deductions
                        </button>
                      </div>
                      <p className="text-[11px] text-emerald-900/90 leading-relaxed">
                        Approved net refund amount:{' '}
                        <strong className="font-mono text-emerald-950">
                          ₹
                          {verifiedResult?.final_amount != null
                            ? verifiedResult.final_amount.toLocaleString('en-IN')
                            : selectedRequest?.final_amount != null
                            ? Number(selectedRequest.final_amount).toLocaleString('en-IN')
                            : finalRefundNum.toLocaleString('en-IN')}
                        </strong>
                        . Now record the banking transaction identifier to mark this disbursement as completed.
                      </p>
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="payment-ref-input" className="text-xs font-semibold text-zinc-900">
                        Bank Transaction Reference / UTR Number *
                      </Label>
                      <Input
                        id="payment-ref-input"
                        type="text"
                        value={paymentRef}
                        onChange={(e) => {
                          setPaymentRef(e.target.value)
                          if (paymentRefError) setPaymentRefError('')
                        }}
                        className={`font-mono text-xs bg-white uppercase ${paymentRefError ? 'border-rose-500' : 'border-border'}`}
                        placeholder="e.g. NEFT202610280042 / UTR99881234"
                      />
                      {paymentRefError && (
                        <p className="text-[11px] text-rose-600 font-medium">{paymentRefError}</p>
                      )}
                      <p className="text-[10px] text-zinc-400">
                        This bank reference is stored in the audit trail and confirms fund disbursement to the student's registered bank account.
                      </p>
                    </div>

                    <DialogFooter className="gap-2 sm:gap-0 pt-2 border-t border-border">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setModalOpen(false)
                          toast.info('Refund remains in VERIFIED status. You can record payment reference later.')
                        }}
                        disabled={isProcessing}
                        className="text-xs h-9 border-border"
                      >
                        Skip for Later
                      </Button>
                      <Button
                        type="submit"
                        size="sm"
                        disabled={isProcessing}
                        className="text-xs h-9 gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700 focus-visible:ring-emerald-600"
                      >
                        {isProcessing ? (
                          <>
                            <RotateCw className="w-3.5 h-3.5 animate-spin" />
                            Recording...
                          </>
                        ) : (
                          <>
                            <FileCheck2 className="w-3.5 h-3.5" />
                            Confirm Disbursement (Mark Processed)
                          </>
                        )}
                      </Button>
                    </DialogFooter>
                  </form>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Confirmation Step before Verify Submit */}
        <AlertDialog open={confirmVerifyOpen} onOpenChange={setConfirmVerifyOpen}>
          <AlertDialogContent className="bg-white">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-heading text-base font-bold text-zinc-950">
                Confirm Refund Verification
              </AlertDialogTitle>
              <AlertDialogDescription className="text-xs text-zinc-600 space-y-2">
                <p>
                  You are confirming: deposit <strong>{formatInr(depositInput || 0)}</strong>, deductions <strong>{formatInr(deductions || 0)}</strong>, net refund <strong>{formatInr(Math.max(0, (Number(depositInput) || 0) - (Number(deductions) || 0)))}</strong>. The student will see these amounts.
                </p>
                <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-zinc-800 text-xs font-mono space-y-1">
                  <div>Deposit: {formatInr(depositInput || 0)}</div>
                  <div>Deductions: -{formatInr(deductions || 0)}</div>
                  <div className="font-bold text-emerald-700 pt-1 border-t border-zinc-200">
                    Net Refund: {formatInr(Math.max(0, (Number(depositInput) || 0) - (Number(deductions) || 0)))}
                  </div>
                </div>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter className="pt-2">
              <AlertDialogCancel className="text-xs h-9" disabled={isVerifying}>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmVerifySubmit}
                disabled={isVerifying}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {isVerifying ? 'Verifying...' : 'Yes, Confirm & Verify'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        {/* Upload Ledger Dialog */}
        <Dialog open={ledgerUploadOpen} onOpenChange={setLedgerUploadOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-base font-bold text-zinc-950 font-heading flex items-center gap-2">
                <Upload className="w-4 h-4 text-zinc-700" />
                Upload Security Deposit Ledger (CSV)
              </DialogTitle>
              <DialogDescription className="text-xs text-zinc-500">
                Upload a CSV with student registration numbers and deposit amounts. Students whose refunds are already verified cannot be altered.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2 text-xs">
              {/* File Input */}
              <div className="space-y-2">
                <Label htmlFor="ledger-file-input" className="font-semibold text-zinc-900">
                  Select CSV File
                </Label>
                <div className="flex items-center gap-3">
                  <Input
                    id="ledger-file-input"
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      setLedgerFile(f || null)
                      setLedgerReport(null)
                    }}
                    className="text-xs bg-white file:mr-3 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200 cursor-pointer"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDownloadTemplate}
                    className="text-xs text-zinc-600 hover:text-zinc-900 shrink-0 gap-1"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Template
                  </Button>
                </div>
                {ledgerFile && (
                  <p className="text-[11px] text-zinc-500">
                    Selected file: <strong className="text-zinc-900">{ledgerFile.name}</strong> ({Math.round(ledgerFile.size / 1024)} KB)
                  </p>
                )}
              </div>

              {/* Action Buttons: Check File (Dry Run) & Upload (Execute) */}
              <div className="flex items-center gap-2 pt-2 border-t border-border">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!ledgerFile || isCheckingFile || isUploadingLedger}
                  onClick={handleCheckLedgerFile}
                  className="text-xs h-8 gap-1.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
                  {isCheckingFile ? 'Checking file...' : 'Check file (Dry run)'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={!ledgerFile || isCheckingFile || isUploadingLedger}
                  onClick={handleApplyLedgerUpload}
                  className="text-xs h-8 gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
                >
                  <Upload className="w-3.5 h-3.5" />
                  {isUploadingLedger ? 'Uploading...' : 'Upload ledger'}
                </Button>
              </div>

              {/* Report Display */}
              {ledgerReport && (
                <div className="space-y-3 pt-3 border-t border-border">
                  <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-zinc-50 border border-border">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={ledgerReport.dry_run ? 'bg-amber-50 text-amber-900 border-amber-300' : 'bg-emerald-50 text-emerald-900 border-emerald-300'}
                      >
                        {ledgerReport.dry_run ? 'Preview (Dry run)' : 'Applied (Live)'}
                      </Badge>
                      <span className="text-xs font-semibold text-zinc-800">
                        Total Rows: {ledgerReport.total_rows}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-emerald-700 font-medium">Updated: {ledgerReport.updated_count}</span>
                      <span className="text-zinc-500 font-medium">• Unchanged: {ledgerReport.unchanged_count ?? 0}</span>
                      <span className="text-rose-600 font-medium">• Rejected: {ledgerReport.rejected_count}</span>
                    </div>
                  </div>

                  {ledgerReport.dry_run && (
                    <p className="text-[11px] text-amber-800 bg-amber-50/60 border border-amber-200 p-2 rounded">
                      This was a dry-run check. No database records were modified. Review the results below and click <strong>"Upload ledger"</strong> to apply changes.
                    </p>
                  )}

                  {/* Rows Table */}
                  <div className="max-h-60 overflow-y-auto border border-border rounded-lg">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-zinc-100 text-zinc-700 sticky top-0 border-b border-border">
                        <tr>
                          <th className="py-1.5 px-2.5 font-semibold">#</th>
                          <th className="py-1.5 px-2.5 font-semibold">Student ID</th>
                          <th className="py-1.5 px-2.5 font-semibold">Status</th>
                          <th className="py-1.5 px-2.5 font-semibold">Old Amount</th>
                          <th className="py-1.5 px-2.5 font-semibold">New Amount</th>
                          <th className="py-1.5 px-2.5 font-semibold">Notes / Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {ledgerReport.rows?.map((row) => (
                          <tr key={row.row_number} className="hover:bg-zinc-50">
                            <td className="py-1.5 px-2.5 font-mono text-zinc-500">{row.row_number}</td>
                            <td className="py-1.5 px-2.5 font-mono font-medium text-zinc-900">{row.registration_number}</td>
                            <td className="py-1.5 px-2.5">
                              <Badge
                                variant="outline"
                                className={`text-[10px] uppercase font-mono ${
                                  row.status === 'updated'
                                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                    : row.status === 'unchanged'
                                    ? 'bg-zinc-100 text-zinc-600 border-zinc-200'
                                    : 'bg-rose-50 text-rose-800 border-rose-200'
                                }`}
                              >
                                {row.status}
                              </Badge>
                            </td>
                            <td className="py-1.5 px-2.5 font-mono text-zinc-600">
                              {row.old_amount != null ? formatInr(row.old_amount) : '—'}
                            </td>
                            <td className="py-1.5 px-2.5 font-mono font-bold text-zinc-900">
                              {row.new_amount != null ? formatInr(row.new_amount) : '—'}
                            </td>
                            <td className="py-1.5 px-2.5 text-zinc-500 text-[11px] max-w-[200px] truncate" title={row.reason || ''}>
                              {row.reason || '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            <DialogFooter className="pt-2 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setLedgerUploadOpen(false)}
                className="text-xs"
              >
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Single Student Deposit Modal */}
        <Dialog open={editStudentModalOpen} onOpenChange={setEditStudentModalOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="text-base font-bold text-zinc-950 font-heading flex items-center gap-2">
                <Edit className="w-4 h-4 text-zinc-700" />
                Update Student Security Deposit
              </DialogTitle>
              <DialogDescription className="text-xs text-zinc-500">
                Update the official security deposit ledger amount for an individual student.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSaveStudentDeposit} className="space-y-4 py-2 text-xs">
              {editStudentError && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <p>{editStudentError}</p>
                </div>
              )}

              {/* Student Identification */}
              <div className="space-y-1.5">
                <Label htmlFor="edit-roster-id" className="font-semibold text-zinc-900">
                  Student Record *
                </Label>
                {editStudentReg ? (
                  <div className="p-2.5 rounded-lg bg-zinc-50 border border-zinc-200 space-y-0.5">
                    <div className="font-semibold text-zinc-900">{editStudentName || 'Student'}</div>
                    <div className="font-mono text-zinc-500">{editStudentReg} (Roster #{editStudentRosterId})</div>
                  </div>
                ) : (
                  <select
                    id="edit-roster-id"
                    value={editStudentRosterId}
                    onChange={(e) => {
                      const selId = e.target.value
                      setEditStudentRosterId(selId)
                      const found = rawItems.find((it) => String(it.roster_id) === String(selId))
                      if (found) {
                        setEditStudentReg(found.registration_number || '')
                        setEditStudentName(found.student_name || '')
                        setEditStudentDeposit(
                          found.ledger_deposit_amount != null
                            ? String(found.ledger_deposit_amount)
                            : found.deposit_amount && Number(found.deposit_amount) > 0
                            ? String(found.deposit_amount)
                            : ''
                        )
                      }
                    }}
                    className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    required
                  >
                    <option value="">Select a student from queue...</option>
                    {rawItems
                      .filter((it) => it.roster_id)
                      .map((it) => (
                        <option key={it.roster_id} value={it.roster_id}>
                          {it.student_name} ({it.registration_number}) — {it.ledger_deposit_amount ? formatInr(it.ledger_deposit_amount) : 'Unset'}
                        </option>
                      ))}
                  </select>
                )}
              </div>

              {/* Deposit Amount */}
              <div className="space-y-1.5">
                <Label htmlFor="edit-deposit-amount" className="font-semibold text-zinc-900">
                  New Security Deposit Amount (₹) *
                </Label>
                <Input
                  id="edit-deposit-amount"
                  type="number"
                  min="0"
                  max="99999999.99"
                  step="0.01"
                  value={editStudentDeposit}
                  onChange={(e) => {
                    setEditStudentDeposit(e.target.value)
                    if (editStudentError) setEditStudentError('')
                  }}
                  placeholder="e.g. 5000.00"
                  className="font-mono text-xs"
                  required
                />
                <p className="text-[11px] text-zinc-500">
                  Amount between 0.00 and 99,999,999.99 with up to 2 decimal places.
                </p>
              </div>

              <DialogFooter className="pt-2 border-t border-border">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditStudentModalOpen(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={isSavingStudentDeposit}
                  className="text-xs bg-zinc-950 text-white hover:bg-zinc-800"
                >
                  {isSavingStudentDeposit ? 'Saving...' : 'Save Deposit'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}

export default RegistrarRefundPage
