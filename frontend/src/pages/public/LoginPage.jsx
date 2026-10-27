import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { authApi } from '@/api/auth'
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
} from 'lucide-react'

const DEMO_ACCOUNTS = [
  { role: 'Student (Day Scholar)', email: 'aarav.sharma@example.edu', desc: 'B.Tech CE' },
  { role: 'Student (Hosteller)', email: 'priya.sharma@example.edu', desc: 'B.Tech CSE' },
  { role: 'Student (Verified Demo)', email: 'aman.gupta@example.edu', desc: 'DEMO2026006' },
  { role: 'Chairperson CS/IT', email: 'hod.csit@example.edu', desc: 'HoD' },
  { role: 'Library Officer', email: 'library.officer@example.edu', desc: 'Officer' },
  { role: 'Hostel Warden', email: 'hostel.warden@example.edu', desc: 'Hostel' },
  { role: 'Accounts / Registrar', email: 'registrar.accounts@example.edu', desc: 'Refunds' },
  { role: 'Administrator', email: 'admin@example.edu', desc: 'System Admin' },
]

export function LoginPage() {
  useDocumentTitle('Sign In')
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})

  const from = location.state?.from?.pathname || null

  const validate = () => {
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

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    try {
      const data = await authApi.login(email.trim(), password)
      login(data.access_token)
      toast.success('Signed in successfully!')

      // Direct to respective role dashboard
      const profile = await authApi.me()

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
            navigate('/admin', { replace: true })
            break
          default:
            navigate('/', { replace: true })
        }
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Invalid email or password. Please try again.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleQuickFill = (demoEmail) => {
    setEmail(demoEmail)
    setErrors((prev) => ({ ...prev, email: undefined }))
    toast.info(`Filled email: ${demoEmail}`)
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
                <span className="font-semibold text-zinc-900 block">Parallel Department Reviews</span>
                <span className="text-zinc-500 leading-snug">All 10 departments verify records concurrently.</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-border shadow-2xs">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-zinc-900 block">Chairperson (HoD) Sign-off</span>
                <span className="text-zinc-500 leading-snug">Official tamper-proof digital certificate with QR code.</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-border shadow-2xs">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <CreditCard className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-semibold text-zinc-900 block">Automated Security Deposit Refund</span>
                <span className="text-zinc-500 leading-snug">Direct bank credit post accounts reconciliation.</span>
              </div>
            </div>
          </div>

          <div className="pt-2 text-[11px] text-zinc-400">
            Student capstone project • Synthetic demo data
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

          <Card className="border-border bg-white shadow-card">
            <form onSubmit={handleSubmit} noValidate>
              <CardHeader className="p-6 pb-4">
                <CardTitle className="text-lg font-bold">Portal Sign In</CardTitle>
                <CardDescription className="text-xs">
                  Enter your university email and password to access your role dashboard.
                </CardDescription>
              </CardHeader>

              <CardContent className="p-6 pt-0 space-y-4">
                {/* Email Field */}
                <div className="space-y-1.5">
                  <Label htmlFor="email" className="text-xs font-semibold text-zinc-800">
                    Institutional Email Address
                  </Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                    <Input
                      id="email"
                      type="email"
                      placeholder="student@example.edu"
                      className={`pl-9 text-sm ${errors.email ? 'border-destructive ring-1 ring-destructive' : ''}`}
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

                {/* Password Field */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password" className="text-xs font-semibold text-zinc-800">
                      Password
                    </Label>
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      className={`pl-9 pr-9 text-sm ${errors.password ? 'border-destructive ring-1 ring-destructive' : ''}`}
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value)
                        if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }))
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
                    <p className="text-[11px] text-destructive font-medium mt-0.5">{errors.password}</p>
                  )}
                </div>

                {/* Submit Action */}
                <Button
                  type="submit"
                  className="w-full bg-primary text-primary-foreground hover:bg-zinc-800 font-semibold text-sm h-10 mt-2 shadow-xs"
                  disabled={loading}
                >
                  {loading ? 'Authenticating Credentials...' : 'Sign In'}
                  {!loading && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>
              </CardContent>

              <CardFooter className="p-6 pt-0 border-t border-zinc-100 flex flex-col items-center justify-center gap-2">
                <p className="text-xs text-zinc-500 text-center mt-3">
                  New student?{' '}
                  <Link to="/signup" className="font-semibold text-black hover:underline underline-offset-2">
                    Register with Roster OTP
                  </Link>
                </p>
              </CardFooter>
            </form>
          </Card>

          {/* Collapsible Demo Accounts (Development Only) */}
          <details className="group rounded-xl border border-zinc-200 bg-white p-4 text-xs transition-all shadow-2xs">
            <summary className="flex items-center justify-between cursor-pointer list-none font-semibold text-zinc-800 select-none">
              <span className="flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-zinc-600" />
                <span>Demo accounts (development only)</span>
              </span>
              <ChevronDown className="w-4 h-4 text-zinc-400 transition-transform duration-200 group-open:rotate-180" />
            </summary>

            <div className="pt-3 space-y-2 border-t border-zinc-100 mt-3">
              <p className="text-[11px] text-zinc-500">
                Click any role to pre-fill their official demo email (seeded password: <code className="font-mono text-zinc-800 font-semibold">SeedPass@123</code>):
              </p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {DEMO_ACCOUNTS.map((acc) => (
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
        </div>
      </div>
    </div>
  )
}

export default LoginPage
