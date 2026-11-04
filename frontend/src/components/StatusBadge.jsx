import React from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  CreditCard,
  FileCheck2,
} from 'lucide-react'

const STATUS_CONFIGS = {
  // Clearance Request Statuses
  SUBMITTED: {
    label: 'In Department Review',
    icon: Clock,
    className: 'bg-zinc-100 text-zinc-800 border-zinc-200 hover:bg-zinc-100',
  },
  ACTION_NEEDED: {
    label: 'Action Needed',
    icon: AlertTriangle,
    className: 'bg-amber-50 text-amber-900 border-amber-200 hover:bg-amber-50',
  },
  HOD_REVIEW: {
    label: 'Awaiting HoD Review',
    icon: ShieldCheck,
    className: 'bg-blue-50 text-blue-900 border-blue-200 hover:bg-blue-50',
  },
  CLEARED: {
    label: 'Cleared (Certificate Issued)',
    icon: FileCheck2,
    className: 'bg-emerald-50 text-emerald-900 border-emerald-200 hover:bg-emerald-50',
  },
  REFUND_VERIFIED: {
    label: 'Refund Verified',
    icon: CreditCard,
    className: 'bg-teal-50 text-teal-900 border-teal-200 hover:bg-teal-50',
  },
  CANCELLED: {
    label: 'Cancelled',
    icon: XCircle,
    className: 'bg-zinc-100 text-zinc-600 border-zinc-300 hover:bg-zinc-100',
  },

  // Department Approval Statuses
  PENDING: {
    label: 'Pending Review',
    icon: Clock,
    className: 'bg-zinc-100 text-zinc-700 border-zinc-200 hover:bg-zinc-100',
  },
  APPROVED: {
    label: 'Approved',
    icon: CheckCircle2,
    className: 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-50',
  },
  REJECTED: {
    label: 'Rejected',
    icon: XCircle,
    className: 'bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-50',
  },
}

export function StatusBadge({ status, size = 'default', customLabel, className = '' }) {
  const config = STATUS_CONFIGS[status] || {
    label: status || 'Unknown',
    icon: Clock,
    className: 'bg-zinc-100 text-zinc-700 border-zinc-200',
  }

  const Icon = config.icon
  const label = customLabel || config.label
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'
  const textClass = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-xs px-2.5 py-1'

  return (
    <Badge
      variant="outline"
      className={`inline-flex items-center gap-1.5 font-medium rounded-full transition-colors ${config.className} ${textClass} ${className}`}
    >
      <Icon className={`${iconSize} shrink-0`} />
      <span>{label}</span>
    </Badge>
  )
}

export default StatusBadge
