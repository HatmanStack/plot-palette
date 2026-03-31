import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createBatch, generateUploadUrl } from '../services/api'
import axios from 'axios'

interface BatchWizardData {
  name: string
  templateId: string
  templateVersion: number
  seedDataPath: string
  seedDataFile: File | null
  budgetLimit: number
  numRecords: number
  outputFormat: 'JSONL' | 'CSV' | 'PARQUET'
  sweepType: 'model_tier' | 'seed_data_path' | 'num_records'
  modelTiers: string[]
  seedDataFiles: File[]
  recordCounts: string
}

const MODEL_TIER_OPTIONS = [
  { value: 'tier-1', label: 'Tier 1 - Llama 3.1 8B (Cheap)' },
  { value: 'tier-2', label: 'Tier 2 - Llama 3.1 70B (Balanced)' },
  { value: 'tier-3', label: 'Tier 3 - Claude 3.5 Sonnet (Premium)' },
]

export default function CreateBatch() {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const [data, setData] = useState<BatchWizardData>({
    name: '',
    templateId: '',
    templateVersion: 1,
    seedDataPath: '',
    seedDataFile: null,
    budgetLimit: 10,
    numRecords: 100,
    outputFormat: 'JSONL',
    sweepType: 'model_tier',
    modelTiers: ['tier-1', 'tier-2', 'tier-3'],
    seedDataFiles: [],
    recordCounts: '50, 100, 500',
  })

  function getSweepValues(): unknown[] {
    switch (data.sweepType) {
      case 'model_tier':
        return data.modelTiers
      case 'num_records':
        return data.recordCounts
          .split(',')
          .map((s) => parseInt(s.trim(), 10))
          .filter((n) => !isNaN(n) && n > 0)
      case 'seed_data_path':
        return data.seedDataFiles.map((f) => f.name)
      default:
        return []
    }
  }

  function getJobCount(): number {
    return getSweepValues().length
  }

  async function handleSubmit() {
    if (!data.templateId || !data.name) {
      setError('Please complete all required fields')
      return
    }

    setLoading(true)
    setError('')

    try {
      let seedDataPath = data.seedDataPath
      const sweepValues = getSweepValues()

      // Upload seed data file if provided (for non-seed-data sweeps)
      if (data.sweepType !== 'seed_data_path' && data.seedDataFile) {
        const { upload_url, s3_key } = await generateUploadUrl(
          data.seedDataFile.name,
          data.seedDataFile.type || 'application/json'
        )
        await axios.put(upload_url, data.seedDataFile, {
          headers: { 'Content-Type': data.seedDataFile.type || 'application/json' },
        })
        seedDataPath = s3_key
      }

      // For seed data sweep, upload each file
      let sweepConfig: Record<string, unknown[]>
      if (data.sweepType === 'seed_data_path') {
        const paths: string[] = []
        for (const file of data.seedDataFiles) {
          const { upload_url, s3_key } = await generateUploadUrl(
            file.name,
            file.type || 'application/json'
          )
          const uploadResponse = await fetch(upload_url, {
            method: 'PUT',
            body: file,
            headers: { 'Content-Type': file.type || 'application/json' },
          })
          if (!uploadResponse.ok) throw new Error('Failed to upload sweep file')
          paths.push(s3_key)
        }
        sweepConfig = { seed_data_path: paths }
      } else if (data.sweepType === 'num_records') {
        sweepConfig = { num_records: sweepValues }
      } else {
        sweepConfig = { model_tier: sweepValues }
      }

      const result = await createBatch({
        name: data.name,
        template_id: data.templateId,
        template_version: data.templateVersion,
        seed_data_path: seedDataPath,
        base_config: {
          budget_limit: data.budgetLimit,
          num_records: data.numRecords,
          output_format: data.outputFormat,
        },
        sweep: sweepConfig,
      })

      navigate(`/jobs/batches/${result.batch_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create batch')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Create Batch Job</h1>

      {/* Step Indicator */}
      <div className="flex items-center justify-between mb-8">
        {[1, 2, 3, 4, 5].map((s) => (
          <div key={s} className="flex items-center flex-1">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                s <= step ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}
            >
              {s}
            </div>
            {s < 5 && (
              <div className={`flex-1 h-1 mx-2 ${s < step ? 'bg-blue-600' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg shadow-md p-6">
        {/* Step 1: Template Selection */}
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Select Template</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Batch Name</label>
              <input
                type="text"
                value={data.name}
                onChange={(e) => setData({ ...data, name: e.target.value })}
                placeholder="e.g., A/B test: model comparison"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Template ID</label>
              <input
                type="text"
                value={data.templateId}
                onChange={(e) => setData({ ...data, templateId: e.target.value })}
                placeholder="Enter template ID"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Template Version</label>
              <input
                type="number"
                min="1"
                value={data.templateVersion}
                onChange={(e) => setData({ ...data, templateVersion: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          </div>
        )}

        {/* Step 2: Seed Data */}
        {step === 2 && data.sweepType !== 'seed_data_path' && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Upload Seed Data</h2>
            <input
              type="file"
              accept=".csv,.jsonl,.json"
              onChange={(e) => setData({ ...data, seedDataFile: e.target.files?.[0] || null })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
            {data.seedDataFile && (
              <p className="text-sm text-green-600">Selected: {data.seedDataFile.name}</p>
            )}
          </div>
        )}

        {step === 2 && data.sweepType === 'seed_data_path' && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Upload Multiple Seed Data Files</h2>
            <input
              type="file"
              accept=".csv,.jsonl,.json"
              multiple
              onChange={(e) => setData({ ...data, seedDataFiles: Array.from(e.target.files || []) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
            {data.seedDataFiles.length > 0 && (
              <p className="text-sm text-green-600">
                Selected: {data.seedDataFiles.map((f) => f.name).join(', ')}
              </p>
            )}
          </div>
        )}

        {/* Step 3: Base Configuration */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Base Configuration</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Budget Limit ($)</label>
              <input
                type="number"
                min="1"
                max="1000"
                value={data.budgetLimit}
                onChange={(e) => setData({ ...data, budgetLimit: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Number of Records</label>
              <input
                type="number"
                min="1"
                max="10000"
                value={data.numRecords}
                onChange={(e) => setData({ ...data, numRecords: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Output Format</label>
              <select
                value={data.outputFormat}
                onChange={(e) => setData({ ...data, outputFormat: e.target.value as 'JSONL' | 'CSV' | 'PARQUET' })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="JSONL">JSONL</option>
                <option value="CSV">CSV</option>
                <option value="PARQUET">Parquet</option>
              </select>
            </div>
          </div>
        )}

        {/* Step 4: Sweep Configuration */}
        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Configure Sweep</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Vary By</label>
              <select
                value={data.sweepType}
                onChange={(e) => setData({ ...data, sweepType: e.target.value as BatchWizardData['sweepType'] })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="model_tier">Model Tier</option>
                <option value="seed_data_path">Seed Data</option>
                <option value="num_records">Record Count</option>
              </select>
            </div>

            {data.sweepType === 'model_tier' && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">Select Model Tiers</label>
                {MODEL_TIER_OPTIONS.map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={data.modelTiers.includes(opt.value)}
                      onChange={(e) => {
                        const tiers = e.target.checked
                          ? [...data.modelTiers, opt.value]
                          : data.modelTiers.filter((t) => t !== opt.value)
                        setData({ ...data, modelTiers: tiers })
                      }}
                    />
                    <span className="text-sm">{opt.label}</span>
                  </label>
                ))}
              </div>
            )}

            {data.sweepType === 'num_records' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Record Counts (comma-separated)
                </label>
                <input
                  type="text"
                  value={data.recordCounts}
                  onChange={(e) => setData({ ...data, recordCounts: e.target.value })}
                  placeholder="50, 100, 500"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            )}

            {data.sweepType === 'seed_data_path' && (
              <p className="text-sm text-gray-600">
                Seed data files will be uploaded in Step 2. Go back to upload multiple files.
              </p>
            )}

            <p className="text-sm text-gray-500">
              This will create <strong>{getJobCount()}</strong> jobs
            </p>
          </div>
        )}

        {/* Step 5: Review */}
        {step === 5 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold mb-4">Review & Create</h2>
            <div className="bg-gray-50 p-4 rounded space-y-2">
              <div className="flex justify-between">
                <span className="font-medium">Batch Name:</span>
                <span>{data.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Template:</span>
                <span>{data.templateId} (v{data.templateVersion})</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Budget per Job:</span>
                <span>${data.budgetLimit}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Sweep Type:</span>
                <span>{data.sweepType.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Jobs to Create:</span>
                <span>{getJobCount()}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Sweep Values:</span>
                <span className="text-right max-w-xs truncate">
                  {getSweepValues().join(', ')}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-6 pt-6 border-t">
          <button
            onClick={() => {
              if (step > 1) setStep(step - 1)
              else navigate('/dashboard')
            }}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            {step === 1 ? 'Cancel' : 'Previous'}
          </button>

          {step < 5 ? (
            <button
              onClick={() => setStep(step + 1)}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? 'Creating...' : `Create ${getJobCount()} Jobs`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
