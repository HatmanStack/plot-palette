import { useQuery } from '@tanstack/react-query'
import { fetchJobs } from '../services/api'

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
    staleTime: 5000,
  })
}
