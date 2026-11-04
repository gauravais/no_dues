import { Link } from 'react-router-dom'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AppShell } from '@/components/AppShell'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  HelpCircle,
  ShieldAlert,
  GraduationCap,
  FileCheck2,
  CreditCard,
  Mail,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react'

export function HelpPage() {
  useDocumentTitle('Help & Clearance Guide')
  const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL

  const clearanceSteps = [
    {
      step: '01',
      title: 'University Google Sign-In',
      description:
        'You sign in with your university Google account (@svsu.ac.in). Your student eligibility is automatically verified against the official university roster.',
    },
    {
      step: '02',
      title: 'Submit Application & Declarations',
      description:
        'Declare whether you were a hostel resident, select your laboratory and workshop subjects, provide bank details for security deposit return, and submit your clearance application.',
    },
    {
      step: '03',
      title: 'Parallel Departmental Review',
      description:
        'Your request is concurrently routed to all designated offices (Academic Department, Central Library, Hostel Office, Sports Section, and Assigned Laboratories). Each officer reviews records independently.',
    },
    {
      step: '04',
      title: 'Chairperson (HoD) Clearance',
      description:
        'Once every department has cleared your account, your application advances to your academic department Chairperson (HoD) for final administrative review and endorsement.',
    },
    {
      step: '05',
      title: 'Certificate Issuance & Deposit Refund',
      description:
        'Instantly download your official digital No-Dues Certificate with a cryptographically verifiable QR code. The Accounts & Finance branch verifies your deposit records for refund credit.',
    },
  ]

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto py-6 space-y-8">
        {/* Header */}
        <div className="space-y-2 border-b border-zinc-200 pb-6">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-800 text-xs font-semibold mb-1">
            <HelpCircle className="w-3.5 h-3.5" />
            Clearance Guide & Support
          </div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight text-zinc-900">
            SVSU No-Dues Clearance Guide
          </h1>
          <p className="text-sm text-zinc-600 leading-relaxed max-w-2xl">
            Everything you need to know about the digital clearance procedure for graduating and exiting students at Shri Vishwakarma Skill University.
          </p>
        </div>

        {/* Security Warning Notice */}
        <Alert className="bg-amber-50 border-amber-200 text-amber-900 shadow-2xs">
          <ShieldAlert className="h-4 w-4 text-amber-800" />
          <AlertTitle className="text-xs font-semibold uppercase tracking-wider">
            Important Security Notice
          </AlertTitle>
          <AlertDescription className="text-xs text-amber-950 mt-1 leading-relaxed font-medium">
            You sign in with your university Google account. University officers and administrators will never ask for your account credentials or verification codes.
          </AlertDescription>
        </Alert>

        {/* What System Does */}
        <Card className="border-border bg-white shadow-card">
          <CardHeader className="p-6 pb-4 border-b border-zinc-100">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-base font-bold text-zinc-900">
                  What is the No-Dues Clearance System?
                </CardTitle>
                <CardDescription className="text-xs mt-0.5 text-zinc-500">
                  Official online clearance platform for Shri Vishwakarma Skill University.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-3 text-xs sm:text-sm text-zinc-700 leading-relaxed">
            <p>
              The <strong>SVSU No-Dues Clearance System</strong> eliminates physical clearance forms and multi-office walking queues by digitizing the student exit and graduation clearance workflow.
            </p>
            <p>
              Through this portal, all clearance requirements are routed in parallel to departmental officers across academic faculties, specialized laboratories, workshops, the central library, hostel management, sports facilities, and the accounts department.
            </p>
          </CardContent>
        </Card>

        {/* 5-Step Clearance Workflow */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-lg font-bold text-zinc-900">
              Clearance Steps for Students
            </h2>
            <span className="text-xs text-zinc-500 font-medium">5-Stage Sequential Process</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {clearanceSteps.map((item) => (
              <Card
                key={item.step}
                className="border-border bg-white shadow-card transition-shadow hover:shadow-md"
              >
                <CardContent className="p-5 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-md bg-zinc-100 text-zinc-700 border border-zinc-200">
                      STEP {item.step}
                    </span>
                    <CheckCircle2 className="w-4 h-4 text-zinc-400" />
                  </div>
                  <h3 className="font-semibold text-sm text-zinc-900 pt-1">
                    {item.title}
                  </h3>
                  <p className="text-xs text-zinc-600 leading-relaxed">
                    {item.description}
                  </p>
                </CardContent>
              </Card>
            ))}

            {/* Quick action card */}
            <Card className="border-dashed border-zinc-300 bg-zinc-50/50 flex flex-col justify-center items-center p-6 text-center">
              <FileCheck2 className="w-8 h-8 text-zinc-400 mb-2" />
              <h3 className="font-semibold text-sm text-zinc-900">
                Ready to begin clearance?
              </h3>
              <p className="text-xs text-zinc-500 mt-1 mb-4 max-w-xs">
                Sign in with your university Google account to initiate clearance.
              </p>
              <div className="flex items-center justify-center gap-3">
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center text-xs font-semibold h-8 px-4 rounded-md bg-zinc-900 text-white hover:bg-zinc-800 transition-colors"
                >
                  Student Sign In
                </Link>
              </div>
            </Card>
          </div>
        </div>

        {/* Security Deposit & Public Verification Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-3">
              <div className="flex items-center gap-2.5">
                <CreditCard className="w-4 h-4 text-zinc-700" />
                <CardTitle className="text-sm font-bold text-zinc-900">
                  Security Deposit Refund Policy
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-6 pt-0 text-xs text-zinc-600 leading-relaxed space-y-2">
              <p>
                Refundable institutional security deposits are processed directly to the bank account registered during your clearance application.
              </p>
              <p>
                Once all offices approve clearance, the Registrar / Accounts Branch verifies the final deposit ledger, applies any university approved deductions, and records the electronic transfer reference.
              </p>
            </CardContent>
          </Card>

          <Card className="border-border bg-white shadow-card">
            <CardHeader className="p-6 pb-3">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-4 h-4 text-zinc-700" />
                <CardTitle className="text-sm font-bold text-zinc-900">
                  Certificate Authenticity Verification
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-6 pt-0 text-xs text-zinc-600 leading-relaxed space-y-2">
              <p>
                Every No-Dues Certificate issued by SVSU features a secure 32-character cryptographic verification code and QR code.
              </p>
              <p>
                External employers, academic institutions, and administrative branches can verify genuine certificates at any time via the{' '}
                <Link to="/verify" className="font-semibold text-zinc-900 underline underline-offset-2">
                  Public Certificate Verification Portal
                </Link>.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Technical Support / Contact Info */}
        {supportEmail && (
          <div className="p-5 rounded-xl border border-zinc-200 bg-zinc-50 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-white border border-zinc-200 flex items-center justify-center text-zinc-700 shrink-0">
                <Mail className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-semibold text-zinc-900 block">
                  Need Help or Assistance?
                </span>
                <span className="text-xs text-zinc-600">
                  For clearance inquiries or technical support, contact the administrative helpdesk at{' '}
                  <a
                    href={`mailto:${supportEmail}`}
                    className="font-medium text-zinc-900 underline underline-offset-2"
                  >
                    {supportEmail}
                  </a>
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}

export default HelpPage
