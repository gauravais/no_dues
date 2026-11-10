import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { departmentApi } from '@/api/department'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { CsvUpload } from '@/components/CsvUpload'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
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
  UserPlus,
  Edit,
  Search,
  RotateCw,
  AlertTriangle,
  Upload,
} from 'lucide-react'

export function OfficerRosterPage() {
  useDocumentTitle('Academic Department Roster')
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState('list')
  const [searchTerm, setSearchTerm] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)

  // Multi-academic department support
  const academicMemberships = useMemo(() => {
    const depts = user?.departments || []
    return depts.filter((d) => d.kind === 'academic')
  }, [user?.departments])

  const hasMultipleAcademic = academicMemberships.length > 1
  const [selectedDeptId, setSelectedDeptId] = useState('ALL')

  // Dialog States
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [selectedStudent, setSelectedStudent] = useState(null)

  // Add Student Form State
  const [addForm, setAddForm] = useState({
    registration_number: '',
    name: '',
    email: '',
    mobile: '',
    programme_id: '',
    address: '',
  })
  const [addError, setAddError] = useState('')

  // Edit Student Form State
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    mobile: '',
    address: '',
    programme_id: '',
  })
  const [editError, setEditError] = useState('')

  // Fetch all programmes
  const { data: allProgrammes = [] } = useQuery({
    queryKey: ['programmes'],
    queryFn: () => departmentApi.getProgrammes(),
  })

  // Filter programmes to officer's academic departments
  const academicDeptIds = useMemo(
    () => new Set(academicMemberships.map((m) => m.id)),
    [academicMemberships]
  )

  const allowedProgrammes = useMemo(() => {
    if (academicDeptIds.size === 0) return allProgrammes
    return allProgrammes.filter((p) => academicDeptIds.has(p.academic_department_id))
  }, [allProgrammes, academicDeptIds])

  // Fetch roster
  const {
    data: rosterData,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['department', 'roster', searchTerm, pageIndex, pageSize, selectedDeptId],
    queryFn: () =>
      departmentApi.getRoster({
        search: searchTerm.trim() || undefined,
        limit: pageSize,
        offset: pageIndex * pageSize,
        departmentId: selectedDeptId === 'ALL' ? undefined : selectedDeptId,
      }),
  })

  const students = useMemo(() => rosterData?.items || [], [rosterData?.items])
  const totalItems = rosterData?.total || 0

  // Extract known programmes from existing roster records for dropdown convenience
  const knownProgrammes = useMemo(() => {
    const map = new Map()
    students.forEach((s) => {
      if (s.programme_id && s.programme_name) {
        map.set(s.programme_id, s.programme_name)
      }
    })
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }))
  }, [students])

  // Create Student Mutation
  const createMutation = useMutation({
    mutationFn: (data) => departmentApi.createRosterStudent(data),
    onSuccess: (res) => {
      if (res?.message) {
        toast.info(res.message)
      } else {
        toast.success('Student added to academic roster successfully.')
      }
      setAddModalOpen(false)
      setAddForm({
        registration_number: '',
        name: '',
        email: '',
        mobile: '',
        programme_id: '',
        address: '',
      })
      setAddError('')
      queryClient.invalidateQueries({ queryKey: ['department', 'roster'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to add student to roster.'
      setAddError(msg)
      toast.error(msg)
    },
  })

  // Patch Student Mutation
  const patchMutation = useMutation({
    mutationFn: ({ id, data }) => departmentApi.patchRosterStudent(id, data),
    onSuccess: (res) => {
      if (res?.message) {
        toast.info(res.message)
      } else {
        toast.success('Student roster record updated successfully.')
      }
      setEditModalOpen(false)
      setSelectedStudent(null)
      setEditError('')
      queryClient.invalidateQueries({ queryKey: ['department', 'roster'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update student record.'
      setEditError(msg)
      toast.error(msg)
    },
  })

  const handleOpenAdd = () => {
    setAddError('')
    // Default programme_id to first known programme if available
    setAddForm((prev) => ({
      ...prev,
      programme_id: allowedProgrammes[0]?.id ? String(allowedProgrammes[0].id) : knownProgrammes[0]?.id ? String(knownProgrammes[0].id) : '',
    }))
    setAddModalOpen(true)
  }

  const handleOpenEdit = (student) => {
    setSelectedStudent(student)
    setEditForm({
      name: student.name || '',
      email: student.email || '',
      mobile: student.mobile || '',
      address: student.address || '',
      programme_id: student.programme_id ? String(student.programme_id) : '',
    })
    setEditError('')
    setEditModalOpen(true)
  }

  const handleAddSubmit = (e) => {
    e.preventDefault()
    if (!addForm.registration_number.trim() || !addForm.name.trim() || !addForm.email.trim() || !addForm.mobile.trim() || !addForm.programme_id) {
      setAddError('All required fields (registration number, name, email, mobile, programme) must be filled.')
      return
    }
    createMutation.mutate(addForm)
  }

  const handleEditSubmit = (e) => {
    e.preventDefault()
    if (!selectedStudent) return
    patchMutation.mutate({
      id: selectedStudent.id,
      data: {
        name: editForm.name.trim(),
        email: editForm.email.trim(),
        mobile: editForm.mobile.trim(),
        address: editForm.address.trim(),
        programme_id: editForm.programme_id ? Number(editForm.programme_id) : undefined,
      },
    })
  }

  // Column definitions for DataTable
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
          <div>
            <span className="font-semibold text-zinc-900 block text-xs">
              {row.original.name}
            </span>
            <span className="text-[11px] text-zinc-500">{row.original.email}</span>
          </div>
        ),
      },
      {
        accessorKey: 'mobile',
        header: 'Mobile',
        cell: ({ row }) => (
          <span className="font-mono text-xs text-zinc-600">
            {row.original.mobile || '—'}
          </span>
        ),
      },
      {
        accessorKey: 'programme_name',
        header: 'Programme',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-700 max-w-[200px] line-clamp-1">
            {row.original.programme_name}
          </span>
        ),
      },
      {
        accessorKey: 'has_user_account',
        header: 'User Account',
        cell: ({ row }) =>
          row.original.has_user_account ? (
            <Badge variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-200 text-[10px]">
              Provisioned
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-zinc-50 text-zinc-500 border-zinc-200 text-[10px]">
              Unregistered
            </Badge>
          ),
      },
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) => (
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleOpenEdit(row.original)}
            className="h-7 px-2.5 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-50 gap-1"
          >
            <Edit className="w-3 h-3" />
            Edit
          </Button>
        ),
      },
    ],
    []
  )

  const renderMobileCard = (item) => (
    <div className="p-4 rounded-xl border border-border bg-white shadow-2xs space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-semibold text-zinc-900 block text-sm">
            {item.name}
          </span>
          <span className="font-mono text-xs text-zinc-500">
            {item.registration_number}
          </span>
        </div>
      </div>

      <div className="text-xs text-zinc-600">
        {item.programme_name} • {item.email}
      </div>

      <div className="flex items-center justify-end text-xs pt-1 border-t border-zinc-100">
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleOpenEdit(item)}
          className="h-7 text-xs border-zinc-200"
        >
          <Edit className="w-3 h-3 mr-1" />
          Edit Record
        </Button>
      </div>
    </div>
  )

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950 flex items-center gap-2.5">
              <Users className="w-6 h-6 text-zinc-900" />
              Academic Department Student Roster
            </h1>
            <p className="text-xs sm:text-sm text-zinc-500 mt-1">
              Maintain the student roster and records for programmes belonging strictly to {user?.department_name || 'your academic department'}. Security deposits are entered by Accounts.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleOpenAdd}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-1.5 h-9 font-semibold shadow-xs"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Add Student
            </Button>
          </div>
        </div>

        {/* Navigation Tabs: Directory List vs CSV Batch Upload */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-zinc-100 p-1 border border-border">
            <TabsTrigger value="list" className="gap-2 text-xs font-semibold">
              <Users className="w-3.5 h-3.5" />
              Roster Directory ({totalItems})
            </TabsTrigger>
            <TabsTrigger value="upload" className="gap-2 text-xs font-semibold">
              <Upload className="w-3.5 h-3.5" />
              CSV Batch Ingestion
            </TabsTrigger>
          </TabsList>

          {/* TAB 1: Roster List Table */}
          <TabsContent value="list" className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-1 max-w-xl">
                <div className="relative w-full max-w-sm">
                  <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-2.5" />
                  <Input
                    placeholder="Search name, registration #, or email..."
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value)
                      setPageIndex(0)
                    }}
                    className="pl-9 text-xs h-9 bg-white"
                  />
                </div>
                {hasMultipleAcademic && (
                  <select
                    value={selectedDeptId}
                    onChange={(e) => {
                      setSelectedDeptId(e.target.value)
                      setPageIndex(0)
                    }}
                    className="h-9 rounded-md border border-input bg-white px-2.5 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring shrink-0"
                  >
                    <option value="ALL">All Academic Depts</option>
                    {academicMemberships.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                className="text-xs gap-1.5 h-8 border-border hover:bg-zinc-100 self-end sm:self-auto"
              >
                <RotateCw className="w-3.5 h-3.5" />
                Refresh
              </Button>
            </div>

            <DataTable
              columns={columns}
              data={students}
              isLoading={isLoading}
              manualPagination={true}
              totalItems={totalItems}
              pageIndex={pageIndex}
              pageSize={pageSize}
              onPageChange={(newIdx) => setPageIndex(newIdx)}
              renderMobileCard={renderMobileCard}
              emptyTitle="No students found in academic roster"
              emptyDescription="No student records match the search query or no students have been enrolled yet."
            />
          </TabsContent>

          {/* TAB 2: CSV Upload */}
          <TabsContent value="upload" className="space-y-4">
            <CsvUpload
              title="Upload Academic Programme Roster CSV"
              description="Batch ingest student roster records for programmes in your academic department. Security deposits are entered by Accounts."
              columnsHint={['registration_number', 'name', 'email', 'mobile', 'programme']}
              onUpload={(file) => departmentApi.uploadRosterCsv(file)}
              onDownloadTemplate={() => departmentApi.downloadRosterTemplate()}
              templateFilename="academic_roster_template.csv"
              onSuccess={(res) => {
                if (res?.message) {
                  toast.info(res.message)
                }
                queryClient.invalidateQueries({ queryKey: ['department', 'roster'] })
              }}
            />
          </TabsContent>
        </Tabs>
      </div>

      {/* Dialog: Add Single Student */}
      <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6 max-h-[90vh] overflow-y-auto">
          <form onSubmit={handleAddSubmit}>
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Add Student to Academic Roster
              </DialogTitle>
              <DialogDescription className="text-xs">
                Enroll a new student record into your department's programme roster.
              </DialogDescription>
            </DialogHeader>

            {addError && (
              <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p className="leading-snug">{addError}</p>
              </div>
            )}

            <div className="space-y-3.5 py-1 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="regNum" className="text-xs font-semibold text-zinc-800">
                  Registration Number *
                </Label>
                <Input
                  id="regNum"
                  placeholder="e.g. 2024CS001"
                  value={addForm.registration_number}
                  onChange={(e) => setAddForm({ ...addForm, registration_number: e.target.value.toUpperCase() })}
                  className="font-mono uppercase text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="studName" className="text-xs font-semibold text-zinc-800">
                  Full Name *
                </Label>
                <Input
                  id="studName"
                  placeholder="Student official name"
                  value={addForm.name}
                  onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="studEmail" className="text-xs font-semibold text-zinc-800">
                  University Email *
                </Label>
                <Input
                  id="studEmail"
                  type="email"
                  placeholder="e.g. 2024cs001@svsu.ac.in"
                  value={addForm.email}
                  onChange={(e) => setAddForm({ ...addForm, email: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="studMobile" className="text-xs font-semibold text-zinc-800">
                  Mobile Number (10 digits) *
                </Label>
                <Input
                  id="studMobile"
                  placeholder="e.g. 9876543210"
                  value={addForm.mobile}
                  onChange={(e) => setAddForm({ ...addForm, mobile: e.target.value })}
                  className="font-mono text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="progId" className="text-xs font-semibold text-zinc-800">
                  Programme ID / Academic Course *
                </Label>
                {knownProgrammes.length > 0 ? (
                  <select
                    id="progId"
                    value={addForm.programme_id}
                    onChange={(e) => setAddForm({ ...addForm, programme_id: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    required
                  >
                    <option value="">Select Department Programme...</option>
                    {knownProgrammes.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} (ID: {p.id})
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id="progId"
                    placeholder="Enter numeric Programme ID (e.g. 1)"
                    value={addForm.programme_id}
                    onChange={(e) => setAddForm({ ...addForm, programme_id: e.target.value })}
                    className="font-mono text-xs"
                    required
                  />
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="studAddress" className="text-xs font-semibold text-zinc-800">
                  Residential Address
                </Label>
                <Input
                  id="studAddress"
                  placeholder="City, State, Postal Code"
                  value={addForm.address}
                  onChange={(e) => setAddForm({ ...addForm, address: e.target.value })}
                  className="text-xs"
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setAddModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={createMutation.isPending}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {createMutation.isPending ? 'Adding Student...' : 'Create Roster Entry'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Dialog: Edit Student Record */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleEditSubmit}>
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Edit Student Roster Record
              </DialogTitle>
              <DialogDescription className="text-xs">
                Update record for {selectedStudent?.registration_number} ({selectedStudent?.name}).
              </DialogDescription>
            </DialogHeader>

            {editError && (
              <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p className="leading-snug">{editError}</p>
              </div>
            )}

            <div className="space-y-3.5 py-1 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="editName" className="text-xs font-semibold text-zinc-800">
                  Student Name
                </Label>
                <Input
                  id="editName"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="editEmail" className="text-xs font-semibold text-zinc-800">
                    Official Email
                  </Label>
                  {selectedStudent?.has_user_account && (
                    <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-900 border-amber-200">
                      User Account Active
                    </Badge>
                  )}
                </div>
                <Input
                  id="editEmail"
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  className="text-xs"
                  required
                />
                {selectedStudent?.has_user_account && (
                  <p className="text-[11px] text-zinc-500">
                    Note: If an active user account has already been registered for this student, changing the email address will be rejected with HTTP 409 Conflict.
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="editMobile" className="text-xs font-semibold text-zinc-800">
                  Mobile Number
                </Label>
                <Input
                  id="editMobile"
                  value={editForm.mobile}
                  onChange={(e) => setEditForm({ ...editForm, mobile: e.target.value })}
                  className="font-mono text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="editProgramme" className="text-xs font-semibold text-zinc-800">
                  Degree Programme
                </Label>
                <select
                  id="editProgramme"
                  value={editForm.programme_id}
                  onChange={(e) => setEditForm({ ...editForm, programme_id: e.target.value })}
                  className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="">Select Enrolled Programme...</option>
                  {allowedProgrammes.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-zinc-500">
                  Only programmes within your academic department are permitted. Programme changes are refused if the student has an active clearance request.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="editAddress" className="text-xs font-semibold text-zinc-800">
                  Address
                </Label>
                <Input
                  id="editAddress"
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
                onClick={() => setEditModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={patchMutation.isPending}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {patchMutation.isPending ? 'Saving Changes...' : 'Save Updates'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

export default OfficerRosterPage
