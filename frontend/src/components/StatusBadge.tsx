interface StatusBadgeProps {
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'BUDGET_EXCEEDED'
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = {
    QUEUED: {
      color: 'bg-gray-100 text-gray-700 border-gray-300',
      label: 'Queued',
    },
    RUNNING: {
      color: 'bg-blue-100 text-blue-700 border-blue-300 animate-pulse',
      label: 'Running',
    },
    COMPLETED: {
      color: 'bg-green-100 text-green-700 border-green-300',
      label: 'Completed',
    },
    FAILED: {
      color: 'bg-red-100 text-red-700 border-red-300',
      label: 'Failed',
    },
    CANCELLED: {
      color: 'bg-yellow-100 text-yellow-700 border-yellow-300',
      label: 'Cancelled',
    },
    BUDGET_EXCEEDED: {
      color: 'bg-orange-100 text-orange-700 border-orange-300',
      label: 'Budget Exceeded',
    },
  }

  const { color, label } = config[status]

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${color}`}>
      {label}
    </span>
  )
}
