import { AppShell } from '@/components/AppShell'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CreditCard } from 'lucide-react'

export function RegistrarPlaceholder() {
  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="font-heading text-2xl font-bold tracking-tight text-zinc-950">
              Registrar & Accounts Section
            </h1>
            <Badge variant="outline" className="bg-zinc-100 text-zinc-700 text-xs font-mono">
              Phase 3 Preview
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Post-clearance security deposit reconciliation, deductions, and payment reference disbursement.
          </p>
        </div>

        <Card className="border-border bg-white shadow-2xs">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900">
                <CreditCard className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">
                  Refund Reconciliation & Disbursement Interface
                </CardTitle>
                <CardDescription className="text-xs">
                  Full Accounts Section ledger terminal scheduled for Phase 3 implementation.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-xs text-zinc-600 leading-relaxed">
            <p>
              Once a clearance certificate is issued, the Accounts Section manages the security deposit refund:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-zinc-700">
              <li>
                <strong>Cleared Student Queue:</strong> Access students ready for refund audit via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">GET /registrar/queue</code>.
              </li>
              <li>
                <strong>Verify Deductions:</strong> Confirm deposit amount and verify deductions via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">
                  POST /registrar/requests/{'{id}'}/verify-refund
                </code>.
              </li>
              <li>
                <strong>Disbursement Tracking:</strong> Record official bank transaction reference (UTR / NEFT) via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">
                  POST /registrar/requests/{'{id}'}/mark-processed
                </code>.
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}

export default RegistrarPlaceholder
