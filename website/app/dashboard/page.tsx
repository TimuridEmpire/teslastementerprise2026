'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, Layers, GitBranch, TrendingUp,
  Crown, Package, Code2, Users, DollarSign, Megaphone,
  ArrowRight, CheckCircle2, Circle,
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell, RadialBarChart, RadialBar,
  CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  AGENTS, COMPANY_KPIS, ACTIVITY_FEED, TASK_THROUGHPUT, REVENUE_FORECAST,
  BUDGET_ALLOCATIONS, AGENT_LOAD, PIPELINE, MESSAGE_FLOW, KANOSEI_WORKFLOWS,
} from '@/lib/mock-data'
import { useHealth, useAudit, useQueue } from '@/lib/hooks'
import { auditToThroughput } from '@/lib/live-metrics'
import type { AgentId } from '@/lib/types'
import type { ApiAuditEvent, ApiQueueItem } from '@/lib/api-types'

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

// ─── Sparkline ─────────────────────────────────────────────────────────────
function Sparkline({ data, color = 'var(--primary)', height = 28 }: { data: number[]; color?: string; height?: number }) {
  const max = Math.max(...data), min = Math.min(...data), range = max - min || 1
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${data.length * 10} ${height}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      <polyline
        fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
        points={data.map((v, i) => `${i * 10},${height - ((v - min) / range) * (height - 4) - 2}`).join(' ')}
      />
    </svg>
  )
}

// ─── Pulse Tab ─────────────────────────────────────────────────────────────
function PulseTab({ liveAudit, liveQueue }: { liveAudit: any[] | null; liveQueue: ApiQueueItem[] | null }) {
  const kpis = liveQueue !== null
    ? [
      ...COMPANY_KPIS.slice(0, 3),
      {
        label: 'Manager Queue',
        value: liveQueue.length,
        delta: undefined,
        trend: 'flat' as const,
        description: 'Live queued router items for MANAGER',
      },
    ]
    : COMPANY_KPIS.slice(0, 4)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>

      {/* KPI grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        {kpis.map((kpi, i) => {
          const positive = kpi.trend === 'up'
          const spark = [60, 65, 62, 70, 75, 80, 85, 87].map((v, j) => v + i * 3 + j)
          return (
            <motion.div
              key={kpi.label}
              className="kpi fade-up"
              style={{ padding: '20px 22px', animationDelay: `${i * 50}ms` }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
                <span className="kpi-label">{kpi.label}</span>
                <span style={{
                  fontSize: 10, padding: '2px 7px', borderRadius: 20, fontWeight: 600,
                  color: positive ? 'var(--green)' : 'var(--red)',
                  background: positive ? 'rgba(52,211,153,0.10)' : 'rgba(248,113,113,0.10)',
                  border: `1px solid ${positive ? 'rgba(52,211,153,0.22)' : 'rgba(248,113,113,0.22)'}`,
                }}>
                  {kpi.delta != null ? (kpi.delta > 0 ? '+' : '') + kpi.delta + '%' : '—'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12 }}>
                <div className="kpi-value" style={{ fontSize: 28 }}>{kpi.value}</div>
                <div style={{ width: 70, flexShrink: 0, opacity: 0.85 }}>
                  <Sparkline data={spark} color={positive ? 'var(--green)' : 'var(--red)'} height={30} />
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Revenue chart full width */}
      <div className="card" style={{ padding: 26 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 18 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>Revenue forecast</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 3 }}>Actual vs. projected · last 6 months + next quarter</div>
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 11.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 2, background: 'var(--primary)', borderRadius: 1, display: 'inline-block' }} /> Actual
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, borderTop: '1.5px dashed var(--primary-2)', display: 'inline-block' }} /> Projected
            </span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={REVENUE_FORECAST} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
            <defs>
              <linearGradient id="revG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="var(--primary)" stopOpacity={0.3} />
                <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11 }} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
            <Tooltip formatter={(v: number) => `$${(v/1000).toFixed(0)}K`} />
            <Area type="monotone" dataKey="actual"   stroke="var(--primary)"   strokeWidth={2}   fill="url(#revG)" />
            <Area type="monotone" dataKey="forecast" stroke="var(--primary-2)" strokeWidth={1.5} fill="none" strokeDasharray="4 3" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Agent load + Activity */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 22 }}>
        {/* Agent load */}
        <div className="card" style={{ padding: 26 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>Agent load</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 3 }}>Capacity utilization this week</div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {AGENT_LOAD.map(a => (
              <div key={a.name} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div className="agent-glyph" style={{ width: 28, height: 28, borderRadius: 7, background: `${a.color}1c`, border: `1px solid ${a.color}33` }}>
                  <span style={{ color: a.color }}>{AGENT_ICONS[a.agentId]}</span>
                </div>
                <span style={{ width: 90, fontSize: 12.5, color: 'var(--text-1)', fontWeight: 500 }}>{a.name}</span>
                <div className="progress" style={{ flex: 1, height: 5 }}>
                  <div className="progress-fill" style={{ width: `${a.value}%`, background: a.color }} />
                </div>
                <span style={{ width: 40, textAlign: 'right', fontSize: 11.5, fontFamily: 'var(--font-mono)', color: a.value >= 85 ? 'var(--amber)' : 'var(--text-2)' }}>
                  {a.value}%
                </span>
              </div>
            ))}
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
              <span style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>mock</span>
            )}
          </div>
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14, maxHeight: 320 }}>
            {(liveAudit ?? ACTIVITY_FEED).slice(0, 7).map((ev: any, i: number) => {
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
function DistributionTab() {
  const totalLoad = AGENT_LOAD.reduce((s, a) => s + a.value, 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>

        {/* Workload donut */}
        <div className="card" style={{ padding: 22 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Workload distribution</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Capacity allocated across agents this week</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, alignItems: 'center' }}>
            <div style={{ position: 'relative' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={AGENT_LOAD} dataKey="value" nameKey="name" innerRadius={58} outerRadius={86} stroke="var(--card)" strokeWidth={2} paddingAngle={1}>
                    {AGENT_LOAD.map((a, i) => <Cell key={i} fill={a.color} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
                <div className="font-display" style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>{totalLoad}</div>
                <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>total %</div>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {AGENT_LOAD.map(a => (
                <div key={a.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: a.color, flexShrink: 0 }} />
                  <span style={{ flex: 1, fontSize: 12, color: 'var(--text-2)' }}>{a.name}</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                    {Math.round((a.value / totalLoad) * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Spend distribution */}
        <div className="card" style={{ padding: 22 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Spend distribution</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Quarterly spend vs allocation by department</div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={BUDGET_ALLOCATIONS} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 0 }} barSize={12}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" tickFormatter={v => `$${v}K`} axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="department" axisLine={false} tickLine={false} width={80} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => `$${v}K`} />
              <Bar dataKey="allocated" name="Allocated" fill="rgba(255,255,255,0.06)" radius={[0, 3, 3, 0]} />
              <Bar dataKey="spent"     name="Spent"     radius={[0, 3, 3, 0]}>
                {BUDGET_ALLOCATIONS.map((b, i) => (
                  <Cell key={i} fill={b.spent / b.allocated > 0.9 ? 'var(--amber)' : AGENT_COLOR[b.agentId] ?? 'var(--primary)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Inter-agent message flow matrix */}
      <div className="card" style={{ padding: 22 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Inter-agent message flow</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Volume of messages between agents · last 7 days</div>
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
            {MESSAGE_FLOW.reduce((s, m) => s + m.count, 0)} messages
          </span>
        </div>
        <MessageMatrix />
      </div>
    </div>
  )
}

function MessageMatrix() {
  const ids: AgentId[] = ['ceo', 'product', 'engineering', 'hr', 'sales', 'marketing', 'finance']
  const max = Math.max(...MESSAGE_FLOW.map(m => m.count))
  const getCount = (from: AgentId, to: AgentId) => MESSAGE_FLOW.find(x => x.from === from && x.to === to)?.count ?? 0
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
function PipelineTab({ liveAudit }: { liveAudit: ApiAuditEvent[] | null }) {
  const liveThroughput = auditToThroughput(liveAudit, 7)
  const throughputData = liveThroughput.length ? liveThroughput : TASK_THROUGHPUT
  const throughputLive = liveThroughput.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Workflows */}
      <div className="card" style={{ padding: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Active workflows</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
              {KANOSEI_WORKFLOWS.length} workflows · {KANOSEI_WORKFLOWS.reduce((s, w) => s + w.stages.length, 0)} stages
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {KANOSEI_WORKFLOWS.map(w => {
            const ownerColor = AGENT_COLOR[w.owner]
            const ownerIcon  = AGENT_ICONS[w.owner]
            return (
              <div key={w.id} style={{ padding: '14px 16px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div className="agent-glyph" style={{ width: 26, height: 26, borderRadius: 7, background: `${ownerColor}1c`, border: `1px solid ${ownerColor}40` }}>
                      <span style={{ color: ownerColor }}>{ownerIcon}</span>
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>{w.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{w.progress}% complete</div>
                    </div>
                  </div>
                  <span className="badge status-active">{w.status}</span>
                </div>
                <div style={{ display: 'flex', gap: 3 }}>
                  {w.stages.map((s, i) => {
                    const ag = AGENT_COLOR[s.agent]
                    const isDone   = s.status === 'done'
                    const isActive = s.status === 'active'
                    return (
                      <div key={i} style={{
                        flex: 1, minWidth: 0, padding: '7px 8px',
                        background: isActive ? `${ag}14` : isDone ? 'rgba(52,211,153,0.06)' : 'transparent',
                        border: '1px solid', borderColor: isActive ? `${ag}50` : isDone ? 'rgba(52,211,153,0.22)' : 'var(--border)',
                        borderRadius: 5,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                          {isDone && <CheckCircle2 size={9} color="var(--green)" strokeWidth={2.5} />}
                          {isActive && <span style={{ width: 5, height: 5, borderRadius: '50%', background: ag }} />}
                          {!isDone && !isActive && <Circle size={5} style={{ color: 'var(--text-4)' }} />}
                        </div>
                        <div style={{ fontSize: 11, color: isDone || isActive ? 'var(--text-1)' : 'var(--text-3)', lineHeight: 1.3, fontWeight: isActive ? 500 : 400 }}>{s.name}</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 18 }}>
        {/* Sales pipeline funnel */}
        <div className="card" style={{ padding: 22 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>Sales pipeline</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>Deals at each stage · managed by Sales agent</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {PIPELINE.map((p, i) => {
              const widthPct = 100 - i * 15
              return (
                <div key={p.stage} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 88, fontSize: 11.5, color: 'var(--text-2)' }}>{p.stage}</div>
                  <div style={{ flex: 1, height: 30, background: 'rgba(255,255,255,0.02)', borderRadius: 5, overflow: 'hidden' }}>
                    <div style={{ width: `${widthPct}%`, height: '100%', background: `${p.color}26`, border: `1px solid ${p.color}55`, borderRadius: 5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 10px' }}>
                      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-1)' }}>{p.count}</span>
                      {p.value > 0 && <span style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>${p.value}K</span>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

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
  const perf = AGENTS.map(a => ({
    id: a.id, name: a.name, role: a.role, color: a.color,
    successRate: a.successRate,
    completed:   a.completedTasks,
    messages:    a.totalMessages,
    activeTasks: a.activeTaskCount,
  })).sort((a, b) => b.successRate - a.successRate)

  const radialData = perf.map(p => ({ name: p.name, value: p.successRate, fill: p.color }))

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
                  <span>{p.activeTasks} active</span>
                  <span>{p.messages} msgs</span>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="font-display" style={{ fontSize: 20, fontWeight: 700, color: p.color, letterSpacing: '-0.02em' }}>
                  {p.successRate}<span style={{ fontSize: 12, color: 'var(--text-3)' }}>%</span>
                </div>
                <div style={{ fontSize: 9.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>success</div>
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
  const { data: managerQueue } = useQueue('MANAGER', process.env.NEXT_PUBLIC_MANAGER_API_KEY ?? '')

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
          {tab === 'pulse'        && <PulseTab liveAudit={audit} liveQueue={managerQueue} />}
          {tab === 'distribution' && <DistributionTab />}
          {tab === 'pipeline'     && <PipelineTab liveAudit={audit} />}
          {tab === 'performance'  && <PerformanceTab liveAudit={audit} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
