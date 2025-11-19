import { useQuery } from '@tanstack/react-query'
import { fetchJobDetails } from '../services/api'
import type { Job } from '../services/api'

export function useJobPolling(jobId: string) {
  return useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: () => fetchJobDetails(jobId),
    refetchInterval: (query) => {
      // Poll every 5 seconds if job is RUNNING or QUEUED
      const status = query.state.data?.status
      if (status === 'RUNNING' || status === 'QUEUED') {
        return 5000
      }
      return false // Don't poll if job is complete
    },
  })
}
