import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { verifyApi } from '@/api/verify'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { toast } from 'sonner'
import { ShieldCheck, Search, CheckCircle2, XCircle, ArrowLeft } from 'lucide-react'

export function VerifyPage() {
  useDocumentTitle('Verify Clearance Certificate')
  const { code: urlCode } = useParams()
  const [code, setCode] = useState(urlCode || '')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleVerify = useCallback(async (codeToVerify) => {
    const cleanCode = (codeToVerify || code).trim()
    if (!cleanCode) {
      toast.error('Please enter a certificate verification code.')
      return
    }

    setLoading(true)
    setSearched(true)
    try {
      const data = await verifyApi.checkCertificate(cleanCode)
      setResult(data)
    } catch (err) {
      setResult({ valid: false, detail: err.response?.data?.detail || 'Certificate not found or invalid' })
    } finally {
      setLoading(false)
    }
  }, [code])

  useEffect(() => {
    if (urlCode) {
      handleVerify(urlCode)
    }
  }, [urlCode, handleVerify])

  return (
    <div className="min-h-screen bg-zinc-50/50 flex flex-col justify-between py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-xl mx-auto w-full space-y-6">
        {/* Back Link & Brand */}
        <div className="flex items-center justify-between">
          <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-600 hover:text-black">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Home
          </Link>
          <span className="font-heading font-extrabold text-base tracking-tight text-black">
            SVSU NO-DUES
          </span>
        </div>

        {/* Verification Card */}
        <Card className="border-border bg-white shadow-card">
          <CardHeader className="p-6 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900 shrink-0">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="font-heading text-lg font-bold">
                  Public Certificate Verification
                </CardTitle>
                <CardDescription className="text-xs">
                  Verify the authenticity of an official SVSU clearance certificate using its unique UUID code.
                </CardDescription>
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-6 pt-0 space-y-4">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleVerify()
              }}
              className="flex gap-2"
            >
              <Input
                placeholder="Enter certificate UUID code..."
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="font-mono text-xs sm:text-sm h-10"
                required
              />
              <Button
                type="submit"
                disabled={loading}
                className="bg-primary text-primary-foreground hover:bg-zinc-800 text-xs shrink-0 gap-1.5 h-10 font-semibold px-4"
              >
                <Search className="w-3.5 h-3.5" />
                {loading ? 'Verifying...' : 'Verify'}
              </Button>
            </form>

            {searched && (
              <div className="pt-2">
                {result?.valid ? (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                      <div>
                        <h3 className="text-sm font-bold text-emerald-950">Valid Clearance Certificate</h3>
                        <p className="text-[11px] text-emerald-800">
                          Issued by Shri Vishwakarma Skill University
                        </p>
                      </div>
                    </div>

                    <div className="space-y-1.5 text-xs text-zinc-700 bg-white/80 p-3 rounded-lg border border-emerald-100 font-sans">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Student Reg. No:</span>
                        <span className="font-mono font-semibold text-zinc-900">
                          {result.masked_registration_number}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Programme:</span>
                        <span className="font-semibold text-zinc-900 text-right max-w-[240px]">
                          {result.programme}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Department:</span>
                        <span className="font-semibold text-zinc-900 text-right max-w-[240px]">
                          {result.department}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Issue Date:</span>
                        <span className="font-mono text-zinc-900">
                          {new Date(result.issued_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4 flex items-start gap-3">
                    <XCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-sm font-bold text-rose-950">Invalid Certificate Code</h3>
                      <p className="text-xs text-rose-800 mt-0.5">
                        {result?.detail || 'No official clearance record matches this code in university database.'}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <footer className="text-center text-xs text-muted-foreground mt-8">
        © 2026 Shri Vishwakarma Skill University
      </footer>
    </div>
  )
}

export default VerifyPage
