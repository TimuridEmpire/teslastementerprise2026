'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Code2, FileText, CheckCircle2, XCircle, Clock, Play, Square, ExternalLink, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { usePolling } from '@/lib/hooks'
import { artifactLabel } from '@/lib/live-metrics'
import type { ApiArtifact, ApiBuildRun } from '@/lib/api-types'

const STATUS_STYLE: Record<string, { color: string; icon: React.ReactNode }> = {
  success:     { color: 'var(--green)', icon: <CheckCircle2 size={11} /> },
  failed:      { color: 'var(--red)',   icon: <XCircle size={11} /> },
  light_demo:  { color: 'var(--sky)',   icon: <FileText size={11} /> },
}

function statusOf(a: ApiArtifact): string {
  return String(a.metadata?.status ?? 'unknown')
}

// Every engineering-type artifact carries the full source of every file it
// generated, embedded as fenced code blocks under "## Generated Source" --
// see engineering_agent.py's _artifact_body(). This page is the one place
// in the control plane where every past build's actual code is browsable,
// independent of whatever OUTPUT_DIR on disk currently holds (it gets wiped
// and reused for every new build, so disk is not durable storage for this).
export default function BuildsPage() {
  const fetchBuilds = useCallback(
    () => api.artifacts.list(undefined, 50).then(rows => rows.filter(a => a.artifact_type === 'engineering')),
    [],
  )
  const { data: artifacts, error } = usePolling<ApiArtifact[]>(fetchBuilds, 8_000)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [fetched, setFetched] = useState<Record<string, ApiArtifact>>({})
  const [fetchError, setFetchError] = useState('')
  const [runs, setRuns] = useState<Record<string, ApiBuildRun>>({})
  const [runPending, setRunPending] = useState<string | null>(null)
  const [runError, setRunError] = useState('')

  const list = artifacts ?? []
  const effectiveId = selectedId ?? list[0]?.artifact_id ?? null

  // Poll active runs so a run started from a previous page load (or that
  // just auto-reaped after its 30-minute cap) stays in sync with reality.
  useEffect(() => {
    let cancelled = false
    const poll = () => api.builds.running().then(rows => {
      if (cancelled) return
      setRuns(Object.fromEntries(rows.map(r => [r.artifact_id, r])))
    }).catch(() => {})
    poll()
    const id = setInterval(poll, 5_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  async function handleRun(artifactId: string) {
    setRunPending(artifactId)
    setRunError('')
    try {
      const run = await api.builds.run(artifactId)
      setRuns(prev => ({ ...prev, [artifactId]: run }))
    } catch (e) {
      setRunError(e instanceof Error ? e.message : 'Failed to start this build.')
    } finally {
      setRunPending(null)
    }
  }

  async function handleStop(artifactId: string) {
    setRunPending(artifactId)
    try {
      await api.builds.stop(artifactId)
    } finally {
      setRuns(prev => { const next = { ...prev }; delete next[artifactId]; return next })
      setRunPending(null)
    }
  }

  useEffect(() => {
    if (!effectiveId || fetched[effectiveId]) return
    setFetchError('')
    api.artifacts.get(effectiveId)
      .then(full => setFetched(prev => ({ ...prev, [effectiveId]: full })))
      .catch(() => setFetchError('Unable to load this build from the router.'))
  }, [effectiveId, fetched])

  const selected = effectiveId ? fetched[effectiveId] ?? list.find(a => a.artifact_id === effectiveId) ?? null : null

  return (
    <div className="p-6 max-w-[1600px] mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="mb-5"
      >
        <div className="flex items-center gap-2 mb-1">
          <Code2 size={16} style={{ color: 'var(--primary-2)' }} />
          <h1 className="text-[18px] font-semibold" style={{ color: 'var(--text-1)' }}>Builds</h1>
        </div>
        <p className="text-[12px]" style={{ color: 'var(--text-3)' }}>
          Every feature the Engineering agent has built, with the actual generated source code --
          not just a status record. Pulled live from the router&apos;s artifact store.
        </p>
      </motion.div>

      <div
        className="card p-3 mb-5 text-[11px] leading-relaxed"
        style={{ background: 'rgba(251,191,36,0.05)', border: '1px solid rgba(251,191,36,0.2)', color: 'var(--text-2)' }}
      >
        <strong style={{ color: 'var(--amber)' }}>Run</strong> executes this build&apos;s generated code, unreviewed,
        as a real local process on this machine (a small auto-reflection server calls whatever class/methods
        Engineering wrote). It is not sandboxed beyond running as its own subprocess bound to localhost.
        Only run builds you trust.
      </div>

      <div className="grid gap-5" style={{ gridTemplateColumns: 'minmax(280px, 340px) 1fr' }}>
        {/* Build list */}
        <div className="card p-3">
          <div className="flex items-center justify-between px-2 py-1.5 mb-1">
            <span className="text-[10.5px] font-mono uppercase tracking-wide" style={{ color: 'var(--text-3)' }}>
              {list.length} {list.length === 1 ? 'build' : 'builds'}
            </span>
            <span className="text-[10.5px] font-mono" style={{ color: list.length ? 'var(--green)' : 'var(--text-3)' }}>
              {list.length ? 'live' : 'waiting'}
            </span>
          </div>
          <div className="flex flex-col gap-1 max-h-[70vh] overflow-auto">
            {list.length === 0 && (
              <div className="text-[11px] px-2 py-6 text-center" style={{ color: 'var(--text-3)' }}>
                {error ? 'Unable to load builds from the router.' : 'No builds yet.'}
              </div>
            )}
            {list.map(a => {
              const isSelected = a.artifact_id === effectiveId
              const status = statusOf(a)
              const style = STATUS_STYLE[status]
              return (
                <button
                  key={a.artifact_id}
                  onClick={() => setSelectedId(a.artifact_id)}
                  className="text-left px-2.5 py-2 rounded-md flex items-start gap-2"
                  style={{
                    background: isSelected ? 'rgba(255,255,255,0.06)' : 'transparent',
                    border: `1px solid ${isSelected ? 'var(--border)' : 'transparent'}`,
                  }}
                >
                  <span style={{ color: style?.color ?? 'var(--text-3)', marginTop: 2, flexShrink: 0 }}>
                    {style?.icon ?? <Clock size={11} />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <div className="text-[11.5px] font-mono truncate" style={{ color: isSelected ? 'var(--text-1)' : 'var(--text-2)' }}>
                      {artifactLabel(a)}
                    </div>
                    <div className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-3)' }}>
                      {a.agent_name} · {new Date(a.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Build detail */}
        <div className="card p-5">
          {selected ? (
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>{selected.title}</div>
                  <div className="text-[10.5px] font-mono mt-1 flex flex-wrap gap-x-2 gap-y-1" style={{ color: 'var(--text-3)' }}>
                    <span>{selected.agent_name}</span>
                    <span>·</span>
                    <span>{new Date(selected.created_at).toLocaleString()}</span>
                    {selected.source_task_type && (<><span>·</span><span>{selected.source_task_type}</span></>)}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {(() => {
                    const status = statusOf(selected)
                    const style = STATUS_STYLE[status]
                    return (
                      <span
                        className="badge flex items-center gap-1"
                        style={{ color: style?.color ?? 'var(--text-3)', borderColor: 'transparent', background: 'rgba(255,255,255,0.04)' }}
                      >
                        {style?.icon}{status}
                      </span>
                    )
                  })()}
                  {effectiveId && runs[effectiveId]?.running ? (
                    <>
                      <a
                        href={runs[effectiveId].url} target="_blank" rel="noreferrer"
                        className="badge flex items-center gap-1"
                        style={{ color: 'var(--green)', borderColor: 'transparent', background: 'rgba(52,211,153,0.10)' }}
                      >
                        <ExternalLink size={11} />open :{runs[effectiveId].port}
                      </a>
                      <button
                        onClick={() => handleStop(effectiveId)}
                        disabled={runPending === effectiveId}
                        className="badge flex items-center gap-1 cursor-pointer"
                        style={{ color: 'var(--red)', borderColor: 'transparent', background: 'rgba(248,113,113,0.10)' }}
                      >
                        <Square size={11} />stop
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => effectiveId && handleRun(effectiveId)}
                      disabled={!effectiveId || runPending === effectiveId}
                      className="badge flex items-center gap-1 cursor-pointer"
                      style={{ color: 'var(--primary-2)', borderColor: 'transparent', background: 'rgba(255,255,255,0.06)' }}
                    >
                      {runPending === effectiveId ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                      run
                    </button>
                  )}
                </div>
              </div>
              {effectiveId && runs[effectiveId]?.init_error && (
                <div className="text-[11px] px-3 py-2 rounded-lg" style={{ color: 'var(--amber)', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.25)' }}>
                  Hosted, but couldn&apos;t auto-instantiate a class to call: {runs[effectiveId].init_error}
                </div>
              )}
              {runError && (
                <div className="text-[11px] px-3 py-2 rounded-lg" style={{ color: 'var(--red)', background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.25)' }}>
                  {runError}
                </div>
              )}
              <pre
                className="rounded-lg p-3 text-[11px] leading-relaxed overflow-auto"
                style={{
                  maxHeight: '65vh',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  color: 'var(--text-2)',
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid var(--border)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {fetchError || selected.content || 'Loading full build content…'}
              </pre>
            </div>
          ) : (
            <div className="text-[11px] text-center py-16" style={{ color: 'var(--text-3)' }}>
              Select a build to view its spec and generated source.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
