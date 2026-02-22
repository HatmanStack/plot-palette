import type { CostAnalytics } from '../services/api'

interface Props {
  byModel: CostAnalytics['by_model']
}

export default function ModelCostBreakdown({ byModel }: Props) {
  if (byModel.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        No model usage data
      </div>
    )
  }

  // Already sorted by total cost descending from the API
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Cost by Model</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="pb-2 font-medium">Model</th>
            <th className="pb-2 font-medium text-right">Total Cost</th>
            <th className="pb-2 font-medium text-right">Jobs</th>
            <th className="pb-2 font-medium text-right">Avg / Job</th>
          </tr>
        </thead>
        <tbody>
          {byModel.map((model) => (
            <tr key={model.model_id} className="border-b last:border-0">
              <td className="py-2 font-medium text-gray-900">
                {model.model_name || model.model_id}
              </td>
              <td className="py-2 text-right text-gray-700">
                ${model.total.toFixed(2)}
              </td>
              <td className="py-2 text-right text-gray-700">
                {model.job_count}
              </td>
              <td className="py-2 text-right text-gray-700">
                ${model.job_count > 0 ? (model.total / model.job_count).toFixed(2) : '0.00'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
