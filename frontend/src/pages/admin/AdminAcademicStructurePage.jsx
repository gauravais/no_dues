import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import {
  GraduationCap,
  Building,
  BookOpen,
  Plus,
  Edit,
  Power,
  Search,
} from 'lucide-react'

const TABS = [
  { id: 'FACULTIES', label: 'Faculties', icon: Building },
  { id: 'ACADEMIC_DEPTS', label: 'Academic departments', icon: GraduationCap },
  { id: 'PROGRAMMES', label: 'Programmes', icon: BookOpen },
]

export function AdminAcademicStructurePage() {
  useDocumentTitle('Academic Structure | SVSU No-Dues')
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState('FACULTIES')
  const [searchTerm, setSearchTerm] = useState('')
  const [showInactive, setShowInactive] = useState(false)

  // 1. Fetch Faculties
  const { data: faculties = [], isLoading: facultiesLoading } = useQuery({
    queryKey: ['admin', 'faculties'],
    queryFn: () => adminApi.getFaculties(),
  })

  // 2. Fetch Academic Departments
  const { data: academicDepts = [], isLoading: deptsLoading } = useQuery({
    queryKey: ['admin', 'academic-departments'],
    queryFn: () => adminApi.getAcademicDepartments(),
  })

  // 3. Fetch Programmes
  const { data: programmes = [], isLoading: programmesLoading } = useQuery({
    queryKey: ['admin', 'programmes'],
    queryFn: () => adminApi.getProgrammes(),
  })

  // Faculty Modal States
  const [facultyModalOpen, setFacultyModalOpen] = useState(false)
  const [editingFaculty, setEditingFaculty] = useState(null)
  const [facultyForm, setFacultyForm] = useState({ name: '', short_code: '' })
  const [facultyError, setFacultyError] = useState('')

  // Academic Department Modal States
  const [deptModalOpen, setDeptModalOpen] = useState(false)
  const [editingDept, setEditingDept] = useState(null)
  const [deptForm, setDeptForm] = useState({ name: '', faculty_id: '', is_active: true })
  const [deptError, setDeptError] = useState('')

  // Programme Modal States
  const [progModalOpen, setProgModalOpen] = useState(false)
  const [editingProg, setEditingProg] = useState(null)
  const [progForm, setProgForm] = useState({ name: '', academic_department_id: '', is_active: true })
  const [progError, setProgError] = useState('')

  // Toggle Confirm States
  const [toggleItem, setToggleItem] = useState(null) // { type: 'dept' | 'prog', item }
  const [toggleError, setToggleError] = useState('')

  // Invalidate queries
  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'faculties'] })
    queryClient.invalidateQueries({ queryKey: ['admin', 'academic-departments'] })
    queryClient.invalidateQueries({ queryKey: ['admin', 'programmes'] })
  }

  // --- MUTATIONS ---

  // Faculty Mutations
  const createFacultyMutation = useMutation({
    mutationFn: (data) => adminApi.createFaculty(data),
    onSuccess: (res) => {
      toast.success(`Faculty "${res.name}" created successfully.`)
      setFacultyModalOpen(false)
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create faculty.'
      setFacultyError(msg)
      toast.error(msg)
    },
  })

  const patchFacultyMutation = useMutation({
    mutationFn: ({ id, data }) => adminApi.patchFaculty(id, data),
    onSuccess: (res) => {
      toast.success(`Faculty "${res.name}" updated successfully.`)
      setFacultyModalOpen(false)
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update faculty.'
      setFacultyError(msg)
      toast.error(msg)
    },
  })

  // Academic Department Mutations
  const createDeptMutation = useMutation({
    mutationFn: (data) => adminApi.createAcademicDepartment(data),
    onSuccess: (res) => {
      toast.success(`Academic department "${res.name}" created successfully.`)
      setDeptModalOpen(false)
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create academic department.'
      setDeptError(msg)
      toast.error(msg)
    },
  })

  const patchDeptMutation = useMutation({
    mutationFn: ({ id, data }) => adminApi.patchAcademicDepartment(id, data),
    onSuccess: (res) => {
      toast.success(`Academic department "${res.name}" updated successfully.`)
      setDeptModalOpen(false)
      setToggleItem(null)
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update academic department.'
      setDeptError(msg)
      setToggleError(msg)
      toast.error(msg)
    },
  })

  // Programme Mutations
  const createProgMutation = useMutation({
    mutationFn: (data) => adminApi.createProgramme(data),
    onSuccess: (res) => {
      toast.success(`Programme "${res.name}" created successfully.`)
      setProgModalOpen(false)
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to create programme.'
      setProgError(msg)
      toast.error(msg)
    },
  })

  const patchProgMutation = useMutation({
    mutationFn: ({ id, data }) => adminApi.patchProgramme(id, data),
    onSuccess: (res) => {
      toast.success(`Programme "${res.name}" updated successfully.`)
      setProgModalOpen(false)
      setToggleItem(null)
      invalidateAll()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || 'Failed to update programme.'
      setProgError(msg)
      setToggleError(msg)
      toast.error(msg)
    },
  })

  // Lookups
  const facultyMap = useMemo(() => {
    const map = new Map()
    faculties.forEach((f) => map.set(f.id, f))
    return map
  }, [faculties])

  const deptMap = useMemo(() => {
    const map = new Map()
    academicDepts.forEach((d) => map.set(d.id, d))
    return map
  }, [academicDepts])

  // Filtered lists
  const filteredFaculties = useMemo(() => {
    if (!searchTerm.trim()) return faculties
    const q = searchTerm.toLowerCase()
    return faculties.filter(
      (f) => f.name.toLowerCase().includes(q) || f.short_code.toLowerCase().includes(q)
    )
  }, [faculties, searchTerm])

  const filteredDepts = useMemo(() => {
    return academicDepts.filter((d) => {
      if (!showInactive && d.is_active === false) return false
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase()
        const f = facultyMap.get(d.faculty_id)
        return (
          d.name.toLowerCase().includes(q) ||
          f?.name.toLowerCase().includes(q) ||
          f?.short_code.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [academicDepts, showInactive, searchTerm, facultyMap])

  const filteredProgrammes = useMemo(() => {
    return programmes.filter((p) => {
      if (!showInactive && p.is_active === false) return false
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase()
        const d = deptMap.get(p.academic_department_id)
        return (
          p.name.toLowerCase().includes(q) ||
          d?.name.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [programmes, showInactive, searchTerm, deptMap])

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto pb-16">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
              Academic Structure
            </h1>
            <p className="text-xs sm:text-sm text-zinc-500 mt-1">
              Configure university faculties, academic departments, and degree programmes across Shri Vishwakarma Skill University.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {activeTab === 'FACULTIES' && (
              <Button
                size="sm"
                onClick={() => {
                  setFacultyError('')
                  setEditingFaculty(null)
                  setFacultyForm({ name: '', short_code: '' })
                  setFacultyModalOpen(true)
                }}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Faculty
              </Button>
            )}

            {activeTab === 'ACADEMIC_DEPTS' && (
              <Button
                size="sm"
                onClick={() => {
                  setDeptError('')
                  setEditingDept(null)
                  setDeptForm({
                    name: '',
                    faculty_id: faculties[0]?.id ? String(faculties[0].id) : '',
                    is_active: true,
                  })
                  setDeptModalOpen(true)
                }}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Academic Department
              </Button>
            )}

            {activeTab === 'PROGRAMMES' && (
              <Button
                size="sm"
                onClick={() => {
                  setProgError('')
                  setEditingProg(null)
                  setProgForm({
                    name: '',
                    academic_department_id: academicDepts[0]?.id ? String(academicDepts[0].id) : '',
                    is_active: true,
                  })
                  setProgModalOpen(true)
                }}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-9 gap-1.5 font-semibold shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Programme
              </Button>
            )}
          </div>
        </div>

        {/* Structure Metrics KPI */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
                Faculties
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-zinc-950">{faculties.length}</span>
                <Building className="w-4 h-4 text-zinc-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
                Academic Departments
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-zinc-950">{academicDepts.length}</span>
                <GraduationCap className="w-4 h-4 text-zinc-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-white shadow-2xs">
            <CardContent className="p-4 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
                Degree Programmes
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-zinc-950">{programmes.length}</span>
                <BookOpen className="w-4 h-4 text-zinc-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <div className="border-b border-border">
          <div className="flex items-center gap-1 overflow-x-auto pb-px">
            {TABS.map((tab) => {
              const TabIcon = tab.icon
              const count =
                tab.id === 'FACULTIES'
                  ? faculties.length
                  : tab.id === 'ACADEMIC_DEPTS'
                  ? academicDepts.length
                  : programmes.length
              const isActive = activeTab === tab.id

              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id)
                    setSearchTerm('')
                  }}
                  className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors ${
                    isActive
                      ? 'border-black text-black bg-zinc-50/50'
                      : 'border-transparent text-zinc-500 hover:text-zinc-900 hover:border-zinc-300'
                  }`}
                >
                  <TabIcon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                  <Badge
                    variant="outline"
                    className={`text-[10px] py-0 px-1.5 font-mono ${
                      isActive ? 'bg-black text-white border-black' : 'bg-zinc-100 text-zinc-600 border-zinc-200'
                    }`}
                  >
                    {count}
                  </Badge>
                </button>
              )
            })}
          </div>
        </div>

        {/* Search & Toggle Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-400" />
              <Input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder={`Search ${activeTab.toLowerCase().replace('_', ' ')}...`}
                className="pl-8 text-xs h-9"
              />
            </div>
            {activeTab !== 'FACULTIES' && (
              <label className="flex items-center gap-2 cursor-pointer text-xs select-none shrink-0 text-zinc-700 font-medium">
                <input
                  type="checkbox"
                  checked={showInactive}
                  onChange={(e) => setShowInactive(e.target.checked)}
                  className="rounded border-zinc-300 text-black focus:ring-black h-3.5 w-3.5"
                />
                <span>Show inactive</span>
              </label>
            )}
          </div>
        </div>

        {/* Tab 1: Faculties Table */}
        {activeTab === 'FACULTIES' && (
          <div className="border border-border rounded-xl bg-white overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50/75 border-b border-border text-zinc-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="p-3">Faculty Name</th>
                  <th className="p-3">Short Code</th>
                  <th className="p-3">Academic Departments</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {facultiesLoading ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-zinc-500">
                      Loading faculties...
                    </td>
                  </tr>
                ) : filteredFaculties.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-zinc-500">
                      No faculties found.
                    </td>
                  </tr>
                ) : (
                  filteredFaculties.map((f) => {
                    const deptsInFaculty = academicDepts.filter((d) => d.faculty_id === f.id)
                    return (
                      <tr key={f.id} className="hover:bg-zinc-50/50 transition-colors">
                        <td className="p-3 font-semibold text-zinc-950 text-xs">
                          {f.name}
                        </td>
                        <td className="p-3 font-mono font-medium text-zinc-700">
                          <Badge variant="outline" className="bg-zinc-50 font-mono text-[10px]">
                            {f.short_code}
                          </Badge>
                        </td>
                        <td className="p-3 text-zinc-600">
                          {deptsInFaculty.length} {deptsInFaculty.length === 1 ? 'department' : 'departments'}
                        </td>
                        <td className="p-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setFacultyError('')
                              setEditingFaculty(f)
                              setFacultyForm({ name: f.name, short_code: f.short_code })
                              setFacultyModalOpen(true)
                            }}
                            className="h-8 px-2 text-xs text-zinc-700 hover:bg-zinc-100"
                          >
                            <Edit className="w-3.5 h-3.5 mr-1" />
                            Rename / Edit
                          </Button>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: Academic Departments Table */}
        {activeTab === 'ACADEMIC_DEPTS' && (
          <div className="border border-border rounded-xl bg-white overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50/75 border-b border-border text-zinc-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="p-3">Department Name</th>
                  <th className="p-3">Parent Faculty</th>
                  <th className="p-3">Programmes</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {deptsLoading ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-zinc-500">
                      Loading academic departments...
                    </td>
                  </tr>
                ) : filteredDepts.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-zinc-500">
                      No academic departments found.
                    </td>
                  </tr>
                ) : (
                  filteredDepts.map((d) => {
                    const f = facultyMap.get(d.faculty_id)
                    const progsInDept = programmes.filter((p) => p.academic_department_id === d.id)

                    return (
                      <tr key={d.id} className="hover:bg-zinc-50/50 transition-colors">
                        <td className="p-3 font-semibold text-zinc-950 text-xs">
                          {d.name}
                        </td>
                        <td className="p-3 text-zinc-700">
                          {f ? `${f.name} (${f.short_code})` : `Faculty #${d.faculty_id}`}
                        </td>
                        <td className="p-3 text-zinc-600">
                          {progsInDept.length} {progsInDept.length === 1 ? 'programme' : 'programmes'}
                        </td>
                        <td className="p-3">
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-medium ${
                              d.is_active
                                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                : 'bg-zinc-100 text-zinc-600 border-zinc-300'
                            }`}
                          >
                            {d.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setDeptError('')
                                setEditingDept(d)
                                setDeptForm({
                                  name: d.name,
                                  faculty_id: String(d.faculty_id),
                                  is_active: d.is_active,
                                })
                                setDeptModalOpen(true)
                              }}
                              className="h-8 px-2 text-xs text-zinc-700 hover:bg-zinc-100"
                            >
                              <Edit className="w-3.5 h-3.5 mr-1" />
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setToggleError('')
                                setToggleItem({ type: 'dept', item: d })
                              }}
                              className={`h-8 px-2 text-xs ${
                                d.is_active
                                  ? 'text-amber-700 hover:bg-amber-50'
                                  : 'text-emerald-700 hover:bg-emerald-50'
                              }`}
                              title={d.is_active ? 'Deactivate department' : 'Activate department'}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 3: Programmes Table */}
        {activeTab === 'PROGRAMMES' && (
          <div className="border border-border rounded-xl bg-white overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50/75 border-b border-border text-zinc-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="p-3">Programme Name</th>
                  <th className="p-3">Academic Department</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {programmesLoading ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-zinc-500">
                      Loading degree programmes...
                    </td>
                  </tr>
                ) : filteredProgrammes.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-zinc-500">
                      No degree programmes found.
                    </td>
                  </tr>
                ) : (
                  filteredProgrammes.map((p) => {
                    const dept = deptMap.get(p.academic_department_id)

                    return (
                      <tr key={p.id} className="hover:bg-zinc-50/50 transition-colors">
                        <td className="p-3 font-semibold text-zinc-950 text-xs">
                          {p.name}
                        </td>
                        <td className="p-3 text-zinc-700">
                          {dept ? dept.name : `Department #${p.academic_department_id}`}
                        </td>
                        <td className="p-3">
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-medium ${
                              p.is_active
                                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                : 'bg-zinc-100 text-zinc-600 border-zinc-300'
                            }`}
                          >
                            {p.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setProgError('')
                                setEditingProg(p)
                                setProgForm({
                                  name: p.name,
                                  academic_department_id: String(p.academic_department_id),
                                  is_active: p.is_active,
                                })
                                setProgModalOpen(true)
                              }}
                              className="h-8 px-2 text-xs text-zinc-700 hover:bg-zinc-100"
                            >
                              <Edit className="w-3.5 h-3.5 mr-1" />
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setToggleError('')
                                setToggleItem({ type: 'prog', item: p })
                              }}
                              className={`h-8 px-2 text-xs ${
                                p.is_active
                                  ? 'text-amber-700 hover:bg-amber-50'
                                  : 'text-emerald-700 hover:bg-emerald-50'
                              }`}
                              title={p.is_active ? 'Deactivate programme' : 'Activate programme'}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Modal: Faculty Create / Edit */}
        <Dialog open={facultyModalOpen} onOpenChange={setFacultyModalOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!facultyForm.name.trim() || !facultyForm.short_code.trim()) {
                  setFacultyError('Faculty name and short code are required.')
                  return
                }
                if (editingFaculty) {
                  patchFacultyMutation.mutate({
                    id: editingFaculty.id,
                    data: {
                      name: facultyForm.name.trim(),
                      short_code: facultyForm.short_code.trim().toUpperCase(),
                    },
                  })
                } else {
                  createFacultyMutation.mutate({
                    name: facultyForm.name.trim(),
                    short_code: facultyForm.short_code.trim().toUpperCase(),
                  })
                }
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  {editingFaculty ? 'Edit Faculty' : 'Add Faculty'}
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Faculties group related academic departments under a common academic division.
                </DialogDescription>
              </DialogHeader>

              {facultyError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {facultyError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="fac-name" className="text-xs font-semibold text-zinc-800">
                    Faculty Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="fac-name"
                    value={facultyForm.name}
                    onChange={(e) => setFacultyForm({ ...facultyForm, name: e.target.value })}
                    placeholder="e.g. Skill Faculty of Engineering and Technology"
                    required
                    maxLength={255}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="fac-code" className="text-xs font-semibold text-zinc-800">
                    Short Code <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="fac-code"
                    value={facultyForm.short_code}
                    onChange={(e) => setFacultyForm({ ...facultyForm, short_code: e.target.value.toUpperCase() })}
                    placeholder="e.g. SFET"
                    className="uppercase font-mono"
                    required
                    maxLength={20}
                  />
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setFacultyModalOpen(false)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createFacultyMutation.isPending || patchFacultyMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {createFacultyMutation.isPending || patchFacultyMutation.isPending
                    ? 'Saving...'
                    : editingFaculty
                    ? 'Save Changes'
                    : 'Create Faculty'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Modal: Academic Department Create / Edit */}
        <Dialog open={deptModalOpen} onOpenChange={setDeptModalOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!deptForm.name.trim() || !deptForm.faculty_id) {
                  setDeptError('Department name and parent faculty are required.')
                  return
                }
                if (editingDept) {
                  patchDeptMutation.mutate({
                    id: editingDept.id,
                    data: {
                      name: deptForm.name.trim(),
                      faculty_id: Number(deptForm.faculty_id),
                      is_active: deptForm.is_active,
                    },
                  })
                } else {
                  createDeptMutation.mutate({
                    name: deptForm.name.trim(),
                    faculty_id: Number(deptForm.faculty_id),
                    is_active: deptForm.is_active,
                  })
                }
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  {editingDept ? 'Edit Academic Department' : 'Add Academic Department'}
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Academic departments manage degree programmes, student rosters, and curriculum labs.
                </DialogDescription>
              </DialogHeader>

              {deptError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {deptError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="ad-name" className="text-xs font-semibold text-zinc-800">
                    Academic Department Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="ad-name"
                    value={deptForm.name}
                    onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })}
                    placeholder="e.g. Skill Department of CS/IT"
                    required
                    maxLength={255}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="ad-faculty" className="text-xs font-semibold text-zinc-800">
                    Parent Faculty <span className="text-rose-500">*</span>
                  </Label>
                  <Select
                    value={deptForm.faculty_id}
                    onValueChange={(val) => setDeptForm({ ...deptForm, faculty_id: val })}
                  >
                    <SelectTrigger id="ad-faculty" className="text-xs">
                      <SelectValue placeholder="Select faculty..." />
                    </SelectTrigger>
                    <SelectContent>
                      {faculties.map((f) => (
                        <SelectItem key={f.id} value={String(f.id)} className="text-xs">
                          {f.name} ({f.short_code})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setDeptModalOpen(false)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createDeptMutation.isPending || patchDeptMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {createDeptMutation.isPending || patchDeptMutation.isPending
                    ? 'Saving...'
                    : editingDept
                    ? 'Save Changes'
                    : 'Create Department'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Modal: Programme Create / Edit */}
        <Dialog open={progModalOpen} onOpenChange={setProgModalOpen}>
          <DialogContent className="sm:max-w-md bg-white p-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!progForm.name.trim() || !progForm.academic_department_id) {
                  setProgError('Programme name and academic department are required.')
                  return
                }
                if (editingProg) {
                  patchProgMutation.mutate({
                    id: editingProg.id,
                    data: {
                      name: progForm.name.trim(),
                      academic_department_id: Number(progForm.academic_department_id),
                      is_active: progForm.is_active,
                    },
                  })
                } else {
                  createProgMutation.mutate({
                    name: progForm.name.trim(),
                    academic_department_id: Number(progForm.academic_department_id),
                    is_active: progForm.is_active,
                  })
                }
              }}
            >
              <DialogHeader className="pb-3">
                <DialogTitle className="font-heading font-bold text-base">
                  {editingProg ? 'Edit Programme' : 'Add Degree Programme'}
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Degree programmes enroll students and attach curriculum laboratory courses.
                </DialogDescription>
              </DialogHeader>

              {progError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900 mb-3">
                  {progError}
                </div>
              )}

              <div className="space-y-4 py-2 text-xs">
                <div className="space-y-1.5">
                  <Label htmlFor="pr-name" className="text-xs font-semibold text-zinc-800">
                    Programme Name <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    id="pr-name"
                    value={progForm.name}
                    onChange={(e) => setProgForm({ ...progForm, name: e.target.value })}
                    placeholder="e.g. B.Tech Computer Science and Engineering"
                    required
                    maxLength={255}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="pr-dept" className="text-xs font-semibold text-zinc-800">
                    Academic Department <span className="text-rose-500">*</span>
                  </Label>
                  <Select
                    value={progForm.academic_department_id}
                    onValueChange={(val) => setProgForm({ ...progForm, academic_department_id: val })}
                  >
                    <SelectTrigger id="pr-dept" className="text-xs">
                      <SelectValue placeholder="Select academic department..." />
                    </SelectTrigger>
                    <SelectContent>
                      {academicDepts.map((d) => (
                        <SelectItem key={d.id} value={String(d.id)} className="text-xs">
                          {d.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <DialogFooter className="gap-2 sm:gap-0 pt-3 border-t border-zinc-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setProgModalOpen(false)}
                  className="text-xs h-9"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createProgMutation.isPending || patchProgMutation.isPending}
                  className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
                >
                  {createProgMutation.isPending || patchProgMutation.isPending
                    ? 'Saving...'
                    : editingProg
                    ? 'Save Changes'
                    : 'Create Programme'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Toggle Active AlertDialog */}
        <AlertDialog open={Boolean(toggleItem)} onOpenChange={(open) => !open && setToggleItem(null)}>
          <AlertDialogContent className="bg-white max-w-md">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-heading font-bold text-base">
                {toggleItem?.item?.is_active ? 'Deactivate' : 'Activate'}{' '}
                {toggleItem?.type === 'dept' ? 'Academic Department' : 'Degree Programme'}
              </AlertDialogTitle>
              <AlertDialogDescription className="text-xs text-zinc-600 space-y-2">
                <span>
                  Are you sure you want to {toggleItem?.item?.is_active ? 'deactivate' : 'activate'}{' '}
                  <strong>"{toggleItem?.item?.name}"</strong>?
                </span>
                <span className="block text-[11px] text-zinc-500">
                  Deactivated academic divisions or programmes will not be available for new student enrollments or requests. Refused if active requests are currently open.
                </span>
              </AlertDialogDescription>
            </AlertDialogHeader>

            {toggleError && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-900">
                {toggleError}
              </div>
            )}

            <AlertDialogFooter>
              <AlertDialogCancel className="text-xs h-9">Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault()
                  if (toggleItem.type === 'dept') {
                    patchDeptMutation.mutate({
                      id: toggleItem.item.id,
                      data: { is_active: !toggleItem.item.is_active },
                    })
                  } else {
                    patchProgMutation.mutate({
                      id: toggleItem.item.id,
                      data: { is_active: !toggleItem.item.is_active },
                    })
                  }
                }}
                disabled={patchDeptMutation.isPending || patchProgMutation.isPending}
                className="bg-black text-white hover:bg-zinc-800 text-xs h-9 font-semibold"
              >
                {patchDeptMutation.isPending || patchProgMutation.isPending ? 'Processing...' : 'Confirm'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AppShell>
  )
}

export default AdminAcademicStructurePage
