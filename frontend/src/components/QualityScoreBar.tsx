interface QualityScoreBarProps {
  score: number
  label: string
  size?: 'sm' | 'md'
}

function getScoreColor(score: number): string {
  if (score >= 0.8) return 'bg-green-500'
  if (score >= 0.6) return 'bg-yellow-500'
  return 'bg-red-500'
}

function getScoreTextColor(score: number): string {
  if (score >= 0.8) return 'text-green-700'
  if (score >= 0.6) return 'text-yellow-700'
  return 'text-red-700'
}

export default function QualityScoreBar({ score, label, size = 'md' }: QualityScoreBarProps) {
  const barHeight = size === 'sm' ? 'h-2' : 'h-3'
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  return (
    <div data-testid="quality-score-bar">
      <div className={`flex justify-between items-center mb-1 ${textSize}`}>
        <span className="text-gray-600">{label}</span>
        <span className={`font-semibold ${getScoreTextColor(score)}`} data-testid="score-value">
          {score.toFixed(2)}
        </span>
      </div>
      <div className={`w-full bg-gray-200 rounded-full ${barHeight}`}>
        <div
          className={`${barHeight} rounded-full transition-all duration-300 ${getScoreColor(score)}`}
          style={{ width: `${Math.min(score * 100, 100)}%` }}
          role="progressbar"
          aria-valuenow={score * 100}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  )
}
