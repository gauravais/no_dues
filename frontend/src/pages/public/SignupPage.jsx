import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { authApi } from '@/api/auth'
import { useAuthConfig } from '@/hooks/useAuthConfig'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { toast } from 'sonner'
import {
  KeyRound,
  Mail,
  UserCheck,
  Lock,
  ArrowRight,
  ArrowLeft,
  Info,
  CreditCard,
} from 'lucide-react'

export function SignupPage() {
  useDocumentTitle('Student Registration')
  const { login } = useAuth()
  const navigate = useNavigate()
  const { data: authConfig, isLoading: configLoading } = useAuthConfig()

  // If OTP signup is disabled, redirect to login with explanatory notice
  useEffect(() => {
    if (!configLoading && authConfig && authConfig.otp_signup_enabled === false) {
      toast.info('Students now sign in with their university Google account. No separate sign-up is needed.')
      navigate('/login', {
        replace: true,
        state: {
          notice: 'Students now sign in with their university Google account. No separate sign-up is needed.',
        },
      })
    }
  }, [authConfig, configLoading, navigate])

  // Step 1: Request OTP state
  const [step, setStep] = useState(1)
  const [registrationNumber, setRegistrationNumber] = useState('')
  const [email, setEmail] = useState('')
  const [devOtpHint, setDevOtpHint] = useState(null)
  const [serverNotice, setServerNotice] = useState('')

  // Step 2: Verify state
  const [otpCode, setOtpCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [rateLimitCooldown, setRateLimitCooldown] = useState(0)
  const [errors, setErrors] = useState({})

  // Cooldown timer for Resend code
  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 1 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  // Cooldown timer for 429 rate limit
  useEffect(() => {
    if (rateLimitCooldown <= 0) return
    const timer = setInterval(() => {
      setRateLimitCooldown((prev) => (prev > 1 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [rateLimitCooldown])

  const validateStep1 = () => {
    const errs = {}
    if (!registrationNumber.trim()) {
      errs.registrationNumber = 'Registration number is required.'
    }
    if (!email.trim()) {
      errs.email = 'University email is required.'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errs.email = 'Please enter a valid email address.'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const validateStep2 = () => {
    const errs = {}
    if (!otpCode.trim() || otpCode.trim().length !== 6) {
      errs.otpCode = 'Enter the 6-digit verification code.'
    }
    if (!password) {
      errs.password = 'Password is required.'
    } else if (password.length < 10) {
      errs.password = 'Password must be at least 10 characters.'
    }
    if (password !== confirmPassword) {
      errs.confirmPassword = 'Passwords do not match.'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleRequestOtp = async (e) => {
    e.preventDefault()
    if (!validateStep1()) return

    const cleanReg = registrationNumber.trim().toUpperCase()
    const cleanEmail = email.trim().toLowerCase()

    setLoading(true)
    try {
      const data = await authApi.requestOtp(cleanReg, cleanEmail)
      const message =
        data?.message ||
        data?.detail ||
        'If the details match our records, a code has been sent to your university email.'
      setServerNotice(message)
      toast.success(message)
      if (import.meta.env.DEV && data?.dev_otp) {
        setDevOtpHint(data.dev_otp)
        setOtpCode(data.dev_otp)
      }
      setStep(2)
      setResendCooldown(60)
      setErrors({})
    } catch (err) {
      if (err.response?.status === 429) {
        const retryHeader =
          err.response?.headers?.['retry-after'] ||
          err.response?.headers?.get?.('retry-after')
        const seconds = Number(retryHeader) || 60
        const minutes = Math.max(1, Math.ceil(seconds / 60))
        const msg = `Too many attempts. Please try again in ${minutes} minute${
          minutes > 1 ? 's' : ''
        }.`
        toast.error(msg)
        setRateLimitCooldown(seconds)
      } else {
        // ALWAYS advance to code step and display the generic notification to prevent account enumeration
        const message =
          err.response?.data?.message ||
          'If the details match our records, a code has been sent to your university email.'
        setServerNotice(message)
        toast.info(message)
        setStep(2)
        setResendCooldown(60)
        setErrors({})
      }
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    if (resendCooldown > 0 || rateLimitCooldown > 0 || resending) return
    const cleanReg = registrationNumber.trim().toUpperCase()
    const cleanEmail = email.trim().toLowerCase()

    setResending(true)
    try {
      const data = await authApi.requestOtp(cleanReg, cleanEmail)
      const message =
        data?.message ||
        data?.detail ||
        'If the details match our records, a code has been sent to your university email.'
      setServerNotice(message)
      toast.success(message)
      if (import.meta.env.DEV && data?.dev_otp) {
        setDevOtpHint(data.dev_otp)
        setOtpCode(data.dev_otp)
      }
      setResendCooldown(60)
    } catch (err) {
      if (err.response?.status === 429) {
        const retryHeader =
          err.response?.headers?.['retry-after'] ||
          err.response?.headers?.get?.('retry-after')
        const seconds = Number(retryHeader) || 60
        const minutes = Math.max(1, Math.ceil(seconds / 60))
        const msg = `Too many attempts. Please try again in ${minutes} minute${
          minutes > 1 ? 's' : ''
        }.`
        toast.error(msg)
        setRateLimitCooldown(seconds)
      } else {
        const message =
          'If the details match our records, a code has been sent to your university email.'
        setServerNotice(message)
        toast.info(message)
        setResendCooldown(60)
      }
    } finally {
      setResending(false)
    }
  }

  const handleVerifyOtp = async (e) => {
    e.preventDefault()
    if (!validateStep2()) return

    const cleanReg = registrationNumber.trim().toUpperCase()
    const cleanOtp = otpCode.trim()

    setLoading(true)
    try {
      const data = await authApi.verifyOtp({
        registrationNumber: cleanReg,
        otp: cleanOtp,
        password,
      })

      login(data.access_token)
      toast.success('Registration complete! Welcome to SVSU No-Dues.')
      navigate('/student', { replace: true })
    } catch (err) {
      if (err.response?.status === 429) {
        const retryHeader =
          err.response?.headers?.['retry-after'] ||
          err.response?.headers?.get?.('retry-after')
        const seconds = Number(retryHeader) || 60
        const minutes = Math.max(1, Math.ceil(seconds / 60))
        toast.error(
          `Too many attempts. Please try again in ${minutes} minute${
            minutes > 1 ? 's' : ''
          }.`
        )
        setRateLimitCooldown(seconds)
      } else {
        toast.error('Invalid or expired verification code.')
        setErrors({ otpCode: 'Invalid or expired verification code.' })
      }
    } finally {
      setLoading(false)
    }
  }

  if (!configLoading && authConfig && authConfig.otp_signup_enabled === false) {
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center p-6 font-sans">
        <Card className="w-full max-w-md p-6 text-center space-y-4 bg-white border-border shadow-card">
          <Info className="w-8 h-8 text-blue-600 mx-auto" />
          <h2 className="font-heading font-bold text-lg text-zinc-900">Redirecting to Sign In</h2>
          <p className="text-xs text-zinc-600 leading-relaxed font-medium">
            Students now sign in with their university Google account. No separate sign-up is needed.
          </p>
          <Button asChild size="sm" className="bg-primary text-primary-foreground font-semibold">
            <Link to="/login">Go to Sign In</Link>
          </Button>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-50/50 flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left Column: Brand & Workflow Briefing Panel (Desktop) */}
        <div className="hidden lg:flex lg:col-span-5 flex-col justify-between space-y-8 pr-4">
          <div className="space-y-4">
            <Link to="/" className="inline-block group">
              <span className="font-heading font-extrabold text-2xl tracking-tight text-black transition-opacity group-hover:opacity-80">
                SVSU NO-DUES
              </span>
            </Link>
            <h2 className="font-heading text-2xl font-bold tracking-tight text-zinc-900 leading-snug">
              Official student account provisioning.
            </h2>
            <p className="text-xs text-zinc-600 leading-relaxed">
              Verify your institutional registration against the official university roster to begin your digital clearance application.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-border shadow-2xs">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <UserCheck className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-zinc-900 block">Roster Verification</span>
                <span className="text-zinc-500 leading-snug">Secure authentication against university academic records.</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-border shadow-2xs">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <CreditCard className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-zinc-900 block">Security Deposit Refund</span>
                <span className="text-zinc-500 leading-snug">Direct deposit credit once all offices clear dues.</span>
              </div>
            </div>
          </div>

          <div className="pt-2 text-[11px] text-zinc-400">
            Shri Vishwakarma Skill University • Digital Clearance
          </div>
        </div>

        {/* Right Column: Signup Form Card */}
        <div className="lg:col-span-7 w-full max-w-md mx-auto space-y-4">
          <div className="text-center lg:hidden mb-4">
            <Link to="/" className="inline-block">
              <span className="font-heading font-extrabold text-2xl tracking-tight text-black">
                SVSU NO-DUES
              </span>
            </Link>
            <p className="text-xs text-zinc-500 mt-1">Student Account Provisioning</p>
          </div>

          {/* Step Indicator */}
          <div className="flex items-center justify-center gap-3">
            <div
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full border transition-colors ${
                step === 1
                  ? 'bg-black text-white border-black'
                  : 'bg-white text-zinc-700 border-zinc-200'
              }`}
            >
              <span>1. Roster Verification</span>
            </div>
            <div className="w-4 h-px bg-zinc-300" />
            <div
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full border transition-colors ${
                step === 2
                  ? 'bg-black text-white border-black'
                  : 'bg-white text-zinc-400 border-zinc-200'
              }`}
            >
              <span>2. OTP & Password</span>
            </div>
          </div>

          <Card className="border-border bg-white shadow-card">
            {step === 1 ? (
              <form onSubmit={handleRequestOtp} noValidate>
                <CardHeader className="p-6 pb-4">
                  <CardTitle className="text-lg font-bold">Student Registration</CardTitle>
                  <CardDescription className="text-xs">
                    Enter your official university registration number and email matching institutional records.
                  </CardDescription>
                </CardHeader>

                <CardContent className="p-6 pt-0 space-y-4">
                  {/* Registration Number */}
                  <div className="space-y-1.5">
                    <Label htmlFor="regNum" className="text-xs font-semibold text-zinc-800">
                      Registration Number
                    </Label>
                    <div className="relative">
                      <UserCheck className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                      <Input
                        id="regNum"
                        placeholder="e.g. 2024CS001"
                        className={`pl-9 font-mono uppercase text-sm ${errors.registrationNumber ? 'border-destructive ring-1 ring-destructive' : ''}`}
                        value={registrationNumber}
                        onChange={(e) => {
                          setRegistrationNumber(e.target.value)
                          if (errors.registrationNumber) setErrors((prev) => ({ ...prev, registrationNumber: undefined }))
                        }}
                        required
                      />
                    </div>
                    {errors.registrationNumber && (
                      <p className="text-[11px] text-destructive font-medium mt-0.5">{errors.registrationNumber}</p>
                    )}
                  </div>

                  {/* Student Email */}
                  <div className="space-y-1.5">
                    <Label htmlFor="email" className="text-xs font-semibold text-zinc-800">
                      Official University Email
                    </Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                      <Input
                        id="email"
                        type="email"
                        placeholder="student@svsu.ac.in"
                        className={`pl-9 text-sm ${errors.email ? 'border-destructive ring-1 ring-destructive' : ''}`}
                        value={email}
                        onChange={(e) => {
                          setEmail(e.target.value)
                          if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
                        }}
                        required
                      />
                    </div>
                    {errors.email && (
                      <p className="text-[11px] text-destructive font-medium mt-0.5">{errors.email}</p>
                    )}
                  </div>

                  <Button
                    type="submit"
                    className="w-full bg-primary text-primary-foreground hover:bg-zinc-800 font-semibold text-sm h-10 mt-2 shadow-xs"
                    disabled={loading || rateLimitCooldown > 0}
                  >
                    {rateLimitCooldown > 0
                      ? `Rate limit active (wait ${rateLimitCooldown}s)`
                      : loading
                      ? 'Validating Roster...'
                      : 'Request Verification OTP'}
                    {!loading && rateLimitCooldown <= 0 && <ArrowRight className="ml-2 h-4 w-4" />}
                  </Button>
                </CardContent>

                <CardFooter className="p-6 pt-0 border-t border-zinc-100 flex flex-col items-center justify-center gap-2">
                  <p className="text-xs text-zinc-500 text-center mt-3">
                    Already have an account?{' '}
                    <Link to="/login" className="font-semibold text-black hover:underline underline-offset-2">
                      Sign in
                    </Link>
                  </p>
                </CardFooter>
              </form>
            ) : (
              <form onSubmit={handleVerifyOtp} noValidate>
                <CardHeader className="p-6 pb-4">
                  <CardTitle className="text-lg font-bold">Verify OTP & Password</CardTitle>
                  <CardDescription className="text-xs">
                    Enter the 6-digit verification code dispatched for {email}.
                  </CardDescription>
                </CardHeader>

                <CardContent className="p-6 pt-0 space-y-4">
                  {/* Generic Dispatch Notification from Server */}
                  {serverNotice && (
                    <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-lg text-xs text-zinc-700 leading-relaxed">
                      {serverNotice}
                    </div>
                  )}

                  <p className="text-xs text-zinc-500">
                    The code is sent to your university email. Check spam if you do not see it.
                  </p>

                  {/* Dev OTP Hint Banner if present */}
                  {import.meta.env.DEV && devOtpHint && (
                    <Alert className="bg-amber-50 border-amber-200 text-amber-900 py-2.5">
                      <Info className="h-4 w-4 text-amber-800" />
                      <AlertTitle className="text-xs font-semibold">Development OTP Mode</AlertTitle>
                      <AlertDescription className="text-xs font-mono font-bold tracking-widest text-amber-950 mt-0.5">
                        Code: {devOtpHint}
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* OTP Code */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="otpCode" className="text-xs font-semibold text-zinc-800">
                        6-Digit Verification Code
                      </Label>
                      <button
                        type="button"
                        onClick={handleResendCode}
                        disabled={resendCooldown > 0 || rateLimitCooldown > 0 || resending}
                        className="text-xs font-semibold text-zinc-900 hover:underline disabled:text-zinc-400 disabled:no-underline"
                      >
                        {resending
                          ? 'Resending...'
                          : resendCooldown > 0
                          ? `Resend code (${resendCooldown}s)`
                          : 'Resend code'}
                      </button>
                    </div>
                    <div className="relative">
                      <KeyRound className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                      <Input
                        id="otpCode"
                        maxLength={6}
                        placeholder="123456"
                        className={`pl-9 font-mono tracking-widest text-base ${errors.otpCode ? 'border-destructive ring-1 ring-destructive' : ''}`}
                        value={otpCode}
                        onChange={(e) => {
                          setOtpCode(e.target.value)
                          if (errors.otpCode) setErrors((prev) => ({ ...prev, otpCode: undefined }))
                        }}
                        autoFocus
                        required
                      />
                    </div>
                    {errors.otpCode && (
                      <p className="text-[11px] text-destructive font-medium mt-0.5">{errors.otpCode}</p>
                    )}
                  </div>

                  {/* Password */}
                  <div className="space-y-1.5">
                    <Label htmlFor="password" className="text-xs font-semibold text-zinc-800">
                      Create Password (minimum 10 characters)
                    </Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                      <Input
                        id="password"
                        type="password"
                        placeholder="••••••••••"
                        className={`pl-9 text-sm ${errors.password ? 'border-destructive ring-1 ring-destructive' : ''}`}
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value)
                          if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }))
                        }}
                        required
                      />
                    </div>
                    {errors.password && (
                      <p className="text-[11px] text-destructive font-medium mt-0.5">{errors.password}</p>
                    )}
                  </div>

                  {/* Confirm Password */}
                  <div className="space-y-1.5">
                    <Label htmlFor="confirmPassword" className="text-xs font-semibold text-zinc-800">
                      Confirm Password
                    </Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                      <Input
                        id="confirmPassword"
                        type="password"
                        placeholder="••••••••"
                        className={`pl-9 text-sm ${errors.confirmPassword ? 'border-destructive ring-1 ring-destructive' : ''}`}
                        value={confirmPassword}
                        onChange={(e) => {
                          setConfirmPassword(e.target.value)
                          if (errors.confirmPassword) setErrors((prev) => ({ ...prev, confirmPassword: undefined }))
                        }}
                        required
                      />
                    </div>
                    {errors.confirmPassword && (
                      <p className="text-[11px] text-destructive font-medium mt-0.5">{errors.confirmPassword}</p>
                    )}
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="w-1/3 text-xs h-10"
                      onClick={() => setStep(1)}
                    >
                      <ArrowLeft className="mr-1 h-3.5 w-3.5" /> Back
                    </Button>
                    <Button
                      type="submit"
                      className="w-2/3 bg-primary text-primary-foreground hover:bg-zinc-800 text-xs h-10 font-semibold"
                      disabled={loading || rateLimitCooldown > 0}
                    >
                      {rateLimitCooldown > 0
                        ? `Wait (${rateLimitCooldown}s)`
                        : loading
                        ? 'Creating Account...'
                        : 'Complete Signup'}
                    </Button>
                  </div>
                </CardContent>
              </form>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

export default SignupPage
