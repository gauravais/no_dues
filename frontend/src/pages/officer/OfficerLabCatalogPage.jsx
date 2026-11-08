import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { departmentApi } from '@/api/department'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Card, CardContent } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
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
  PlusCircle,
  Edit,
  RotateCw,
  AlertTriangle,
  Upload,
  CheckCircle2,
  XCircle,
  Power,
  FileCheck2,
  Download,
  Plus,
  ArrowRight,
} from 'lucide-react'

export function OfficerLabCatalogPage() {
  useDocumentTitle('Academic Lab Catalog | SVSU No-Dues')
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState('list') // 'list', 'my-workshops', 'upload'
  const [activeFilter, setActiveFilter] = useState('ALL') // ALL, ACTIVE, INACTIVE
  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)

  // Multi-academic department support
  const academicMemberships = useMemo(() => {
    const depts = user?.departments || []
    return depts.filter((d) => d.kind === 'academic')
  }, [user?.departments])

  const hasMultipleAcademic = academicMemberships.length > 1
  const [selectedDeptId, setSelectedDeptId] = useState('ALL')

  // Subject Modals State
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [selectedCourse, setSelectedCourse] = useState(null)

  // Create Subject Form State
  const [createForm, setCreateForm] = useState({
    code: '',
    name: '',
    lab_department_id: '',
    specialization: '',
    academic_department_id: '',
  })
  const [createError, setCreateError] = useState('')

  // Edit Subject Form State
  const [editForm, setEditForm] = useState({
    code: '',
    name: '',
    lab_department_id: '',
    specialization: '',
    is_active: true,
  })
  const [editError, setEditError] = useState('')

  // "My Labs & Workshops" Panel States
  const [createWorkshopModalOpen, setCreateWorkshopModalOpen] = useState(false)
  const [workshopForm, setWorkshopForm] = useState({ name: '', description: '' })
  const [workshopError, setWorkshopError] = useState('')

  const [editWorkshopModalOpen, setEditWorkshopModalOpen] = useState(false)
  const [editingWorkshop, setEditingWorkshop] = useState(null)
  const [editWorkshopForm, setEditWorkshopForm] = useState({ name: '', description: '', is_active: true })
  const [editWorkshopError, setEditWorkshopError] = useState('')

  // CSV Upload Advanced State
  const [uploadFile, setUploadFile] = useState(null)
  const [checkingFile, setCheckingFile] = useState(false)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [createMissingOffices, setCreateMissingOffices] = useState(false)
  const [dryRunReport, setDryRunReport] = useState(null)
  const [finalUploadReport, setFinalUploadReport] = useState(null)

  // 1. Fetch Lab / Workshop Offices from GET /department/lab-workshops
  const {
    data: labWorkshops = [],
    isLoading: workshopsLoading,
  } = useQuery({
    queryKey: ['department', 'lab-workshops'],
    queryFn: () => departmentApi.getLabWorkshops(),
  })

  // 2. Fetch Lab Courses
  const {
    data: labData,
    isLoading,
  } = useQuery({
    queryKey: ['department', 'lab-courses', activeFilter, pageIndex, pageSize, selectedDeptId],
    queryFn: () =>
      departmentApi.getLabCourses({
        is_active: activeFilter === 'ALL' ? undefined : activeFilter === 'ACTIVE',
        limit: pageSize,
        offset: pageIndex * pageSize,
        departmentId: selectedDeptId === 'ALL' ? undefined : selectedDeptId,
      }),
  })

  const courses = useMemo(() => labData?.items || [], [labData?.items])
  const totalItems = labData?.total || 0

  // Filter lab workshops for searchable picker
  const activeLabOffices = useMemo(
    () => labWorkshops.filter((o) => o.is_active !== false),
    [labWorkshops]
  )

  // Invalidate all related queries
  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['department', 'lab-courses'] })
    queryClient.invalidateQueries({ queryKey: ['department', 'lab-workshops'] })
  }

  // --- MUTATIONS ---

  // Create Lab Course Mutation
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
        academic_department_id: '',
      })
      setCreateError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create lab course.'
      setCreateError(msg)
      toast.error(msg)
    },
  })

  // Patch Lab Course Mutation
  const patchMutation = useMutation({
    mutationFn: ({ id, data }) => departmentApi.patchLabCourse(id, data),
    onSuccess: () => {
      toast.success('Lab course updated successfully.')
      setEditModalOpen(false)
      setSelectedCourse(null)
      setEditError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update lab course.'
      setEditError(msg)
      toast.error(msg)
    },
  })

  // Toggle Subject Active Status
  const handleToggleActive = useCallback(
    (course) => {
      patchMutation.mutate({
        id: course.id,
        data: { is_active: !course.is_active },
      })
    },
    [patchMutation]
  )

  // Create Lab Workshop Office Mutation
  const createWorkshopMutation = useMutation({
    mutationFn: (data) => departmentApi.createLabWorkshop(data),
    onSuccess: (res) => {
      toast.success(`Lab/Workshop "${res.name}" created successfully.`)
      setCreateWorkshopModalOpen(false)
      setWorkshopForm({ name: '', description: '' })
      setWorkshopError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create lab/workshop office.'
      setWorkshopError(msg)
      toast.error(msg)
    },
  })

  // Patch Lab Workshop Office Mutation
  const patchWorkshopMutation = useMutation({
    mutationFn: ({ id, data }) => departmentApi.patchLabWorkshop(id, data),
    onSuccess: (res) => {
      toast.success(`Lab/Workshop "${res.name}" updated successfully.`)
      setEditWorkshopModalOpen(false)
      setEditingWorkshop(null)
      setEditWorkshopError('')
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update lab/workshop office.'
      setEditWorkshopError(msg)
      toast.error(msg)
    },
  })

  // Open Handlers
  const handleOpenCreate = () => {
    setCreateError('')
    setCreateForm({
      code: '',
      name: '',
      lab_department_id: activeLabOffices[0]?.id ? String(activeLabOffices[0].id) : '',
      specialization: '',
      academic_department_id: academicMemberships[0]?.id ? String(academicMemberships[0].id) : '',
    })
    setCreateModalOpen(true)
  }

  const handleOpenEdit = (course) => {
    setSelectedCourse(course)
    setEditForm({
      code: course.code || '',
      name: course.name || '',
      lab_department_id: course.lab_department_id ? String(course.lab_department_id) : '',
      specialization: course.specialization || '',
      is_active: course.is_active,
    })
    setEditError('')
    setEditModalOpen(true)
  }

  const handleOpenEditWorkshop = (ws) => {
    setEditingWorkshop(ws)
    setEditWorkshopForm({
      name: ws.name,
      description: ws.description || '',
      is_active: ws.is_active,
    })
    setEditWorkshopError('')
    setEditWorkshopModalOpen(true)
  }

  // Submit Handlers
  const handleCreateSubmit = (e) => {
    e.preventDefault()
    if (!createForm.code.trim() || !createForm.name.trim() || !createForm.lab_department_id) {
      setCreateError('Course code, name, and signing lab/workshop office are mandatory.')
      return
    }
    const payload = {
      code: createForm.code.trim().toUpperCase(),
      name: createForm.name.trim(),
      lab_department_id: Number(createForm.lab_department_id),
      specialization: createForm.specialization.trim() || undefined,
    }
    if (hasMultipleAcademic && createForm.academic_department_id) {
      payload.academic_department_id = Number(createForm.academic_department_id)
    }
    createMutation.mutate(payload)
  }

  const handleEditSubmit = (e) => {
    e.preventDefault()
    if (!selectedCourse) return
    patchMutation.mutate({
      id: selectedCourse.id,
      data: {
        code: editForm.code.trim().toUpperCase(),
        name: editForm.name.trim(),
        lab_department_id: Number(editForm.lab_department_id),
        specialization: editForm.specialization.trim() || null,
        is_active: editForm.is_active,
      },
    })
  }

  // CSV Dry Run ("Check file") Handler
  const handleCheckFile = async () => {
    if (!uploadFile) {
      toast.error('Please select a CSV file first.')
      return
    }
    setCheckingFile(true)
    setDryRunReport(null)
    setFinalUploadReport(null)
    try {
      const res = await departmentApi.uploadLabCoursesCsv(uploadFile, {
        dry_run: true,
        create_missing_offices: createMissingOffices,
      })
      setDryRunReport(res)
      toast.info(`Dry run complete: ${res.total_rows} rows analyzed.`)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to analyze CSV file.'
      toast.error(msg)
    } finally {
      setCheckingFile(false)
    }
  }

  // CSV Final Upload Handler
  const handleUploadFile = async () => {
    if (!uploadFile) {
      toast.error('Please select a CSV file first.')
      return
    }
    setUploadingFile(true)
    try {
      const res = await departmentApi.uploadLabCoursesCsv(uploadFile, {
        dry_run: false,
        create_missing_offices: createMissingOffices,
      })
      setFinalUploadReport(res)
      setDryRunReport(null)
      toast.success(`Upload complete: ${res.created_count} created, ${res.updated_count} updated.`)
      invalidateAll()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to upload lab courses CSV.'
      toast.error(msg)
    } finally {
      setUploadingFile(false)
    }
  }

  const handleDownloadTemplate = async () => {
    try {
      const blob = await departmentApi.downloadLabCoursesTemplate()
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/csv' }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'lab_courses_template.csv')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to download template.')
    }
  }

  // Table Columns
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
            {row.original.lab_department_name || `Office #${row.original.lab_department_id}`}
          </Badge>
        ),
      },
      {
        accessorKey: 'is_active',
        header: 'Status',
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
        <Badge
          variant="outline"
          className={`text-[10px] ${
            item.is_active
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-zinc-100 text-zinc-500 border-zinc-300'
          }`}
        >
          {item.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </div>

      <div className="text-xs text-zinc-600 space-y-1">
        <div>
          <span className="text-zinc-400">Signing Facility: </span>
          <span className="font-medium">{item.lab_department_name}</span>
        </div>
        {item.specialization && (
          <div>
            <span className="text-zinc-400">Track: </span>
            <span className="font-medium">{item.specialization}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 pt-2 border-t border-zinc-100">
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleOpenEdit(item)}
          className="h-7 text-xs flex-1 gap-1"
        >
          <Edit className="w-3 h-3" />
          Edit
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleToggleActive(item)}
          className={`h-7 text-xs flex-1 gap-1 ${
            item.is_active ? 'text-zinc-600' : 'text-emerald-700'
          }`}
        >
          <Power className="w-3 h-3" />
          {item.is_active ? 'Deactivate' : 'Activate'}
        </Button>
      </div>
    </div>
  )

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-16">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
              Laboratory & Workshop Catalog
            </h1>
            <p className="text-xs sm:text-sm text-zinc-500 mt-1">
              Curriculum laboratory subjects and workshop facilities for academic department clearance.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleOpenCreate}
              className="bg-black text-white hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold shadow-xs"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              Add Subject
            </Button>
          </div>
        </div>

        {/* Academic Department Switcher (if officer has multiple) */}
        {hasMultipleAcademic && (
          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl flex items-center justify-between text-xs">
            <span className="font-medium text-zinc-700">Filter by Academic Department:</span>
            <select
              value={selectedDeptId}
              onChange={(e) => {
                setSelectedDeptId(e.target.value)
                setPageIndex(0)
              }}
              className="h-8 rounded-md border border-zinc-300 bg-white px-3 py-1 text-xs"
            >
              <option value="ALL">All my academic departments</option>
              {academicMemberships.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Top-Level Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <div className="border-b border-border mb-6">
            <TabsList className="bg-transparent h-auto p-0 gap-6">
              <TabsTrigger
                value="list"
                className="data-[state=active]:border-black data-[state=active]:text-black text-zinc-500 border-b-2 border-transparent rounded-none px-2 py-3 text-xs font-semibold"
              >
                Lab Subjects ({totalItems})
              </TabsTrigger>
              <TabsTrigger
                value="my-workshops"
                className="data-[state=active]:border-black data-[state=active]:text-black text-zinc-500 border-b-2 border-transparent rounded-none px-2 py-3 text-xs font-semibold"
              >
                My Labs & Workshops ({labWorkshops.length})
              </TabsTrigger>
              <TabsTrigger
                value="upload"
                className="data-[state=active]:border-black data-[state=active]:text-black text-zinc-500 border-b-2 border-transparent rounded-none px-2 py-3 text-xs font-semibold gap-1.5"
              >
                <Upload className="w-3.5 h-3.5" />
                CSV Batch Upload
              </TabsTrigger>
            </TabsList>
          </div>

          {/* TAB 1: Lab Subjects Catalog */}
          <TabsContent value="list" className="space-y-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-zinc-500 font-medium">Filter status:</span>
                {['ALL', 'ACTIVE', 'INACTIVE'].map((f) => (
                  <Button
                    key={f}
                    variant={activeFilter === f ? 'secondary' : 'ghost'}
                    size="sm"
                    onClick={() => {
                      setActiveFilter(f)
                      setPageIndex(0)
                    }}
                    className="h-7 text-xs px-2.5 font-medium"
                  >
                    {f === 'ALL' ? 'All' : f === 'ACTIVE' ? 'Active' : 'Inactive'}
                  </Button>
                ))}
              </div>

              <span className="text-xs text-zinc-400 font-mono">
                Total: {totalItems} subjects
              </span>
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

          {/* TAB 2: My Labs & Workshops Panel */}
          <TabsContent value="my-workshops" className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-zinc-950">
                  Managed Labs & Workshops
                </h3>
                <p className="text-xs text-zinc-500">
                  Offices hosted by your department. You can create new facilities and edit those you created.
                </p>
              </div>

              <Button
                size="sm"
                onClick={() => {
                  setWorkshopError('')
                  setWorkshopForm({ name: '', description: '' })
                  setCreateWorkshopModalOpen(true)
                }}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-8 gap-1.5 font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                New Lab or Workshop
              </Button>
            </div>

            <div className="border border-border rounded-xl bg-white overflow-hidden shadow-2xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-50/75 border-b border-border text-zinc-600 font-semibold uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="p-3">Facility Name</th>
                    <th className="p-3">Description</th>
                    <th className="p-3">Hosted Subjects</th>
                    <th className="p-3">Status</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {workshopsLoading ? (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-zinc-500">
                        Loading labs and workshops...
                      </td>
                    </tr>
                  ) : labWorkshops.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-zinc-500">
                        No labs or workshops assigned to your academic department yet.
                      </td>
                    </tr>
                  ) : (
                    labWorkshops.map((ws) => (
                      <tr key={ws.id} className="hover:bg-zinc-50/50 transition-colors">
                        <td className="p-3 font-semibold text-zinc-950">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span>{ws.name}</span>
                            {ws.created_by_me && (
                              <Badge variant="outline" className="text-[9px] bg-zinc-100 text-zinc-700 py-0">
                                Created by you
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="p-3 text-zinc-600 max-w-[260px]">
                          {ws.description || <span className="text-zinc-400 italic">No description</span>}
                        </td>
                        <td className="p-3 font-mono font-medium text-zinc-800">
                          {ws.subject_count || 0} subjects
                        </td>
                        <td className="p-3">
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-medium ${
                              ws.is_active
                                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                : 'bg-zinc-100 text-zinc-600 border-zinc-300'
                            }`}
                          >
                            {ws.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </td>
                        <td className="p-3 text-right">
                          {ws.editable ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenEditWorkshop(ws)}
                              className="h-8 px-2 text-xs text-zinc-700 hover:bg-zinc-100 gap-1"
                            >
                              <Edit className="w-3.5 h-3.5" />
                              Edit
                            </Button>
                          ) : (
                            <span className="text-[11px] text-zinc-400 italic">
                              Managed centrally
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </TabsContent>

          {/* TAB 3: Advanced CSV Batch Upload */}
          <TabsContent value="upload" className="space-y-6">
            <Card className="border-border bg-white shadow-2xs">
              <CardContent className="p-6 space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
                  <div>
                    <h3 className="text-base font-bold text-zinc-950">
                      Upload Lab Courses CSV Batch
                    </h3>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      Ingest laboratory subjects mapped to signing facilities. Format: code, name, lab_office, specialization.
                    </p>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadTemplate}
                    className="text-xs gap-1.5 h-8 bg-zinc-50"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download CSV Template
                  </Button>
                </div>

                {/* File picker */}
                <div className="space-y-3">
                  <Label htmlFor="lab-csv" className="text-xs font-semibold text-zinc-800">
                    Select CSV File
                  </Label>
                  <Input
                    id="lab-csv"
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => {
                      setUploadFile(e.target.files?.[0] || null)
                      setDryRunReport(null)
                      setFinalUploadReport(null)
                    }}
                    className="text-xs cursor-pointer"
                  />
                </div>

                {/* Checkbox: Create missing labs and workshops */}
                <div className="p-3.5 rounded-xl border border-zinc-200 bg-zinc-50/50 space-y-1">
                  <label className="flex items-start gap-2.5 cursor-pointer text-xs select-none">
                    <input
                      type="checkbox"
                      checked={createMissingOffices}
                      onChange={(e) => setCreateMissingOffices(e.target.checked)}
                      className="mt-0.5 rounded border-zinc-300 text-black focus:ring-black h-4 w-4"
                    />
                    <div className="space-y-0.5">
                      <span className="font-bold text-zinc-900 block">
                        Create missing labs and workshops automatically
                      </span>
                      <span className="text-[11px] text-zinc-500 block leading-relaxed">
                        When ticked, any laboratory or workshop office named in the CSV that does not exist in the university directory will be automatically created under Labs & Workshops. Unticked by default to prevent accidental spelling duplicates.
                      </span>
                    </div>
                  </label>
                </div>

                {/* Action Buttons: Check File (Dry Run) & Upload */}
                <div className="flex items-center gap-3 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCheckFile}
                    disabled={!uploadFile || checkingFile || uploadingFile}
                    className="text-xs h-9 gap-1.5 font-semibold"
                  >
                    {checkingFile ? (
                      <>
                        <RotateCw className="w-3.5 h-3.5 animate-spin" />
                        Checking file...
                      </>
                    ) : (
                      <>
                        <FileCheck2 className="w-3.5 h-3.5" />
                        Check file (Dry Run)
                      </>
                    )}
                  </Button>

                  <Button
                    type="button"
                    onClick={handleUploadFile}
                    disabled={!uploadFile || checkingFile || uploadingFile}
                    className="bg-black text-white hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold"
                  >
                    {uploadingFile ? (
                      <>
                        <RotateCw className="w-3.5 h-3.5 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="w-3.5 h-3.5" />
                        Upload & Ingest
                      </>
                    )}
                  </Button>
                </div>

                {/* Dry Run Preview Report */}
                {dryRunReport && (
                  <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/40 space-y-3 text-xs">
                    <div className="flex items-center gap-2">
                      <FileCheck2 className="w-4 h-4 text-blue-700" />
                      <span className="font-bold text-blue-950 text-sm">
                        Pre-Upload Simulation Report
                      </span>
                      <Badge variant="outline" className="bg-blue-100 text-blue-900 border-blue-300 text-[10px] font-mono">
                        DRY RUN PREVIEW
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                      <div className="p-2.5 bg-white rounded-lg border border-blue-100">
                        <span className="text-[11px] text-zinc-500 block">Total Rows</span>
                        <span className="font-bold text-sm font-mono text-zinc-900">{dryRunReport.total_rows}</span>
                      </div>
                      <div className="p-2.5 bg-white rounded-lg border border-blue-100">
                        <span className="text-[11px] text-zinc-500 block">New Subjects</span>
                        <span className="font-bold text-sm font-mono text-emerald-700">+{dryRunReport.created_count}</span>
                      </div>
                      <div className="p-2.5 bg-white rounded-lg border border-blue-100">
                        <span className="text-[11px] text-zinc-500 block">Updated</span>
                        <span className="font-bold text-sm font-mono text-blue-700">{dryRunReport.updated_count}</span>
                      </div>
                      <div className="p-2.5 bg-white rounded-lg border border-blue-100">
                        <span className="text-[11px] text-zinc-500 block">Rejected / Errors</span>
                        <span className="font-bold text-sm font-mono text-rose-600">{dryRunReport.rejected_count}</span>
                      </div>
                    </div>

                    {dryRunReport.offices_to_create && dryRunReport.offices_to_create.length > 0 && (
                      <div className="p-3 bg-white rounded-lg border border-blue-200 space-y-1">
                        <span className="font-semibold text-zinc-900 block">
                          Labs and Workshops to be Created ({dryRunReport.offices_to_create.length}):
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {dryRunReport.offices_to_create.map((off, idx) => (
                            <Badge key={idx} variant="outline" className="bg-blue-50 text-blue-900 border-blue-200 font-mono text-[10px]">
                              {off}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Preview Rows Table */}
                    {dryRunReport.rows && dryRunReport.rows.length > 0 && (
                      <div className="max-h-[200px] overflow-y-auto border border-blue-200 rounded-lg bg-white">
                        <table className="w-full text-left text-[11px]">
                          <thead className="bg-zinc-50 border-b text-zinc-600">
                            <tr>
                              <th className="p-2">Row</th>
                              <th className="p-2">Code</th>
                              <th className="p-2">Status</th>
                              <th className="p-2">Details</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-100">
                            {dryRunReport.rows.map((r) => (
                              <tr key={r.row_number}>
                                <td className="p-2 font-mono text-zinc-500">#{r.row_number}</td>
                                <td className="p-2 font-mono font-semibold text-zinc-900">{r.code}</td>
                                <td className="p-2">
                                  <Badge
                                    variant="outline"
                                    className={`text-[9px] ${
                                      r.status === 'created'
                                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                        : r.status === 'updated'
                                        ? 'bg-blue-50 text-blue-800 border-blue-200'
                                        : 'bg-rose-50 text-rose-800 border-rose-200'
                                    }`}
                                  >
                                    {r.status}
                                  </Badge>
                                </td>
                                <td className="p-2 text-zinc-600">{r.reason || 'OK'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Final Real Upload Report */}
                {finalUploadReport && (
                  <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/40 space-y-4 text-xs">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                      <span className="font-bold text-emerald-950 text-sm">
                        Batch Ingestion Completed
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="p-2.5 bg-white rounded-lg border border-emerald-100">
                        <span className="text-[11px] text-zinc-500 block">Total Rows</span>
                        <span className="font-bold text-sm font-mono text-zinc-900">{finalUploadReport.total_rows}</span>
                      </div>
                      <div className="p-2.5 bg-white rounded-lg border border-emerald-100">
                        <span className="text-[11px] text-zinc-500 block">Created</span>
                        <span className="font-bold text-sm font-mono text-emerald-700">+{finalUploadReport.created_count}</span>
                      </div>
                      <div className="p-2.5 bg-white rounded-lg border border-emerald-100">
                        <span className="text-[11px] text-zinc-500 block">Updated</span>
                        <span className="font-bold text-sm font-mono text-blue-700">{finalUploadReport.updated_count}</span>
                      </div>
                      <div className="p-2.5 bg-white rounded-lg border border-emerald-100">
                        <span className="text-[11px] text-zinc-500 block">Rejected</span>
                        <span className="font-bold text-sm font-mono text-rose-600">{finalUploadReport.rejected_count}</span>
                      </div>
                    </div>

                    {/* Created Offices */}
                    {finalUploadReport.offices_to_create && finalUploadReport.offices_to_create.length > 0 && (
                      <div className="p-3 bg-white rounded-lg border border-emerald-200 space-y-1">
                        <span className="font-semibold text-zinc-900 block">
                          Newly Created Laboratories & Workshops:
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {finalUploadReport.offices_to_create.map((off, idx) => (
                            <Badge key={idx} variant="outline" className="bg-emerald-50 text-emerald-900 border-emerald-200 font-mono text-[10px]">
                              {off}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Offices Changed per Subject */}
                    {finalUploadReport.rows && finalUploadReport.rows.filter((r) => r.status === 'updated' && r.reason?.includes('office changed')).length > 0 && (
                      <div className="p-3 bg-white rounded-lg border border-blue-200 space-y-1.5">
                        <span className="font-semibold text-zinc-900 block">
                          Office Reassignments:
                        </span>
                        <div className="space-y-1">
                          {finalUploadReport.rows
                            .filter((r) => r.status === 'updated' && r.reason?.includes('office changed'))
                            .map((r) => (
                              <div key={r.row_number} className="text-[11px] flex items-center gap-2">
                                <span className="font-mono font-bold text-zinc-900">{r.code}:</span>
                                <span className="text-zinc-600">{r.reason}</span>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}

                    {/* Warning List: Offices without an assigned officer */}
                    {finalUploadReport.offices_without_officers && finalUploadReport.offices_without_officers.length > 0 && (
                      <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 space-y-2">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-700" />
                          <span className="font-bold text-amber-950">
                            Offices Without an Assigned Dealing Officer
                          </span>
                        </div>
                        <p className="text-[11px] text-amber-900">
                          The following offices are attached to your subjects but do not have an active dealing officer to sign clearances:
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {finalUploadReport.offices_without_officers.map((off, idx) => (
                            <Badge key={idx} variant="outline" className="bg-white border-amber-300 text-amber-900 text-[10px]">
                              {off}
                            </Badge>
                          ))}
                        </div>
                        {user?.role === 'admin' && (
                          <div className="pt-1">
                            <Link
                              to="/admin/offices"
                              className="text-xs font-semibold text-amber-950 underline hover:text-black inline-flex items-center gap-1"
                            >
                              Go to Offices & Staffing to assign officers
                              <ArrowRight className="w-3 h-3" />
                            </Link>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Dialog: Create Subject */}
        <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form onSubmit={handleCreateSubmit}>
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  Add Laboratory Subject
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Create a new curriculum lab or workshop subject mapped to an active signing facility.
                </DialogDescription>
              </DialogHeader>

              {createError && (
                <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <p className="leading-snug">{createError}</p>
                </div>
              )}

              <div className="space-y-3.5 py-1 text-xs">
                {hasMultipleAcademic && (
                  <div className="space-y-1.5">
                    <Label htmlFor="academicDeptSelect" className="text-xs font-semibold text-zinc-800">
                      Academic Department *
                    </Label>
                    <select
                      id="academicDeptSelect"
                      value={createForm.academic_department_id}
                      onChange={(e) =>
                        setCreateForm({ ...createForm, academic_department_id: e.target.value })
                      }
                      className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      required
                    >
                      {academicMemberships.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

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
                    Signing Lab / Workshop Office *
                  </Label>
                  <select
                    id="signingOffice"
                    value={createForm.lab_department_id}
                    onChange={(e) => setCreateForm({ ...createForm, lab_department_id: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    required
                  >
                    <option value="">Select Signing Laboratory / Workshop...</option>
                    {activeLabOffices.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
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
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Lab Course'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Dialog: Edit Subject (code, name, office searchable select, specialization, active) */}
        <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form onSubmit={handleEditSubmit}>
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  Edit Laboratory Subject
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Update subject details, signing lab office assignment, and active catalog state.
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
                  <Label htmlFor="editLabCode" className="text-xs font-semibold text-zinc-800">
                    Course Code <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="editLabCode"
                    value={editForm.code}
                    onChange={(e) => setEditForm({ ...editForm, code: e.target.value.toUpperCase() })}
                    className="font-mono uppercase text-xs"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="editLabName" className="text-xs font-semibold text-zinc-800">
                    Subject Name <span className="text-rose-500">*</span>
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
                  <Label htmlFor="editLabDept" className="text-xs font-semibold text-zinc-800">
                    Signing Lab / Workshop Office <span className="text-rose-500">*</span>
                  </Label>
                  <select
                    id="editLabDept"
                    value={editForm.lab_department_id}
                    onChange={(e) => setEditForm({ ...editForm, lab_department_id: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    required
                  >
                    <option value="">Select Signing Laboratory / Workshop...</option>
                    {activeLabOffices.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="editSpec" className="text-xs font-semibold text-zinc-800">
                    Specialization / Track
                  </Label>
                  <Input
                    id="editSpec"
                    value={editForm.specialization}
                    onChange={(e) => setEditForm({ ...editForm, specialization: e.target.value })}
                    placeholder="e.g. Core or Artificial Intelligence"
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
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {patchMutation.isPending ? 'Saving Updates...' : 'Save Updates'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Dialog: Create Lab / Workshop Office */}
        <Dialog open={createWorkshopModalOpen} onOpenChange={setCreateWorkshopModalOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!workshopForm.name.trim()) {
                  setWorkshopError('Office name is required.')
                  return
                }
                createWorkshopMutation.mutate({
                  name: workshopForm.name.trim(),
                  description: workshopForm.description.trim() || null,
                })
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  New Lab or Workshop Office
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Create a new laboratory or workshop facility for your academic department.
                </DialogDescription>
              </DialogHeader>

              {workshopError && (
                <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs">
                  {workshopError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="ws-name" className="text-xs font-semibold text-zinc-800">
                    Facility Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="ws-name"
                    value={workshopForm.name}
                    onChange={(e) => setWorkshopForm({ ...workshopForm, name: e.target.value })}
                    placeholder="e.g. Embedded Systems Lab, CNC Workshop"
                    required
                    maxLength={80}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="ws-desc" className="text-xs font-semibold text-zinc-800">
                    Description (Optional)
                  </Label>
                  <Textarea
                    id="ws-desc"
                    value={workshopForm.description}
                    onChange={(e) => setWorkshopForm({ ...workshopForm, description: e.target.value })}
                    placeholder="Brief description of the facility and equipment..."
                    className="text-xs min-h-[70px]"
                    maxLength={500}
                  />
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCreateWorkshopModalOpen(false)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createWorkshopMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {createWorkshopMutation.isPending ? 'Creating...' : 'Create Facility'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Dialog: Edit Lab / Workshop Office */}
        <Dialog open={editWorkshopModalOpen} onOpenChange={setEditWorkshopModalOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!editWorkshopForm.name.trim()) {
                  setEditWorkshopError('Facility name is required.')
                  return
                }
                patchWorkshopMutation.mutate({
                  id: editingWorkshop.id,
                  data: {
                    name: editWorkshopForm.name.trim(),
                    description: editWorkshopForm.description.trim() || null,
                    is_active: editWorkshopForm.is_active,
                  },
                })
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  Edit Lab or Workshop Office
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Rename facility, update description, or change active status.
                </DialogDescription>
              </DialogHeader>

              {editWorkshopError && (
                <div className="p-3 mb-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-900 text-xs">
                  {editWorkshopError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="edit-ws-name" className="text-xs font-semibold text-zinc-800">
                    Facility Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="edit-ws-name"
                    value={editWorkshopForm.name}
                    onChange={(e) => setEditWorkshopForm({ ...editWorkshopForm, name: e.target.value })}
                    required
                    maxLength={80}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="edit-ws-desc" className="text-xs font-semibold text-zinc-800">
                    Description
                  </Label>
                  <Textarea
                    id="edit-ws-desc"
                    value={editWorkshopForm.description}
                    onChange={(e) => setEditWorkshopForm({ ...editWorkshopForm, description: e.target.value })}
                    className="text-xs min-h-[70px]"
                    maxLength={500}
                  />
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <input
                    type="checkbox"
                    id="editWsActive"
                    checked={editWorkshopForm.is_active}
                    onChange={(e) => setEditWorkshopForm({ ...editWorkshopForm, is_active: e.target.checked })}
                    className="h-4 w-4 rounded border-zinc-300 text-black focus:ring-black accent-zinc-900 cursor-pointer"
                  />
                  <Label htmlFor="editWsActive" className="text-xs font-medium text-zinc-800 cursor-pointer">
                    Facility is active for lab subjects and clearance declaration
                  </Label>
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditWorkshopModalOpen(false)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={patchWorkshopMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {patchWorkshopMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}

export default OfficerLabCatalogPage
