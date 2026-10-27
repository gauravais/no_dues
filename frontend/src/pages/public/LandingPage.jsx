import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StatusBadge } from '@/components/StatusBadge'
import {
  ArrowRight,
  ShieldCheck,
  Zap,
  CreditCard,
  QrCode,
  CheckCircle2,
  AlertTriangle,
  FileCheck2,
  ChevronRight,
} from 'lucide-react'

const DEPARTMENTS_MARQUEE = [
  'Skill Faculty of Engineering & Technology',
  'Skill Department of CS/IT',
  'Central University Library',
  'Sports & Gymnasium Section',
  'Hostel Office (Boys & Girls)',
  'Robotics & Automation Lab',
  'Electronics & IoT Workshop',
  'Dean Student Welfare Section',
  'Registrar & Accounts Office',
]

const WORKFLOW_STEPS = [
  {
    step: '01',
    title: 'Bank Verification',
    desc: 'Verify institutional identity with Roster OTP and register bank details. Security deposits are returned directly to this account.',
    icon: CreditCard,
  },
  {
    step: '02',
    title: 'Parallel Reviews',
    desc: 'Clearance requests dispatch to Library, Sports, Hostel, Assigned Labs, and Academic offices at the exact same moment.',
    icon: Zap,
  },
  {
    step: '03',
    title: 'Chairperson Review',
    desc: 'Once every department approves, the Academic Chairperson (HoD) verifies the dossier and generates an official UUID certificate.',
    icon: ShieldCheck,
  },
  {
    step: '04',
    title: 'Refund Disbursed',
    desc: 'Accounts & Registrar verify eligible security deposit deductions and record the bank UTR/NEFT payment reference.',
    icon: FileCheck2,
  },
]

// Sample preview departments for the in-code product visual
const SAMPLE_DEPARTMENTS = [
  { name: 'Library', status: 'APPROVED', remarks: 'All books returned' },
  { name: 'Sports Section', status: 'APPROVED', remarks: 'Kit returned' },
  { name: 'Computer Lab / Centre', status: 'APPROVED', remarks: 'Equipments verified' },
  { name: 'General Branch', status: 'APPROVED', remarks: 'No transport dues' },
  { name: 'Hostel Office', status: 'APPROVED', remarks: 'Room vacated' },
  { name: 'Dean Student Welfare', status: 'APPROVED', remarks: 'Cleared' },
  { name: 'N.S.S. Section', status: 'APPROVED', remarks: 'Cleared' },
  { name: 'R&S Branch', status: 'APPROVED', remarks: 'Documents verified' },
  { name: 'Skill Dept of CS/IT', status: 'PENDING', remarks: 'Under faculty review' },
  { name: 'Account Section', status: 'REJECTED', remarks: 'Lab breakage fine: Rs. 150' },
]

export function LandingPage() {
  useDocumentTitle('Official Clearance Portal')
  const heroRef = useRef(null)
  const cursorRef = useRef(null)
  const [hasFinePointer, setHasFinePointer] = useState(false)

  // 1. Detect fine pointer (mouse) vs touch, and check prefers-reduced-motion
  useEffect(() => {
    const isFine = window.matchMedia('(pointer: fine)').matches
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    setHasFinePointer(isFine && !prefersReducedMotion)

    // Lazy load GSAP & Lenis strictly on this route when reduced motion is NOT requested
    if (!prefersReducedMotion) {
      let lenisInstance = null

      Promise.all([import('lenis'), import('gsap')]).then(([LenisModule, gsapModule]) => {
        const Lenis = LenisModule.default || LenisModule
        const gsap = gsapModule.gsap || gsapModule.default

        lenisInstance = new Lenis({
          duration: 1.0,
          smoothWheel: true,
        })

        function raf(time) {
          lenisInstance?.raf(time)
          requestAnimationFrame(raf)
        }
        requestAnimationFrame(raf)

        if (heroRef.current) {
          gsap.fromTo(
            heroRef.current.querySelectorAll('.reveal-text'),
            { opacity: 0, y: 20 },
            { opacity: 1, y: 0, duration: 0.7, stagger: 0.12, ease: 'power2.out', clearProps: 'transform' }
          )
        }
      }).catch(() => {
        // Fallback gracefully without animations
      })

      return () => {
        if (lenisInstance) {
          lenisInstance.destroy()
        }
      }
    }
  }, [])

  // 2. Custom Mix-Blend-Mode Cursor for fine pointers (disabled over inputs/buttons)
  useEffect(() => {
    if (!hasFinePointer) return

    const handleMouseMove = (e) => {
      if (!cursorRef.current) return
      cursorRef.current.style.transform = `translate3d(${e.clientX - 10}px, ${e.clientY - 10}px, 0)`

      const target = e.target
      const isInput =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'BUTTON' ||
        target.closest('button') ||
        target.closest('a')

      cursorRef.current.style.opacity = isInput ? '0' : '1'
    }

    window.addEventListener('mousemove', handleMouseMove, { passive: true })
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [hasFinePointer])

  return (
    <div className="min-h-screen bg-white text-zinc-950 font-sans selection:bg-zinc-900 selection:text-white">
      {/* Custom Mix-Blend Cursor (pointer: fine only, never over inputs) */}
      {hasFinePointer && (
        <div
          ref={cursorRef}
          className="pointer-events-none fixed top-0 left-0 z-50 h-5 w-5 rounded-full bg-black mix-blend-difference transition-opacity duration-150 ease-out"
          style={{ opacity: 0 }}
        />
      )}

      {/* Sticky Navigation Bar with Frosted Glass Blur */}
      <header className="sticky top-0 z-40 w-full border-b border-border bg-white/90 backdrop-blur-md transition-all">
        <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 group">
            <span className="font-heading font-extrabold text-lg sm:text-xl tracking-tight text-black transition-opacity group-hover:opacity-80">
              SVSU NO-DUES
            </span>
            <Badge variant="outline" className="hidden sm:inline-flex text-[10px] font-medium py-0 px-1.5 border-zinc-200 text-zinc-500 bg-zinc-50">
              DIGITAL PORTAL
            </Badge>
          </Link>

          <nav className="flex items-center gap-2 sm:gap-3">
            <Link
              to="/verify"
              className="text-xs sm:text-sm font-medium text-zinc-600 hover:text-black px-2.5 py-1.5 rounded-md transition-colors"
            >
              Verify Certificate
            </Link>
            <Button asChild variant="outline" size="sm" className="text-xs">
              <Link to="/login">Sign In</Link>
            </Button>
            <Button
              asChild
              size="sm"
              className="text-xs bg-primary text-primary-foreground hover:bg-zinc-800"
            >
              <Link to="/signup">Student Sign Up</Link>
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section
        ref={heroRef}
        className="relative overflow-hidden pt-16 pb-20 md:pt-24 md:pb-28 border-b border-border bg-gradient-to-b from-zinc-50/50 to-white"
      >
        <div className="container mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 text-center relative z-10">
          {/* Eyebrow Pill */}
          <div className="reveal-text inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-white shadow-2xs text-xs font-medium text-zinc-800 mb-6">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Digital Security Deposit Refund & Clearance System</span>
          </div>

          {/* Main Headline */}
          <h1 className="reveal-text font-heading text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-black leading-[1.08] mb-6">
            Autonomous university clearance.
            <br />
            <span className="text-zinc-400 font-bold">Zero paper forms.</span>
          </h1>

          {/* Subheading */}
          <p className="reveal-text text-base sm:text-lg text-zinc-600 max-w-2xl mx-auto mb-8 leading-relaxed font-normal">
            A parallel departmental clearance workflow for Shri Vishwakarma Skill University.
            Students apply once; all departments verify simultaneously; the Chairperson signs off; and security deposits are refunded automatically.
          </p>

          {/* Dual CTAs with Strict Hierarchy */}
          <div className="reveal-text flex flex-col sm:flex-row items-center justify-center gap-3 mb-16">
            <Button
              asChild
              size="lg"
              className="bg-primary text-primary-foreground hover:bg-zinc-800 font-semibold h-11 px-6 rounded-lg gap-2 shadow-xs w-full sm:w-auto text-sm"
            >
              <Link to="/signup">
                Apply for Clearance <ArrowRight className="w-4 h-4" />
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              size="lg"
              className="text-sm font-medium h-11 px-6 rounded-lg border-border hover:bg-zinc-50 w-full sm:w-auto"
            >
              <Link to="/login">Portal Login</Link>
            </Button>
          </div>

          {/* In-Code Product Visual (Stylized Clearance Dossier Card with 10 Parallel Departments) */}
          <div className="reveal-text mx-auto max-w-4xl text-left">
            <div className="rounded-2xl border border-border bg-white p-4 sm:p-6 shadow-card ring-1 ring-zinc-900/5 transition-all">
              {/* Card Topbar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-border gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-black text-white flex items-center justify-center font-heading font-bold text-sm">
                    AG
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-heading text-sm font-bold text-zinc-950">
                        Aman Gupta
                      </span>
                      <span className="text-xs font-mono text-zinc-500">
                        (DEMO2026006)
                      </span>
                    </div>
                    <span className="text-xs text-zinc-500 block">
                      B.Tech Computer Science & Engineering • Skill Faculty of Engineering & Technology
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="bg-amber-50 text-amber-900 border-amber-200 text-xs py-0.5">
                    Sample Preview
                  </Badge>
                  <StatusBadge status="ACTION_NEEDED" size="sm" />
                </div>
              </div>

              {/* Progress Bar & Counter */}
              <div className="py-4 space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-zinc-700">Departmental Clearances Dispatched</span>
                  <span className="font-mono font-semibold text-zinc-900">8 of 10 Approved (80%)</span>
                </div>
                <div className="h-2 w-full bg-zinc-100 rounded-full overflow-hidden">
                  <div className="h-full bg-black rounded-full transition-all" style={{ width: '80%' }} />
                </div>
              </div>

              {/* Parallel Department Reviews Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5 pt-2">
                {SAMPLE_DEPARTMENTS.map((dept, i) => (
                  <div
                    key={i}
                    className={`rounded-lg p-2.5 border text-xs flex flex-col justify-between transition-colors ${
                      dept.status === 'APPROVED'
                        ? 'bg-zinc-50/50 border-zinc-200'
                        : dept.status === 'REJECTED'
                        ? 'bg-rose-50/80 border-rose-200'
                        : 'bg-white border-zinc-200'
                    }`}
                  >
                    <div>
                      <div className="font-semibold text-zinc-900 text-[11px] leading-tight mb-1 truncate">
                        {dept.name}
                      </div>
                      <div className="text-[10px] text-zinc-500 line-clamp-1">
                        {dept.remarks}
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <StatusBadge status={dept.status} size="sm" />
                    </div>
                  </div>
                ))}
              </div>

              {/* Visual Action Callout */}
              <div className="mt-4 pt-3 border-t border-zinc-100 flex flex-col sm:flex-row items-center justify-between text-xs text-zinc-500 gap-2">
                <span className="flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                  <span>1 Department flagged pending due. Student resubmits only to Account Section.</span>
                </span>
                <span className="font-mono text-[11px] text-zinc-400">
                  Real-time status updates every 30s
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Infinite Department Marquee Ticker */}
      <section className="border-b border-border bg-zinc-50/70 py-4 overflow-hidden">
        <div className="flex w-max animate-marquee space-x-8">
          {[...DEPARTMENTS_MARQUEE, ...DEPARTMENTS_MARQUEE].map((dept, index) => (
            <div
              key={index}
              className="flex items-center gap-3 text-xs font-semibold text-zinc-600 uppercase tracking-widest shrink-0"
            >
              <span>{dept}</span>
              <span className="text-zinc-300">•</span>
            </div>
          ))}
        </div>
      </section>

      {/* "How It Works" Section with Connected Visual Progression */}
      <section className="py-20 md:py-24 bg-white border-b border-border">
        <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight text-zinc-950 mb-3">
              How the clearance lifecycle functions
            </h2>
            <p className="text-sm sm:text-base text-zinc-600">
              Replacing the legacy multi-week paper run with parallel departmental processing.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {WORKFLOW_STEPS.map((item, index) => {
              const Icon = item.icon
              return (
                <div
                  key={item.step}
                  className="group relative rounded-xl border border-border p-6 bg-white flex flex-col justify-between hover:border-black hover:shadow-card transition-all duration-200"
                >
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="font-mono text-xs font-bold text-zinc-400 group-hover:text-black transition-colors">
                        STEP {item.step}
                      </span>
                      <div className="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 group-hover:bg-black group-hover:text-white transition-colors">
                        <Icon className="w-4.5 h-4.5" />
                      </div>
                    </div>
                    <h3 className="font-heading text-base font-bold text-zinc-900 mb-2">
                      {item.title}
                    </h3>
                    <p className="text-xs text-zinc-600 leading-relaxed">
                      {item.desc}
                    </p>
                  </div>
                  {index < 3 && (
                    <div className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-6 h-6 rounded-full bg-white border border-border text-zinc-400 flex items-center justify-center shadow-2xs">
                      <ChevronRight className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Public QR Verification Callout with Mock Certificate */}
      <section className="py-20 md:py-24 bg-zinc-50 border-b border-border">
        <div className="container mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Left Column: Explanatory Copy */}
            <div className="space-y-5">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white border border-border text-xs font-semibold text-zinc-800 shadow-2xs">
                <QrCode className="w-3.5 h-3.5 text-zinc-700" />
                <span>Instant Tamper-Proof Verification</span>
              </div>
              <h2 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight text-zinc-950">
                Official Digital Certificate with Unguessable QR Code
              </h2>
              <p className="text-sm text-zinc-600 leading-relaxed">
                When the Chairperson (HoD) approves final clearance, a cryptographically unique UUID certificate code is issued.
                Prospective employers, partner institutions, and academic bodies can verify clearance status instantly without authentication or personal privacy leaks.
              </p>

              <div className="pt-2">
                <Button asChild variant="outline" size="sm" className="text-xs gap-1.5 border-zinc-300 hover:bg-white shadow-2xs">
                  <Link to="/verify">
                    Try Certificate Verification <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </Button>
              </div>
            </div>

            {/* Right Column: Stylized Mock Certificate Visual */}
            <div className="rounded-xl border border-border bg-white p-6 shadow-card space-y-4 font-sans relative">
              <div className="flex items-center justify-between pb-3 border-b border-border">
                <div>
                  <span className="font-heading font-extrabold text-xs tracking-wider uppercase text-zinc-400 block">
                    Official Clearance Certificate
                  </span>
                  <span className="font-heading font-bold text-sm text-zinc-900">
                    Shri Vishwakarma Skill University
                  </span>
                </div>
                <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-200">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="col-span-2 space-y-2">
                  <div>
                    <span className="text-[10px] text-zinc-400 uppercase tracking-wide block">Recipient</span>
                    <span className="font-semibold text-zinc-900">Aarav Sharma (DEMO2026001)</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-400 uppercase tracking-wide block">Programme & Dept</span>
                    <span className="text-zinc-700">B.Tech Computer Engineering • CS/IT</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-400 uppercase tracking-wide block">Verification Code</span>
                    <span className="font-mono text-[11px] text-zinc-900 font-semibold bg-zinc-50 px-1.5 py-0.5 rounded border border-zinc-200">
                      a9d4c721-8f4b-4a7a-b9c1-4821a0f912e8
                    </span>
                  </div>
                </div>

                {/* QR Code Placeholder Box */}
                <div className="col-span-1 rounded-lg border border-dashed border-zinc-300 p-2 flex flex-col items-center justify-center text-center bg-zinc-50/50">
                  <QrCode className="w-10 h-10 text-zinc-800 mb-1" />
                  <span className="text-[9px] text-zinc-500 font-mono">Scan to Verify</span>
                </div>
              </div>

              <div className="pt-2 border-t border-zinc-100 flex items-center justify-between text-[11px] text-zinc-400 font-mono">
                <span>Status: ISSUED & CLEARED</span>
                <span>Security Deposit: ELIGIBLE</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action Band */}
      <section className="py-16 md:py-20 bg-white border-b border-border">
        <div className="container mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <h2 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight text-zinc-950">
            Ready to initiate university clearance?
          </h2>
          <p className="text-sm text-zinc-600 max-w-xl mx-auto leading-relaxed">
            Students can verify their registered email via one-time password and submit in under three minutes.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button asChild size="lg" className="bg-primary text-primary-foreground hover:bg-zinc-800 text-sm h-11 px-6 shadow-xs w-full sm:w-auto">
              <Link to="/signup">
                Create Student Account <ArrowRight className="w-4 h-4 ml-2" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="text-sm h-11 px-6 border-border hover:bg-zinc-50 w-full sm:w-auto">
              <Link to="/login">Sign In</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Polished Multi-Column Footer */}
      <footer className="bg-white py-12 border-t border-border">
        <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 pb-8 border-b border-zinc-100">
            {/* Col 1: Wordmark & Disclaimer */}
            <div className="md:col-span-2 space-y-3">
              <span className="font-heading font-extrabold text-base tracking-tight text-black block">
                SVSU NO-DUES CLEARANCE
              </span>
              <p className="text-xs text-zinc-500 max-w-sm leading-relaxed">
                Shri Vishwakarma Skill University capstone project.
                Digital workflow replacing manual university paper-based clearance forms.
              </p>
              <p className="text-[11px] text-zinc-400">
                Student capstone project. Not an official university system. Demo uses synthetic data.
              </p>
            </div>

            {/* Col 2: Navigation Links */}
            <div className="space-y-2.5">
              <h4 className="font-heading font-bold text-xs uppercase tracking-wider text-zinc-900">
                Portal Access
              </h4>
              <ul className="space-y-1.5 text-xs text-zinc-600">
                <li>
                  <Link to="/login" className="hover:text-black transition-colors">Portal Login</Link>
                </li>
                <li>
                  <Link to="/signup" className="hover:text-black transition-colors">Student Registration</Link>
                </li>
                <li>
                  <Link to="/verify" className="hover:text-black transition-colors">Verify Certificate</Link>
                </li>
              </ul>
            </div>

            {/* Col 3: Institutional Scope */}
            <div className="space-y-2.5">
              <h4 className="font-heading font-bold text-xs uppercase tracking-wider text-zinc-900">
                University Scope
              </h4>
              <ul className="space-y-1.5 text-xs text-zinc-500">
                <li>Skill Faculty of Engineering & Tech</li>
                <li>Skill Department of CS/IT</li>
                <li>Security Deposit Refund Audit</li>
              </ul>
            </div>
          </div>

          <div className="pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-zinc-400 gap-2">
            <span>© 2026 Shri Vishwakarma Skill University (Demo Capstone)</span>
            <span>FastAPI • React 19 • Tailwind CSS • shadcn/ui</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
