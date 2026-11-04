import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { authApi } from '@/api/auth'
import { useAuthConfig } from '@/hooks/useAuthConfig'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { toast } from 'sonner'
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  ArrowRight,
  Sparkles,
  Zap,
  ShieldCheck,
  CreditCard,
  ChevronDown,
  AlertTriangle,
  ShieldAlert,
  Info,
} from 'lucide-react'

const DEV_STAFF_ACCOUNTS = import.meta.env.DEV // wording-ok
  ? [
      { role: 'Administrator', email: 'admin@svsu.ac.in', desc: 'System Admin' },
      { role: 'Accounts / Registrar', email: 'registrar.accounts@svsu.ac.in', desc: 'R&S Branch' },
      { role: 'Chairperson CS/IT', email: 'hod.csit@svsu.ac.in', desc: 'HoD' },
      { role: 'Academic Officer (CS/IT)', email: 'officer.csit@svsu.ac.in', desc: 'CS/IT Dept' },
      { role: 'Library Officer', email: 'library.officer@svsu.ac.in', desc: 'Central Library' },
      { role: 'Hostel Officer', email: 'hostel.officer@svsu.ac.in', desc: 'Hostel' },
      { role: 'Sports Officer', email: 'sports.officer@svsu.ac.in', desc: 'Sports Section' },
      { role: 'Accounts Officer', email: 'accounts.officer@svsu.ac.in', desc: 'Account Section' },
    ]
  : []

export function LoginPage() {
  useDocumentTitle('Sign In')
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // Public authentication configuration from /auth/config
  const { data: authConfig, isLoading: configLoading } = useAuthConfig()

  // Password Login State
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [cooldownSeconds, setCooldownSeconds] = useState(0)
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')

  // Google OAuth State
  const googleBtnContainerRef = useRef(null)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [googleScriptError, setGoogleScriptError] = useState(false)
  const [googleCooldownSeconds, setGoogleCooldownSeconds] = useState(0)
  const [googleErrorPanel, setGoogleErrorPanel] = useState(null) // { code, message }

  // Staff Password Section Accordion State
  // Default to collapsed when Google is enabled & available; open if Google is unavailable or missing client ID
  const isGoogleAvailable = Boolean(authConfig?.google_enabled && authConfig?.google_client_id)
  const [isPasswordOpen, setIsPasswordOpen] = useState(false)

  // Automatic open of password section if Google is disabled or fails to load
  useEffect(() => {
    if (!configLoading && (!isGoogleAvailable || googleScriptError)) {
      setIsPasswordOpen(true)
    }
  }, [configLoading, isGoogleAvailable, googleScriptError])

  // Cooldown timer for password login rate limit (429)
  useEffect(() => {
    if (cooldownSeconds <= 0) return
    const timer = setInterval(() => {
      setCooldownSeconds((prev) => (prev > 1 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldownSeconds])

  // Cooldown timer for Google login rate limit (429)
  useEffect(() => {
    if (googleCooldownSeconds <= 0) return
    const timer = setInterval(() => {
      setGoogleCooldownSeconds((prev) => (prev > 1 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [googleCooldownSeconds])

  const from = location.state?.from?.pathname || null
  const noticeMessage = location.state?.notice || null

  const allowedDomainHint = authConfig?.allowed_domain_hint || 'svsu.ac.in'

  const navigateAfterLogin = useCallback(
    async (accessToken, mustChangePassword) => {
      login(accessToken, { must_change_password: Boolean(mustChangePassword) })

      if (mustChangePassword) {
        navigate('/change-password', { replace: true })
        return
      }

      // Fetch fresh profile and route to respective dashboard
      try {
        const profile = await authApi.me()
        if (profile.must_change_password) {
          navigate('/change-password', { replace: true })
          return
        }

        if (from) {
          navigate(from, { replace: true })
        } else {
          switch (profile.role) {
            case 'student':
              navigate('/student', { replace: true })
              break
            case 'dept_officer':
              navigate('/officer', { replace: true })
              break
            case 'hod':
              navigate('/hod', { replace: true })
              break
            case 'registrar_accounts':
              navigate('/registrar', { replace: true })
              break
            case 'admin':
              navigate('/admin/offices', { replace: true })
              break
            default:
              navigate('/', { replace: true })
          }
        }
      } catch {
        navigate('/', { replace: true })
      }
    },
    [login, navigate, from]
  )

  // Handle Google OAuth Credential returned by Google Identity Services
  const handleGoogleCredentialResponse = useCallback(
    async (response) => {
      if (!response?.credential) return

      setGoogleLoading(true)
      setGoogleErrorPanel(null)
      setApiError('')

      try {
        // Send credential to POST /auth/google (never stored locally)
        const data = await authApi.googleLogin(response.credential)
        toast.success('Signed in successfully with your university Google account!')
        await navigateAfterLogin(data.access_token, data.must_change_password)
      } catch (err) {
        const status = err.response?.status
        const detail = err.response?.data?.detail

        if (status === 429) {
          const retryHeader =
            err.response?.headers?.['retry-after'] || err.response?.headers?.get?.('retry-after')
          const seconds = Number(retryHeader) || 60
          const minutes = Math.max(1, Math.ceil(seconds / 60))
          setGoogleCooldownSeconds(seconds)
          setGoogleErrorPanel({
            code: 'RATE_LIMITED',
            message: `Too many sign-in attempts. Please try again in ${minutes} minute${minutes > 1 ? 's' : ''}.`,
          })
          toast.error(`Too many attempts. Please try again in ${minutes} minute${minutes > 1 ? 's' : ''}.`)
        } else if (status === 403) {
          const code = typeof detail === 'object' ? detail.code : null
          if (code === 'NOT_ELIGIBLE') {
            setGoogleErrorPanel({
              code: 'NOT_ELIGIBLE',
              message: 'Your account is not in the student list. Please contact your department office.',
            })
          } else if (code === 'ACCOUNT_DISABLED') {
            setGoogleErrorPanel({
              code: 'ACCOUNT_DISABLED',
              message: 'Your account has been deactivated. Please contact your department office or administrator.',
            })
          } else if (code === 'SUB_MISMATCH') {
            setGoogleErrorPanel({
              code: 'SUB_MISMATCH',
              message: 'Google account ID mismatch. Please sign in with the university Google account originally linked to your record.',
            })
          } else {
            setGoogleErrorPanel({
              code: 'FORBIDDEN',
              message:
                typeof detail === 'object'
                  ? detail.message
                  : detail || 'Access forbidden for this account.',
            })
          }
        } else if (status === 401) {
          setGoogleErrorPanel({
            code: 'UNAUTHORIZED',
            message:
              typeof detail === 'string'
                ? detail
                : 'Invalid or unauthorized university Google account. Please use your official university account.',
          })
        } else {
          setGoogleErrorPanel({
            code: 'ERROR',
            message:
              typeof detail === 'string'
                ? detail
                : 'Google sign-in failed. Please try again or use email and password if you are staff.',
          })
        }
      } finally {
        setGoogleLoading(false)
      }
    },
    [navigateAfterLogin]
  )

  // Lazy-load Google Identity Services script on the login page strictly when google_enabled and client ID are present
  useEffect(() => {
    if (!isGoogleAvailable) return

    const SCRIPT_ID = 'google-identity-services-script'
    let scriptElement = document.getElementById(SCRIPT_ID)

    const initGoogleButton = () => {
      if (!window.google?.accounts?.id || !googleBtnContainerRef.current) return
      try {
        window.google.accounts.id.initialize({
          client_id: authConfig.google_client_id,
          callback: handleGoogleCredentialResponse,
          auto_select: false,
          cancel_on_tap_outside: true,
        })

        // Render standard Google button inside container
        googleBtnContainerRef.current.innerHTML = ''
        window.google.accounts.id.renderButton(googleBtnContainerRef.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'rectangular',
          logo_alignment: 'left',
          width: 320,
        })
      } catch (err) {
        console.error('Failed to initialize Google button:', err)
        setGoogleScriptError(true)
        setIsPasswordOpen(true)
      }
    }

    if (window.google?.accounts?.id) {
      initGoogleButton()
      return
    }

    if (!scriptElement) {
      scriptElement = document.createElement('script')
      scriptElement.id = SCRIPT_ID
      scriptElement.src = 'https://accounts.google.com/gsi/client'
      scriptElement.async = true
      scriptElement.defer = true
      scriptElement.onload = () => {
        initGoogleButton()
      }
      scriptElement.onerror = () => {
        setGoogleScriptError(true)
        setIsPasswordOpen(true)
      }
      document.body.appendChild(scriptElement)
    } else {
      scriptElement.addEventListener('load', initGoogleButton)
      scriptElement.addEventListener('error', () => {
        setGoogleScriptError(true)
        setIsPasswordOpen(true)
      })
    }

    // Safety timeout in case a privacy blocker intercepts the script silently
    const timeout = setTimeout(() => {
      if (!window.google?.accounts?.id) {
        setGoogleScriptError(true)
        setIsPasswordOpen(true)
      }
    }, 4000)

    return () => {
      clearTimeout(timeout)
      if (scriptElement) {
        scriptElement.removeEventListener('load', initGoogleButton)
      }
    }
  }, [isGoogleAvailable, authConfig?.google_client_id, handleGoogleCredentialResponse])

  // Password validation
  const validatePasswordForm = () => {
    const errs = {}
    if (!email.trim()) {
      errs.email = 'University email is required.'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errs.email = 'Please enter a valid email address.'
    }
    if (!password) {
      errs.password = 'Password is required.'
    } else if (password.length < 6) {
      errs.password = 'Password must be at least 6 characters.'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  // Handle password form submit
  const handlePasswordSubmit = async (e) => {
    e.preventDefault()
    setApiError('')
    setGoogleErrorPanel(null)
    if (!validatePasswordForm()) return

    setLoading(true)
    const normalizedEmail = email.trim().toLowerCase()
    try {
      const data = await authApi.login(normalizedEmail, password)
      toast.success('Signed in successfully!')
      await navigateAfterLogin(data.access_token, data.must_change_password)
    } catch (err) {
      if (err.response?.status === 429) {
        const retryHeader =
          err.response?.headers?.['retry-after'] || err.response?.headers?.get?.('retry-after')
        const seconds = Number(retryHeader) || 60
        const minutes = Math.max(1, Math.ceil(seconds / 60))
        const msg = `Too many failed attempts. Please try again in ${minutes} minute${minutes > 1 ? 's' : ''}.`
        toast.error(msg)
        setApiError(msg)
        setCooldownSeconds(seconds)
      } else {
        const msg = err.response?.data?.detail || 'Incorrect email or password. Please try again.'
        toast.error(msg)
        setApiError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleQuickFill = (staffEmail) => {
    setEmail(staffEmail)
    setErrors((prev) => ({ ...prev, email: undefined }))
    setApiError('')
    setIsPasswordOpen(true)
    toast.info(`Filled email: ${staffEmail}`)
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
              Autonomous departmental clearance for Shri Vishwakarma Skill University.
            </h2>
            <p className="text-xs text-zinc-600 leading-relaxed">
              Replacing manual signature running with an automated parallel approval lifecycle.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-border shadow-2xs">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <Zap className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-zinc-900 block">Single Sign-On</span>
                <span className="text-zinc-500 leading-snug">
                  Students and staff sign in with their university Google account.
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-border shadow-2xs">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-zinc-900 block">Chairperson (HoD) Sign-off</span>
                <span className="text-zinc-500 leading-snug">
                  Official tamper-proof digital certificate with QR code verification.
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-border shadow-2xs">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <CreditCard className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-zinc-900 block">Automated Security Deposit Refund</span>
                <span className="text-zinc-500 leading-snug">
                  Direct bank credit post accounts reconciliation.
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Authentication Card */}
        <div className="lg:col-span-7 w-full max-w-md mx-auto space-y-4">
          <div className="text-center lg:hidden mb-4">
            <Link to="/" className="inline-block">
              <span className="font-heading font-extrabold text-2xl tracking-tight text-black">
                SVSU NO-DUES
              </span>
            </Link>
            <p className="text-xs text-zinc-500 mt-1">Digital University Clearance Portal</p>
          </div>

          {/* Optional notice banner (e.g. redirected from /signup) */}
          {noticeMessage && (
            <div className="p-3.5 rounded-xl border border-blue-200 bg-blue-50 text-blue-950 text-xs flex items-start gap-2.5 shadow-2xs">
              <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <p className="font-medium leading-relaxed">{noticeMessage}</p>
            </div>
          )}

          {/* Google Error / Edge Case Panels */}
          {googleErrorPanel && (
            <div
              className={`p-4 rounded-xl border text-xs space-y-1.5 shadow-2xs ${
                googleErrorPanel.code === 'NOT_ELIGIBLE'
                  ? 'border-amber-200 bg-amber-50 text-amber-950'
                  : googleErrorPanel.code === 'ACCOUNT_DISABLED'
                  ? 'border-rose-200 bg-rose-50 text-rose-950'
                  : 'border-zinc-200 bg-zinc-50 text-zinc-900'
              }`}
            >
              <div className="flex items-center gap-2 font-semibold">
                {googleErrorPanel.code === 'NOT_ELIGIBLE' && (
                  <>
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>Account Not Found On Roster</span>
                  </>
                )}
                {googleErrorPanel.code === 'ACCOUNT_DISABLED' && (
                  <>
                    <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>Account Disabled</span>
                  </>
                )}
                {googleErrorPanel.code !== 'NOT_ELIGIBLE' &&
                  googleErrorPanel.code !== 'ACCOUNT_DISABLED' && (
                    <>
                      <AlertTriangle className="w-4 h-4 text-zinc-600 shrink-0" />
                      <span>Sign-In Notice</span>
                    </>
                  )}
              </div>
              <p className="text-xs leading-relaxed font-medium">{googleErrorPanel.message}</p>
            </div>
          )}

          {/* Script Failure Notice (e.g. adblocker or privacy setting) */}
          {googleScriptError && isGoogleAvailable && (
            <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-950 text-xs space-y-1.5 shadow-2xs">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Google Sign-In Unavailable</span>
              </div>
              <p className="leading-relaxed">
                Google sign-in could not load. Staff can use email and password; students, please try another
                browser or disable tracking protection for this site.
              </p>
            </div>
          )}

          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-4">
              <CardTitle className="text-lg font-bold">Portal Sign In</CardTitle>
              <CardDescription className="text-xs">
                {isGoogleAvailable
                  ? 'Continue with your institutional Google account or enter staff credentials.'
                  : 'Enter your university email and password to access your role dashboard.'}
              </CardDescription>
            </CardHeader>

            <CardContent className="p-6 pt-0 space-y-5">
              {/* SECTION A: Primary Google Sign-In (Rendered when Google is configured) */}
              {isGoogleAvailable && !googleScriptError && (
                <div className="space-y-3 pt-1 pb-1">
                  {/* Google Button Container */}
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <div
                      ref={googleBtnContainerRef}
                      className={`w-full flex justify-center min-h-[44px] ${
                        googleCooldownSeconds > 0 || googleLoading
                          ? 'opacity-50 pointer-events-none'
                          : ''
                      }`}
                    />
                    <p className="text-[11px] text-zinc-500 font-medium text-center">
                      Use your university account (@{allowedDomainHint})
                    </p>
                  </div>

                  {googleLoading && (
                    <div className="p-2.5 text-xs bg-zinc-100 border border-zinc-200 text-zinc-800 rounded-lg text-center font-medium flex items-center justify-center gap-2">
                      <div className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin" />
                      <span>Verifying university Google account...</span>
                    </div>
                  )}

                  {googleCooldownSeconds > 0 && (
                    <div className="p-2.5 text-xs bg-amber-50 border border-amber-200 text-amber-900 rounded-lg text-center font-medium">
                      Too many attempts. Google sign-in paused for {googleCooldownSeconds}s.
                    </div>
                  )}

                  {/* Visual Divider */}
                  <div className="relative pt-2">
                    <div className="absolute inset-0 flex items-center" aria-hidden="true">
                      <div className="w-full border-t border-zinc-200" />
                    </div>
                    <div className="relative flex justify-center text-[10px] uppercase font-semibold tracking-wider">
                      <span className="bg-white px-2 text-zinc-400">or</span>
                    </div>
                  </div>
                </div>
              )}

              {/* SECTION B: Staff and Admin Password Login Form */}
              {/* When Google is enabled, rendered as a collapsible section. When Google is disabled, rendered openly. */}
              {isGoogleAvailable && !googleScriptError ? (
                <details
                  open={isPasswordOpen}
                  onToggle={(e) => setIsPasswordOpen(e.currentTarget.open)}
                  className="group rounded-xl border border-zinc-200 bg-white p-4 text-xs transition-all shadow-2xs"
                >
                  <summary className="flex items-center justify-between cursor-pointer list-none font-semibold text-xs text-zinc-700 select-none hover:text-black">
                    <span className="flex items-center gap-2">
                      <Lock className="w-3.5 h-3.5 text-zinc-500" />
                      <span>Staff and admin: sign in with email and password</span>
                    </span>
                    <ChevronDown className="w-4 h-4 text-zinc-400 transition-transform duration-200 group-open:rotate-180" />
                  </summary>

                  <div className="pt-4 border-t border-zinc-100 mt-3">
                    <form onSubmit={handlePasswordSubmit} noValidate className="space-y-4">
                      {/* Email Field */}
                      <div className="space-y-1.5">
                        <Label htmlFor="staff-email" className="text-xs font-semibold text-zinc-800">
                          Staff Email Address
                        </Label>
                        <div className="relative">
                          <Mail className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                          <Input
                            id="staff-email"
                            type="email"
                            placeholder="officer@svsu.ac.in"
                            className={`pl-9 text-sm ${
                              errors.email ? 'border-destructive ring-1 ring-destructive' : ''
                            }`}
                            value={email}
                            onChange={(e) => {
                              setEmail(e.target.value)
                              if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
                            }}
                            autoComplete="username"
                            required
                          />
                        </div>
                        {errors.email && (
                          <p className="text-[11px] text-destructive font-medium mt-0.5">
                            {errors.email}
                          </p>
                        )}
                      </div>

                      {/* Password Field */}
                      <div className="space-y-1.5">
                        <Label htmlFor="staff-password" className="text-xs font-semibold text-zinc-800">
                          Password
                        </Label>
                        <div className="relative">
                          <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                          <Input
                            id="staff-password"
                            type={showPassword ? 'text' : 'password'}
                            placeholder="••••••••"
                            className={`pl-9 pr-9 text-sm ${
                              errors.password ? 'border-destructive ring-1 ring-destructive' : ''
                            }`}
                            value={password}
                            onChange={(e) => {
                              setPassword(e.target.value)
                              if (errors.password)
                                setErrors((prev) => ({ ...prev, password: undefined }))
                            }}
                            autoComplete="current-password"
                            required
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-2.5 text-zinc-400 hover:text-zinc-700 transition-colors"
                            tabIndex={-1}
                            aria-label="Toggle password visibility"
                          >
                            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                        {errors.password && (
                          <p className="text-[11px] text-destructive font-medium mt-0.5">
                            {errors.password}
                          </p>
                        )}
                      </div>

                      {/* Password API Error Display */}
                      {apiError && (
                        <div className="p-3 text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-md font-medium">
                          {apiError}
                        </div>
                      )}

                      {/* Submit Action */}
                      <Button
                        type="submit"
                        className="w-full bg-primary text-primary-foreground hover:bg-zinc-800 font-semibold text-sm h-10 shadow-xs"
                        disabled={loading || cooldownSeconds > 0}
                      >
                        {cooldownSeconds > 0
                          ? `Rate limit active (wait ${cooldownSeconds}s)`
                          : loading
                          ? 'Authenticating...'
                          : 'Sign In with Password'}
                        {!loading && cooldownSeconds <= 0 && <ArrowRight className="ml-2 h-4 w-4" />}
                      </Button>
                    </form>
                  </div>
                </details>
              ) : (
                /* When Google is disabled or unavailable, render password form directly */
                <form onSubmit={handlePasswordSubmit} noValidate className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="fallback-email" className="text-xs font-semibold text-zinc-800">
                      Institutional Email Address
                    </Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                      <Input
                        id="fallback-email"
                        type="email"
                        placeholder="user@svsu.ac.in"
                        className={`pl-9 text-sm ${
                          errors.email ? 'border-destructive ring-1 ring-destructive' : ''
                        }`}
                        value={email}
                        onChange={(e) => {
                          setEmail(e.target.value)
                          if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
                        }}
                        autoComplete="username"
                        required
                      />
                    </div>
                    {errors.email && (
                      <p className="text-[11px] text-destructive font-medium mt-0.5">{errors.email}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="fallback-password" className="text-xs font-semibold text-zinc-800">
                      Password
                    </Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                      <Input
                        id="fallback-password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="••••••••"
                        className={`pl-9 pr-9 text-sm ${
                          errors.password ? 'border-destructive ring-1 ring-destructive' : ''
                        }`}
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value)
                          if (errors.password)
                            setErrors((prev) => ({ ...prev, password: undefined }))
                        }}
                        autoComplete="current-password"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-2.5 text-zinc-400 hover:text-zinc-700 transition-colors"
                        tabIndex={-1}
                        aria-label="Toggle password visibility"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {errors.password && (
                      <p className="text-[11px] text-destructive font-medium mt-0.5">
                        {errors.password}
                      </p>
                    )}
                  </div>

                  {apiError && (
                    <div className="p-3 text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-md font-medium">
                      {apiError}
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full bg-primary text-primary-foreground hover:bg-zinc-800 font-semibold text-sm h-10 mt-2 shadow-xs"
                    disabled={loading || cooldownSeconds > 0}
                  >
                    {cooldownSeconds > 0
                      ? `Rate limit active (wait ${cooldownSeconds}s)`
                      : loading
                      ? 'Authenticating...'
                      : 'Sign In'}
                    {!loading && cooldownSeconds <= 0 && <ArrowRight className="ml-2 h-4 w-4" />}
                  </Button>
                </form>
              )}
            </CardContent>

            <CardFooter className="p-6 pt-0 border-t border-zinc-100 flex flex-col items-center justify-center gap-2">
              {authConfig?.otp_signup_enabled ? (
                <p className="text-xs text-zinc-500 text-center mt-3">
                  New student?{' '}
                  <Link
                    to="/signup"
                    className="font-semibold text-black hover:underline underline-offset-2"
                  >
                    Register with Roster OTP
                  </Link>
                </p>
              ) : (
                <p className="text-xs text-zinc-500 text-center mt-3">
                  Students sign in with their university Google account. No separate registration is required.
                </p>
              )}
            </CardFooter>
          </Card>

          {/* Collapsible Quick Sign-in Accounts (Development Only) */}
          {import.meta.env.DEV && DEV_STAFF_ACCOUNTS.length > 0 && (
            <details className="group rounded-xl border border-zinc-200 bg-white p-4 text-xs transition-all shadow-2xs">
              <summary className="flex items-center justify-between cursor-pointer list-none font-semibold text-zinc-800 select-none">
                <span className="flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-zinc-600" />
                  <span>Quick sign-in (development only)</span> {/* wording-ok */}
                </span>
                <ChevronDown className="w-4 h-4 text-zinc-400 transition-transform duration-200 group-open:rotate-180" />
              </summary>

              <div className="pt-3 space-y-2 border-t border-zinc-100 mt-3">
                <p className="text-[11px] text-zinc-500">
                  Click any staff role to pre-fill their official university email in the password form:
                </p>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {DEV_STAFF_ACCOUNTS.map((acc) => (
                    <button
                      key={acc.email}
                      type="button"
                      onClick={() => handleQuickFill(acc.email)}
                      className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-md bg-zinc-50 border border-zinc-200 hover:border-black hover:bg-zinc-100 text-zinc-800 transition-colors"
                    >
                      <span className="font-semibold">{acc.role}</span>
                      <span className="text-zinc-400 font-mono text-[10px]">({acc.desc})</span>
                    </button>
                  ))}
                </div>
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  )
}

export default LoginPage
