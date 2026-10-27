import React from 'react'
import { Check, Clock, AlertTriangle, ShieldCheck, FileCheck } from 'lucide-react'

export function StepTimeline({ status, approvals = [], hodRemarks = null }) {
  // Determine status of each step:
  // Step 1: Submission (always complete if request exists)
  // Step 2: Department Clearance
  // Step 3: Chairperson / HoD Clearance
  // Step 4: Certificate & Refund

  const hasRejectedDepts = approvals.some((a) => a.status === 'REJECTED')
  const allDeptsApproved =
    approvals.length > 0 && approvals.every((a) => a.status === 'APPROVED')

  const steps = [
    {
      id: 'submitted',
      title: 'Applied',
      subtitle: 'Dispatched to departments',
      icon: Check,
      state: 'complete',
    },
    {
      id: 'departments',
      title: 'Departments',
      subtitle: hasRejectedDepts
        ? 'Dues / Action Required'
        : allDeptsApproved
        ? 'All Departments Cleared'
        : 'Parallel Reviews Pending',
      icon: hasRejectedDepts ? AlertTriangle : allDeptsApproved ? Check : Clock,
      state: hasRejectedDepts
        ? 'warning'
        : allDeptsApproved
        ? 'complete'
        : 'active',
    },
    {
      id: 'hod',
      title: 'HoD Review',
      subtitle:
        status === 'CLEARED' || status === 'REFUND_VERIFIED'
          ? 'Chairperson Approved'
          : status === 'ACTION_NEEDED' && !hasRejectedDepts && hodRemarks
          ? 'HoD Action Needed'
          : status === 'HOD_REVIEW'
          ? 'Awaiting HoD Decision'
          : 'Pending Department Approvals',
      icon:
        status === 'CLEARED' || status === 'REFUND_VERIFIED'
          ? Check
          : status === 'ACTION_NEEDED' && !hasRejectedDepts
          ? AlertTriangle
          : ShieldCheck,
      state:
        status === 'CLEARED' || status === 'REFUND_VERIFIED'
          ? 'complete'
          : status === 'HOD_REVIEW'
          ? 'active'
          : status === 'ACTION_NEEDED' && !hasRejectedDepts
          ? 'warning'
          : 'pending',
    },
    {
      id: 'refund',
      title: 'Cleared & Refund',
      subtitle:
        status === 'REFUND_VERIFIED'
          ? 'Refund Verified'
          : status === 'CLEARED'
          ? 'Certificate Issued'
          : 'Pending Final Clearance',
      icon: FileCheck,
      state:
        status === 'REFUND_VERIFIED'
          ? 'complete'
          : status === 'CLEARED'
          ? 'active'
          : 'pending',
    },
  ]

  return (
    <div className="w-full py-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {steps.map((step, idx) => {
          const Icon = step.icon

          let circleStyle = 'bg-zinc-100 text-zinc-400 border-zinc-200'
          let borderTop = 'border-t-2 border-zinc-200'

          if (step.state === 'complete') {
            circleStyle = 'bg-black text-white border-black'
            borderTop = 'border-t-2 border-black'
          } else if (step.state === 'active') {
            circleStyle = 'bg-zinc-900 text-white border-zinc-900 ring-4 ring-zinc-100'
            borderTop = 'border-t-2 border-black'
          } else if (step.state === 'warning') {
            circleStyle = 'bg-amber-600 text-white border-amber-600 ring-4 ring-amber-100'
            borderTop = 'border-t-2 border-amber-500'
          }

          return (
            <div key={step.id} className={`pt-3 ${borderTop} transition-colors`}>
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold border ${circleStyle}`}
                >
                  <Icon className="w-3.5 h-3.5" />
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Step 0{idx + 1}
                </span>
              </div>
              <p className="text-sm font-semibold text-foreground tracking-tight">
                {step.title}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5 leading-snug">
                {step.subtitle}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default StepTimeline
