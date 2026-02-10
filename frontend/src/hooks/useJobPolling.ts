import { useQuery } from '@tanstack/react-query'
import { fetchJobDetails } from '../services/api'
import type { Job } from '../services/api'

export function useJobPolling(jobId: string) {
  return useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: () => fetchJobDetails(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'RUNNING') {
        return 5000
      }
      if (status === 'QUEUED') {
        return 15000 // Slower polling for queued jobs
      }
      return false // Don't poll if job is complete
    },
    refetchIntervalInBackground: false,
  })
}
