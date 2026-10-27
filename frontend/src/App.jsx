import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/auth/AuthContext'
import { ProtectedRoute } from '@/auth/ProtectedRoute'
import { Toaster } from '@/components/ui/sonner'
import { ErrorBoundary } from '@/components/ErrorBoundary'

// Pages
import LandingPage from '@/pages/public/LandingPage'
import LoginPage from '@/pages/public/LoginPage'
import SignupPage from '@/pages/public/SignupPage'
import VerifyPage from '@/pages/public/VerifyPage'
import NotFoundPage from '@/pages/public/NotFoundPage'
import ForbiddenPage from '@/pages/public/ForbiddenPage'

// Protected Dashboard Views
import StudentDashboard from '@/pages/student/StudentDashboard'
import OfficerQueuePage from '@/pages/officer/OfficerQueuePage'
import HodQueuePage from '@/pages/hod/HodQueuePage'
import HodRequestDetailPage from '@/pages/hod/HodRequestDetailPage'
import RegistrarRefundPage from '@/pages/registrar/RegistrarRefundPage'
import AdminDashboardPage from '@/pages/admin/AdminDashboardPage'

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
            <Routes>
              {/* Public Routes */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/verify" element={<VerifyPage />} />
              <Route path="/verify/:code" element={<VerifyPage />} />

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
                path="/officer"
                element={
                  <ProtectedRoute allowedRoles={['dept_officer']}>
                    <OfficerQueuePage />
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
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminDashboardPage />
                  </ProtectedRoute>
                }
              />

              {/* Error Pages */}
              <Route path="/forbidden" element={<ForbiddenPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </BrowserRouter>
        </ErrorBoundary>
        {/* Mount Sonner Toaster once at root */}
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </QueryClientProvider>
  )
}
