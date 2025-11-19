import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createJob } from '../services/api'

interface WizardData {
  templateId: string
  seedDataFile: File | null
  budgetLimit: number
  numRecords: number
  outputFormat: 'JSONL' | 'CSV' | 'PARQUET'
}

export default function CreateJob() {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const [data, setData] = useState<WizardData>({
    templateId: '',
    seedDataFile: null,
    budgetLimit: 10,
    numRecords: 100,
    outputFormat: 'JSONL',
  })

  async function handleSubmit() {
    if (!data.templateId || !data.seedDataFile) {
      setError('Please complete all required fields')
      return
    }

    setLoading(true)
    setError('')

    try {
      // In a real implementation, we would:
      // 1. Upload seed data to S3 via presigned URL
      // 2. Get the S3 key
      // 3. Create the job with that key

      const seedDataKey = `seed-data/user-id/${data.seedDataFile.name}`

      const job = await createJob({
        'template-id': data.templateId,
        'seed-data-key': seedDataKey,
        'budget-limit': data.budgetLimit,
        'num-records': data.numRecords,
        'output-format': data.outputFormat,
      })

      navigate(`/jobs/${job['job-id']}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create job')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Create New Job</h1>

      {/* Step Indicator */}
      <div className="flex items-center justify-between mb-8">
        {[1, 2, 3, 4].map((s) => (
          <div key={s} className="flex items-center flex-1">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                s <= step
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-600'
              }`}
            >
              {s}
            </div>
            {s < 4 && (
              <div
                className={`flex-1 h-1 mx-2 ${
                  s < step ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              />
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
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Template ID
              </label>
              <input
                type="text"
                value={data.templateId}
                onChange={(e) => setData({ ...data, templateId: e.target.value })}
                placeholder="Enter template ID"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="text-sm text-gray-500 mt-1">
                Enter a template ID or select from the templates page
              </p>
            </div>
          </div>
        )}

        {/* Step 2: Seed Data Upload */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Upload Seed Data</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Seed Data File (CSV or JSONL)
              </label>
              <input
                type="file"
                accept=".csv,.jsonl,.json"
                onChange={(e) =>
                  setData({ ...data, seedDataFile: e.target.files?.[0] || null })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              {data.seedDataFile && (
                <p className="text-sm text-green-600 mt-2">
                  Selected: {data.seedDataFile.name}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Step 3: Configuration */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">Job Configuration</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Budget Limit ($)
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={data.budgetLimit}
                onChange={(e) =>
                  setData({ ...data, budgetLimit: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <input
                type="range"
                min="1"
                max="100"
                value={data.budgetLimit}
                onChange={(e) =>
                  setData({ ...data, budgetLimit: Number(e.target.value) })
                }
                className="w-full mt-2"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Number of Records
              </label>
              <input
                type="number"
                min="1"
                max="10000"
                value={data.numRecords}
                onChange={(e) =>
                  setData({ ...data, numRecords: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Output Format
              </label>
              <select
                value={data.outputFormat}
                onChange={(e) =>
                  setData({ ...data, outputFormat: e.target.value as 'JSONL' | 'CSV' | 'PARQUET' })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="JSONL">JSONL</option>
                <option value="CSV">CSV</option>
                <option value="PARQUET">Parquet</option>
              </select>
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold mb-4">Review & Create</h2>

            <div className="bg-gray-50 p-4 rounded space-y-2">
              <div className="flex justify-between">
                <span className="font-medium">Template:</span>
                <span>{data.templateId}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Seed Data:</span>
                <span>{data.seedDataFile?.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Budget:</span>
                <span>${data.budgetLimit}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Records:</span>
                <span>{data.numRecords}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Format:</span>
                <span>{data.outputFormat}</span>
              </div>
            </div>

            <p className="text-sm text-gray-600">
              Estimated cost: ${(data.numRecords * 0.01).toFixed(2)} - ${(data.numRecords * 0.05).toFixed(2)}
            </p>
          </div>
        )}

        {/* Navigation Buttons */}
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

          {step < 4 ? (
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
              {loading ? 'Creating...' : 'Create Job'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
