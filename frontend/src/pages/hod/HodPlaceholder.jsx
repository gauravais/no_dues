import { AppShell } from '@/components/AppShell'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ShieldCheck } from 'lucide-react'

export function HodPlaceholder() {
  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="font-heading text-2xl font-bold tracking-tight text-zinc-950">
              Chairperson (HoD) Final Review Queue
            </h1>
            <Badge variant="outline" className="bg-zinc-100 text-zinc-700 text-xs font-mono">
              Phase 2 Preview
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Academic Department Chairperson final clearance and certificate issuance.
          </p>
        </div>

        <Card className="border-border bg-white shadow-2xs">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">
                  Chairperson Approval & Dossier Review
                </CardTitle>
                <CardDescription className="text-xs">
                  Full HoD decision terminal scheduled for Phase 2 implementation.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-xs text-zinc-600 leading-relaxed">
            <p>
              When all departmental reviews are approved, clearance applications route to the Chairperson:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-zinc-700">
              <li>
                <strong>HoD Review Queue:</strong> Access students awaiting final clearance via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">GET /hod/queue</code>.
              </li>
              <li>
                <strong>Comprehensive Dossier:</strong> Inspect full student clearance dossier and all departmental sign-offs via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">GET /hod/requests/{'{id}'}</code>.
              </li>
              <li>
                <strong>Final Clearance Decision:</strong> Grant final approval (generating official UUID certificate) or reject with remarks via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">
                  POST /hod/requests/{'{id}'}/decision
                </code>.
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}

export default HodPlaceholder
