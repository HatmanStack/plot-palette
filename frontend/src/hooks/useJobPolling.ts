import { useQuery } from '@tanstack/react-query'
import { fetchJobDetails } from '../services/api'
import type { Job } from '../services/api'

/**
 * Hook for polling job details. When enablePolling is false (SSE active),
 * only fetches initial data without interval refetch.
 */
export function useJobPolling(jobId: string, enablePolling: boolean = true) {
  return useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: () => fetchJobDetails(jobId),
    refetchInterval: enablePolling
      ? (query) => {
          const status = query.state.data?.status
          if (status === 'RUNNING') {
            return 5000
          }
          if (status === 'QUEUED') {
            return 15000 // Slower polling for queued jobs
          }
          return false // Don't poll if job is complete
        }
      : false,
    refetchIntervalInBackground: false,
  })
}
