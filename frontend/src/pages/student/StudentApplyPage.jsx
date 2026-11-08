import { useState, useMemo, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { studentApi } from '@/api/student'
import { departmentApi } from '@/api/department'
import { useAuth } from '@/auth/AuthContext'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { toast } from 'sonner'
import {
  Landmark,
  Home,
  FlaskConical,
  Building2,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  X,
  Search,
  ShieldAlert,
  Send,
  RotateCw,
  Check,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'

const STEPS = [
  { id: 1, label: 'Bank Details', icon: Landmark, description: 'Refund account' },
  { id: 2, label: 'Residence', icon: Home, description: 'Hosteller or day scholar' },
  { id: 3, label: 'Labs & Workshops', icon: FlaskConical, description: 'Attended labs' },
  { id: 4, label: 'Additional Facilities', icon: Building2, description: 'Optional facilities' },
  { id: 5, label: 'Review & Submit', icon: CheckCircle2, description: 'Confirmation' },
]

export function StudentApplyPage() {
  useDocumentTitle('Apply for Clearance')
  const { user } = useAuth()
  const navigate = useNavigate()

  // Stepper state
  const [currentStep, setCurrentStep] = useState(1)

  // Step 1: Bank details state
  const [editingBank, setEditingBank] = useState(false)
  const [bankSubmitting, setBankSubmitting] = useState(false)
  const [bankForm, setBankForm] = useState({
    accountNumber: '',
    ifscCode: '',
    accountHolderName: user?.full_name || '',
    bankAddress: '',
  })

  // Step 2: Residence state (true = hosteller, false = day scholar, null = not chosen)
  const [isHosteller, setIsHosteller] = useState(null)

  // Step 3: Labs and workshops state
  const [selectedLabIds, setSelectedLabIds] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDirectLabIds, setSelectedDirectLabIds] = useState([])
  const [directLabsOpen, setDirectLabsOpen] = useState(false)
  const [directLabSearch, setDirectLabSearch] = useState('')

  // Step 4: Additional facilities state & note
  const [selectedOtherDepartmentIds, setSelectedOtherDepartmentIds] = useState([])
  const [otherDeptsSearch, setOtherDeptsSearch] = useState('')
  const [othersNote, setOthersNote] = useState('')

  // Step 5: Review & confirmation state
  const [confirmed, setConfirmed] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [blockError, setBlockError] = useState(null)

  // 1. Check if student already has an active clearance request
  const { data: currentRequest, isLoading: requestLoading } = useQuery({
    queryKey: ['student', 'current-request'],
    queryFn: async () => {
      try {
        return await studentApi.getCurrentRequest()
      } catch (err) {
        if (err.response?.status === 404) return null
        throw err
      }
    },
    staleTime: 30000,
  })

  // 2. Fetch Bank Details
  const {
    data: bankDetails,
    isLoading: bankLoading,
    refetch: refetchBank,
  } = useQuery({
    queryKey: ['student', 'bank-details'],
    queryFn: async () => {
      try {
        return await studentApi.getBankDetails()
      } catch (err) {
        if (err.response?.status === 404) return null
        throw err
      }
    },
    staleTime: 60000,
  })

  // 3. Fetch Lab Catalog for student's programme
  const { data: labCatalogData, isLoading: catalogLoading } = useQuery({
    queryKey: ['student', 'lab-catalog'],
    queryFn: async () => {
      try {
        return await studentApi.getLabCatalog()
      } catch (err) {
        if (err.response?.status === 404) return { lab_courses: [], direct_offices: [], assigned_only_departments: [] }
        throw err
      }
    },
    staleTime: 300000,
  })

  // 4. Fetch additional facilities
  const { data: assignedOnlyDepts = [], isLoading: deptsLoading } = useQuery({
    queryKey: ['departments', 'additional-facilities'],
    queryFn: async () => {
      try {
        return await studentApi.getAdditionalFacilities()
      } catch {
        return await departmentApi.getAssignedOnlyDepartments()
      }
    },
    staleTime: 300000,
  })

  const labCourses = useMemo(() => labCatalogData?.lab_courses || [], [labCatalogData])
  const directOffices = useMemo(() => labCatalogData?.direct_offices || [], [labCatalogData])
  const additionalFacilities = useMemo(
    () => (labCatalogData?.assigned_only_departments?.length ? labCatalogData.assigned_only_departments : assignedOnlyDepts),
    [labCatalogData, assignedOnlyDepts]
  )

  // Pre-fill holder name from bank details or auth profile
  useEffect(() => {
    if (bankDetails) {
      setBankForm({
        accountHolderName: bankDetails.account_holder_name || user?.full_name || '',
        ifscCode: bankDetails.ifsc_code || '',
        bankAddress: bankDetails.bank_address || '',
        accountNumber: '',
      })
    } else if (user?.full_name) {
      setBankForm((prev) => ({ ...prev, accountHolderName: user.full_name }))
    }
  }, [bankDetails, user])

  // Filter and group lab courses
  const filteredLabCourses = useMemo(() => {
    if (!searchQuery.trim()) return labCourses
    const q = searchQuery.toLowerCase().trim()
    return labCourses.filter(
      (c) =>
        c.code?.toLowerCase().includes(q) ||
        c.name?.toLowerCase().includes(q) ||
        c.lab_department_name?.toLowerCase().includes(q) ||
        c.specialization?.toLowerCase().includes(q)
    )
  }, [labCourses, searchQuery])

  const groupedLabCourses = useMemo(() => {
    const groups = {}
    filteredLabCourses.forEach((c) => {
      const spec = c.specialization?.trim() || 'General / Core Laboratories'
      if (!groups[spec]) groups[spec] = []
      groups[spec].push(c)
    })
    return groups
  }, [filteredLabCourses])

  const selectedCoursesList = useMemo(() => {
    return labCourses.filter((c) => selectedLabIds.includes(c.id))
  }, [labCourses, selectedLabIds])

  // Direct offices filter and selection
  const filteredDirectOffices = useMemo(() => {
    if (!directLabSearch.trim()) return directOffices
    const q = directLabSearch.toLowerCase().trim()
    return directOffices.filter(
      (o) => o.name?.toLowerCase().includes(q) || o.description?.toLowerCase().includes(q)
    )
  }, [directOffices, directLabSearch])

  const selectedDirectOfficesList = useMemo(() => {
    return directOffices.filter((o) => selectedDirectLabIds.includes(o.id))
  }, [directOffices, selectedDirectLabIds])

  // Additional facilities filter and selection
  const filteredAdditionalFacilities = useMemo(() => {
    if (!otherDeptsSearch.trim()) return additionalFacilities
    const q = otherDeptsSearch.toLowerCase().trim()
    return additionalFacilities.filter(
      (d) => d.name?.toLowerCase().includes(q) || d.description?.toLowerCase().includes(q)
    )
  }, [additionalFacilities, otherDeptsSearch])

  const selectedOtherDeptsList = useMemo(() => {
    return additionalFacilities.filter((d) => selectedOtherDepartmentIds.includes(d.id))
  }, [additionalFacilities, selectedOtherDepartmentIds])

  // Lab selection toggle
  const toggleLabCourse = (courseId) => {
    setSelectedLabIds((prev) =>
      prev.includes(courseId) ? prev.filter((id) => id !== courseId) : [...prev, courseId]
    )
  }

  const removeLabCourse = (courseId) => {
    setSelectedLabIds((prev) => prev.filter((id) => id !== courseId))
  }

  const toggleDirectLabOffice = (officeId) => {
    const target = directOffices.find((o) => o.id === officeId)
    if (target && target.has_active_officer === false) return
    setSelectedDirectLabIds((prev) =>
      prev.includes(officeId) ? prev.filter((id) => id !== officeId) : [...prev, officeId]
    )
  }

  const removeDirectLabOffice = (officeId) => {
    setSelectedDirectLabIds((prev) => prev.filter((id) => id !== officeId))
  }

  const toggleOtherDepartment = (deptId) => {
    const target = additionalFacilities.find((d) => d.id === deptId)
    if (target && target.has_active_officer === false) return
    setSelectedOtherDepartmentIds((prev) =>
      prev.includes(deptId) ? prev.filter((id) => id !== deptId) : [...prev, deptId]
    )
  }

  const removeOtherDepartment = (deptId) => {
    setSelectedOtherDepartmentIds((prev) => prev.filter((id) => id !== deptId))
  }

  // Handle Bank details submission
  const handleSaveBank = async (e) => {
    e.preventDefault()
    const { accountNumber, ifscCode, accountHolderName, bankAddress } = bankForm

    const cleanAccount = accountNumber.trim()
    const cleanIfsc = ifscCode.trim().toUpperCase()
    const cleanHolder = accountHolderName.trim()
    const cleanAddress = bankAddress.trim()

    if (!/^\d{9,18}$/.test(cleanAccount)) {
      toast.error('Account number must be digits only, between 9 and 18 characters.')
      return
    }

    if (!/^[A-Z]{4}0[A-Z0-9]{6}$/.test(cleanIfsc)) {
      toast.error('IFSC code must match standard format: 4 letters, 0, then 6 alphanumeric characters (e.g. SBIN0001234).')
      return
    }

    if (!cleanHolder) {
      toast.error('Account holder name is required.')
      return
    }

    if (!cleanAddress) {
      toast.error('Bank branch address is required.')
      return
    }

    setBankSubmitting(true)
    try {
      await studentApi.updateBankDetails({
        accountNumber: cleanAccount,
        ifscCode: cleanIfsc,
        accountHolderName: cleanHolder,
        bankAddress: cleanAddress,
      })
      toast.success('Bank details saved securely.')
      setEditingBank(false)
      await refetchBank()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to update bank details.'
      toast.error(msg)
    } finally {
      setBankSubmitting(false)
    }
  }

  // Step Validations
  const validateStep = (step) => {
    if (step === 1) {
      if (!bankDetails && !editingBank) {
        toast.error('Please save your refund bank details before continuing.')
        return false
      }
      if (editingBank) {
        toast.error('Please complete and save your bank details first.')
        return false
      }
      return true
    }
    if (step === 2) {
      if (isHosteller === null) {
        toast.error('Please select your residential status (Hosteller or Day Scholar).')
        return false
      }
      return true
    }
    if (step === 3) {
      // Empty selection is explicitly allowed per requirement
      return true
    }
    if (step === 4) {
      if (othersNote.length > 500) {
        toast.error('Note must be at most 500 characters.')
        return false
      }
      return true
    }
    return true
  }

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(prev + 1, 5))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Final Submission
  const handleSubmitClearance = async () => {
    if (!confirmed) {
      toast.error('Please check the confirmation box before submitting.')
      return
    }

    setSubmitting(true)
    setBlockError(null)

    try {
      await studentApi.createRequest({
        isHosteller: Boolean(isHosteller),
        labCourseIds: selectedLabIds,
        labWorkshopDepartmentIds: selectedDirectLabIds,
        otherOfficeIds: selectedOtherDepartmentIds,
        othersNote: othersNote.trim() || null,
      })
      toast.success('Clearance application submitted successfully!')
      navigate('/student')
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail || 'Failed to submit clearance application.'

      if (status === 409) {
        // Friendly 409 alert message instructing contact with university office
        setBlockError(
          detail.includes('active dealing officer') || detail.includes('Head of Department')
            ? `Clearance application is currently blocked because an applicable office lacks an active dealing officer or HoD. Please contact the University Academic / Administration Office for assistance: "${detail}"`
            : detail
        )
      } else if (status === 422) {
        toast.error('Validation error. Please review your input declarations.')
      } else {
        toast.error(detail)
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (requestLoading) {
    return (
      <AppShell>
        <div className="max-w-4xl mx-auto space-y-6">
          <Skeleton className="h-10 w-1/3" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </AppShell>
    )
  }

  // If student already has an active clearance request, direct them to dashboard
  if (currentRequest) {
    return (
      <AppShell>
        <div className="max-w-3xl mx-auto py-8">
          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <CardTitle className="text-base font-bold text-zinc-950">
                    Active Clearance Request Exists
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Request #{currentRequest.id} is currently active ({currentRequest.status}).
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-3 text-xs text-zinc-600">
              <p>
                You already have an active clearance application in progress. University regulations permit only one active clearance request at a time.
              </p>
            </CardContent>
            <CardFooter className="p-6 pt-0 flex justify-end">
              <Button
                onClick={() => navigate('/student')}
                className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold gap-1.5"
              >
                Go to Clearance Dossier
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </CardFooter>
          </Card>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-8 pb-16">
        {/* Breadcrumb / Top bar */}
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Link
                to="/student"
                className="text-xs text-muted-foreground hover:text-black transition-colors flex items-center gap-1"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Student Dossier
              </Link>
              <span className="text-zinc-300">/</span>
              <span className="text-xs font-semibold text-black">Apply for Clearance</span>
            </div>
            <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-950 mt-1">
              Clearance Application Wizard
            </h1>
          </div>
          <Badge variant="outline" className="text-xs font-mono bg-zinc-50 border-zinc-200">
            Step {currentStep} of {STEPS.length}
          </Badge>
        </div>

        {/* Horizontal Accessible Stepper Header */}
        <nav aria-label="Application Progress" className="relative">
          <ol className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {STEPS.map((step) => {
              const isPassed = currentStep > step.id
              const isCurrent = currentStep === step.id

              return (
                <li key={step.id}>
                  <button
                    type="button"
                    onClick={() => {
                      if (step.id < currentStep) {
                        setCurrentStep(step.id)
                      } else if (step.id > currentStep) {
                        if (validateStep(currentStep)) setCurrentStep(step.id)
                      }
                    }}
                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                      isCurrent
                        ? 'border-black bg-zinc-50 ring-1 ring-black/5 shadow-2xs'
                        : isPassed
                        ? 'border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-900'
                        : 'border-zinc-200/60 bg-white/50 text-zinc-400 opacity-60'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div
                        className={`w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold ${
                          isPassed
                            ? 'bg-black text-white'
                            : isCurrent
                            ? 'bg-black text-white'
                            : 'bg-zinc-100 text-zinc-500'
                        }`}
                      >
                        {isPassed ? <Check className="w-3.5 h-3.5" /> : step.id}
                      </div>
                      <span className="text-xs font-bold truncate text-zinc-900">{step.label}</span>
                    </div>
                    <span className="text-[10px] text-zinc-500 line-clamp-1 block">
                      {step.description}
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        </nav>

        {/* Critical friendly 409 blocking banner */}
        {blockError && (
          <Alert className="bg-rose-50 border-rose-300 text-rose-950 p-4 rounded-xl shadow-xs">
            <ShieldAlert className="h-5 w-5 text-rose-700 mt-0.5" />
            <div className="flex-1 ml-2">
              <AlertTitle className="text-sm font-bold">Clearance Application Blocked</AlertTitle>
              <AlertDescription className="text-xs mt-1 text-rose-900 leading-relaxed space-y-2">
                <p>{blockError}</p>
                <p className="text-[11px] text-rose-800">
                  Please notify your academic department coordinator or the University Central Administration to designate an active dealing officer so that clearance reviews can be dispatched.
                </p>
              </AlertDescription>
            </div>
          </Alert>
        )}

        {/* STEP 1: Bank Details */}
        {currentStep === 1 && (
          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-black text-white flex items-center justify-center">
                  <Landmark className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold">Step 1: Security Deposit Refund Bank Details</CardTitle>
                  <CardDescription className="text-xs">
                    Your institutional caution money and security deposit will be disbursed directly to this account upon final clearance.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6 pt-0 space-y-6">
              {bankLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-20 w-full" />
                </div>
              ) : bankDetails && !editingBank ? (
                /* Masked Saved Card View */
                <div className="rounded-xl border border-border bg-zinc-50/60 p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-border/80 pb-3">
                    <div className="flex items-center gap-2">
                      <Badge className="bg-emerald-600 text-white text-[10px] font-semibold tracking-wider">
                        Registered & Verified
                      </Badge>
                      <span className="text-xs text-muted-foreground">Encrypted at rest</span>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setEditingBank(true)}
                      className="text-xs h-7 border-border hover:bg-zinc-100"
                    >
                      Edit Account Details
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider block">
                        Beneficiary Name
                      </span>
                      <p className="font-semibold text-zinc-900 mt-0.5">{bankDetails.account_holder_name}</p>
                    </div>
                    <div>
                      <span className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider block">
                        Account Number
                      </span>
                      <p className="font-mono font-bold text-zinc-900 mt-0.5 text-sm">
                        {bankDetails.account_number_masked}
                      </p>
                    </div>
                    <div>
                      <span className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider block">
                        Bank IFSC Code
                      </span>
                      <p className="font-mono font-semibold text-zinc-900 mt-0.5">{bankDetails.ifsc_code}</p>
                    </div>
                    <div>
                      <span className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider block">
                        Branch Address
                      </span>
                      <p className="text-zinc-700 mt-0.5">{bankDetails.bank_address}</p>
                    </div>
                  </div>
                </div>
              ) : (
                /* Bank Input Form */
                <form id="bank-form" onSubmit={handleSaveBank} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="accountHolderName" className="text-xs font-semibold text-zinc-800">
                      Beneficiary Account Holder Name <span className="text-rose-500">*</span>
                    </Label>
                    <Input
                      id="accountHolderName"
                      value={bankForm.accountHolderName}
                      onChange={(e) => setBankForm({ ...bankForm, accountHolderName: e.target.value })}
                      placeholder="Official name on passbook / cheque"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="accountNumber" className="text-xs font-semibold text-zinc-800">
                        Bank Account Number (9 to 18 digits) <span className="text-rose-500">*</span>
                      </Label>
                      <Input
                        id="accountNumber"
                        value={bankForm.accountNumber}
                        onChange={(e) => setBankForm({ ...bankForm, accountNumber: e.target.value })}
                        placeholder="e.g. 123456789012"
                        pattern="^\d{9,18}$"
                        required
                        autoComplete="off"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="ifscCode" className="text-xs font-semibold text-zinc-800">
                        Bank IFSC Code <span className="text-rose-500">*</span>
                      </Label>
                      <Input
                        id="ifscCode"
                        value={bankForm.ifscCode}
                        onChange={(e) => setBankForm({ ...bankForm, ifscCode: e.target.value.toUpperCase() })}
                        placeholder="e.g. SBIN0001234"
                        pattern="^[A-Z]{4}0[A-Z0-9]{6}$"
                        className="uppercase font-mono"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="bankAddress" className="text-xs font-semibold text-zinc-800">
                      Bank Branch Name & Address <span className="text-rose-500">*</span>
                    </Label>
                    <Input
                      id="bankAddress"
                      value={bankForm.bankAddress}
                      onChange={(e) => setBankForm({ ...bankForm, bankAddress: e.target.value })}
                      placeholder="e.g. State Bank of India, SVSU Campus Branch, Palwal"
                      required
                    />
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2">
                    {bankDetails && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setEditingBank(false)}
                        className="text-xs"
                      >
                        Cancel
                      </Button>
                    )}
                    <Button
                      type="submit"
                      size="sm"
                      disabled={bankSubmitting}
                      className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold"
                    >
                      {bankSubmitting ? 'Saving...' : 'Save Bank Details'}
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>

            <CardFooter className="p-6 pt-0 border-t border-border flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Step 1 of 5</span>
              <Button
                type="button"
                onClick={handleNext}
                disabled={!bankDetails || editingBank}
                className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold gap-1.5"
              >
                Continue to Residence
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* STEP 2: Residence */}
        {currentStep === 2 && (
          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-black text-white flex items-center justify-center">
                  <Home className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold">Step 2: University Hostel Residence</CardTitle>
                  <CardDescription className="text-xs">
                    Declare whether you resided in university student hostels during your degree programme.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6 pt-0 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4" role="radiogroup" aria-label="Residence status">
                {/* Option A: Hosteller */}
                <label
                  className={`relative flex flex-col p-5 rounded-xl border cursor-pointer transition-all ${
                    isHosteller === true
                      ? 'border-black ring-1 ring-black bg-zinc-50/70 shadow-2xs'
                      : 'border-border bg-white hover:bg-zinc-50/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-heading font-bold text-sm text-zinc-950 flex items-center gap-2">
                      <Home className="w-4 h-4 text-zinc-700" />
                      Hosteller (Campus Resident)
                    </span>
                    <input
                      type="radio"
                      name="residence"
                      checked={isHosteller === true}
                      onChange={() => setIsHosteller(true)}
                      className="h-4 w-4 text-black border-zinc-300 focus:ring-black"
                    />
                  </div>
                  <p className="text-xs text-zinc-600 leading-relaxed flex-1">
                    I occupied university student hostel accommodations during my studies.
                  </p>
                  <div className="mt-4 pt-3 border-t border-zinc-200/60 flex items-center gap-1.5 text-[11px] text-zinc-500">
                    <Badge variant="outline" className="bg-zinc-100 text-zinc-800 text-[10px] font-mono">
                      Hostel Office Clearance Required
                    </Badge>
                  </div>
                </label>

                {/* Option B: Day Scholar */}
                <label
                  className={`relative flex flex-col p-5 rounded-xl border cursor-pointer transition-all ${
                    isHosteller === false
                      ? 'border-black ring-1 ring-black bg-zinc-50/70 shadow-2xs'
                      : 'border-border bg-white hover:bg-zinc-50/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-heading font-bold text-sm text-zinc-950 flex items-center gap-2">
                      <Building2 className="w-4 h-4 text-zinc-700" />
                      Day Scholar (Non-Hosteller)
                    </span>
                    <input
                      type="radio"
                      name="residence"
                      checked={isHosteller === false}
                      onChange={() => setIsHosteller(false)}
                      className="h-4 w-4 text-black border-zinc-300 focus:ring-black"
                    />
                  </div>
                  <p className="text-xs text-zinc-600 leading-relaxed flex-1">
                    I commuted daily and never resided in university hostel premises.
                  </p>
                  <div className="mt-4 pt-3 border-t border-zinc-200/60 flex items-center gap-1.5 text-[11px] text-zinc-500">
                    <Badge variant="outline" className="bg-zinc-100 text-zinc-800 text-[10px] font-mono">
                      Hostel Office Clearance Omitted
                    </Badge>
                  </div>
                </label>
              </div>

              <div className="rounded-lg bg-zinc-50 border border-border p-3 text-xs text-muted-foreground flex items-center gap-2">
                <span className="font-semibold text-zinc-800">Note:</span>
                Your declaration replaces any earlier roster assumptions and determines whether the Hostel Office reviews your clearance.
              </div>
            </CardContent>

            <CardFooter className="p-6 pt-0 border-t border-border flex items-center justify-between">
              <Button type="button" variant="outline" size="sm" onClick={handleBack} className="text-xs gap-1.5">
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Bank Details
              </Button>
              <Button
                type="button"
                onClick={handleNext}
                disabled={isHosteller === null}
                className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold gap-1.5"
              >
                Continue to Labs & Workshops
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* STEP 3: Labs and Workshops */}
        {currentStep === 3 && (
          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-black text-white flex items-center justify-center">
                    <FlaskConical className="w-4 h-4" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-bold">Step 3: Labs and workshops you attended</CardTitle>
                    <CardDescription className="text-xs">
                      Select the laboratory subjects and workshop facilities you attended during your studies.
                    </CardDescription>
                  </div>
                </div>
                <Badge variant="outline" className="text-xs font-mono bg-zinc-50">
                  {selectedLabIds.length + selectedDirectLabIds.length} Selected
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="p-6 pt-0 space-y-5">
              {/* Mandatory Help Text Callout */}
              <Alert className="bg-zinc-50 border-zinc-200 text-zinc-900 py-3 rounded-lg">
                <FlaskConical className="h-4 w-4 text-zinc-700" />
                <AlertDescription className="text-xs font-medium leading-relaxed">
                  Select only the labs and workshops you actually used. Your department checks this list and can add anything missing.
                </AlertDescription>
              </Alert>

              {/* Selected Chips Strip */}
              {(selectedCoursesList.length > 0 || selectedDirectOfficesList.length > 0) && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-zinc-700">
                      Selected Labs & Workshops ({selectedCoursesList.length + selectedDirectOfficesList.length}):
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedLabIds([])
                        setSelectedDirectLabIds([])
                      }}
                      className="text-[11px] text-zinc-500 hover:text-black underline"
                    >
                      Clear all
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5 p-2.5 rounded-lg bg-zinc-50 border border-zinc-200">
                    {selectedCoursesList.map((c) => (
                      <Badge
                        key={`course-${c.id}`}
                        variant="secondary"
                        className="bg-white border border-zinc-300 text-zinc-900 text-xs py-1 px-2.5 flex items-center gap-1.5 shadow-2xs"
                      >
                        <span className="font-mono font-semibold">{c.code}</span>
                        <span className="text-zinc-600 truncate max-w-[200px]">{c.name}</span>
                        <button
                          type="button"
                          onClick={() => removeLabCourse(c.id)}
                          aria-label={`Remove ${c.name}`}
                          className="hover:bg-zinc-200 rounded p-0.5 text-zinc-500 hover:text-black"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                    {selectedDirectOfficesList.map((o) => (
                      <Badge
                        key={`direct-${o.id}`}
                        variant="secondary"
                        className="bg-white border border-zinc-300 text-zinc-900 text-xs py-1 px-2.5 flex items-center gap-1.5 shadow-2xs"
                      >
                        <span className="text-zinc-700 font-semibold truncate max-w-[200px]">{o.name}</span>
                        <span className="text-[10px] text-zinc-400 font-mono">(Direct office)</span>
                        <button
                          type="button"
                          onClick={() => removeDirectLabOffice(o.id)}
                          aria-label={`Remove ${o.name}`}
                          className="hover:bg-zinc-200 rounded p-0.5 text-zinc-500 hover:text-black"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Search filter input */}
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-400" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by course code, title, or signing lab office (e.g. CS-L101, Lab-1)..."
                  className="pl-9 pr-9 text-xs"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-2.5 text-zinc-400 hover:text-black"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Grouped Courses List */}
              {catalogLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ) : Object.keys(groupedLabCourses).length === 0 ? (
                <div className="p-8 text-center text-xs text-muted-foreground border border-dashed rounded-xl">
                  {searchQuery
                    ? `No lab courses matching "${searchQuery}".`
                    : 'No specific lab courses configured for your programme. An empty selection is permitted.'}
                </div>
              ) : (
                <div className="space-y-6 max-h-[340px] overflow-y-auto pr-1">
                  {Object.entries(groupedLabCourses).map(([groupTitle, courses]) => (
                    <div key={groupTitle} className="space-y-2">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 sticky top-0 bg-white py-1">
                        {groupTitle} ({courses.length})
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {courses.map((course) => {
                          const isChecked = selectedLabIds.includes(course.id)
                          return (
                            <label
                              key={course.id}
                              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors text-xs ${
                                isChecked
                                  ? 'border-black bg-zinc-50 ring-1 ring-black/5'
                                  : 'border-zinc-200 bg-white hover:bg-zinc-50/60'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggleLabCourse(course.id)}
                                className="mt-0.5 rounded border-zinc-300 text-black focus:ring-black h-4 w-4"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="font-mono font-bold text-zinc-950">{course.code}</span>
                                  <Badge variant="outline" className="text-[10px] bg-white py-0 border-zinc-200 text-zinc-600">
                                    Signed by: {course.lab_department_name}
                                  </Badge>
                                </div>
                                <p className="font-medium text-zinc-800 mt-0.5 line-clamp-2 leading-snug">
                                  {course.name}
                                </p>
                              </div>
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Collapsible "My lab or workshop is not listed" panel */}
              <div className="border border-zinc-200 rounded-xl overflow-hidden bg-zinc-50/40">
                <button
                  type="button"
                  onClick={() => setDirectLabsOpen((prev) => !prev)}
                  className="w-full flex items-center justify-between p-3.5 text-xs font-semibold text-zinc-900 hover:bg-zinc-100/60 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-zinc-600" />
                    <span>My lab or workshop is not listed</span>
                    {selectedDirectLabIds.length > 0 && (
                      <Badge variant="outline" className="text-[10px] bg-white font-mono">
                        {selectedDirectLabIds.length} selected
                      </Badge>
                    )}
                  </div>
                  {directLabsOpen ? (
                    <ChevronUp className="w-4 h-4 text-zinc-500" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-zinc-500" />
                  )}
                </button>

                {directLabsOpen && (
                  <div className="p-4 pt-1 border-t border-zinc-200 bg-white space-y-3">
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      If you attended a specific laboratory or workshop that does not appear in your curriculum subjects list, choose the facility directly below:
                    </p>

                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-400" />
                      <Input
                        value={directLabSearch}
                        onChange={(e) => setDirectLabSearch(e.target.value)}
                        placeholder="Search labs & workshops by name..."
                        className="pl-8 text-xs h-8"
                      />
                    </div>

                    {filteredDirectOffices.length === 0 ? (
                      <div className="p-4 text-center text-xs text-muted-foreground">
                        {directLabSearch
                          ? `No lab or workshop matching "${directLabSearch}".`
                          : 'No additional lab or workshop offices found.'}
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[220px] overflow-y-auto pt-1">
                        {filteredDirectOffices.map((office) => {
                          const isChecked = selectedDirectLabIds.includes(office.id)
                          const isAvailable = office.has_active_officer !== false
                          return (
                            <label
                              key={office.id}
                              className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs transition-colors ${
                                !isAvailable
                                  ? 'border-zinc-200 bg-zinc-50/70 text-zinc-400 cursor-not-allowed opacity-75'
                                  : isChecked
                                    ? 'border-black bg-zinc-50 ring-1 ring-black/5 cursor-pointer'
                                    : 'border-zinc-200 bg-white hover:bg-zinc-50/50 cursor-pointer'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                disabled={!isAvailable}
                                onChange={() => {
                                  if (isAvailable) toggleDirectLabOffice(office.id)
                                }}
                                className="mt-0.5 rounded border-zinc-300 text-black focus:ring-black h-3.5 w-3.5 disabled:opacity-50 disabled:cursor-not-allowed"
                              />
                              <div className="flex-1 min-w-0">
                                <span
                                  className={`font-semibold block truncate ${
                                    isAvailable ? 'text-zinc-900' : 'text-zinc-500'
                                  }`}
                                >
                                  {office.name}
                                </span>
                                {office.description && (
                                  <p className="text-[11px] text-zinc-500 line-clamp-1">{office.description}</p>
                                )}
                                {!isAvailable && (
                                  <p className="text-[11px] text-amber-700 font-medium mt-1">
                                    Not available yet. Contact your department office.
                                  </p>
                                )}
                              </div>
                            </label>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </CardContent>

            <CardFooter className="p-6 pt-0 border-t border-border flex items-center justify-between">
              <Button type="button" variant="outline" size="sm" onClick={handleBack} className="text-xs gap-1.5">
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Residence
              </Button>
              <Button
                type="button"
                onClick={handleNext}
                className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold gap-1.5"
              >
                Continue to Additional Facilities
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* STEP 4: Additional Facilities (Optional) */}
        {currentStep === 4 && (
          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-black text-white flex items-center justify-center">
                  <Building2 className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold">Step 4: Additional facilities (optional)</CardTitle>
                  <CardDescription className="text-xs">
                    Declare specialized facilities you utilized and provide any supporting notes.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6 pt-0 space-y-6">
              {/* Mandatory Help Text Callout */}
              <Alert className="bg-zinc-50 border-zinc-200 text-zinc-900 py-3 rounded-lg">
                <Building2 className="h-4 w-4 text-zinc-700" />
                <AlertDescription className="text-xs font-medium leading-relaxed">
                  Only add a facility you actually used, for example Others.
                </AlertDescription>
              </Alert>

              {/* Selected Facilities Strip */}
              {selectedOtherDeptsList.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-zinc-700">
                      Selected Additional Facilities ({selectedOtherDeptsList.length}):
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelectedOtherDepartmentIds([])}
                      className="text-[11px] text-zinc-500 hover:text-black underline"
                    >
                      Clear all
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5 p-2.5 rounded-lg bg-zinc-50 border border-zinc-200">
                    {selectedOtherDeptsList.map((d) => (
                      <Badge
                        key={`other-${d.id}`}
                        variant="secondary"
                        className="bg-white border border-zinc-300 text-zinc-900 text-xs py-1 px-2.5 flex items-center gap-1.5 shadow-2xs"
                      >
                        <span className="text-zinc-800 font-semibold">{d.name}</span>
                        <button
                          type="button"
                          onClick={() => removeOtherDepartment(d.id)}
                          aria-label={`Remove ${d.name}`}
                          className="hover:bg-zinc-200 rounded p-0.5 text-zinc-500 hover:text-black"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Searchable multi-select of additional facilities */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-zinc-800 block">
                  Select Additional Facilities
                </Label>

                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-400" />
                  <Input
                    value={otherDeptsSearch}
                    onChange={(e) => setOtherDeptsSearch(e.target.value)}
                    placeholder="Search additional facilities..."
                    className="pl-8 text-xs h-8"
                  />
                </div>

                {deptsLoading || catalogLoading ? (
                  <Skeleton className="h-20 w-full" />
                ) : filteredAdditionalFacilities.length === 0 ? (
                  <div className="p-4 text-center text-xs text-muted-foreground border border-dashed rounded-lg">
                    {otherDeptsSearch
                      ? `No facilities matching "${otherDeptsSearch}".`
                      : 'No additional facilities listed.'}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 max-h-[220px] overflow-y-auto">
                    {filteredAdditionalFacilities.map((dept) => {
                      const isChecked = selectedOtherDepartmentIds.includes(dept.id)
                      const isAvailable = dept.has_active_officer !== false
                      return (
                        <label
                          key={dept.id}
                          className={`flex items-start gap-2.5 p-3 rounded-lg border text-xs transition-colors ${
                            !isAvailable
                              ? 'border-zinc-200 bg-zinc-50/70 text-zinc-400 cursor-not-allowed opacity-75'
                              : isChecked
                                ? 'border-black bg-zinc-50 ring-1 ring-black/5 cursor-pointer'
                                : 'border-zinc-200 bg-white hover:bg-zinc-50/50 cursor-pointer'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            disabled={!isAvailable}
                            onChange={() => {
                              if (isAvailable) toggleOtherDepartment(dept.id)
                            }}
                            className="mt-0.5 rounded border-zinc-300 text-black focus:ring-black h-3.5 w-3.5 disabled:opacity-50 disabled:cursor-not-allowed"
                          />
                          <div className="flex-1 min-w-0">
                            <span
                              className={`font-semibold block ${
                                isAvailable ? 'text-zinc-900' : 'text-zinc-500'
                              }`}
                            >
                              {dept.name}
                            </span>
                            {dept.description && (
                              <p className="text-[11px] text-zinc-500 line-clamp-1">{dept.description}</p>
                            )}
                            {!isAvailable && (
                              <p className="text-[11px] text-amber-700 font-medium mt-1">
                                Not available yet. Contact your department office.
                              </p>
                            )}
                          </div>
                        </label>
                      )
                    })}
                  </div>
                )}
              </div>

              <Separator />

              {/* Textarea for note (max 500 characters) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="othersNote" className="text-xs font-semibold text-zinc-800">
                    Additional Declarations Note (Optional, max 500 characters)
                  </Label>
                  <span
                    className={`text-[11px] font-mono ${
                      othersNote.length > 500 ? 'text-rose-600 font-bold' : 'text-zinc-400'
                    }`}
                  >
                    {othersNote.length} / 500
                  </span>
                </div>
                <Textarea
                  id="othersNote"
                  value={othersNote}
                  onChange={(e) => setOthersNote(e.target.value.slice(0, 500))}
                  placeholder="e.g., Completed thesis research in Robotics Centre; all microcontrollers returned to In-Charge on 15 Oct."
                  className="text-xs min-h-[100px] resize-y"
                  maxLength={500}
                />
                <p className="text-[11px] text-muted-foreground">
                  Your academic department reviews this note during clearance inspection and can attach additional offices if necessary.
                </p>
              </div>
            </CardContent>

            <CardFooter className="p-6 pt-0 border-t border-border flex items-center justify-between">
              <Button type="button" variant="outline" size="sm" onClick={handleBack} className="text-xs gap-1.5">
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Labs & Workshops
              </Button>
              <Button
                type="button"
                onClick={handleNext}
                className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold gap-1.5"
              >
                Continue to Review
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* STEP 5: Review & Submit */}
        {currentStep === 5 && (
          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-black text-white flex items-center justify-center">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-lg font-bold">Step 5: Review Declarations & Confirm</CardTitle>
                  <CardDescription className="text-xs">
                    Please verify your declarations. Once submitted, clearance reviews will be dispatched across all applicable offices.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6 pt-0 space-y-6">
              {/* Review summary cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                {/* 1. Bank Details Summary */}
                <div className="p-4 rounded-xl border border-zinc-200 bg-zinc-50/50 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-zinc-950 flex items-center gap-1.5">
                      <Landmark className="w-3.5 h-3.5 text-zinc-700" />
                      Refund Bank Account
                    </span>
                    <button
                      type="button"
                      onClick={() => setCurrentStep(1)}
                      className="text-[11px] text-zinc-500 hover:text-black underline"
                    >
                      Change
                    </button>
                  </div>
                  <div className="space-y-1 text-zinc-700 pt-1">
                    <p className="font-mono font-semibold text-zinc-900">{bankDetails?.account_number_masked}</p>
                    <p>{bankDetails?.account_holder_name} • {bankDetails?.ifsc_code}</p>
                    <p className="text-[11px] text-zinc-500 truncate">{bankDetails?.bank_address}</p>
                  </div>
                </div>

                {/* 2. Residence Declaration Summary */}
                <div className="p-4 rounded-xl border border-zinc-200 bg-zinc-50/50 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-zinc-950 flex items-center gap-1.5">
                      <Home className="w-3.5 h-3.5 text-zinc-700" />
                      Residential Status
                    </span>
                    <button
                      type="button"
                      onClick={() => setCurrentStep(2)}
                      className="text-[11px] text-zinc-500 hover:text-black underline"
                    >
                      Change
                    </button>
                  </div>
                  <div className="pt-1">
                    <Badge variant="outline" className="bg-white text-zinc-900 font-semibold py-1">
                      {isHosteller ? 'Hosteller (Hostel Office Review Included)' : 'Day Scholar (No Hostel Review)'}
                    </Badge>
                  </div>
                </div>
              </div>

              {/* 3. Grouped Heading: Labs and workshops you attended */}
              <div className="p-4 rounded-xl border border-zinc-200 bg-zinc-50/50 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-zinc-950 flex items-center gap-1.5">
                    <FlaskConical className="w-3.5 h-3.5 text-zinc-700" />
                    Labs and workshops you attended ({selectedCoursesList.length + selectedDirectOfficesList.length})
                  </span>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(3)}
                    className="text-[11px] text-zinc-500 hover:text-black underline"
                  >
                    Edit
                  </button>
                </div>
                {selectedCoursesList.length === 0 && selectedDirectOfficesList.length === 0 ? (
                  <p className="text-zinc-500 italic pt-0.5">None declared (empty declaration permitted).</p>
                ) : (
                  <div className="space-y-2 pt-1">
                    {selectedCoursesList.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {selectedCoursesList.map((c) => (
                          <Badge key={`rev-course-${c.id}`} variant="secondary" className="bg-white border text-xs py-0.5">
                            <span className="font-mono font-semibold mr-1">{c.code}</span>
                            {c.name}
                            <span className="text-[10px] text-zinc-500 ml-1.5">({c.lab_department_name})</span>
                          </Badge>
                        ))}
                      </div>
                    )}
                    {selectedDirectOfficesList.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {selectedDirectOfficesList.map((o) => (
                          <Badge key={`rev-direct-${o.id}`} variant="secondary" className="bg-white border text-xs py-0.5">
                            <span className="font-semibold text-zinc-900">{o.name}</span>
                            <span className="text-[10px] text-zinc-500 ml-1.5">(Direct office)</span>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 4. Grouped Heading: Additional facilities (optional) */}
              <div className="p-4 rounded-xl border border-zinc-200 bg-zinc-50/50 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-zinc-950 flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-zinc-700" />
                    Additional facilities (optional) ({selectedOtherDeptsList.length})
                  </span>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(4)}
                    className="text-[11px] text-zinc-500 hover:text-black underline"
                  >
                    Edit
                  </button>
                </div>

                {selectedOtherDeptsList.length === 0 ? (
                  <p className="text-zinc-500 italic pt-0.5">No additional facilities declared.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {selectedOtherDeptsList.map((d) => (
                      <Badge key={`rev-other-${d.id}`} variant="secondary" className="bg-white border text-xs py-0.5">
                        <span className="font-semibold text-zinc-900">{d.name}</span>
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="pt-2 border-t border-zinc-200/60">
                  <span className="text-[11px] font-semibold text-zinc-600 block mb-0.5">Note:</span>
                  <p className="text-zinc-700 italic">
                    {othersNote ? `"${othersNote}"` : 'None provided'}
                  </p>
                </div>
              </div>

              {/* Required confirmation checkbox */}
              <div className="rounded-xl border border-zinc-300 bg-white p-4 space-y-2">
                <label className="flex items-start gap-3 cursor-pointer text-xs select-none">
                  <input
                    type="checkbox"
                    id="confirm-declaration"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                    className="mt-0.5 rounded border-zinc-400 text-black focus:ring-black h-4 w-4"
                  />
                  <div className="space-y-1">
                    <span className="font-bold text-zinc-900 block leading-tight">
                      I confirm that the above declarations are accurate and complete.
                    </span>
                    <span className="text-[11px] text-zinc-500 block leading-relaxed">
                      I understand that false statements or omitted facilities will delay my degree clearance and caution deposit refund. My academic department has authority to attach any omitted offices.
                    </span>
                  </div>
                </label>
              </div>
            </CardContent>

            <CardFooter className="p-6 pt-0 border-t border-border flex items-center justify-between">
              <Button type="button" variant="outline" size="sm" onClick={handleBack} className="text-xs gap-1.5">
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Notes
              </Button>
              <Button
                type="button"
                onClick={handleSubmitClearance}
                disabled={!confirmed || submitting}
                className="bg-black text-white hover:bg-zinc-800 text-xs font-semibold gap-2 shadow-xs"
              >
                {submitting ? (
                  <>
                    <RotateCw className="w-3.5 h-3.5 animate-spin" />
                    Submitting Application...
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    Submit No-Dues Application
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>
        )}
      </div>
    </AppShell>
  )
}

export default StudentApplyPage
