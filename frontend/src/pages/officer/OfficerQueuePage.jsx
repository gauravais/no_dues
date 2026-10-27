import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { departmentApi } from '@/api/department'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { StatusBadge } from '@/components/StatusBadge'
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
  Building2,
  CheckCircle2,
  XCircle,
  Search,
  RotateCw,
  AlertTriangle,
  History,
  Clock,
  ShieldCheck,
} from 'lucide-react'

export function OfficerQueuePage() {
  useDocumentTitle('Department Clearance Queue')
  const { user } = useAuth()

  const [statusTab, setStatusTab] = useState('PENDING')
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)
  const [searchTerm, setSearchTerm] = useState('')

  // Decision Modal State
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState(null)
  const [decision, setDecision] = useState('APPROVED')
  const [remarks, setRemarks] = useState('')
  const [remarksError, setRemarksError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [conflictError, setConflictError] = useState(null)

  // Fetch queue
  const {
    data: queueResponse,
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['department', 'queue', statusTab, pageIndex, pageSize],
    queryFn: async () => {
      return await departmentApi.getQueue({
        status: statusTab === 'ALL' ? undefined : statusTab,
        limit: pageSize,
        offset: pageIndex * pageSize,
      })
    },
  })

  const rawItems = useMemo(() => queueResponse?.items || [], [queueResponse?.items])
  const totalItems = queueResponse?.total || 0

  // Client-side search filtering (API does not support search query parameter)
  const filteredItems = useMemo(() => {
    if (!searchTerm.trim()) return rawItems
    const term = searchTerm.toLowerCase().trim()
    return rawItems.filter(
      (item) =>
        item.student_name?.toLowerCase().includes(term) ||
        item.registration_number?.toLowerCase().includes(term) ||
        item.programme_name?.toLowerCase().includes(term)
    )
  }, [rawItems, searchTerm])

  const openDecisionModal = (item) => {
    setSelectedItem(item)
    setDecision('APPROVED')
    setRemarks('')
    setRemarksError('')
    setConflictError(null)
    setDialogOpen(true)
  }

  const handleDecisionSubmit = async () => {
    if (!selectedItem) return

    // Validation: remarks mandatory for REJECTED
    if (decision === 'REJECTED' && !remarks.trim()) {
      setRemarksError('Remarks are strictly mandatory when rejecting an application.')
      return
    }

    if (remarks.length > 500) {
      setRemarksError('Remarks cannot exceed 500 characters.')
      return
    }

    setIsSubmitting(true)
    setConflictError(null)

    try {
      await departmentApi.submitDecision(selectedItem.approval_id, {
        decision,
        remarks: remarks.trim() || null,
      })

      toast.success(
        decision === 'APPROVED'
          ? `Cleared dues for ${selectedItem.student_name}.`
          : `Rejected dues for ${selectedItem.student_name} with remarks.`
      )
      setDialogOpen(false)
      refetch()
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail

      if (status === 409) {
        setConflictError(
          'Conflict: This approval was already decided by another officer or session. Please refresh the queue.'
        )
        toast.error('Approval already decided. (HTTP 409 Conflict)')
      } else if (status === 404) {
        setConflictError(
          'Approval record not found or does not belong to your assigned department.'
        )
        toast.error('Record not found. (HTTP 404)')
      } else if (status === 400) {
        setRemarksError(detail || 'Invalid submission.')
        toast.error(detail || 'Validation error.')
      } else {
        toast.error(detail || 'Failed to submit decision. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // Column definitions for TanStack Table
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
        accessorKey: 'programme_name',
        header: 'Programme',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-600 line-clamp-2 max-w-[260px]">
            {row.original.programme_name}
          </span>
        ),
      },
      {
        accessorKey: 'submitted_at',
        header: 'Submitted',
        cell: ({ row }) => {
          const dateStr = row.original.submitted_at
          if (!dateStr) return <span className="text-zinc-400">—</span>
          const d = new Date(dateStr)
          return (
            <div className="text-xs text-zinc-600">
              <span>{d.toLocaleDateString()}</span>
              <span className="text-zinc-400 block text-[10px]">{d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          )
        },
      },
      {
        accessorKey: 'resubmission_count',
        header: 'Resubmissions',
        cell: ({ row }) => {
          const count = row.original.resubmission_count
          return count > 0 ? (
            <Badge variant="outline" className="bg-amber-50 text-amber-900 border-amber-200 text-[10px] gap-1">
              <History className="w-3 h-3 text-amber-700" />
              {count} {count === 1 ? 'resubmission' : 'resubmissions'}
            </Badge>
          ) : (
            <span className="text-zinc-400 text-xs font-mono">0</span>
          )
        },
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) => {
          const item = row.original
          const isPending = item.status === 'PENDING'

          return isPending ? (
            <Button
              size="sm"
              onClick={() => openDecisionModal(item)}
              className="h-8 px-3 text-xs bg-zinc-950 text-white hover:bg-zinc-800"
            >
              Review
            </Button>
          ) : (
            <span className="text-xs text-zinc-400 italic">Decided</span>
          )
        },
      },
    ],
    []
  )

  // Status Filter Tabs definition
  const statusTabsConfig = {
    currentTab: statusTab,
    onTabChange: (val) => {
      setStatusTab(val)
      setPageIndex(0)
    },
    tabs: [
      { value: 'PENDING', label: 'Pending Dues' },
      { value: 'APPROVED', label: 'Approved' },
      { value: 'REJECTED', label: 'Rejected' },
      { value: 'ALL', label: 'All Records' },
    ],
  }

  // Mobile Card Renderer
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
        <StatusBadge status={item.status} />
      </div>

      <div className="text-xs text-zinc-600 line-clamp-2">
        {item.programme_name}
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-500 pt-1 border-t border-zinc-100">
        <span className="flex items-center gap-1 text-[11px]">
          <Clock className="w-3 h-3 text-zinc-400" />
          {item.submitted_at ? new Date(item.submitted_at).toLocaleDateString() : '—'}
        </span>
        {item.resubmission_count > 0 && (
          <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-900 border-amber-200">
            {item.resubmission_count} resubmission(s)
          </Badge>
        )}
      </div>

      {item.status === 'PENDING' && (
        <Button
          size="sm"
          onClick={() => openDecisionModal(item)}
          className="w-full mt-2 h-8 text-xs bg-zinc-950 text-white hover:bg-zinc-800"
        >
          Review Clearance
        </Button>
      )}
    </div>
  )

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 border border-border flex items-center justify-center text-zinc-900">
                <Building2 className="w-4 h-4" />
              </div>
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
                {user?.department_name ? `${user.department_name} Clearance Queue` : 'Department Clearance Queue'}
              </h1>
              {isRefetching && (
                <RotateCw className="w-4 h-4 text-zinc-400 animate-spin" />
              )}
            </div>
            <p className="text-xs sm:text-sm text-zinc-500">
              Department Officer: <span className="font-medium text-zinc-800">{user?.full_name || user?.email}</span> • Authenticated Department Reviewer
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetch()
                toast.info('Department queue refreshed.')
              }}
              className="text-xs gap-1.5 h-8 border-border bg-white hover:bg-zinc-100"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Sync Queue
            </Button>
          </div>
        </div>

        {/* Toolbar: Search input */}
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
          statusTabs={statusTabsConfig}
          renderMobileCard={renderMobileCard}
          emptyTitle={`No ${statusTab.toLowerCase()} requests`}
          emptyDescription={`There are currently no student clearance applications in ${statusTab} status for your department.`}
        />

        {/* Decision Modal Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-md bg-white border-border">
            <DialogHeader>
              <DialogTitle className="font-heading text-lg font-bold text-zinc-950">
                Department Clearance Review
              </DialogTitle>
              <DialogDescription className="text-xs text-zinc-500">
                Record your department's decision for the student's security deposit refund application.
              </DialogDescription>
            </DialogHeader>

            {selectedItem && (
              <div className="space-y-4 py-2">
                {/* Student Context Card */}
                <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-xs space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-zinc-900">{selectedItem.student_name}</span>
                    <span className="font-mono text-zinc-600">{selectedItem.registration_number}</span>
                  </div>
                  <p className="text-[11px] text-zinc-500">{selectedItem.programme_name}</p>
                  {selectedItem.resubmission_count > 0 && (
                    <div className="pt-1 flex items-center gap-1 text-[11px] text-amber-800">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Resubmitted record (#{selectedItem.resubmission_count})</span>
                    </div>
                  )}
                </div>

                {/* Conflict / Error Banner */}
                {conflictError && (
                  <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <span>{conflictError}</span>
                  </div>
                )}

                {/* Decision Selection: Approve vs Reject */}
                <div className="space-y-2">
                  <Label className="text-xs font-semibold text-zinc-900">
                    Decision Action
                  </Label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setDecision('APPROVED')
                        setRemarksError('')
                      }}
                      className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-xs font-semibold transition-all ${
                        decision === 'APPROVED'
                          ? 'border-emerald-600 bg-emerald-50/50 text-emerald-950 ring-1 ring-emerald-600'
                          : 'border-border bg-white text-zinc-600 hover:bg-zinc-50'
                      }`}
                    >
                      <CheckCircle2 className={`w-4 h-4 ${decision === 'APPROVED' ? 'text-emerald-600' : 'text-zinc-400'}`} />
                      Approve Clearance
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setDecision('REJECTED')
                      }}
                      className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-xs font-semibold transition-all ${
                        decision === 'REJECTED'
                          ? 'border-rose-600 bg-rose-50/50 text-rose-950 ring-1 ring-rose-600'
                          : 'border-border bg-white text-zinc-600 hover:bg-zinc-50'
                      }`}
                    >
                      <XCircle className={`w-4 h-4 ${decision === 'REJECTED' ? 'text-rose-600' : 'text-zinc-400'}`} />
                      Reject with Remarks
                    </button>
                  </div>
                </div>

                {/* Remarks Field */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <Label htmlFor="officer-remarks" className="font-semibold text-zinc-900">
                      {decision === 'REJECTED' ? (
                        <span className="text-rose-700">Rejection Remarks (Mandatory) *</span>
                      ) : (
                        <span>Officer Remarks (Optional)</span>
                      )}
                    </Label>
                    <span className={`text-[11px] font-mono ${remarks.length > 500 ? 'text-rose-600 font-bold' : 'text-zinc-400'}`}>
                      {remarks.length} / 500
                    </span>
                  </div>

                  <Textarea
                    id="officer-remarks"
                    rows={3}
                    placeholder={
                      decision === 'REJECTED'
                        ? 'Specify outstanding dues, missing equipment, fine amounts, or books to return...'
                        : 'Optional verification notes (e.g. All books returned and dues cleared).'
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
                  {decision === 'REJECTED' && (
                    <p className="text-[11px] text-zinc-500">
                      The student will see these remarks in their dashboard and will be required to resolve them before resubmitting.
                    </p>
                  )}
                </div>
              </div>
            )}

            <DialogFooter className="gap-2 sm:gap-0 pt-2 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDialogOpen(false)}
                disabled={isSubmitting}
                className="text-xs h-9 border-border hover:bg-zinc-100"
              >
                Cancel
              </Button>

              <Button
                size="sm"
                onClick={handleDecisionSubmit}
                disabled={isSubmitting}
                className={`text-xs h-9 gap-1.5 text-white ${
                  decision === 'APPROVED'
                    ? 'bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-600'
                    : 'bg-rose-600 hover:bg-rose-700 focus-visible:ring-rose-600'
                }`}
              >
                {isSubmitting ? (
                  <>
                    <RotateCw className="w-3.5 h-3.5 animate-spin" />
                    Recording...
                  </>
                ) : decision === 'APPROVED' ? (
                  <>
                    <ShieldCheck className="w-3.5 h-3.5" />
                    Confirm Approval
                  </>
                ) : (
                  <>
                    <XCircle className="w-3.5 h-3.5" />
                    Confirm Rejection
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}

export default OfficerQueuePage
