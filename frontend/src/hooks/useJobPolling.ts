import { useCallback, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchJobDetails } from '../services/api'
import type { Job } from '../services/api'

const MAX_POLL_COUNT = 300 // At 5s intervals = ~25 minutes max

// Module-level poll tracking keyed by jobId
const pollCounts = new Map<string, number>()

/**
 * Hook for polling job details. When enablePolling is false (SSE active),
 * only fetches initial data without interval refetch.
 *
 * Stops polling after MAX_POLL_COUNT iterations to prevent infinite
 * polling on corrupt or stuck job status.
 */
export function useJobPolling(jobId: string, enablePolling: boolean = true) {
  const [pollTimedOut, setPollTimedOut] = useState(false)

  // Initialize poll count for this job if not present
  if (!pollCounts.has(jobId)) {
    pollCounts.set(jobId, 0)
  }

  const handleRefetchInterval = useCallback(
    (queryResult: { state: { data: Job | undefined } }) => {
      const status = queryResult.state.data?.status

      // Don't increment counter for terminal statuses
      if (
        status === 'COMPLETED' ||
        status === 'FAILED' ||
        status === 'CANCELLED' ||
        status === 'BUDGET_EXCEEDED'
      ) {
        return false
      }

      // Increment poll count and check limit
      const count = (pollCounts.get(jobId) ?? 0) + 1
      pollCounts.set(jobId, count)

      if (count >= MAX_POLL_COUNT) {
        setPollTimedOut(true)
        return false
      }

      if (status === 'RUNNING') {
        return 5000
      }
      if (status === 'QUEUED') {
        return 15000 // Slower polling for queued jobs
      }
      return false // Don't poll if job is complete
    },
    [jobId]
  )

  const query = useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: () => fetchJobDetails(jobId),
    refetchInterval:
      enablePolling && !pollTimedOut ? handleRefetchInterval : false,
    refetchIntervalInBackground: false,
  })

  return { ...query, pollTimedOut }
}
