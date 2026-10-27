import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
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
import { Menu, LogOut } from 'lucide-react'

const ROLE_LABELS = {
  student: 'Student',
  dept_officer: 'Department Officer',
  hod: 'Chairperson (HoD)',
  registrar_accounts: 'Registrar / Accounts',
  admin: 'Administrator',
}

export function AppShell({ children }) {
  const { user, logout, isStudent, isOfficer, isHod, isRegistrar, isAdmin } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [logoutDialogOpen, setLogoutDialogOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  const navLinks = [
    ...(isStudent ? [{ label: 'My Clearance', path: '/student' }] : []),
    ...(isOfficer ? [{ label: 'Department Queue', path: '/officer' }] : []),
    ...(isHod ? [{ label: 'HoD Approvals', path: '/hod' }] : []),
    ...(isRegistrar ? [{ label: 'Refunds & Accounts', path: '/registrar' }] : []),
    ...(isAdmin ? [{ label: 'System Admin', path: '/admin' }] : []),
    { label: 'Verify Certificate', path: '/verify' },
  ]

  const handleLogoutClick = () => {
    setLogoutDialogOpen(true)
  }

  const handleConfirmLogout = () => {
    setLogoutDialogOpen(false)
    logout()
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 w-full border-b border-border bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
        <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand Wordmark */}
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2">
              <span className="font-heading font-extrabold text-lg sm:text-xl tracking-tight text-black">
                SVSU NO-DUES
              </span>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => {
                const isActive = location.pathname === link.path
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`px-3 py-1.5 text-xs sm:text-sm font-medium rounded-md transition-colors ${
                      isActive
                        ? 'bg-zinc-100 text-zinc-900 font-semibold'
                        : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50'
                    }`}
                  >
                    {link.label}
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* Right Section: User & Sign Out */}
          <div className="hidden md:flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-xs font-semibold text-zinc-900 leading-none">
                    {user.full_name || user.email}
                  </div>
                  <div className="flex items-center justify-end gap-1.5 mt-1">
                    <Badge
                      variant="outline"
                      className="text-[10px] font-medium px-1.5 py-0 bg-zinc-50 border-zinc-200 text-zinc-600 uppercase tracking-wider"
                    >
                      {ROLE_LABELS[user.role] || user.role}
                    </Badge>
                    {user.department_name && (
                      <span className="text-[11px] text-muted-foreground truncate max-w-[120px]">
                        • {user.department_name}
                      </span>
                    )}
                  </div>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLogoutClick}
                  className="h-8 gap-1.5 text-xs text-zinc-700 hover:text-red-600 hover:bg-red-50 hover:border-red-200"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sign Out
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/login')}
                  className="text-xs"
                >
                  Sign In
                </Button>
                <Button
                  size="sm"
                  onClick={() => navigate('/signup')}
                  className="text-xs bg-black text-white hover:bg-zinc-800"
                >
                  Student Sign Up
                </Button>
              </div>
            )}
          </div>

          {/* Mobile Hamburger Menu */}
          <div className="flex md:hidden items-center gap-2">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="h-9 w-9">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Toggle navigation menu</span>
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-72 bg-white p-6">
                <SheetHeader className="text-left border-b border-zinc-100 pb-4 mb-4">
                  <SheetTitle className="font-heading font-bold text-lg text-black">
                    SVSU NO-DUES
                  </SheetTitle>
                  {user && (
                    <div className="mt-2">
                      <p className="text-xs font-semibold text-zinc-900 truncate">
                        {user.full_name || user.email}
                      </p>
                      <Badge
                        variant="outline"
                        className="mt-1 text-[10px] font-medium bg-zinc-50 text-zinc-600"
                      >
                        {ROLE_LABELS[user.role] || user.role}
                      </Badge>
                    </div>
                  )}
                </SheetHeader>

                <div className="flex flex-col gap-2">
                  {navLinks.map((link) => {
                    const isActive = location.pathname === link.path
                    return (
                      <Link
                        key={link.path}
                        to={link.path}
                        onClick={() => setMobileOpen(false)}
                        className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                          isActive
                            ? 'bg-zinc-100 text-black font-semibold'
                            : 'text-zinc-600 hover:bg-zinc-50'
                        }`}
                      >
                        {link.label}
                      </Link>
                    )
                  })}
                </div>

                <div className="mt-8 pt-4 border-t border-zinc-100">
                  {user ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setMobileOpen(false)
                        handleLogoutClick()
                      }}
                      className="w-full gap-2 text-xs text-red-600 hover:bg-red-50"
                    >
                      <LogOut className="w-4 h-4" />
                      Sign Out
                    </Button>
                  ) : (
                    <div className="flex flex-col gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setMobileOpen(false)
                          navigate('/login')
                        }}
                        className="w-full text-xs"
                      >
                        Sign In
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          setMobileOpen(false)
                          navigate('/signup')
                        }}
                        className="w-full text-xs bg-black text-white"
                      >
                        Student Sign Up
                      </Button>
                    </div>
                  )}
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-border bg-white py-6">
        <div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <p>
            Student capstone project. Not an official university system. Demo uses synthetic data.
          </p>
          <div className="flex items-center gap-4">
            <Link to="/verify" className="hover:text-foreground underline underline-offset-4">
              Public Verification
            </Link>
            <span>•</span>
            <span>Shri Vishwakarma Skill University</span>
          </div>
        </div>
      </footer>

      {/* Logout Confirmation Dialog */}
      <AlertDialog open={logoutDialogOpen} onOpenChange={setLogoutDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading text-lg font-bold">
              Sign out of your session?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-muted-foreground">
              You will be signed out of your SVSU clearance account on this device. Any unsubmitted changes will not be saved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="text-xs">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmLogout}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs font-semibold"
            >
              Sign Out
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default AppShell
