import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/auth/AuthContext'
import { ProtectedRoute } from '@/auth/ProtectedRoute'
import { Toaster } from '@/components/ui/sonner'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Skeleton } from '@/components/ui/skeleton'

// Lazy-loaded Pages (code splitting)
const LandingPage = lazy(() => import('@/pages/public/LandingPage'))
const LoginPage = lazy(() => import('@/pages/public/LoginPage'))
const SignupPage = lazy(() => import('@/pages/public/SignupPage'))
const VerifyPage = lazy(() => import('@/pages/public/VerifyPage'))
const HelpPage = lazy(() => import('@/pages/public/HelpPage'))
const ChangePasswordPage = lazy(() => import('@/pages/public/ChangePasswordPage'))
const NotFoundPage = lazy(() => import('@/pages/public/NotFoundPage'))
const ForbiddenPage = lazy(() => import('@/pages/public/ForbiddenPage'))

// Lazy-loaded Protected Dashboard Views
const StudentDashboard = lazy(() => import('@/pages/student/StudentDashboard'))
const StudentApplyPage = lazy(() => import('@/pages/student/StudentApplyPage'))
const OfficerQueuePage = lazy(() => import('@/pages/officer/OfficerQueuePage'))
const OfficerRosterPage = lazy(() => import('@/pages/officer/OfficerRosterPage'))
const OfficerLabCatalogPage = lazy(() => import('@/pages/officer/OfficerLabCatalogPage'))
const OfficerRequestDetailPage = lazy(() => import('@/pages/officer/OfficerRequestDetailPage'))
const HodQueuePage = lazy(() => import('@/pages/hod/HodQueuePage'))
const HodRequestDetailPage = lazy(() => import('@/pages/hod/HodRequestDetailPage'))
const RegistrarRefundPage = lazy(() => import('@/pages/registrar/RegistrarRefundPage'))
const RegistrarRequestDetailPage = lazy(() => import('@/pages/registrar/RegistrarRequestDetailPage'))
const AdminOfficesPage = lazy(() => import('@/pages/admin/AdminOfficesPage'))
const AdminUsersPage = lazy(() => import('@/pages/admin/AdminUsersPage'))
const AdminRosterPage = lazy(() => import('@/pages/admin/AdminRosterPage'))
const AdminLabCoursesPage = lazy(() => import('@/pages/admin/AdminLabCoursesPage'))

function RouteFallback() {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md space-y-4">
        <div className="flex items-center space-x-3">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
        <Skeleton className="h-32 w-full rounded-xl" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      </div>
    </div>
  )
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ErrorBoundary>
          <BrowserRouter>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                {/* Public Routes */}
                <Route path="/" element={<LandingPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/signup" element={<SignupPage />} />
                <Route path="/verify" element={<VerifyPage />} />
                <Route path="/verify/:code" element={<VerifyPage />} />
                <Route path="/help" element={<HelpPage />} />

                {/* Authenticated Global Route */}
                <Route
                  path="/change-password"
                  element={
                    <ProtectedRoute>
                      <ChangePasswordPage />
                    </ProtectedRoute>
                  }
                />

                {/* Role-Protected Routes */}
                <Route
                  path="/student"
                  element={
                    <ProtectedRoute allowedRoles={['student']}>
                      <StudentDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/student/apply"
                  element={
                    <ProtectedRoute allowedRoles={['student']}>
                      <StudentApplyPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/officer"
                  element={
                    <ProtectedRoute allowedRoles={['dept_officer']}>
                      <OfficerQueuePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/officer/roster"
                  element={
                    <ProtectedRoute allowedRoles={['dept_officer']}>
                      <OfficerRosterPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/officer/lab-catalog"
                  element={
                    <ProtectedRoute allowedRoles={['dept_officer']}>
                      <OfficerLabCatalogPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/officer/requests/:id"
                  element={
                    <ProtectedRoute allowedRoles={['dept_officer']}>
                      <OfficerRequestDetailPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/hod"
                  element={
                    <ProtectedRoute allowedRoles={['hod']}>
                      <HodQueuePage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/hod/requests/:id"
                  element={
                    <ProtectedRoute allowedRoles={['hod']}>
                      <HodRequestDetailPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/registrar"
                  element={
                    <ProtectedRoute allowedRoles={['registrar_accounts']}>
                      <RegistrarRefundPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/registrar/requests/:id"
                  element={
                    <ProtectedRoute allowedRoles={['registrar_accounts']}>
                      <RegistrarRequestDetailPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/admin"
                  element={<Navigate to="/admin/offices" replace />}
                />
                <Route
                  path="/admin/offices"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <AdminOfficesPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/users"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <AdminUsersPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/roster"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <AdminRosterPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/lab-courses"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <AdminLabCoursesPage />
                    </ProtectedRoute>
                  }
                />

                {/* Error Pages */}
                <Route path="/forbidden" element={<ForbiddenPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ErrorBoundary>
        {/* Mount Sonner Toaster once at root */}
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </QueryClientProvider>
  )
}
