import { useEffect } from 'react'

/**
 * Custom hook to update document title per view
 * @param {string} title
 */
export function useDocumentTitle(title) {
  useEffect(() => {
    const previousTitle = document.title
    document.title = title ? `${title} | SVSU No-Dues` : 'SVSU No-Dues Clearance System'
    return () => {
      document.title = previousTitle
    }
  }, [title])
}

export default useDocumentTitle
