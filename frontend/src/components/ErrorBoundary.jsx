import React from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import { Button } from '@/components/ui/button'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    // Keep error logging clean and minimal
    if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) {
      console.error('ErrorBoundary caught an unhandled error:', error, errorInfo)
    }
  }

  handleReload = () => {
    window.location.reload()
  }

  handleGoHome = () => {
    window.location.href = '/'
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 text-center font-sans">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-rose-50 text-rose-600 mb-6 border border-rose-100">
            <AlertTriangle className="h-8 w-8" />
          </div>
          <h1 className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground mb-2">
            Something unexpected happened
          </h1>
          <p className="text-sm text-muted-foreground max-w-md mb-6 leading-relaxed">
            An application error occurred while rendering this view. You can reload the page or return to the homepage to resume your session.
          </p>

          {this.state.error?.message && (
            <div className="max-w-md w-full bg-zinc-50 border border-zinc-200 rounded-lg p-3 mb-6 text-left">
              <span className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider block mb-1">
                Diagnostic Information
              </span>
              <p className="font-mono text-xs text-rose-700 break-words">
                {this.state.error.message}
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button
              onClick={this.handleReload}
              className="bg-primary text-primary-foreground hover:bg-zinc-800 gap-2 text-xs font-semibold"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reload Page
            </Button>
            <Button
              variant="outline"
              onClick={this.handleGoHome}
              className="gap-2 text-xs text-zinc-700"
            >
              <Home className="w-3.5 h-3.5" />
              Return to Home
            </Button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
