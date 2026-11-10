import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { CsvUpload } from '@/components/CsvUpload'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  Users,
  Search,
  Edit,
  Upload,
  AlertTriangle,
  Info,
} from 'lucide-react'

export function AdminRosterPage() {
  useDocumentTitle('Master Student Roster (Fallback) | SVSU No-Dues')
  const queryClient = useQueryClient()

  const [viewMode, setViewMode] = useState('list') // 'list' or 'upload'
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)

  // Edit Roster Modal
  const [editTarget, setEditTarget] = useState(null)
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    mobile: '',
    address: '',
  })
  const [editError, setEditError] = useState('')

  // Query Master Roster
  const {
    data: rosterData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin', 'roster', searchQuery, pageIndex, pageSize],
    queryFn: () =>
      adminApi.getRoster({
        search: searchQuery.trim() || undefined,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const rosterItems = useMemo(() => rosterData?.items || [], [rosterData?.items])

  // Edit Mutation
  const editMutation = useMutation({
    mutationFn: ({ id, data }) => adminApi.updateRosterEntry(id, data),
    onSuccess: (res) => {
      if (res?.message) {
        toast.info(res.message)
      } else {
        toast.success('Student roster record updated successfully.')
      }
      setEditTarget(null)
      setEditError('')
      queryClient.invalidateQueries({ queryKey: ['admin', 'roster'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update student roster record.'
      setEditError(msg)
      toast.error(msg)
    },
  })

  const openEditDialog = (item) => {
    setEditTarget(item)
    setEditForm({
      name: item.name || '',
      email: item.email || '',
      mobile: item.mobile || '',
      address: item.address || '',
    })
    setEditError('')
  }

  const handleEditSubmit = (e) => {
    e.preventDefault()
    if (!editTarget) return

    editMutation.mutate({
      id: editTarget.id,
      data: {
        address: editForm.address,
        mobile: editForm.mobile,
      },
    })
  }

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setSearchQuery(searchInput)
    setPageIndex(0)
  }

  const downloadRosterTemplate = () => {
    const csvContent =
      'registration_number,name,email,mobile,address,programme\r\n' +
      '2026CS901,Arjun Mehta,arjun.mehta@svsu.ac.in,9876543210,Campus Hostels SVSU,Bachelor of Technology (B.Tech.) Computer Engineering\r\n'
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'master_roster_template.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // Columns
  const columns = useMemo(
    () => [
      {
        accessorKey: 'registration_number',
        header: 'Reg Number',
        cell: ({ row }) => (
          <span className="font-mono font-semibold text-zinc-900 text-xs">
            {row.original.registration_number}
          </span>
        ),
      },
      {
        accessorKey: 'name',
        header: 'Student Name',
        cell: ({ row }) => (
          <div className="py-1">
            <span className="font-semibold text-zinc-900 block text-xs">
              {row.original.name}
            </span>
            <span className="text-[11px] text-zinc-500 font-mono">
              {row.original.email}
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'programme_name',
        header: 'Programme',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-700 max-w-[200px] line-clamp-1">
            {row.original.programme_name || '-'}
          </span>
        ),
      },
      {
        accessorKey: 'mobile',
        header: 'Contact',
        cell: ({ row }) => (
          <span className="font-mono text-xs text-zinc-600">
            {row.original.mobile || '—'}
          </span>
        ),
      },
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) => (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => openEditDialog(row.original)}
            className="h-7 text-[11px] text-zinc-600 hover:text-black gap-1"
          >
            <Edit className="w-3 h-3" />
            Edit Profile
          </Button>
        ),
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
              <Users className="w-5 h-5 text-zinc-900" />
              <h1 className="font-heading text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
                Master Student Roster (Global Fallback)
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Institutional fallback for viewing and managing university student records across all academic departments. Security deposits are entered by Accounts.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant={viewMode === 'list' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('list')}
              className="text-xs h-9"
            >
              Roster Directory
            </Button>
            <Button
              variant={viewMode === 'upload' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('upload')}
              className="text-xs h-9 gap-1.5"
            >
              <Upload className="w-3.5 h-3.5" />
              CSV Ingestion
            </Button>
          </div>
        </div>

        {viewMode === 'upload' ? (
          <div className="max-w-2xl mx-auto py-4">
            <CsvUpload
              title="Global Student Roster Batch Ingestion"
              description="Upload a CSV with student registration records. Required columns: registration_number, name, email, mobile, address, programme. Security deposits are entered by Accounts."
              columnsHint={['registration_number', 'name', 'email', 'mobile', 'address', 'programme']}
              onDownloadTemplate={downloadRosterTemplate}
              onUpload={async (file) => {
                const res = await adminApi.uploadRosterCsv(file)
                if (res?.message) {
                  toast.info(res.message)
                }
                queryClient.invalidateQueries({ queryKey: ['admin', 'roster'] })
                return res
              }}
            />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Notice Banner */}
            <div className="p-3.5 rounded-xl bg-zinc-50 border border-zinc-200 text-xs text-zinc-600 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                <strong className="text-zinc-800">Clearance Protocol Notice:</strong> Hostel residency and security deposit amounts are no longer maintained on the student roster. Security deposits are entered by Accounts. Students declare hostel residency directly when applying for clearance, and the Accounts Branch audits and records official deposit amounts during refund verification.
              </p>
            </div>

            {/* Search Toolbar */}
            <form
              onSubmit={handleSearchSubmit}
              className="flex items-center gap-2 max-w-md bg-zinc-50/80 p-2 rounded-xl border border-border"
            >
              <div className="relative flex-1">
                <Input
                  placeholder="Search by roll number, name, or email..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="text-xs h-9 bg-white pl-8"
                />
                <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-3" />
              </div>
              <Button
                type="submit"
                size="sm"
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 px-4 font-semibold shrink-0"
              >
                Search
              </Button>
              {searchQuery && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearchInput('')
                    setSearchQuery('')
                    setPageIndex(0)
                  }}
                  className="text-xs h-9 text-zinc-500 hover:text-black"
                >
                  Clear
                </Button>
              )}
            </form>

            {/* Table */}
            {isError ? (
              <div className="p-6 rounded-xl border border-rose-200 bg-rose-50 text-rose-900 text-xs">
                <p className="font-semibold">Failed to load student roster.</p>
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
                data={rosterItems}
                loading={isLoading}
                emptyMessage="No student records found."
                pageSize={pageSize}
              />
            )}
          </div>
        )}
      </div>

      {/* EDIT MODAL */}
      <Dialog
        open={Boolean(editTarget)}
        onOpenChange={(open) => {
          if (!open) {
            setEditTarget(null)
            setEditError('')
          }
        }}
      >
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleEditSubmit}>
            <DialogHeader className="pb-3 border-b border-zinc-100">
              <DialogTitle className="font-heading font-bold text-base">
                Edit Student Roster Profile
              </DialogTitle>
              <DialogDescription className="text-xs">
                Update record for <strong className="text-zinc-900">{editTarget?.registration_number}</strong> ({editTarget?.name}).
              </DialogDescription>
            </DialogHeader>

            {editError && (
              <div className="p-3 my-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p>{editError}</p>
              </div>
            )}

            <div className="space-y-3.5 py-4 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="mMobile" className="text-xs font-semibold text-zinc-800">
                  Mobile Number
                </Label>
                <Input
                  id="mMobile"
                  value={editForm.mobile}
                  onChange={(e) => setEditForm({ ...editForm, mobile: e.target.value })}
                  className="font-mono text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="mAddress" className="text-xs font-semibold text-zinc-800">
                  Residential Address
                </Label>
                <Input
                  id="mAddress"
                  value={editForm.address}
                  onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                  className="text-xs"
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEditTarget(null)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={editMutation.isPending}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {editMutation.isPending ? 'Saving...' : 'Save Updates'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

export default AdminRosterPage
