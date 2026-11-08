import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { adminApi } from '@/api/admin'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
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
  CheckCircle2,
  RotateCw,
  FileCheck2,
  ArrowRight,
  Power,
} from 'lucide-react'

export function AdminLabCoursesPage() {
  useDocumentTitle('Master Lab Catalog | SVSU No-Dues')
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
    code: '',
    name: '',
    lab_department_id: '',
    specialization: '',
    is_active: true,
  })
  const [editError, setEditError] = useState('')

  // Advanced CSV Upload States
  const [uploadFile, setUploadFile] = useState(null)
  const [checkingFile, setCheckingFile] = useState(false)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [createMissingOffices, setCreateMissingOffices] = useState(false)
  const [dryRunReport, setDryRunReport] = useState(null)
  const [finalUploadReport, setFinalUploadReport] = useState(null)

  // Fetch Academic Departments
  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: () => adminApi.getDepartments(),
  })

  // Fetch Lab / Workshop Offices (from getAdminDepartments or getAssignedOnlyDepartments)
  const { data: adminDeptsData } = useQuery({
    queryKey: ['admin', 'departments', 'all'],
    queryFn: () => adminApi.getAdminDepartments(),
  })

  const labWorkshopOffices = useMemo(() => {
    const all = adminDeptsData?.items || []
    return all.filter((d) => d.category === 'LAB_WORKSHOP' && d.is_active !== false)
  }, [adminDeptsData])

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
        academic_department_id: academicDeptFilter === 'ALL' ? undefined : academicDeptFilter,
        is_active: activeFilter === 'ALL' ? undefined : activeFilter === 'true',
        limit: pageSize,
        offset: pageIndex * pageSize,
      }),
  })

  const courses = useMemo(() => labCoursesData?.items || [], [labCoursesData?.items])

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'lab-courses'] })
  }

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
      invalidateAll()
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
      invalidateAll()
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
      code: createForm.code.trim().toUpperCase(),
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
        code: editForm.code.trim().toUpperCase(),
        name: editForm.name.trim(),
        lab_department_id: Number(editForm.lab_department_id),
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
      code: course.code,
      name: course.name,
      lab_department_id: course.lab_department_id ? String(course.lab_department_id) : '',
      specialization: course.specialization || '',
      is_active: course.is_active,
    })
    setEditError('')
  }

  // Advanced CSV Handlers
  const handleCheckFile = async () => {
    if (!uploadFile) {
      toast.error('Please select a CSV file first.')
      return
    }
    setCheckingFile(true)
    setDryRunReport(null)
    setFinalUploadReport(null)
    try {
      const res = await adminApi.uploadLabCoursesCsv(uploadFile, {
        dry_run: true,
        create_missing_offices: createMissingOffices,
      })
      setDryRunReport(res)
      toast.info(`Dry run complete: ${res.total_rows} rows analyzed.`)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to simulate CSV upload.'
      toast.error(msg)
    } finally {
      setCheckingFile(false)
    }
  }

  const handleUploadFile = async () => {
    if (!uploadFile) {
      toast.error('Please select a CSV file first.')
      return
    }
    setUploadingFile(true)
    try {
      const res = await adminApi.uploadLabCoursesCsv(uploadFile, {
        dry_run: false,
        create_missing_offices: createMissingOffices,
      })
      setFinalUploadReport(res)
      setDryRunReport(null)
      toast.success(`Upload complete: ${res.created_count} created, ${res.updated_count} updated.`)
      invalidateAll()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to batch upload lab courses.'
      toast.error(msg)
    } finally {
      setUploadingFile(false)
    }
  }

  const handleDownloadTemplate = async () => {
    try {
      const blob = await adminApi.downloadLabCoursesTemplate()
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/csv' }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'master_lab_courses_template.csv')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to download template.')
    }
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
                Track: {row.original.specialization}
              </span>
            )}
          </div>
        ),
      },
      {
        accessorKey: 'academic_department_name',
        header: 'Academic Department',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-700 max-w-[200px] line-clamp-1">
            {row.original.academic_department_name || '-'}
          </span>
        ),
      },
      {
        accessorKey: 'lab_department_name',
        header: 'Signing Lab / Workshop',
        cell: ({ row }) => (
          <Badge
            variant="outline"
            className="bg-zinc-50 text-zinc-800 border-zinc-200 text-[10px] font-mono"
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
                : 'bg-zinc-100 text-zinc-500 border-zinc-300 text-[10px]'
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
                variant="ghost"
                size="sm"
                onClick={() => openEditDialog(item)}
                className="h-7 text-xs text-zinc-600 hover:text-black gap-1 px-2"
              >
                <Edit className="w-3.5 h-3.5" />
                Edit
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleToggleActive(item)}
                className={`h-7 text-xs gap-1 px-2 ${
                  item.is_active
                    ? 'text-zinc-500 hover:text-rose-600'
                    : 'text-emerald-700 hover:bg-emerald-50'
                }`}
              >
                <Power className="w-3.5 h-3.5" />
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
      <div className="space-y-6 max-w-7xl mx-auto pb-16">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <FlaskConical className="w-5 h-5 text-zinc-900" />
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
                Master Laboratory Catalog
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-zinc-500">
              Centrally manage laboratory subjects and signing lab/workshop facilities across all university faculties.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant={viewMode === 'list' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('list')}
              className="text-xs h-9"
            >
              Catalog View
            </Button>
            <Button
              variant={viewMode === 'upload' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('upload')}
              className="text-xs h-9 gap-1.5"
            >
              <Upload className="w-3.5 h-3.5" />
              Batch Ingest
            </Button>
            {viewMode === 'list' && (
              <Button
                size="sm"
                onClick={() => {
                  setCreateError('')
                  setCreateForm({
                    code: '',
                    name: '',
                    academic_department_id: academicDepartments[0]?.id ? String(academicDepartments[0].id) : '',
                    lab_department_id: labWorkshopOffices[0]?.id ? String(labWorkshopOffices[0].id) : '',
                    specialization: '',
                  })
                  setIsCreateOpen(true)
                }}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                Create Course
              </Button>
            )}
          </div>
        </div>

        {viewMode === 'upload' ? (
          /* CSV BATCH INGEST VIEW */
          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-6 space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
                <div>
                  <h3 className="text-base font-bold text-zinc-950">
                    Master Lab Courses CSV Upload
                  </h3>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Batch upload laboratory subjects with automatic facility discovery. Format: code, name, lab_office, specialization.
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
                <Label htmlFor="admin-lab-csv" className="text-xs font-semibold text-zinc-800">
                  Select CSV File
                </Label>
                <Input
                  id="admin-lab-csv"
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
                      When ticked, any laboratory or workshop facility named in the CSV that does not exist in the university directory will be automatically created under Labs & Workshops. Unticked by default to prevent accidental duplicates.
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
                        The following offices are referenced by subjects but do not have an active dealing officer to sign clearances:
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {finalUploadReport.offices_without_officers.map((off, idx) => (
                          <Badge key={idx} variant="outline" className="bg-white border-amber-300 text-amber-900 text-[10px]">
                            {off}
                          </Badge>
                        ))}
                      </div>
                      <div className="pt-1">
                        <Link
                          to="/admin/offices"
                          className="text-xs font-semibold text-amber-950 underline hover:text-black inline-flex items-center gap-1"
                        >
                          Go to Offices & Staffing to assign officers
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          /* CATALOG LIST VIEW */
          <div className="space-y-4">
            {/* Filter Bar */}
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={academicDeptFilter}
                onChange={(e) => {
                  setAcademicDeptFilter(e.target.value)
                  setPageIndex(0)
                }}
                className="h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="ALL">All Academic Departments</option>
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
                Map a teaching curriculum lab subject to a signing lab/workshop facility.
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
                  Academic Department <span className="text-rose-500">*</span>
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
                  Signing Lab / Workshop Office <span className="text-rose-500">*</span>
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
                  <option value="">Select Signing Laboratory / Workshop...</option>
                  {labWorkshopOffices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} (ID: {d.id})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="cCode" className="text-xs font-semibold text-zinc-800">
                    Subject Code <span className="text-rose-500">*</span>
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
                  Subject Title <span className="text-rose-500">*</span>
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

      {/* EDIT MODAL (code, name, office searchable select, specialization, active) */}
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
                Update course code, title, and assigned signing lab office.
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
                <Label htmlFor="editCode" className="text-xs font-semibold text-zinc-800">
                  Course Code <span className="text-rose-500">*</span>
                </Label>
                <Input
                  id="editCode"
                  value={editForm.code}
                  onChange={(e) => setEditForm({ ...editForm, code: e.target.value.toUpperCase() })}
                  className="font-mono text-xs uppercase"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="editName" className="text-xs font-semibold text-zinc-800">
                  Subject Title <span className="text-rose-500">*</span>
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
                <Label htmlFor="editLabOffice" className="text-xs font-semibold text-zinc-800">
                  Signing Lab / Workshop Office <span className="text-rose-500">*</span>
                </Label>
                <select
                  id="editLabOffice"
                  value={editForm.lab_department_id}
                  onChange={(e) => setEditForm({ ...editForm, lab_department_id: e.target.value })}
                  className="w-full h-9 rounded-md border border-input bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  required
                >
                  <option value="">Select Signing Laboratory / Workshop...</option>
                  {labWorkshopOffices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} (ID: {d.id})
                    </option>
                  ))}
                </select>
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
