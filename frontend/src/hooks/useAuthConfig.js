import { useQuery } from '@tanstack/react-query'
import { authApi } from '@/api/auth'

/**
 * Hook to load public authentication configuration (/auth/config) once at startup.
 */
export function useAuthConfig() {
  return useQuery({
    queryKey: ['auth', 'config'],
    queryFn: () => authApi.getConfig(),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
}

export default useAuthConfig
