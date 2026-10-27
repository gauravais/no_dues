import React from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { FileQuestion, ArrowLeft } from 'lucide-react'

export function NotFoundPage() {
  useDocumentTitle('404 Page Not Found')
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-zinc-100 text-zinc-900 mb-6">
        <FileQuestion className="h-8 w-8" />
      </div>
      <h1 className="font-heading text-4xl font-extrabold tracking-tight text-foreground mb-2">
        404 — Page Not Found
      </h1>
      <p className="text-sm text-muted-foreground max-w-md mb-8">
        The requested resource does not exist or has been moved. Check the URL or return to the homepage.
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

export default NotFoundPage
