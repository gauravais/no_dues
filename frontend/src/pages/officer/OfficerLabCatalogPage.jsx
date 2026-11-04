import { useState, useMemo, useCallback } from 'react'
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
  FlaskConical,
  PlusCircle,
  Edit,
  RotateCw,
  AlertTriangle,
  Upload,
  CheckCircle2,
  XCircle,
  Power,
} from 'lucide-react'

export function OfficerLabCatalogPage() {
  useDocumentTitle('Academic Lab Catalog')
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState('list')
  const [activeFilter, setActiveFilter] = useState('ALL') // ALL, ACTIVE, INACTIVE
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)

  // Dialog States
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [selectedCourse, setSelectedCourse] = useState(null)

  // Create Form State
  const [createForm, setCreateForm] = useState({
    code: '',
    name: '',
    lab_department_id: '',
    specialization: '',
  })
  const [createError, setCreateError] = useState('')

  // Edit Form State
  const [editForm, setEditForm] = useState({
    name: '',
    specialization: '',
    is_active: true,
  })
  const [editError, setEditError] = useState('')

  // Fetch ASSIGNED_ONLY service departments for lab mapping dropdown
  const { data: assignedOnlyDepts = [] } = useQuery({
    queryKey: ['departments', 'assigned-only'],
    queryFn: () => departmentApi.getAssignedOnlyDepartments(),
    staleTime: 300000,
  })

  // Fetch Lab Courses
  const {
    data: labData,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['department', 'lab-courses', activeFilter, pageIndex, pageSize],
    queryFn: () =>
      departmentApi.getLabCourses({
        is_active: activeFilter === 'ALL' ? undefined : activeFilter === 'ACTIVE',
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const courses = useMemo(() => labData?.items || [], [labData?.items])
  const totalItems = labData?.total || 0

  // Create Course Mutation
  const createMutation = useMutation({
    mutationFn: (data) => departmentApi.createLabCourse(data),
    onSuccess: () => {
      toast.success('Lab course created successfully.')
      setCreateModalOpen(false)
      setCreateForm({
        code: '',
        name: '',
        lab_department_id: '',
        specialization: '',
      })
      setCreateError('')
      queryClient.invalidateQueries({ queryKey: ['department', 'lab-courses'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create lab course.'
      setCreateError(msg)
      toast.error(msg)
    },
  })

  // Patch Course Mutation
  const patchMutation = useMutation({
    mutationFn: ({ id, data }) => departmentApi.patchLabCourse(id, data),
    onSuccess: () => {
      toast.success('Lab course updated successfully.')
      setEditModalOpen(false)
      setSelectedCourse(null)
      setEditError('')
      queryClient.invalidateQueries({ queryKey: ['department', 'lab-courses'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update lab course.'
      setEditError(msg)
      toast.error(msg)
    },
  })

  // Toggle Active Status
  const handleToggleActive = useCallback((course) => {
    patchMutation.mutate({
      id: course.id,
      data: { is_active: !course.is_active },
    })
  }, [patchMutation])

  const handleOpenCreate = () => {
    setCreateError('')
    setCreateForm({
      code: '',
      name: '',
      lab_department_id: assignedOnlyDepts[0]?.id ? String(assignedOnlyDepts[0].id) : '',
      specialization: '',
    })
    setCreateModalOpen(true)
  }

  const handleOpenEdit = (course) => {
    setSelectedCourse(course)
    setEditForm({
      name: course.name || '',
      specialization: course.specialization || '',
      is_active: course.is_active,
    })
    setEditError('')
    setEditModalOpen(true)
  }

  const handleCreateSubmit = (e) => {
    e.preventDefault()
    if (!createForm.code.trim() || !createForm.name.trim() || !createForm.lab_department_id) {
      setCreateError('Course code, name, and assigned signing lab office are mandatory.')
      return
    }
    createMutation.mutate(createForm)
  }

  const handleEditSubmit = (e) => {
    e.preventDefault()
    if (!selectedCourse) return
    patchMutation.mutate({
      id: selectedCourse.id,
      data: editForm,
    })
  }

  // Column definitions for DataTable
  const columns = useMemo(
    () => [
      {
        accessorKey: 'code',
        header: 'Course Code',
        cell: ({ row }) => (
          <span className="font-mono font-bold text-xs text-zinc-950">
            {row.original.code}
          </span>
        ),
      },
      {
        accessorKey: 'name',
        header: 'Subject Name',
        cell: ({ row }) => (
          <div>
            <span className="font-semibold text-zinc-900 block text-xs">
              {row.original.name}
            </span>
            {row.original.specialization && (
              <span className="text-[11px] text-zinc-500">
                Track: {row.original.specialization}
              </span>
            )}
          </div>
        ),
      },
      {
        accessorKey: 'lab_department_name',
        header: 'Signing Lab / Workshop Office',
        cell: ({ row }) => (
          <Badge variant="outline" className="text-xs bg-zinc-50 border-zinc-200 text-zinc-800">
            {row.original.lab_department_name || `Dept #${row.original.lab_department_id}`}
          </Badge>
        ),
      },
      {
        accessorKey: 'is_active',
        header: 'Catalog Status',
        cell: ({ row }) =>
          row.original.is_active ? (
            <Badge variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-200 text-[10px] gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              Active
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-zinc-100 text-zinc-500 border-zinc-300 text-[10px] gap-1">
              <XCircle className="w-3 h-3 text-zinc-400" />
              Inactive
            </Badge>
          ),
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => {
          const item = row.original
          return (
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleOpenEdit(item)}
                className="h-7 px-2.5 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-50 gap-1"
              >
                <Edit className="w-3 h-3" />
                Edit
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleToggleActive(item)}
                className={`h-7 px-2 text-xs gap-1 ${
                  item.is_active
                    ? 'border-zinc-200 text-zinc-600 hover:text-rose-600 hover:border-rose-200'
                    : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'
                }`}
              >
                <Power className="w-3 h-3" />
                {item.is_active ? 'Deactivate' : 'Activate'}
              </Button>
            </div>
          )
        },
      },
    ],
    [handleToggleActive]
  )

  const renderMobileCard = (item) => (
    <div className="p-4 rounded-xl border border-border bg-white shadow-2xs space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-mono font-bold text-xs text-zinc-900 block">
            {item.code}
          </span>
          <span className="font-semibold text-sm text-zinc-900">
            {item.name}
          </span>
        </div>
        {item.is_active ? (
          <Badge variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-200 text-[10px]">
            Active
          </Badge>
        ) : (
          <Badge variant="outline" className="bg-zinc-100 text-zinc-500 border-zinc-300 text-[10px]">
            Inactive
          </Badge>
        )}
      </div>

      <div className="text-xs text-zinc-600">
        Signing Office: <strong>{item.lab_department_name}</strong>
        {item.specialization && <span> • Specialization: {item.specialization}</span>}
      </div>

      <div className="flex items-center gap-2 pt-1 border-t border-zinc-100">
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleOpenEdit(item)}
          className="flex-1 h-7 text-xs border-zinc-200"
        >
          <Edit className="w-3 h-3 mr-1" />
          Edit
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleToggleActive(item)}
          className="flex-1 h-7 text-xs border-zinc-200"
        >
          <Power className="w-3 h-3 mr-1" />
          {item.is_active ? 'Deactivate' : 'Activate'}
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
              <FlaskConical className="w-6 h-6 text-zinc-900" />
              Academic Department Laboratory Catalog
            </h1>
            <p className="text-xs sm:text-sm text-zinc-500 mt-1">
              Configure and maintain laboratory subjects and their signing facilities for programmes in {user?.department_name || 'your academic department'}.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleOpenCreate}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs gap-1.5 h-9 font-semibold shadow-xs"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              Add Lab Subject
            </Button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-zinc-100 p-1 border border-border">
            <TabsTrigger value="list" className="gap-2 text-xs font-semibold">
              <FlaskConical className="w-3.5 h-3.5" />
              Lab Courses ({totalItems})
            </TabsTrigger>
            <TabsTrigger value="upload" className="gap-2 text-xs font-semibold">
              <Upload className="w-3.5 h-3.5" />
              CSV Batch Ingestion
            </TabsTrigger>
          </TabsList>

          {/* TAB 1: Lab Courses List */}
          <TabsContent value="list" className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Button
                  variant={activeFilter === 'ALL' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setActiveFilter('ALL')
                    setPageIndex(0)
                  }}
                  className="h-8 text-xs"
                >
                  All ({totalItems})
                </Button>
                <Button
                  variant={activeFilter === 'ACTIVE' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setActiveFilter('ACTIVE')
                    setPageIndex(0)
                  }}
                  className="h-8 text-xs"
                >
                  Active Only
                </Button>
                <Button
                  variant={activeFilter === 'INACTIVE' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setActiveFilter('INACTIVE')
                    setPageIndex(0)
                  }}
                  className="h-8 text-xs"
                >
                  Inactive
                </Button>
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
              data={courses}
              isLoading={isLoading}
              manualPagination={true}
              totalItems={totalItems}
              pageIndex={pageIndex}
              pageSize={pageSize}
              onPageChange={(newIdx) => setPageIndex(newIdx)}
              renderMobileCard={renderMobileCard}
              emptyTitle="No lab courses found"
              emptyDescription="No lab subjects configured for this academic department yet."
            />
          </TabsContent>

          {/* TAB 2: CSV Upload */}
          <TabsContent value="upload" className="space-y-4">
            <CsvUpload
              title="Upload Lab Courses CSV Batch"
              description="Batch import lab subjects mapped to signing facilities for your department's programmes."
              columnsHint={['code', 'name', 'lab_office', 'specialization']}
              onUpload={(file) => departmentApi.uploadLabCoursesCsv(file)}
              onDownloadTemplate={() => departmentApi.downloadLabCoursesTemplate()}
              templateFilename="lab_courses_template.csv"
              onSuccess={() => {
                queryClient.invalidateQueries({ queryKey: ['department', 'lab-courses'] })
              }}
            />
          </TabsContent>
        </Tabs>
      </div>

      {/* Dialog: Create Lab Course */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleCreateSubmit}>
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Add Laboratory Subject
              </DialogTitle>
              <DialogDescription className="text-xs">
                Create a new lab or workshop subject mapped to an assigned signing facility.
              </DialogDescription>
            </DialogHeader>

            {createError && (
              <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p className="leading-snug">{createError}</p>
              </div>
            )}

            <div className="space-y-3.5 py-1 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="labCode" className="text-xs font-semibold text-zinc-800">
                  Course / Subject Code *
                </Label>
                <Input
                  id="labCode"
                  placeholder="e.g. CSE401"
                  value={createForm.code}
                  onChange={(e) => setCreateForm({ ...createForm, code: e.target.value.toUpperCase() })}
                  className="font-mono uppercase text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="labName" className="text-xs font-semibold text-zinc-800">
                  Subject / Laboratory Name *
                </Label>
                <Input
                  id="labName"
                  placeholder="e.g. Advanced Operating Systems Laboratory"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="signingOffice" className="text-xs font-semibold text-zinc-800">
                  Signing Service Facility (Assigned-Only Office) *
                </Label>
                <select
                  id="signingOffice"
                  value={createForm.lab_department_id}
                  onChange={(e) => setCreateForm({ ...createForm, lab_department_id: e.target.value })}
                  className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  required
                >
                  <option value="">Select Signing Laboratory / Workshop...</option>
                  {assignedOnlyDepts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.code})
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-zinc-500">
                  Must be an assigned-only service facility (e.g. Lab-1 through Lab-9, Workshop-1 through Workshop-3).
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="specialization" className="text-xs font-semibold text-zinc-800">
                  Academic Specialization / Track (Optional)
                </Label>
                <Input
                  id="specialization"
                  placeholder="e.g. Artificial Intelligence, IoT, or Core"
                  value={createForm.specialization}
                  onChange={(e) => setCreateForm({ ...createForm, specialization: e.target.value })}
                  className="text-xs"
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCreateModalOpen(false)}
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
                {createMutation.isPending ? 'Creating Subject...' : 'Create Lab Course'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Dialog: Edit Lab Course */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleEditSubmit}>
            <DialogHeader className="pb-3">
              <DialogTitle className="font-heading font-bold text-base">
                Edit Laboratory Subject
              </DialogTitle>
              <DialogDescription className="text-xs">
                Update course information for {selectedCourse?.code}.
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
                <Label htmlFor="editLabName" className="text-xs font-semibold text-zinc-800">
                  Subject Name
                </Label>
                <Input
                  id="editLabName"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="editSpec" className="text-xs font-semibold text-zinc-800">
                  Specialization / Track
                </Label>
                <Input
                  id="editSpec"
                  value={editForm.specialization}
                  onChange={(e) => setEditForm({ ...editForm, specialization: e.target.value })}
                  className="text-xs"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="editIsActive"
                  checked={editForm.is_active}
                  onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                  className="h-4 w-4 rounded border-zinc-300 text-black focus:ring-black accent-zinc-900 cursor-pointer"
                />
                <Label htmlFor="editIsActive" className="text-xs font-medium text-zinc-800 cursor-pointer">
                  Subject is active in student clearance declaration catalog
                </Label>
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
                {patchMutation.isPending ? 'Saving Updates...' : 'Save Updates'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

export default OfficerLabCatalogPage
