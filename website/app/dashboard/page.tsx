'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, Layers, GitBranch, TrendingUp,
  Crown, Package, Code2, Users, DollarSign, Megaphone,
  FileText, Download,
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell, RadialBarChart, RadialBar,
  CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import { AGENTS, TASK_THROUGHPUT } from '@/lib/mock-data'
import { useHealth, useAudit, useQueue, useArtifacts } from '@/lib/hooks'
import { auditToThroughput, auditToAgentStats, auditToMessageFlow, type AgentStat } from '@/lib/live-metrics'
import { downloadArtifactsReportPdf, getLastReportGeneratedAt } from '@/lib/memory'
import type { AgentId } from '@/lib/types'
import type { ApiArtifact, ApiAuditEvent, ApiQueueItem } from '@/lib/api-types'

// No router/agent surface reports revenue, budget, or sales-pipeline data
// (see README "Live vs Mock Data") — Finance and Sales have no worker
// implementation in this repo. Rather than show fabricated numbers next to
// genuinely live ones, those panels are replaced with an explicit
// "not available" notice below.
function NotAvailablePanel({ title, subtitle, reason }: { title: string; subtitle: string; reason: string }) {
  return (
    <div className="card" style={{ padding: 22 }}>
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>{title}</div>
        <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{subtitle}</div>
      </div>
      <div style={{
        padding: 24, textAlign: 'center', color: 'var(--text-3)', fontSize: 12, lineHeight: 1.6,
        border: '1px dashed var(--border)', borderRadius: 8, background: 'rgba(255,255,255,0.015)',
      }}>
        {reason}
      </div>
    </div>
  )
}

// ─── Agent icon map ────────────────────────────────────────────────────────
const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={13} />, product: <Package size={13} />, engineering: <Code2 size={13} />,
  hr: <Users size={13} />, sales: <TrendingUp size={13} />, marketing: <Megaphone size={13} />,
  finance: <DollarSign size={13} />,
}
const AGENT_COLOR: Record<AgentId, string> = {
  ceo: 'var(--agent-ceo)', product: 'var(--agent-product)', engineering: 'var(--agent-engineering)',
  hr: 'var(--agent-hr)', sales: 'var(--agent-sales)', marketing: 'var(--agent-marketing)', finance: 'var(--agent-finance)',
}
// Router-side agent names (as they appear in ApiArtifact.agent_name) mapped
// to the website's UI AgentId, for icon/color lookups on live artifacts.
const ROUTER_NAME_TO_AGENT_ID: Record<string, AgentId> = {
  CEO: 'ceo', PM: 'product', Product: 'product', Engineering: 'engineering',
  HR: 'hr', Sales: 'sales', Marketing: 'marketing', Finance: 'finance',
}

// ─── Pulse Tab ─────────────────────────────────────────────────────────────
function LatestWorkPanel({ artifacts }: { artifacts: ApiArtifact[] | null }) {
  const latest = artifacts?.[0] ?? null
  const [downloading, setDownloading] = useState(false)
  const [lastGenerated, setLastGenerated] = useState<string | null>(null)

  useEffect(() => {
    setLastGenerated(getLastReportGeneratedAt())
  }, [])

  async function handleDownloadReport() {
    setDownloading(true)
    try {
      await downloadArtifactsReportPdf()
      setLastGenerated(getLastReportGeneratedAt())
    } catch (err) {
      console.error('Failed to generate artifact report PDF:', err)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="card" style={{ padding: 26, display: 'flex', flexDirection: 'column', minHeight: 320 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={14} style={{ color: 'var(--primary-2)' }} />
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>Latest agent output</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={handleDownloadReport}
            disabled={downloading}
            className="btn btn-secondary"
            title={
              lastGenerated
                ? `Aggregates every artifact into one PDF. Last generated ${new Date(lastGenerated).toLocaleString()}.`
                : 'Aggregates every artifact into one downloadable PDF report.'
            }
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, padding: '5px 10px' }}
          >
            {downloading
              ? <div className="spinner" style={{ width: 11, height: 11 }} />
              : <Download size={11} />}
            {downloading ? 'Generating…' : 'Download report'}
          </button>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 10.5, color: latest ? 'var(--green)' : 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
            {latest && <span className="live-dot" style={{ width: 5, height: 5 }} />}
            {latest ? 'live' : 'waiting'}
          </span>
        </div>
      </div>
      {latest ? (
        <>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12.5, color: 'var(--text-1)', fontWeight: 600 }}>{latest.title}</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
              {latest.agent_name} · {latest.artifact_type} · {new Date(latest.created_at).toLocaleString()}
            </div>
          </div>
          <pre
            style={{
              margin: 0,
              flex: 1,
              maxHeight: 260,
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: 11,
              lineHeight: 1.55,
              color: 'var(--text-2)',
              fontFamily: 'var(--font-mono)',
              padding: 14,
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'rgba(255,255,255,0.025)',
            }}
          >
            {latest.content ?? 'Artifact content is loading...'}
          </pre>
        </>
      ) : (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: 'var(--text-3)', fontSize: 12, lineHeight: 1.6, border: '1px solid var(--border)', borderRadius: 8, background: 'rgba(255,255,255,0.02)', padding: 24 }}>
          No live agent outputs yet. Complete onboarding or run the initiation workflow.
        </div>
      )}
    </div>
  )
}

function PulseTab({ liveAudit, liveQueue, liveArtifacts }: { liveAudit: ApiAuditEvent[] | null; liveQueue: ApiQueueItem[] | null; liveArtifacts: ApiArtifact[] | null }) {
  const stats = auditToAgentStats(liveAudit)
  const totalMessages = Object.values(stats).reduce((sum, s) => sum + s.messages, 0)
  const maxMessages = Math.max(1, ...Object.values(stats).map(s => s.messages))

  const kpis = [
    { label: 'Router Events', value: liveAudit?.length ?? 0, description: 'Total audit events recorded' },
    { label: 'Messages Routed', value: totalMessages, description: 'Inter-agent messages sent this session' },
    { label: 'Artifacts Produced', value: liveArtifacts?.length ?? 0, description: 'Completed deliverables written by agents' },
    { label: 'Manager Queue', value: liveQueue?.length ?? 0, description: 'Live queued router items for MANAGER' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>

      {/* KPI grid — real counts derived from the router's own audit log/queue/artifacts, no fabricated deltas or trend lines */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        {kpis.map((kpi, i) => (
          <motion.div
            key={kpi.label}
            className="kpi fade-up"
            style={{ padding: '20px 22px', animationDelay: `${i * 50}ms` }}
          >
            <div style={{ marginBottom: 14 }}>
              <span className="kpi-label">{kpi.label}</span>
            </div>
            <div className="kpi-value" style={{ fontSize: 28 }}>{kpi.value}</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 6 }}>{kpi.description}</div>
          </motion.div>
        ))}
      </div>

      <LatestWorkPanel artifacts={liveArtifacts} />

      <NotAvailablePanel
        title="Revenue forecast"
        subtitle="Business/financial metrics"
        reason="Not available — the router only knows message lifecycle events. Revenue requires a Finance agent emitting structured metric events, which this repo does not implement."
      />

      {/* Agent activity + Activity feed */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 22 }}>
        {/* Agent activity — real message counts from the audit log */}
        <div className="card" style={{ padding: 26 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>Agent activity</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 3 }}>Messages sent/received this session (router audit log)</div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {AGENTS.map(agent => {
              const s = stats[agent.id]
              const pct = Math.round((s.messages / maxMessages) * 100)
              return (
                <div key={agent.id} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div className="agent-glyph" style={{ width: 28, height: 28, borderRadius: 7, background: `${agent.color}1c`, border: `1px solid ${agent.color}33` }}>
                    <span style={{ color: agent.color }}>{AGENT_ICONS[agent.id]}</span>
                  </div>
                  <span style={{ width: 90, fontSize: 12.5, color: 'var(--text-1)', fontWeight: 500 }}>{agent.name}</span>
                  <div className="progress" style={{ flex: 1, height: 5 }}>
                    <div className="progress-fill" style={{ width: `${pct}%`, background: agent.color }} />
                  </div>
                  <span style={{ width: 40, textAlign: 'right', fontSize: 11.5, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                    {s.messages}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Activity feed */}
        <div className="card" style={{ padding: 26, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>Live activity</div>
            {liveAudit ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 10.5, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
                <span className="live-dot" style={{ width: 5, height: 5 }} /> live
              </span>
            ) : (
              <span style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>waiting</span>
            )}
          </div>
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14, maxHeight: 320 }}>
            {liveAudit && liveAudit.length === 0 && (
              <div style={{ textAlign: 'center', padding: '36px 12px', color: 'var(--text-3)', fontSize: 12, lineHeight: 1.5 }}>
                No live router activity yet. Complete onboarding or run the initiation workflow.
              </div>
            )}
            {(liveAudit ?? []).slice(0, 7).map((ev: any, i: number) => {
              const agentId = (ev.agentId ?? ev.actor ?? 'ceo') as AgentId
              const color   = AGENT_COLOR[agentId] ?? 'var(--primary)'
              const icon    = AGENT_ICONS[agentId]
              const title   = ev.title ?? ev.event_type ?? 'Event'
              const when    = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ev.when ?? ''
              return (
                <div key={ev.id ?? i} style={{ display: 'flex', gap: 11 }}>
                  <div className="agent-glyph" style={{ width: 26, height: 26, borderRadius: 7, background: `${color}1c`, border: `1px solid ${color}30`, flexShrink: 0 }}>
                    <span style={{ color }}>{icon}</span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, color: 'var(--text-1)', lineHeight: 1.5 }}>{title}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{when}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Distribution Tab ──────────────────────────────────────────────────────
function DistributionTab({ liveAudit }: { liveAudit: ApiAuditEvent[] | null }) {
  const stats = auditToAgentStats(liveAudit)
  const flow = auditToMessageFlow(liveAudit)
  const totalMessages = Object.values(stats).reduce((s, a) => s + a.messages, 0)
  const agentPieData = AGENTS.map(a => ({ ...a, messages: stats[a.id].messages }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>

        {/* Workload donut — real message-share per agent, from the router's audit log */}
        <div className="card" style={{ padding: 22 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Workload distribution</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Share of messages routed this session, by agent</div>
          </div>
          {totalMessages === 0 ? (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
              No messages routed yet.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, alignItems: 'center' }}>
              <div style={{ position: 'relative' }}>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={agentPieData} dataKey="messages" nameKey="name" innerRadius={58} outerRadius={86} stroke="var(--card)" strokeWidth={2} paddingAngle={1}>
                      {agentPieData.map((a, i) => <Cell key={i} fill={a.color} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
                  <div className="font-display" style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>{totalMessages}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>messages</div>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {AGENTS.map(a => (
                  <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: a.color, flexShrink: 0 }} />
                    <span style={{ flex: 1, fontSize: 12, color: 'var(--text-2)' }}>{a.name}</span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                      {totalMessages > 0 ? Math.round((stats[a.id].messages / totalMessages) * 100) : 0}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <NotAvailablePanel
          title="Spend distribution"
          subtitle="Budget vs. actual spend by department"
          reason="Not available — no Finance agent worker is implemented in this repo, so the router has no budget/spend data to show."
        />
      </div>

      {/* Inter-agent message flow matrix — real, from message_submitted audit events */}
      <div className="card" style={{ padding: 22 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Inter-agent message flow</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Volume of messages between agents this session</div>
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
            {flow.reduce((s, m) => s + m.count, 0)} messages
          </span>
        </div>
        <MessageMatrix flow={flow} />
      </div>
    </div>
  )
}

function MessageMatrix({ flow }: { flow: { from: AgentId; to: AgentId; count: number }[] }) {
  const ids: AgentId[] = ['ceo', 'product', 'engineering', 'hr', 'sales', 'marketing', 'finance']
  const max = Math.max(1, ...flow.map(m => m.count))
  const getCount = (from: AgentId, to: AgentId) => flow.find(x => x.from === from && x.to === to)?.count ?? 0
  const names: Record<AgentId, string> = { ceo: 'CEO', product: 'Prod', engineering: 'Eng', hr: 'HR', sales: 'Sales', marketing: 'Mkt', finance: 'Fin' }

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: `90px repeat(${ids.length}, 1fr)`, gap: 3, fontFamily: 'var(--font-mono)', fontSize: 10.5, minWidth: 560 }}>
        <div />
        {ids.map(id => (
          <div key={`h-${id}`} style={{ textAlign: 'center', color: AGENT_COLOR[id], fontWeight: 600, padding: '6px 0' }}>{names[id]}</div>
        ))}
        {ids.map(from => (
          <>
            <div key={`r-${from}`} style={{ display: 'flex', alignItems: 'center', gap: 5, color: AGENT_COLOR[from], fontWeight: 600, padding: '4px 0' }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: AGENT_COLOR[from], flexShrink: 0 }} />
              {names[from]}
            </div>
            {ids.map(to => {
              const n = getCount(from, to)
              const intensity = n / max
              return (
                <div key={`${from}-${to}`} style={{
                  aspectRatio: '1.4 / 1',
                  background: from === to ? 'var(--surface-2)' : n === 0 ? 'rgba(255,255,255,0.02)' : `rgba(255,255,255,${0.05 + intensity * 0.28})`,
                  border: '1px solid var(--border)',
                  borderRadius: 4,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10.5, color: from === to ? 'var(--text-4)' : intensity > 0.5 ? 'white' : 'var(--text-2)',
                }}>
                  {from === to ? '—' : n || ''}
                </div>
              )
            })}
          </>
        ))}
      </div>
    </div>
  )
}

// ─── Pipeline Tab ──────────────────────────────────────────────────────────
function PipelineTab({ liveAudit, liveArtifacts }: { liveAudit: ApiAuditEvent[] | null; liveArtifacts: ApiArtifact[] | null }) {
  const liveThroughput = auditToThroughput(liveAudit, 7)
  const throughputData = liveThroughput.length ? liveThroughput : TASK_THROUGHPUT
  const throughputLive = liveThroughput.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Recent completed work — real, from GET /artifacts across all agents */}
      <div className="card" style={{ padding: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Recent completed work</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
              {liveArtifacts?.length ?? 0} artifacts this session
            </div>
          </div>
        </div>
        {liveArtifacts && liveArtifacts.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {liveArtifacts.slice(0, 8).map(a => {
              const agentId = ROUTER_NAME_TO_AGENT_ID[a.agent_name]
              const color = agentId ? AGENT_COLOR[agentId] : 'var(--text-3)'
              const icon = agentId ? AGENT_ICONS[agentId] : <FileText size={13} />
              return (
                <div key={a.artifact_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}>
                  <div className="agent-glyph" style={{ width: 28, height: 28, borderRadius: 7, background: `${color}1c`, border: `1px solid ${color}40`, flexShrink: 0 }}>
                    <span style={{ color }}>{icon}</span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-1)' }}>{a.title}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                      {a.agent_name} · {a.artifact_type} · {new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
            No completed work yet. Complete onboarding or run the initiation workflow.
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 18 }}>
        <NotAvailablePanel
          title="Sales pipeline"
          subtitle="Deals at each stage"
          reason="Not available — no Sales agent worker is implemented in this repo, so there is no pipeline data to show."
        />

        {/* Task throughput */}
        <div className="card" style={{ padding: 22 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Router throughput</div>
              <span style={{ fontSize: 10.5, color: throughputLive ? 'var(--green)' : 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{throughputLive ? 'live' : 'mock'}</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Completed vs blocked router events</div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={throughputData} margin={{ top: 4, right: 0, bottom: 0, left: -24 }} barSize={12} barGap={4}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="completed" name="Completed" fill="var(--green)" radius={[3,3,0,0]} />
              <Bar dataKey="blocked"   name="Blocked"   fill="var(--red)"   radius={[3,3,0,0]} opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

// ─── Performance Tab ───────────────────────────────────────────────────────
function PerformanceTab({ liveAudit }: { liveAudit: ApiAuditEvent[] | null }) {
  const liveThroughput = auditToThroughput(liveAudit, 7)
  const completionTrend = liveThroughput.length ? liveThroughput : TASK_THROUGHPUT
  const completionTrendLive = liveThroughput.length > 0
  const stats = auditToAgentStats(liveAudit)
  // Real per-agent numbers from the router's own audit log (message_acked /
  // message_nacked / message_submitted events) — replaces the fabricated
  // successRate/completedTasks/totalMessages/activeTaskCount fields on the
  // static mock-data.ts Agent records. successRate is null (rendered as
  // "—") until an agent has at least one acked/nacked message.
  const perf = AGENTS.map(a => {
    const s: AgentStat = stats[a.id]
    return {
      id: a.id, name: a.name, role: a.role, color: a.color,
      successRate: s.successRate,
      completed: s.completed,
      messages: s.messages,
      pending: Math.max(0, s.messages - s.completed - s.failed),
    }
  }).sort((a, b) => (b.successRate ?? -1) - (a.successRate ?? -1))

  const radialData = perf.map(p => ({ name: p.name, value: p.successRate ?? 0, fill: p.color }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 18 }}>
        {/* Radial success rate */}
        <div className="card" style={{ padding: 22 }}>
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Success rate</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Task completion ratio per agent</div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <RadialBarChart innerRadius={26} outerRadius={120} data={radialData} startAngle={90} endAngle={-270}>
              <RadialBar dataKey="value" cornerRadius={4} background={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Tooltip formatter={(v: number) => `${v}%`} />
            </RadialBarChart>
          </ResponsiveContainer>
        </div>

        {/* Scorecards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {perf.map(p => (
            <div key={p.id} className="card card-hover" style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 14 }}>
              <div className="agent-glyph" style={{ width: 36, height: 36, borderRadius: 9, background: `${p.color}1c`, border: `1px solid ${p.color}40` }}>
                <span style={{ color: p.color }}>{AGENT_ICONS[p.id as AgentId]}</span>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>{p.name}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-3)' }}>· {p.role}</span>
                </div>
                <div style={{ display: 'flex', gap: 14, fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>
                  <span>{p.completed} done</span>
                  <span>{p.pending} pending</span>
                  <span>{p.messages} msgs</span>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="font-display" style={{ fontSize: 20, fontWeight: 700, color: p.color, letterSpacing: '-0.02em' }}>
                  {p.successRate ?? '—'}{p.successRate != null && <span style={{ fontSize: 12, color: 'var(--text-3)' }}>%</span>}
                </div>
                <div style={{ fontSize: 9.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                  {p.successRate != null ? 'success' : 'no data yet'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 7-day completion trend */}
      <div className="card" style={{ padding: 22 }}>
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Router completion trend</div>
            <span style={{ fontSize: 10.5, color: completionTrendLive ? 'var(--green)' : 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{completionTrendLive ? 'live' : 'mock'}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Ack/submission events across the router</div>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={completionTrend} margin={{ top: 4, right: 0, bottom: 0, left: -24 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line type="monotone" dataKey="completed" stroke="var(--primary-2)" strokeWidth={2}
              dot={{ r: 3, fill: 'var(--primary)', strokeWidth: 0 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ─── Main Dashboard ─────────────────────────────────────────────────────────
const TABS = [
  { id: 'pulse',        label: 'Pulse',        Icon: Activity },
  { id: 'distribution', label: 'Distribution', Icon: Layers },
  { id: 'pipeline',     label: 'Pipeline',     Icon: GitBranch },
  { id: 'performance',  label: 'Performance',  Icon: TrendingUp },
] as const

type TabId = typeof TABS[number]['id']

export default function DashboardPage() {
  const [tab, setTab] = useState<TabId>('pulse')
  const { data: health } = useHealth()
  const { data: audit  } = useAudit(50)
  const { data: managerQueue } = useQueue('MANAGER')
  const { data: artifacts } = useArtifacts('', 10)

  return (
    <div style={{ padding: 'clamp(20px, 3vw, 32px) clamp(20px, 3vw, 32px) 40px', maxWidth: 1400, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span className="eyebrow">Operations</span>
            {health ? (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                padding: '2px 9px', borderRadius: 999,
                background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.22)',
                color: 'var(--green)', fontSize: 9.5, fontFamily: 'var(--font-mono)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
              }}>
                <span className="live-dot" style={{ width: 5, height: 5 }} /> {health.backend}
              </span>
            ) : (
              <span style={{
                padding: '2px 9px', borderRadius: 999,
                background: 'rgba(251,191,36,0.10)', border: '1px solid rgba(251,191,36,0.25)',
                color: 'var(--amber)', fontSize: 9.5, fontFamily: 'var(--font-mono)', fontWeight: 600,
              }}>
                demo data
              </span>
            )}
          </div>
          <h1 style={{ fontSize: 26, fontWeight: 600, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
            Company Overview
          </h1>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="tabs">
          {TABS.map(t => (
            <div
              key={t.id}
              className={`tab${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              <t.Icon size={12} />{t.label}
            </div>
          ))}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
          showing <span style={{ color: 'var(--text-1)' }}>{TABS.find(t => t.id === tab)?.label.toLowerCase()}</span>
        </div>
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {tab === 'pulse'        && <PulseTab liveAudit={audit} liveQueue={managerQueue} liveArtifacts={artifacts} />}
          {tab === 'distribution' && <DistributionTab liveAudit={audit} />}
          {tab === 'pipeline'     && <PipelineTab liveAudit={audit} liveArtifacts={artifacts} />}
          {tab === 'performance'  && <PerformanceTab liveAudit={audit} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
