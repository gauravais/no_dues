import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { authApi } from '@/api/auth'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { toast } from 'sonner'
import {
  KeyRound,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'

export function ChangePasswordPage() {
  useDocumentTitle('Change Password')
  const { user, mustChangePassword, refreshProfile } = useAuth()
  const navigate = useNavigate()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})

  // Live checklist criteria
  const isMinLength = newPassword.length >= 10
  const isDifferent = Boolean(
    newPassword && currentPassword && newPassword !== currentPassword
  )
  const isMatching = Boolean(
    newPassword && confirmPassword && newPassword === confirmPassword
  )

  const validate = () => {
    const errs = {}
    if (!currentPassword) {
      errs.currentPassword = 'Enter your current password.'
    }
    if (!newPassword) {
      errs.newPassword = 'Enter a new password.'
    } else if (newPassword.length < 10) {
      errs.newPassword = 'New password must be at least 10 characters.'
    } else if (currentPassword && newPassword === currentPassword) {
      errs.newPassword = 'New password must be different from current password.'
    }
    if (!confirmPassword) {
      errs.confirmPassword = 'Confirm your new password.'
    } else if (newPassword !== confirmPassword) {
      errs.confirmPassword = 'Passwords do not match.'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    setErrors({})

    try {
      await authApi.changePassword(currentPassword, newPassword)
      toast.success('Password changed successfully!')
      await refreshProfile()

      // Redirect to the role's default dashboard
      switch (user?.role) {
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
          break
      }
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail

      if (status === 422 && Array.isArray(detail)) {
        // Backend validation errors
        const mappedErrors = {}
        detail.forEach((item) => {
          const field = item.loc?.[item.loc.length - 1]
          if (field === 'current_password') {
            mappedErrors.currentPassword = item.msg
          } else if (field === 'new_password') {
            mappedErrors.newPassword = item.msg
          }
        })
        setErrors(mappedErrors)
        toast.error('Please fix the errors in the form.')
      } else if (status === 400 && typeof detail === 'string') {
        const lower = detail.toLowerCase()
        if (lower.includes('current') || lower.includes('incorrect')) {
          setErrors({ currentPassword: detail })
        } else if (lower.includes('different') || lower.includes('10')) {
          setErrors({ newPassword: detail })
        } else {
          toast.error(detail)
        }
      } else {
        toast.error(
          typeof detail === 'string'
            ? detail
            : 'Failed to update password. Please check your inputs.'
        )
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell>
      <div className="max-w-xl mx-auto py-6 space-y-6">
        {/* Notice if forced by admin */}
        {mustChangePassword && (
          <Alert className="bg-amber-50 border-amber-200 text-amber-900 shadow-2xs">
            <AlertTriangle className="h-4 w-4 text-amber-800" />
            <AlertTitle className="text-xs font-semibold">
              Temporary Password Update Required
            </AlertTitle>
            <AlertDescription className="text-xs text-amber-800 mt-1 leading-relaxed">
              An administrator set a temporary password. Choose your own to continue.
            </AlertDescription>
          </Alert>
        )}

        <Card className="border-border bg-white shadow-card">
          <CardHeader className="p-6 pb-4 border-b border-zinc-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <KeyRound className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-lg font-bold">
                  {mustChangePassword ? 'Set Your New Password' : 'Change Account Password'}
                </CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  Update your credentials for secure access across SVSU No-Dues.
                </CardDescription>
              </div>
            </div>
          </CardHeader>

          <form onSubmit={handleSubmit} noValidate>
            <CardContent className="p-6 space-y-5">
              {/* Current Password */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="currentPassword"
                  className="text-xs font-semibold text-zinc-800"
                >
                  Current Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                  <Input
                    id="currentPassword"
                    type={showCurrent ? 'text' : 'password'}
                    placeholder="Enter current or temporary password"
                    className={`pl-9 pr-10 text-sm ${
                      errors.currentPassword
                        ? 'border-destructive ring-1 ring-destructive'
                        : ''
                    }`}
                    value={currentPassword}
                    onChange={(e) => {
                      setCurrentPassword(e.target.value)
                      if (errors.currentPassword) {
                        setErrors((prev) => ({ ...prev, currentPassword: undefined }))
                      }
                    }}
                    autoFocus
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrent(!showCurrent)}
                    className="absolute right-3 top-2.5 text-zinc-400 hover:text-zinc-600 focus:outline-hidden"
                    tabIndex={-1}
                    aria-label={showCurrent ? 'Hide password' : 'Show password'}
                  >
                    {showCurrent ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {errors.currentPassword && (
                  <p className="text-[11px] text-destructive font-medium mt-0.5">
                    {errors.currentPassword}
                  </p>
                )}
              </div>

              {/* New Password */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="newPassword"
                  className="text-xs font-semibold text-zinc-800"
                >
                  New Password (minimum 10 characters)
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                  <Input
                    id="newPassword"
                    type={showNew ? 'text' : 'password'}
                    placeholder="Choose a strong new password"
                    className={`pl-9 pr-10 text-sm ${
                      errors.newPassword
                        ? 'border-destructive ring-1 ring-destructive'
                        : ''
                    }`}
                    value={newPassword}
                    onChange={(e) => {
                      setNewPassword(e.target.value)
                      if (errors.newPassword) {
                        setErrors((prev) => ({ ...prev, newPassword: undefined }))
                      }
                    }}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowNew(!showNew)}
                    className="absolute right-3 top-2.5 text-zinc-400 hover:text-zinc-600 focus:outline-hidden"
                    tabIndex={-1}
                    aria-label={showNew ? 'Hide password' : 'Show password'}
                  >
                    {showNew ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {errors.newPassword && (
                  <p className="text-[11px] text-destructive font-medium mt-0.5">
                    {errors.newPassword}
                  </p>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="confirmPassword"
                  className="text-xs font-semibold text-zinc-800"
                >
                  Confirm New Password
                </Label>
                <div className="relative">
                  <ShieldCheck className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                  <Input
                    id="confirmPassword"
                    type={showConfirm ? 'text' : 'password'}
                    placeholder="Re-enter your new password"
                    className={`pl-9 pr-10 text-sm ${
                      errors.confirmPassword
                        ? 'border-destructive ring-1 ring-destructive'
                        : ''
                    }`}
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value)
                      if (errors.confirmPassword) {
                        setErrors((prev) => ({ ...prev, confirmPassword: undefined }))
                      }
                    }}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-2.5 text-zinc-400 hover:text-zinc-600 focus:outline-hidden"
                    tabIndex={-1}
                    aria-label={showConfirm ? 'Hide password' : 'Show password'}
                  >
                    {showConfirm ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="text-[11px] text-destructive font-medium mt-0.5">
                    {errors.confirmPassword}
                  </p>
                )}
              </div>

              {/* Live Checklist */}
              <div className="rounded-lg border border-zinc-200 bg-zinc-50/70 p-3.5 space-y-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-600 block">
                  Password Requirements
                </span>
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    {isMinLength ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    )}
                    <span className={isMinLength ? 'text-zinc-900 font-medium' : 'text-zinc-500'}>
                      At least 10 characters long ({newPassword.length} / 10)
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {isDifferent ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    )}
                    <span className={isDifferent ? 'text-zinc-900 font-medium' : 'text-zinc-500'}>
                      Different from your current password
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {isMatching ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    )}
                    <span className={isMatching ? 'text-zinc-900 font-medium' : 'text-zinc-500'}>
                      Matches confirm password
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>

            <CardFooter className="p-6 pt-0 border-t border-zinc-100 flex items-center justify-between gap-4">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-xs text-zinc-500 hover:text-zinc-900"
                onClick={() => navigate(-1)}
                disabled={loading || mustChangePassword}
              >
                Cancel
              </Button>

              <Button
                type="submit"
                className="bg-primary text-primary-foreground hover:bg-zinc-800 font-semibold text-xs h-9 px-4 shadow-xs"
                disabled={loading || !isMinLength || !isDifferent || !isMatching}
              >
                {loading ? 'Updating Password...' : 'Save New Password'}
                {!loading && <ArrowRight className="ml-1.5 h-3.5 w-3.5" />}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </AppShell>
  )
}

export default ChangePasswordPage
