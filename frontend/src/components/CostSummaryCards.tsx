import type { CostAnalytics } from '../services/api'

interface Props {
  summary: CostAnalytics['summary']
}

function formatCurrency(value: number): string {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export default function CostSummaryCards({ summary }: Props) {
  const cards = [
    {
      label: 'Total Spend',
      value: formatCurrency(summary.total_spend),
      highlight: true,
    },
    {
      label: 'Jobs Run',
      value: summary.job_count.toString(),
      highlight: false,
    },
    {
      label: 'Avg Cost / Job',
      value: formatCurrency(summary.avg_cost_per_job),
      highlight: false,
    },
    {
      label: 'Budget Efficiency',
      value: formatPercent(summary.budget_efficiency),
      highlight: false,
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`bg-white rounded-lg shadow p-4 ${card.highlight ? 'ring-2 ring-blue-500' : ''}`}
        >
          <p className="text-sm text-gray-500">{card.label}</p>
          <p className={`text-2xl font-bold mt-1 ${card.highlight ? 'text-blue-600' : 'text-gray-900'}`}>
            {card.value}
          </p>
        </div>
      ))}
    </div>
  )
}
