import { useState } from 'react'
import { generateSeedData } from '../services/api'
import { useToast } from '../hooks/useToast'

interface SeedDataGeneratorProps {
  templateId: string
  onGenerated: (s3Key: string, count: number) => void
}

const MODEL_TIERS = [
  { value: 'tier-1', label: 'Tier 1 - Llama 8B (Recommended for cost)' },
  { value: 'tier-2', label: 'Tier 2 - Llama 70B (Balanced)' },
  { value: 'tier-3', label: 'Tier 3 - Claude Sonnet (Best quality)' },
]

export default function SeedDataGenerator({ templateId, onGenerated }: SeedDataGeneratorProps) {
  const { toast } = useToast()
  const [count, setCount] = useState(10)
  const [modelTier, setModelTier] = useState('tier-1')
  const [exampleData, setExampleData] = useState('')
  const [instructions, setInstructions] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{
    records_generated: number
    records_invalid: number
    total_cost: number
  } | null>(null)

  async function handleGenerate() {
    if (!templateId) {
      toast('Please select a template first', 'error')
      return
    }

    setLoading(true)
    setResult(null)

    try {
      let parsedExample: Record<string, unknown> | undefined
      if (exampleData.trim()) {
        try {
          parsedExample = JSON.parse(exampleData)
        } catch {
          toast('Example data must be valid JSON', 'error')
          setLoading(false)
          return
        }
      }

      const response = await generateSeedData({
        template_id: templateId,
        count,
        model_tier: modelTier,
        example_data: parsedExample,
        instructions: instructions || undefined,
      })

      setResult({
        records_generated: response.records_generated,
        records_invalid: response.records_invalid,
        total_cost: response.total_cost,
      })

      onGenerated(response.s3_key, response.records_generated)
      toast(`Generated ${response.records_generated} seed records`, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to generate seed data', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Number of Records (1-100)
        </label>
        <input
          type="number"
          min="1"
          max="100"
          value={count}
          onChange={(e) => setCount(Math.min(100, Math.max(1, Number(e.target.value))))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Model Tier</label>
        <select
          value={modelTier}
          onChange={(e) => setModelTier(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        >
          {MODEL_TIERS.map((tier) => (
            <option key={tier.value} value={tier.value}>
              {tier.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Example Data (optional, JSON)
        </label>
        <textarea
          value={exampleData}
          onChange={(e) => setExampleData(e.target.value)}
          placeholder='{"author": {"name": "...", "biography": "..."}}'
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Instructions (optional)
        </label>
        <textarea
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          placeholder="Generate diverse authors from different eras and cultures"
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>

      <button
        onClick={handleGenerate}
        disabled={loading || !templateId}
        className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Generating...' : `Generate ${count} Records`}
      </button>

      {result && (
        <div className="bg-green-50 border border-green-200 p-4 rounded-md">
          <p className="text-green-800">
            Generated {result.records_generated} records
            {result.records_invalid > 0 && ` (${result.records_invalid} invalid filtered)`}
            . Cost: ${result.total_cost.toFixed(2)}
          </p>
        </div>
      )}
    </div>
  )
}
