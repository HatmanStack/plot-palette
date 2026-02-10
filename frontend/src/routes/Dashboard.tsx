import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useJobs } from '../hooks/useJobs'
import JobCard from '../components/JobCard'
import { deleteJob } from '../services/api'

type FilterType = 'ALL' | 'RUNNING' | 'COMPLETED' | 'FAILED'
type SortType = 'created' | 'status' | 'cost'

export default function Dashboard() {
  const { data: jobs, isLoading, error, refetch } = useJobs()
  const [filter, setFilter] = useState<FilterType>('ALL')
  const [sort, setSort] = useState<SortType>('created')

  const filteredAndSortedJobs = useMemo(() => {
    if (!jobs) return []

    let filtered = jobs

    // Apply filter
    if (filter !== 'ALL') {
      filtered = jobs.filter((job) => job.status === filter)
    }

    // Apply sort
    const sorted = [...filtered].sort((a, b) => {
      switch (sort) {
        case 'created':
          return new Date(b['created_at']).getTime() - new Date(a['created_at']).getTime()
        case 'status':
          return a.status.localeCompare(b.status)
        case 'cost':
          return b['cost_estimate'] - a['cost_estimate']
        default:
          return 0
      }
    })

    return sorted
  }, [jobs, filter, sort])

  async function handleDelete(jobId: string) {
    if (confirm('Are you sure you want to delete this job?')) {
      try {
        await deleteJob(jobId)
        refetch()
      } catch (err) {
        console.error('Failed to delete job:', err)
      }
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-xl text-gray-600">Loading jobs...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
        Error loading jobs: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <Link
          to="/jobs/new"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
        >
          + Create New Job
        </Link>
      </div>

      {/* Filters and Sorting */}
      <div className="bg-white rounded-lg shadow p-4 mb-6 flex gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Filter:</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as FilterType)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
          >
            <option value="ALL">All Jobs</option>
            <option value="RUNNING">Running</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Sort by:</label>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortType)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
          >
            <option value="created">Created Date</option>
            <option value="status">Status</option>
            <option value="cost">Cost</option>
          </select>
        </div>

        <div className="ml-auto text-sm text-gray-600">
          Showing {filteredAndSortedJobs.length} of {jobs?.length || 0} jobs
        </div>
      </div>

      {/* Job List */}
      {filteredAndSortedJobs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500 text-lg mb-4">No jobs found</p>
          <Link
            to="/jobs/new"
            className="inline-block px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Create Your First Job
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAndSortedJobs.map((job) => (
            <JobCard key={job['job_id']} job={job} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
