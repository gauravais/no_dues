import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { hodApi } from '@/api/hod'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { DataTable } from '@/components/DataTable'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import {
  GraduationCap,
  RotateCw,
  Home,
  Clock,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  Building2,
} from 'lucide-react'

const PROGRAMME_DEPARTMENT_MAP = {
  // CS/IT
  'Master of Computer Application (MCA)': 'Skill Department of CS/IT',
  'Bachelor of Technology (B.Tech.) Computer Science & Engineering': 'Skill Department of CS/IT',
  'Bachelor of Technology (B.Tech.) Computer Engineering': 'Skill Department of CS/IT',
  'Bachelor in Computer Applications (BCA)': 'Skill Department of CS/IT',
  'Diploma in Computer (Generative AI/ Cyber Security)': 'Skill Department of CS/IT',
  // Industry 4.0
  'Diploma in Industrial Electronics': 'Skill Department of Industry 4.0',
  'Bachelor of Vocation Robotics and Automation': 'Skill Department of Industry 4.0',
  'Master of Technology Robotics and Automation': 'Skill Department of Industry 4.0',
  'PG Diploma in Semiconductor Device Packaging': 'Skill Department of Industry 4.0',
  // Construction
  'Diploma of Vocation Draughtsmanship (Civil)': 'Skill Department of Construction Management and Technology',
  'Undergraduate Diploma in Interior Design': 'Skill Department of Construction Management and Technology',
  'Diploma in Civil Engineering': 'Skill Department of Construction Management and Technology',
  // Automotive
  'Diploma of Vocation Mechanical Manufacturing': 'Skill Department of Automotive Studies',
  'Diploma in Mechanical Engineering': 'Skill Department of Automotive Studies',
  'Bachelor of Vocation Mechanical Manufacturing': 'Skill Department of Automotive Studies',
  'Bachelor of Technology Mechanical and Smart Manufacturing': 'Skill Department of Automotive Studies',
  'Bachelor of Vocation Mechatronics': 'Skill Department of Automotive Studies',
  // Green Tech
  'Bachelor of Vocation Solar Technology': 'Skill Department of Green Technology',
  'Bachelor of Vocation (Refrigeration and Air Conditioning)': 'Skill Department of Green Technology',
  'Bachelor of Technology Electrical Engineering': 'Skill Department of Green Technology',
}

function resolveDepartmentName(item, userDepts) {
  if (item.department_name) return item.department_name
  if (item.programme_name && PROGRAMME_DEPARTMENT_MAP[item.programme_name]) {
    return PROGRAMME_DEPARTMENT_MAP[item.programme_name]
  }
  const p = (item.programme_name || '').toLowerCase()
  for (const d of userDepts) {
    const dName = d.name.toLowerCase()
    if (
      (p.includes('computer') || p.includes('mca') || p.includes('bca') || p.includes('cs') || p.includes('it')) &&
      (dName.includes('cs') || dName.includes('it'))
    ) {
      return d.name
    }
    if (
      (p.includes('robotics') || p.includes('industry') || p.includes('electronics')) &&
      dName.includes('industry')
    ) {
      return d.name
    }
    if (
      (p.includes('civil') || p.includes('construction') || p.includes('interior')) &&
      dName.includes('construction')
    ) {
      return d.name
    }
    if (
      (p.includes('mechanical') || p.includes('automotive') || p.includes('mechatronics') || p.includes('manufacturing')) &&
      dName.includes('automotive')
    ) {
      return d.name
    }
    if (
      (p.includes('solar') || p.includes('green') || p.includes('refrigeration') || p.includes('electrical')) &&
      dName.includes('green')
    ) {
      return d.name
    }
  }
  return userDepts[0]?.name || 'Academic Department'
}

export function HodQueuePage() {
  useDocumentTitle('HoD Review Queue')
  const { user } = useAuth()
  const navigate = useNavigate()

  const [selectedDeptFilter, setSelectedDeptFilter] = useState('ALL')

  const academicDepts = useMemo(() => {
    return (user?.departments || []).filter((d) => d.kind === 'academic')
  }, [user])

  const hasMultipleAcademic = academicDepts.length > 1

  // Fetch HoD Review Queue
  const {
    data: queue = [],
    isLoading,
    isError,
    error,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['hod', 'queue'],
    queryFn: async () => {
      return await hodApi.getQueue()
    },
  })

  const departmentName = user?.department_name || (academicDepts[0]?.name) || 'Academic Department'

  const filteredQueue = useMemo(() => {
    if (!hasMultipleAcademic || selectedDeptFilter === 'ALL') {
      return queue
    }
    return queue.filter((item) => {
      const dept = resolveDepartmentName(item, academicDepts)
      return dept === selectedDeptFilter
    })
  }, [queue, hasMultipleAcademic, selectedDeptFilter, academicDepts])

  // Columns for HoD review queue
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
      ...(hasMultipleAcademic
        ? [
            {
              id: 'department',
              header: 'Department',
              cell: ({ row }) => (
                <Badge
                  variant="outline"
                  className="text-[11px] font-medium bg-zinc-50 border-zinc-200 text-zinc-800"
                >
                  {resolveDepartmentName(row.original, academicDepts)}
                </Badge>
              ),
            },
          ]
        : []),
      {
        accessorKey: 'programme_name',
        header: 'Academic Programme',
        cell: ({ row }) => (
          <span className="text-xs text-zinc-700 max-w-[280px] line-clamp-2">
            {row.original.programme_name}
          </span>
        ),
      },
      {
        accessorKey: 'is_hosteller',
        header: 'Type',
        cell: ({ row }) => {
          const isHosteller = row.original.is_hosteller
          return isHosteller ? (
            <Badge variant="outline" className="text-[10px] bg-indigo-50 text-indigo-900 border-indigo-200 gap-1">
              <Home className="w-3 h-3 text-indigo-600" />
              Hosteller
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] bg-zinc-50 text-zinc-600 border-zinc-200">
              Day Scholar
            </Badge>
          )
        },
      },
      {
        accessorKey: 'submitted_at',
        header: 'Submitted',
        cell: ({ row }) => {
          const dateStr = row.original.submitted_at
          if (!dateStr) return <span className="text-zinc-400">—</span>
          const d = new Date(dateStr)
          return (
            <span className="text-xs text-zinc-600">
              {d.toLocaleDateString()}
            </span>
          )
        },
      },
      {
        id: 'status',
        header: 'Workflow Stage',
        cell: () => <StatusBadge status="HOD_REVIEW" />,
      },
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) => {
          const item = row.original
          return (
            <Button
              size="sm"
              onClick={() => navigate(`/hod/requests/${item.request_id}`)}
              className="h-8 px-3 text-xs gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
            >
              Review Dossier
              <ArrowRight className="w-3 h-3" />
            </Button>
          )
        },
      },
    ],
    [navigate, hasMultipleAcademic, academicDepts]
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
        <StatusBadge status="HOD_REVIEW" />
      </div>

      {hasMultipleAcademic && (
        <div className="flex items-center gap-1.5 pt-0.5">
          <span className="text-[11px] text-zinc-500 font-medium">Department:</span>
          <Badge variant="outline" className="text-[10px] bg-zinc-50 text-zinc-800 border-zinc-200">
            {resolveDepartmentName(item, academicDepts)}
          </Badge>
        </div>
      )}

      <div className="text-xs text-zinc-600">
        {item.programme_name}
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-500 pt-1 border-t border-zinc-100">
        <span>{item.is_hosteller ? 'Hosteller' : 'Day Scholar'}</span>
        <span className="flex items-center gap-1 text-[11px]">
          <Clock className="w-3 h-3 text-zinc-400" />
          {item.submitted_at ? new Date(item.submitted_at).toLocaleDateString() : '—'}
        </span>
      </div>

      <Button
        size="sm"
        onClick={() => navigate(`/hod/requests/${item.request_id}`)}
        className="w-full mt-2 h-8 text-xs gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
      >
        Inspect Full Dossier
        <ArrowRight className="w-3 h-3" />
      </Button>
    </div>
  )

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 border border-border flex items-center justify-center text-zinc-900">
                <GraduationCap className="w-4 h-4" />
              </div>
              <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950">
                Chairperson Review Queue
              </h1>
              {isRefetching && (
                <RotateCw className="w-4 h-4 text-zinc-400 animate-spin" />
              )}
            </div>
            <p className="text-xs sm:text-sm text-zinc-500">
              {hasMultipleAcademic ? (
                <>
                  Covering <span className="font-semibold text-zinc-900">{academicDepts.length} Academic Departments</span> • Final authority for student certificate issuance.
                </>
              ) : (
                <>
                  Covering Academic Department:{' '}
                  <span className="font-semibold text-zinc-900">{departmentName}</span> • Final authority for student certificate issuance.
                </>
              )}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetch()
                toast.info('HoD queue updated.')
              }}
              className="text-xs gap-1.5 h-8 border-border bg-white hover:bg-zinc-100"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Refresh
            </Button>
          </div>
        </div>

        {/* API Error State with Retry Button */}
        {isError && (
          <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-destructive">
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Failed to load Chairperson review queue: {error?.response?.data?.detail || error?.message || 'Server connection error'}</span>
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

        {/* Informational Guidance Banner */}
        <div className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-4 flex items-start gap-3 text-xs text-zinc-600">
          <ShieldCheck className="w-4 h-4 text-zinc-900 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold text-zinc-900 block">Final Departmental Clearance Protocol</span>
            <p className="leading-relaxed text-[11px] text-zinc-500">
              Only students who have received approval from all applicable service departments (Library, Sports, Hostel, Labs, Accounts) appear in this queue. Granting approval issues an official university certificate and advances the record for security deposit refund.
            </p>
          </div>
        </div>

        {/* Multi-Department Filter Controls */}
        {hasMultipleAcademic && (
          <div className="flex items-center gap-2.5 p-3 rounded-xl border border-border bg-zinc-50/70">
            <Building2 className="w-4 h-4 text-zinc-600 shrink-0" />
            <span className="text-xs font-semibold text-zinc-700">Filter by Department:</span>
            <select
              value={selectedDeptFilter}
              onChange={(e) => setSelectedDeptFilter(e.target.value)}
              className="h-8 rounded-md border border-input bg-white px-2.5 py-1 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="ALL">All Academic Departments ({queue.length})</option>
              {academicDepts.map((d) => {
                const count = queue.filter((item) => resolveDepartmentName(item, academicDepts) === d.name).length
                return (
                  <option key={d.id} value={d.name}>
                    {d.name} ({count})
                  </option>
                )
              })}
            </select>
          </div>
        )}

        {/* DataTable */}
        <DataTable
          columns={columns}
          data={filteredQueue}
          isLoading={isLoading}
          manualPagination={false}
          pageSize={10}
          renderMobileCard={renderMobileCard}
          emptyTitle="Review queue is clear"
          emptyDescription={`There are currently no clearance dossiers awaiting Chairperson review in ${
            selectedDeptFilter === 'ALL' ? departmentName : selectedDeptFilter
          }.`}
        />
      </div>
    </AppShell>
  )
}

export default HodQueuePage
