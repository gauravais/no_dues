import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { departmentApi } from '@/api/department'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  FlaskConical,
  Plus,
  Upload,
  Edit,
  AlertTriangle,
  Download,
} from 'lucide-react'

export function AdminLabCoursesPage() {
  useDocumentTitle('Master Lab Catalog (Fallback) | SVSU No-Dues')
  const queryClient = useQueryClient()

  const [viewMode, setViewMode] = useState('list') // 'list' or 'upload'
  const [academicDeptFilter, setAcademicDeptFilter] = useState('ALL')
  const [activeFilter, setActiveFilter] = useState('ALL')
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(30)

  // Modals State
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState(null)

  // Forms
  const [createForm, setCreateForm] = useState({
    code: '',
    name: '',
    academic_department_id: '',
    lab_department_id: '',
    specialization: '',
  })
  const [createError, setCreateError] = useState('')

  const [editForm, setEditForm] = useState({
    name: '',
    specialization: '',
    is_active: true,
  })
  const [editError, setEditError] = useState('')

  // Fetch Departments
  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: () => adminApi.getDepartments(),
  })

  // Fetch Assigned-Only Service Lab Departments
  const { data: assignedOnlyDepts = [] } = useQuery({
    queryKey: ['departments', 'assigned-only'],
    queryFn: () => departmentApi.getAssignedOnlyDepartments(),
  })

  const academicDepartments = useMemo(
    () => departments.filter((d) => d.kind === 'academic'),
    [departments]
  )

  // Fetch Master Lab Courses
  const {
    data: labCoursesData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      'admin',
      'lab-courses',
      academicDeptFilter,
      activeFilter,
      pageIndex,
      pageSize,
    ],
    queryFn: () =>
      adminApi.getLabCourses({
        academic_department_id: academicDeptFilter,
        is_active: activeFilter,
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const courses = useMemo(() => labCoursesData?.items || [], [labCoursesData?.items])

  // Create Mutation
  const createMutation = useMutation({
    mutationFn: (data) => adminApi.createLabCourse(data),
    onSuccess: () => {
      toast.success('Lab course created successfully.')
      setIsCreateOpen(false)
      setCreateForm({
        code: '',
        name: '',
        academic_department_id: '',
        lab_department_id: '',
        specialization: '',
      })
      setCreateError('')
      queryClient.invalidateQueries({ queryKey: ['admin', 'lab-courses'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create lab course.'
      setCreateError(msg)
      toast.error(msg)
    },
  })

  // Patch Mutation
  const patchMutation = useMutation({
    mutationFn: ({ id, data }) => adminApi.patchLabCourse(id, data),
    onSuccess: () => {
      toast.success('Lab course updated successfully.')
      setEditTarget(null)
      setEditError('')
      queryClient.invalidateQueries({ queryKey: ['admin', 'lab-courses'] })
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update lab course.'
      setEditError(msg)
      toast.error(msg)
    },
  })

  const handleCreateSubmit = (e) => {
    e.preventDefault()
    if (
      !createForm.code.trim() ||
      !createForm.name.trim() ||
      !createForm.academic_department_id ||
      !createForm.lab_department_id
    ) {
      setCreateError('Course code, course name, academic department, and lab office are mandatory.')
      return
    }

    createMutation.mutate({
      code: createForm.code.trim(),
      name: createForm.name.trim(),
      academic_department_id: Number(createForm.academic_department_id),
      lab_department_id: Number(createForm.lab_department_id),
      specialization: createForm.specialization.trim() || undefined,
    })
  }

  const handleEditSubmit = (e) => {
    e.preventDefault()
    if (!editTarget) return
    patchMutation.mutate({
      id: editTarget.id,
      data: {
        name: editForm.name.trim(),
        specialization: editForm.specialization.trim() || null,
        is_active: editForm.is_active,
      },
    })
  }

  const handleToggleActive = useCallback(
    (course) => {
      patchMutation.mutate({
        id: course.id,
        data: { is_active: !course.is_active },
      })
    },
    [patchMutation]
  )

  const openEditDialog = (course) => {
    setEditTarget(course)
    setEditForm({
      name: course.name,
      specialization: course.specialization || '',
      is_active: course.is_active,
    })
    setEditError('')
  }

  // Columns
  const columns = useMemo(
    () => [
      {
        accessorKey: 'code',
        header: 'Course Code',
        cell: ({ row }) => (
          <span className="font-mono font-bold text-xs text-zinc-900 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
            {row.original.code}
          </span>
        ),
      },
      {
        accessorKey: 'name',
        header: 'Course Title',
        cell: ({ row }) => (
          <div className="py-1">
            <span className="font-semibold text-xs text-zinc-900 block">
              {row.original.name}
            </span>
            {row.original.specialization && (
              <span className="text-[11px] text-zinc-500">
                Spec: {row.original.specialization}
              </span>
            )}
          </div>
        ),
      },
      {
        accessorKey: 'academic_department_name',
        header: 'Academic Faculty',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-700 max-w-[200px] line-clamp-1">
            {row.original.academic_department_name || '-'}
          </span>
        ),
      },
      {
        accessorKey: 'lab_department_name',
        header: 'Service Lab Office',
        cell: ({ row }) => (
          <Badge
            variant="outline"
            className="bg-indigo-50 text-indigo-800 border-indigo-200 text-[10px] font-mono"
          >
            {row.original.lab_department_name || '-'}
          </Badge>
        ),
      },
      {
        accessorKey: 'is_active',
        header: 'Status',
        cell: ({ row }) => (
          <Badge
            variant="outline"
            className={
              row.original.is_active
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200 text-[10px]'
                : 'bg-zinc-100 text-zinc-600 border-zinc-200 text-[10px]'
            }
          >
            {row.original.is_active ? 'Active' : 'Inactive'}
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
                size="sm"
                variant="ghost"
                onClick={() => openEditDialog(item)}
                className="h-7 text-[11px] text-zinc-600 hover:text-black gap-1"
              >
                <Edit className="w-3 h-3" />
                Edit
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleToggleActive(item)}
                className={`h-7 text-[11px] ${
                  item.is_active
                    ? 'hover:bg-rose-50 text-zinc-700 hover:text-rose-700 border-zinc-200'
                    : 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
                }`}
              >
                {item.is_active ? 'Deactivate' : 'Activate'}
              </Button>
            </div>
          )
        },
      },
    ],
    [handleToggleActive]
  )

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-zinc-900" />
              <h1 className="font-heading text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
                Master Lab Catalog (Global Fallback)
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Institutional directory mapping academic laboratory subjects to specialized service departments.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant={viewMode === 'list' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('list')}
              className="text-xs h-9"
            >
              Catalog Directory
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
            <Button
              size="sm"
              onClick={() => {
                setCreateError('')
                setIsCreateOpen(true)
              }}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold"
            >
              <Plus className="w-3.5 h-3.5" />
              Create Lab Course
            </Button>
          </div>
        </div>

        {viewMode === 'upload' ? (
          <div className="max-w-2xl mx-auto py-4 space-y-4">
            <div className="p-6 rounded-xl border border-border bg-white shadow-card space-y-4">
              <div className="space-y-1">
                <h2 className="font-heading text-base font-bold text-zinc-900">
                  Global Lab Catalog CSV Reference
                </h2>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Bulk CSV ingestion of laboratory subjects is delegated directly to each respective Academic Department Officer (<span className="font-mono text-zinc-800 font-medium">/officer/lab-catalog</span>). Administrators provision and oversee courses across any academic department using the <strong>Create Lab Course</strong> dialog, or download the official template below.
                </p>
              </div>

              <div className="pt-2 flex items-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    const blob = await adminApi.downloadLabCoursesTemplate()
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = 'lab_courses_template.csv'
                    a.click()
                    URL.revokeObjectURL(url)
                    toast.success('Lab courses template downloaded.')
                  }}
                  className="text-xs gap-1.5 h-8 bg-white border-zinc-200"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download Lab Courses Reference Template (CSV)
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setViewMode('list')
                    setIsCreateOpen(true)
                  }}
                  className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-8 gap-1.5 font-semibold"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Create Lab Course
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Filter Toolbar */}
            <div className="flex items-center gap-2 bg-zinc-50/80 p-3 rounded-xl border border-border flex-wrap">
              <select
                value={academicDeptFilter}
                onChange={(e) => {
                  setAcademicDeptFilter(e.target.value)
                  setPageIndex(0)
                }}
                className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="ALL">All Academic Faculties</option>
                {academicDepartments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>

              <select
                value={activeFilter}
                onChange={(e) => {
                  setActiveFilter(e.target.value)
                  setPageIndex(0)
                }}
                className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="ALL">All Statuses</option>
                <option value="true">Active Only</option>
                <option value="false">Inactive Only</option>
              </select>

              {(academicDeptFilter !== 'ALL' || activeFilter !== 'ALL') && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setAcademicDeptFilter('ALL')
                    setActiveFilter('ALL')
                    setPageIndex(0)
                  }}
                  className="text-xs h-9 text-zinc-500 hover:text-black"
                >
                  Clear Filters
                </Button>
              )}
            </div>

            {/* Table */}
            {isError ? (
              <div className="p-6 rounded-xl border border-rose-200 bg-rose-50 text-rose-900 text-xs">
                <p className="font-semibold">Failed to load lab courses catalog.</p>
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
                data={courses}
                loading={isLoading}
                emptyMessage="No lab courses match the active filters."
                pageSize={pageSize}
              />
            )}
          </div>
        )}
      </div>

      {/* CREATE LAB COURSE MODAL */}
      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!open) {
            setIsCreateOpen(false)
            setCreateError('')
          }
        }}
      >
        <DialogContent className="sm:max-w-md bg-white p-6">
          <form onSubmit={handleCreateSubmit}>
            <DialogHeader className="pb-3 border-b border-zinc-100">
              <DialogTitle className="font-heading font-bold text-base flex items-center gap-2">
                <FlaskConical className="w-4 h-4 text-zinc-900" />
                Create Lab Course (Global)
              </DialogTitle>
              <DialogDescription className="text-xs">
                Map a teaching curriculum lab subject to an ASSIGNED_ONLY service department.
              </DialogDescription>
            </DialogHeader>

            {createError && (
              <div className="p-3 my-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p>{createError}</p>
              </div>
            )}

            <div className="space-y-3.5 py-4 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="acadDept" className="text-xs font-semibold text-zinc-800">
                  Academic Faculty
                </Label>
                <select
                  id="acadDept"
                  value={createForm.academic_department_id}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, academic_department_id: e.target.value })
                  }
                  className="w-full h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  required
                >
                  <option value="">Select Academic Department...</option>
                  {academicDepartments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="serviceLab" className="text-xs font-semibold text-zinc-800">
                  Signing Service Lab (ASSIGNED_ONLY)
                </Label>
                <select
                  id="serviceLab"
                  value={createForm.lab_department_id}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, lab_department_id: e.target.value })
                  }
                  className="w-full h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  required
                >
                  <option value="">Select Assigned-Only Service Lab...</option>
                  {assignedOnlyDepts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} (ID: {d.id})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="cCode" className="text-xs font-semibold text-zinc-800">
                    Subject Code
                  </Label>
                  <Input
                    id="cCode"
                    placeholder="e.g. CSE-L101"
                    value={createForm.code}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, code: e.target.value.toUpperCase() })
                    }
                    className="font-mono text-xs uppercase"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="cSpec" className="text-xs font-semibold text-zinc-800">
                    Specialization (Optional)
                  </Label>
                  <Input
                    id="cSpec"
                    placeholder="e.g. AI & ML"
                    value={createForm.specialization}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, specialization: e.target.value })
                    }
                    className="text-xs"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="cName" className="text-xs font-semibold text-zinc-800">
                  Subject Title
                </Label>
                <Input
                  id="cName"
                  placeholder="e.g. Advanced Operating Systems Lab"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="text-xs"
                  required
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t border-zinc-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsCreateOpen(false)}
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
                {createMutation.isPending ? 'Creating...' : 'Create Course'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

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
                Edit Lab Course
              </DialogTitle>
              <DialogDescription className="text-xs">
                Update details for <strong className="text-zinc-900">{editTarget?.code}</strong>.
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
                <Label htmlFor="editName" className="text-xs font-semibold text-zinc-800">
                  Subject Title
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
                <Label htmlFor="editSpec" className="text-xs font-semibold text-zinc-800">
                  Specialization
                </Label>
                <Input
                  id="editSpec"
                  value={editForm.specialization}
                  onChange={(e) => setEditForm({ ...editForm, specialization: e.target.value })}
                  className="text-xs"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="editActive"
                  checked={editForm.is_active}
                  onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                  className="h-4 w-4 rounded border-zinc-300 text-black focus:ring-black accent-zinc-900 cursor-pointer"
                />
                <Label htmlFor="editActive" className="text-xs font-medium text-zinc-800 cursor-pointer">
                  Subject is active in student declaration catalog
                </Label>
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
                disabled={patchMutation.isPending}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {patchMutation.isPending ? 'Saving...' : 'Save Updates'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

export default AdminLabCoursesPage
