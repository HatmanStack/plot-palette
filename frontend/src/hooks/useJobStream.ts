import { useEffect, useRef, useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import type { Job } from '../services/api'

const TERMINAL_STATUSES = new Set(['COMPLETED', 'FAILED', 'BUDGET_EXCEEDED', 'CANCELLED'])
const MAX_ERRORS = 3

interface UseJobStreamResult {
  isConnected: boolean
  error: Error | null
  useFallbackPolling: boolean
}

export function useJobStream(jobId: string): UseJobStreamResult {
  const queryClient = useQueryClient()
  const { idToken } = useAuth()
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [useFallbackPolling, setUseFallbackPolling] = useState(false)
  const errorCountRef = useRef(0)
  const esRef = useRef<EventSource | null>(null)

  const cleanup = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    // Don't connect if no token or job is terminal
    const currentJob = queryClient.getQueryData<Job>(['job', jobId])
    if (currentJob && TERMINAL_STATUSES.has(currentJob.status)) {
      return
    }

    if (!idToken) {
      return
    }

    const apiEndpoint = import.meta.env.VITE_API_ENDPOINT || ''
    const url = `${apiEndpoint}/jobs/${jobId}/stream?token=${encodeURIComponent(idToken)}`

    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => {
      setIsConnected(true)
      setError(null)
      errorCountRef.current = 0
    }

    es.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        // Update React Query cache
        queryClient.setQueryData(['job', jobId], (old: Job | undefined) => {
          if (!old) return old
          return { ...old, ...data }
        })

        // Close if terminal
        if (data.status && TERMINAL_STATUSES.has(data.status)) {
          cleanup()
        }
      } catch {
        // Ignore parse errors
      }
    }

    es.addEventListener('complete', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        queryClient.setQueryData(['job', jobId], (old: Job | undefined) => {
          if (!old) return old
          return { ...old, ...data }
        })
      } catch {
        // Ignore parse errors
      }
      cleanup()
    })

    es.onerror = () => {
      setIsConnected(false)
      errorCountRef.current += 1
      setError(new Error('Connection lost'))

      if (errorCountRef.current >= MAX_ERRORS) {
        cleanup()
        setUseFallbackPolling(true)
      }
    }

    return cleanup
  }, [jobId, idToken, queryClient, cleanup])

  return { isConnected, error, useFallbackPolling }
}
