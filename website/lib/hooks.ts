'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { ApiAgent, ApiHealth, ApiAuditEvent, ApiQueueItem, ApiRegistration } from './api-types'

// ─── Generic polling hook ─────────────────────────────────────────────────────

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
): { data: T | null; error: string | null; loading: boolean; refresh: () => void } {
  const [data, setData]       = useState<T | null>(null)
  const [error, setError]     = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const mountedRef             = useRef(true)
  const timerRef               = useRef<ReturnType<typeof setInterval> | null>(null)

  const run = useCallback(async () => {
    try {
      const result = await fetcher()
      if (mountedRef.current) { setData(result); setError(null) }
    } catch (e) {
      if (mountedRef.current)
        setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  // intentionally omitting fetcher from deps — callers pass stable references
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    mountedRef.current = true
    run()
    timerRef.current = setInterval(run, intervalMs)
    return () => {
      mountedRef.current = false
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [run, intervalMs])

  return { data, error, loading, refresh: run }
}

// ─── Specific hooks (cadences per UI-Team.md §7) ──────────────────────────────

/** GET /health — every 30 s */
export function useHealth() {
  return usePolling<ApiHealth>(() => api.health(), 30_000)
}

/** GET /agents — every 15 s, uses MANAGER credentials */
export function useAgents() {
  return usePolling<ApiAgent[]>(() => api.agents.list(), 15_000)
}

/** GET /audit — every 8 s */
export function useAudit(limit = 20) {
  return usePolling<ApiAuditEvent[]>(() => api.audit.list(limit), 8_000)
}

/** GET /registrations — every 12 s (admin screen) */
export function useRegistrations(status?: string) {
  return usePolling<ApiRegistration[]>(() => api.registrations.list(status), 12_000)
}

/**
 * GET /queue/{recipient} — every 4 s (active agent queue view).
 * Skips fetching when apiKey is empty (API offline / not yet configured).
 */
export function useQueue(recipient: string, apiKey: string) {
  const enabled = Boolean(recipient && apiKey)
  const fetcher = useCallback(
    () => enabled
      ? api.queue.list(recipient, apiKey)
      : Promise.resolve([] as ApiQueueItem[]),
    [recipient, apiKey, enabled]
  )
  return usePolling<ApiQueueItem[]>(fetcher, 4_000)
}
