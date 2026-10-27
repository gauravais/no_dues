import React from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { ShieldAlert, ArrowLeft } from 'lucide-react'

export function ForbiddenPage() {
  useDocumentTitle('403 Access Forbidden')
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-50 text-red-600 mb-6">
        <ShieldAlert className="h-8 w-8" />
      </div>
      <h1 className="font-heading text-4xl font-extrabold tracking-tight text-foreground mb-2">
        403 — Access Forbidden
      </h1>
      <p className="text-sm text-muted-foreground max-w-md mb-8">
        You do not have administrative or departmental authorization to view this section.
      </p>
      <div className="flex gap-4">
        <Button asChild variant="outline">
          <Link to="/" className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>
        </Button>
      </div>
    </div>
  )
}

export default ForbiddenPage
