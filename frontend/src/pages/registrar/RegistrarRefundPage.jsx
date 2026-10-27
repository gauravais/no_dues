import { useState, useMemo } from 'react'
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
  Landmark,
  RotateCw,
  Search,
  CheckCircle2,
  CreditCard,
  Receipt,
  FileCheck2,
} from 'lucide-react'

export function RegistrarRefundPage() {
  useDocumentTitle('Refunds & Disbursements')
  const { user } = useAuth()

  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)
  const [searchTerm, setSearchTerm] = useState('')

  // Refund Modal Flow State
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedRequest, setSelectedRequest] = useState(null)
  const [activeStep, setActiveStep] = useState(1) // 1: verify-refund, 2: mark-processed

  // Step 1 Form: Verify Refund
  const [deductions, setDeductions] = useState('0')
  const [remarks, setRemarks] = useState('')
  const [deductionsError, setDeductionsError] = useState('')
  const [isVerifying, setIsVerifying] = useState(false)

  // Step 2 Form: Mark Processed
  const [paymentRef, setPaymentRef] = useState('')
  const [paymentRefError, setPaymentRefError] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [verifiedResult, setVerifiedResult] = useState(null)

  // Fetch Cleared Requests Queue
  const {
    data: queueResponse,
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['registrar', 'queue', pageIndex, pageSize],
    queryFn: async () => {
      return await registrarApi.getQueue({
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

  const openRefundModal = (req) => {
    setSelectedRequest(req)
    setActiveStep(1)
    setDeductions('0')
    setRemarks('')
    setDeductionsError('')
    setPaymentRef('')
    setPaymentRefError('')
    setVerifiedResult(null)
    setModalOpen(true)
  }

  // Handle Step 1: Verify Refund
  const handleVerifyRefund = async (e) => {
    e.preventDefault()
    if (!selectedRequest) return

    const numDeductions = Number(deductions)
    const deposit = Number(selectedRequest.deposit_amount)

    if (isNaN(numDeductions) || numDeductions < 0) {
      setDeductionsError('Deductions must be a valid number greater than or equal to 0.')
      return
    }

    if (numDeductions > deposit) {
      setDeductionsError(`Deductions cannot exceed the total security deposit (₹${deposit.toLocaleString('en-IN')}).`)
      return
    }

    setDeductionsError('')
    setIsVerifying(true)

    try {
      const res = await registrarApi.verifyRefund(selectedRequest.request_id, {
        deductions: numDeductions,
        remarks: remarks.trim() || null,
      })

      setVerifiedResult(res)
      toast.success(`Security deposit refund verified for ₹${res.final_amount.toLocaleString('en-IN')}.`)
      // Advance immediately to Step 2 so the registrar can record bank payment reference without losing context
      setActiveStep(2)
      refetch()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to verify refund deductions.'
      toast.error(msg)
      setDeductionsError(msg)
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

  // Column definitions
  const columns = useMemo(
    () => [
      {
        id: 'student',
        header: 'Student',
        cell: ({ row }) => {
          const item = row.original
          return (
            <div>
              <span className="font-semibold text-zinc-900 block text-xs sm:text-sm">
                {item.student_name}
              </span>
              <span className="font-mono text-[11px] text-zinc-500">
                {item.registration_number}
              </span>
            </div>
          )
        },
      },
      {
        accessorKey: 'programme',
        header: 'Programme',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-600 line-clamp-2 max-w-[240px]">
            {row.original.programme}
          </span>
        ),
      },
      {
        accessorKey: 'deposit_amount',
        header: 'Security Deposit',
        cell: ({ row }) => {
          const amt = row.original.deposit_amount
          return (
            <span className="font-mono font-bold text-xs sm:text-sm text-zinc-900">
              ₹{Number(amt).toLocaleString('en-IN')}
            </span>
          )
        },
      },
      {
        accessorKey: 'cleared_at',
        header: 'Cleared On',
        cell: ({ row }) => {
          const d = row.original.cleared_at
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
            <Button
              size="sm"
              onClick={() => openRefundModal(item)}
              className="h-8 px-3 text-xs gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
            >
              <CreditCard className="w-3.5 h-3.5" />
              Reconcile Refund
            </Button>
          )
        },
      },
    ],
    []
  )

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
        <Badge variant="outline" className="text-[10px] font-mono bg-zinc-50">
          {item.refund_status}
        </Badge>
      </div>

      <div className="text-xs text-zinc-600">
        {item.programme}
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-500 pt-1 border-t border-zinc-100">
        <span>Security Deposit:</span>
        <span className="font-mono font-bold text-zinc-900 text-sm">
          ₹{Number(item.deposit_amount).toLocaleString('en-IN')}
        </span>
      </div>

      <Button
        size="sm"
        onClick={() => openRefundModal(item)}
        className="w-full mt-2 h-8 text-xs gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
      >
        <CreditCard className="w-3.5 h-3.5" />
        Process Refund
      </Button>
    </div>
  )

  const depositNum = selectedRequest ? Number(selectedRequest.deposit_amount) : 0
  const deductionsNum = !isNaN(Number(deductions)) ? Number(deductions) : 0
  const finalRefundNum = Math.max(0, depositNum - deductionsNum)

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

          <div className="flex items-center gap-2">
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

        {/* Workflow Advisory Banner */}
        <div className="rounded-xl border border-border bg-zinc-50/70 p-4 text-xs text-zinc-600 space-y-1.5">
          <div className="flex items-center gap-2 font-semibold text-zinc-900">
            <Receipt className="w-4 h-4 text-zinc-700" />
            <span>Post-Clearance Refund Procedure</span>
          </div>
          <p className="leading-relaxed text-[11px] text-zinc-500">
            This queue contains students who have attained final HoD clearance (<code className="font-mono text-zinc-800">CLEARED</code>).
            Enter verified deductions, review the live net calculation, approve the refund, and record the bank transaction reference (UTR/NEFT).
          </p>
        </div>

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
          emptyTitle="No cleared requests pending refund"
          emptyDescription="There are currently no students awaiting security deposit refund reconciliation."
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
                      Initial Deposit: ₹{depositNum.toLocaleString('en-IN')}
                    </span>
                  </div>
                </div>

                {/* Step 1: Verify Deductions Form */}
                {activeStep === 1 && (
                  <form onSubmit={handleVerifyRefund} className="space-y-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="deductions-input" className="text-xs font-semibold text-zinc-900">
                        Deductions Amount (₹) *
                      </Label>
                      <Input
                        id="deductions-input"
                        type="number"
                        min="0"
                        max={depositNum}
                        step="1"
                        value={deductions}
                        onChange={(e) => {
                          setDeductions(e.target.value)
                          if (deductionsError) setDeductionsError('')
                        }}
                        className={`font-mono text-xs bg-white ${deductionsError ? 'border-rose-500' : 'border-border'}`}
                        placeholder="0"
                      />
                      {deductionsError && (
                        <p className="text-[11px] text-rose-600 font-medium">{deductionsError}</p>
                      )}
                      <p className="text-[10px] text-zinc-400">
                        Enter 0 if no outstanding breakage, library loss, or hosteller dues apply.
                      </p>
                    </div>

                    {/* Live Preview Calculation Card */}
                    <div className="p-4 rounded-xl border border-border bg-zinc-50/80 space-y-2 text-xs">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 block">
                        Live Calculation Breakdown
                      </span>
                      <div className="flex justify-between text-zinc-600">
                        <span>Original Security Deposit:</span>
                        <span className="font-mono font-medium">₹{depositNum.toLocaleString('en-IN')}</span>
                      </div>
                      <div className="flex justify-between text-rose-700">
                        <span>Less Verified Deductions:</span>
                        <span className="font-mono font-medium">- ₹{deductionsNum.toLocaleString('en-IN')}</span>
                      </div>
                      <div className="pt-2 border-t border-zinc-200 flex justify-between items-center text-sm font-bold text-zinc-950">
                        <span className="text-xs">Net Refund Payable to Student:</span>
                        <span className="font-mono text-emerald-800 text-base">
                          ₹{finalRefundNum.toLocaleString('en-IN')}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="refund-remarks" className="text-xs font-semibold text-zinc-900">
                        Reconciliation Notes / Remarks (Optional)
                      </Label>
                      <Textarea
                        id="refund-remarks"
                        rows={2}
                        placeholder="e.g. Cleared with full refund, zero deductions."
                        value={remarks}
                        onChange={(e) => setRemarks(e.target.value)}
                        className="text-xs bg-white border-border resize-none"
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
                        disabled={isVerifying}
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
                      <div className="flex items-center gap-1.5 font-semibold text-emerald-900">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>Security Deposit Verified</span>
                      </div>
                      <p className="text-[11px] text-emerald-900/90 leading-relaxed">
                        Approved net refund amount:{' '}
                        <strong className="font-mono text-emerald-950">
                          ₹{verifiedResult?.final_amount?.toLocaleString('en-IN') ?? finalRefundNum.toLocaleString('en-IN')}
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
      </div>
    </AppShell>
  )
}

export default RegistrarRefundPage
