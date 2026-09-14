'use client'

import { motion } from 'framer-motion'
import { Network, Crown, Code2, FlaskConical, CheckCircle2, XCircle, Loader2, GraduationCap } from 'lucide-react'
import { useAudit } from '@/lib/hooks'
import { auditToSwarmRuns, auditToLessons, type SwarmStep } from '@/lib/live-metrics'

const ROLE_ICON: Record<string, React.ReactNode> = {
  'Lead Developer': <Crown size={13} />,
  'Software Developer': <Code2 size={13} />,
  'Testing Engineer': <FlaskConical size={13} />,
}
const ROLE_COLOR: Record<string, string> = {
  'Lead Developer': 'var(--amber)',
  'Software Developer': 'var(--agent-engineering)',
  'Testing Engineer': 'var(--sky)',
}

const PHASE_LABEL: Record<string, string> = {
  build_started: 'Started the build',
  planned: 'Wrote the development plan',
  files_identified: 'Identified files to create',
  wrote_file: 'Wrote a file',
  wrote_tests: 'Wrote the test suite',
  ran_tests: 'Ran the test suite',
  build_succeeded: 'Build succeeded',
  build_failed: 'Build failed — out of fix attempts',
}

function phaseLabel(step: SwarmStep): string {
  if (PHASE_LABEL[step.phase]) return PHASE_LABEL[step.phase]
  const m = step.phase.match(/^(reviewed_failure|fixed_file|rewrote_tests|ran_tests)_iter_(\d+)$/)
  if (m) {
    const [, kind, n] = m
    const label: Record<string, string> = {
      reviewed_failure: `Reviewed the failure (fix attempt ${n})`,
      fixed_file: `Rewrote a file (fix attempt ${n})`,
      rewrote_tests: `Rewrote the test suite (fix attempt ${n})`,
      ran_tests: `Re-ran the test suite (fix attempt ${n})`,
    }
    return label[kind] ?? step.phase
  }
  return step.phase
}

const STATUS_STYLE: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  running:   { color: 'var(--sky)',   icon: <Loader2 size={11} className="animate-spin" />, label: 'in progress' },
  succeeded: { color: 'var(--green)', icon: <CheckCircle2 size={11} />, label: 'succeeded' },
  failed:    { color: 'var(--red)',   icon: <XCircle size={11} />, label: 'failed' },
}

export default function SwarmPage() {
  const { data: audit, error } = useAudit(300)
  const runs = auditToSwarmRuns(audit, 15)
  const lessons = auditToLessons(audit)
  const lessonsByRole = Object.keys(ROLE_ICON)
    .map(role => ({ role, rules: lessons.filter(l => l.role === role) }))
    .filter(g => g.rules.length > 0)

  return (
    <div className="p-6 max-w-[1000px] mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="mb-5"
      >
        <div className="flex items-center gap-2 mb-1">
          <Network size={16} style={{ color: 'var(--primary-2)' }} />
          <h1 className="text-[18px] font-semibold" style={{ color: 'var(--text-1)' }}>Agent Swarm</h1>
        </div>
        <p className="text-[12px] leading-relaxed max-w-[70ch]" style={{ color: 'var(--text-3)' }}>
          What actually collaborates to build a feature: not new top-level company agents spawning (the
          department roster is fixed), but three specialized CrewAI roles inside Engineering &mdash; a{' '}
          <b style={{ color: 'var(--text-2)' }}>Lead Developer</b> that plans and reviews, a{' '}
          <b style={{ color: 'var(--text-2)' }}>Software Developer</b> that writes code, and a{' '}
          <b style={{ color: 'var(--text-2)' }}>Testing Engineer</b> that writes and runs tests &mdash;
          handing work back and forth, including a real feedback loop when tests fail. Pulled live from
          the router&apos;s own audit log.
        </p>
      </motion.div>

      {lessonsByRole.length > 0 && (
        <div className="card p-5 mb-5">
          <div className="flex items-center gap-2 mb-1">
            <GraduationCap size={14} style={{ color: 'var(--primary-2)' }} />
            <h2 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Lessons Learned</h2>
          </div>
          <p className="text-[11px] leading-relaxed mb-4 max-w-[70ch]" style={{ color: 'var(--text-3)' }}>
            Not model fine-tuning &mdash; the local models are never retrained. Whenever a role is caught
            provably violating one of its own instructions (a tab used instead of a comma, a test file not
            put last, a test run failing with a specific error), that mistake is recorded here and fed back
            into that same role&apos;s own future prompts, so it doesn&apos;t keep repeating it.
          </p>
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${lessonsByRole.length}, 1fr)` }}>
            {lessonsByRole.map(({ role, rules }) => {
              const color = ROLE_COLOR[role] ?? 'var(--text-3)'
              return (
                <div key={role}>
                  <div className="flex items-center gap-1.5 mb-2" style={{ color }}>
                    {ROLE_ICON[role]}
                    <span className="text-[11.5px] font-semibold">{role}</span>
                  </div>
                  <ul className="flex flex-col gap-1.5">
                    {rules.map(l => (
                      <li key={l.rule} className="text-[10.5px] leading-relaxed px-2 py-1.5 rounded-md" style={{ color: 'var(--text-2)', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
                        {l.rule}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-4">
        {runs.length === 0 && (
          <div className="card p-8 text-center text-[12px] leading-relaxed" style={{ color: 'var(--text-3)' }}>
            {error
              ? 'Unable to load swarm activity from the router.'
              : <>No swarm activity yet. Send a build request &mdash; e.g. <code style={{ fontFamily: 'var(--font-mono)' }}>/eng &lt;request&gt;</code> in
                  Chat, with Engineering running in full (non-light-demo) mode &mdash; and the real Lead Developer /
                  Software Developer / Testing Engineer collaboration will appear here as it happens.</>
            }
          </div>
        )}

        {runs.map(run => {
          const style = STATUS_STYLE[run.status]
          return (
            <div key={run.runId} className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-[12px] font-mono" style={{ color: 'var(--text-3)' }}>{run.runId}</span>
                  <span className="badge flex items-center gap-1" style={{ color: style.color, borderColor: 'transparent', background: 'rgba(255,255,255,0.04)' }}>
                    {style.icon}{style.label}
                  </span>
                </div>
                <span className="text-[10.5px] font-mono" style={{ color: 'var(--text-3)' }}>
                  {new Date(run.startedAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>

              <div className="flex flex-col gap-3">
                {run.steps.map((step, i) => {
                  const color = ROLE_COLOR[step.role] ?? 'var(--text-3)'
                  return (
                    <div key={step.id} className="flex gap-3">
                      <div className="flex flex-col items-center flex-shrink-0">
                        <div
                          className="w-6 h-6 rounded-md flex items-center justify-center"
                          style={{ background: `${color}1c`, border: `1px solid ${color}35`, color }}
                        >
                          {ROLE_ICON[step.role] ?? <Network size={12} />}
                        </div>
                        {i < run.steps.length - 1 && <div style={{ width: 1, flex: 1, background: 'var(--border)', marginTop: 4 }} />}
                      </div>
                      <div className="min-w-0 flex-1 pb-1">
                        <div className="flex items-baseline gap-2 flex-wrap">
                          <span className="text-[11.5px] font-semibold" style={{ color: 'var(--text-1)' }}>{step.role}</span>
                          <span className="text-[11px]" style={{ color: 'var(--text-2)' }}>{phaseLabel(step)}</span>
                          <span className="text-[10px] font-mono ml-auto" style={{ color: 'var(--text-3)' }}>
                            {new Date(step.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </span>
                        </div>
                        {step.detail && (
                          <div
                            className="text-[11px] mt-1 px-2.5 py-1.5 rounded-md"
                            style={{
                              color: step.phase.includes('failed') || step.detail.startsWith('failed') ? 'var(--red)' : 'var(--text-3)',
                              background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
                              fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                            }}
                          >
                            {step.detail}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
