import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { FileQuestion } from 'lucide-react'

export function EmptyState({
  icon: Icon = FileQuestion,
  title = 'No records found',
  description = 'There are no items to display at this moment.',
  action = null,
  className = '',
}) {
  return (
    <Card className={`border-dashed border-zinc-200 bg-zinc-50/50 ${className}`}>
      <CardContent className="flex flex-col items-center justify-center p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 text-zinc-600 mb-4">
          <Icon className="h-6 w-6" />
        </div>
        <h3 className="text-base font-semibold text-zinc-900 tracking-tight mb-1">{title}</h3>
        <p className="text-sm text-zinc-500 max-w-sm mb-4">{description}</p>
        {action && <div>{action}</div>}
      </CardContent>
    </Card>
  )
}

export default EmptyState
