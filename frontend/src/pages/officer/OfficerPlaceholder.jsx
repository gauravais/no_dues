import { AppShell } from '@/components/AppShell'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Building2 } from 'lucide-react'

export function OfficerPlaceholder() {
  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="font-heading text-2xl font-bold tracking-tight text-zinc-950">
              Department Clearance Review Queue
            </h1>
            <Badge variant="outline" className="bg-zinc-100 text-zinc-700 text-xs font-mono">
              Phase 2 Preview
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Manage incoming student clearance reviews for your assigned university office.
          </p>
        </div>

        <Card className="border-border bg-white shadow-2xs">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">
                  Department Officer Workflow Interface
                </CardTitle>
                <CardDescription className="text-xs">
                  Full departmental decision dashboard scheduled for Phase 2 implementation.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-xs text-zinc-600 leading-relaxed">
            <p>
              As a Department Officer (Library, Hostel, Sports, Labs, or Academic), your role allows you to:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-zinc-700">
              <li>
                <strong>Fetch Clearance Queue:</strong> View real-time pending student submissions via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">GET /department/queue</code>.
              </li>
              <li>
                <strong>Render Decisions:</strong> Approve student dues or reject with mandatory remarks via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">
                  POST /department/approvals/{'{id}'}/decision
                </code>.
              </li>
              <li>
                <strong>Review Resubmissions:</strong> Inspect student resubmissions when dues have been settled.
              </li>
            </ul>
            <div className="rounded-lg bg-zinc-50 border border-zinc-200 p-4 text-[11px] text-zinc-500">
              💡 <em>Backend API endpoints for Department Officers are fully active and passing all tests. Frontend UI views will be expanded in Phase 2.</em>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}

export default OfficerPlaceholder
