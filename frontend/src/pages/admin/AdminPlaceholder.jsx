import { AppShell } from '@/components/AppShell'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Settings2 } from 'lucide-react'

export function AdminPlaceholder() {
  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="font-heading text-2xl font-bold tracking-tight text-zinc-950">
              System Administration
            </h1>
            <Badge variant="outline" className="bg-zinc-100 text-zinc-700 text-xs font-mono">
              Phase 3 Preview
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Student roster ingestion, officer staff provisioning, and role governance.
          </p>
        </div>

        <Card className="border-border bg-white shadow-2xs">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-900">
                <Settings2 className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">
                  Administrator Console
                </CardTitle>
                <CardDescription className="text-xs">
                  Roster CSV processor and user provisioning views scheduled for Phase 3.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-xs text-zinc-600 leading-relaxed">
            <p>
              Administrative control endpoints available in backend:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-zinc-700">
              <li>
                <strong>Roster CSV Upload:</strong> Bulk ingest official university student roster via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">POST /admin/roster/upload</code>.
              </li>
              <li>
                <strong>Staff User Provisioning:</strong> Create officers, HoDs, and accounts staff with temporary passwords via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">POST /admin/users</code>.
              </li>
              <li>
                <strong>Roster Edits & Lab Assignments:</strong> Update hostel status and assigned workshops via{' '}
                <code className="text-zinc-900 font-mono bg-zinc-100 px-1 py-0.5 rounded">
                  PUT /admin/roster/{'{id}'}/assigned-departments
                </code>.
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}

export default AdminPlaceholder
