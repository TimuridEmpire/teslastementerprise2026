'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Globe, Layers, Database, Brain, CheckCircle2, AlertCircle,
  XCircle, Clock, Activity, Server,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts'
import { useHealth, useAudit } from '@/lib/hooks'

const ARCH_LAYERS = [
  { label: 'Web UI',            icon: <Globe size={14} />,    color: 'var(--sky)',      detail: 'Next.js 14 · React 18 · Framer Motion' },
  { label: 'API / Orchestrator',icon: <Layers size={14} />,   color: 'var(--indigo)',   detail: 'FastAPI · enterprise_router · priority queue' },
  { label: 'Agent Layer',       icon: <Brain size={14} />,    color: 'var(--agent-product)', detail: '7 top-level agents + worker pools' },
  { label: 'Persistence',       icon: <Database size={14} />, color: 'var(--agent-hr)', detail: 'SQLite / MongoDB · message store' },
]

// Synthetic latency data
const latencyData = Array.from({ length: 20 }, (_, i) => ({
  t: `${i}s`,
  ui: 10 + Math.round(Math.random() * 8),
  api: 18 + Math.round(Math.random() * 15),
}))

const TABS = ['Overview', 'Audit Log', 'Architecture'] as const
type Tab = typeof TABS[number]

export default function ObservabilityPage() {
  const [tab, setTab] = useState<Tab>('Overview')
  const { data: health, loading: healthLoading } = useHealth()
  const { data: audit,  loading: auditLoading  } = useAudit(50)

  const statusColor = (s: string | undefined) =>
    s === 'ok' || s === 'operational' ? 'var(--green)' : s ? 'var(--amber)' : 'var(--text-3)'

  return (
    <div className="p-6 space-y-5 max-w-[1600px] mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[16px] font-bold" style={{ color: 'var(--text-1)' }}>Observability</h1>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-3)' }}>System health, traces, and audit log</p>
        </div>
        {health && (
          <span className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--green)' }}>
            <span className="live-dot" style={{ width: 6, height: 6 }} />
            {health.backend} · {health.status}
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl w-fit" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-1.5 rounded-lg text-[12px] font-medium transition-all cursor-pointer"
            style={{
              background: tab === t ? 'var(--surface)' : 'transparent',
              color:      tab === t ? 'var(--text-1)'  : 'var(--text-3)',
              border:     tab === t ? '1px solid var(--border)' : '1px solid transparent',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {tab === 'Overview' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">

          {/* Health cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'API Status',  value: healthLoading ? '…' : (health?.status ?? 'offline'), icon: <Server size={13} />, color: health ? 'var(--green)' : 'var(--red)' },
              { label: 'Backend',     value: healthLoading ? '…' : (health?.backend ?? '—'),     icon: <Database size={13} />, color: 'var(--indigo-2)' },
              { label: 'Agents',      value: '7',  icon: <Brain size={13} />,    color: 'var(--agent-product)' },
              { label: 'Audit Events',value: audit ? String(audit.length) : '—', icon: <Activity size={13} />, color: 'var(--amber)' },
            ].map(card => (
              <div key={card.label} className="card p-4">
                <div className="flex items-center gap-2 mb-3" style={{ color: 'var(--text-3)' }}>
                  {card.icon}
                  <span className="text-[11px]">{card.label}</span>
                </div>
                <div className="font-display text-xl font-bold capitalize" style={{ color: card.color }}>{card.value}</div>
              </div>
            ))}
          </div>

          {/* Latency chart */}
          <div className="card p-5">
            <h3 className="text-[13px] font-semibold mb-4" style={{ color: 'var(--text-1)' }}>Response Latency (synthetic)</h3>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={latencyData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="t" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} unit="ms" />
                <Tooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11 }}
                  cursor={{ stroke: 'var(--border)' }}
                />
                <Line type="monotone" dataKey="ui"  stroke="var(--sky)"    strokeWidth={1.5} dot={false} name="UI" />
                <Line type="monotone" dataKey="api" stroke="var(--indigo)" strokeWidth={1.5} dot={false} name="API" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* System layers */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {ARCH_LAYERS.map(layer => (
              <div key={layer.label} className="card p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span style={{ color: layer.color }}>{layer.icon}</span>
                  <span className="text-[12.5px] font-semibold" style={{ color: 'var(--text-1)' }}>{layer.label}</span>
                </div>
                <div className="text-[10px] leading-relaxed" style={{ color: 'var(--text-3)' }}>{layer.detail}</div>
                <div className="flex items-center gap-1.5 mt-3">
                  <CheckCircle2 size={10} style={{ color: 'var(--green)' }} />
                  <span className="text-[10px]" style={{ color: 'var(--green)' }}>Operational</span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Audit Log tab */}
      {tab === 'Audit Log' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card overflow-hidden">
          <div
            className="grid text-[10px] font-semibold px-4 py-2.5"
            style={{ gridTemplateColumns: '180px 160px 140px 1fr', color: 'var(--text-3)', borderBottom: '1px solid var(--border)' }}
          >
            <span>TIME</span><span>EVENT TYPE</span><span>ACTOR</span><span>SUBJECT</span>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: '60vh' }}>
            {auditLoading && (
              <div className="text-center py-8 text-[12px]" style={{ color: 'var(--text-3)' }}>Loading audit log…</div>
            )}
            {!auditLoading && !audit && (
              <div className="text-center py-8 text-[12px]" style={{ color: 'var(--text-3)' }}>
                Audit log unavailable — API offline or admin secret not configured
              </div>
            )}
            {audit?.map((ev, i) => (
              <div
                key={ev.id}
                className="grid px-4 py-3 text-[11px]"
                style={{
                  gridTemplateColumns: '180px 160px 140px 1fr',
                  borderBottom: '1px solid var(--border)',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                }}
              >
                <span className="font-mono" style={{ color: 'var(--text-3)' }}>
                  {new Date(ev.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                <span className="font-mono" style={{ color: 'var(--indigo-2)' }}>{ev.event_type}</span>
                <span style={{ color: 'var(--text-2)' }}>{ev.actor}</span>
                <span className="truncate" style={{ color: 'var(--text-3)' }}>{ev.subject_id}</span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Architecture tab */}
      {tab === 'Architecture' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
          <div className="card p-6">
            <h3 className="text-[13px] font-semibold mb-5" style={{ color: 'var(--text-1)' }}>System Architecture</h3>
            <div className="flex flex-col items-center gap-2">
              {ARCH_LAYERS.map((layer, i) => (
                <div key={layer.label} className="w-full max-w-lg">
                  <div
                    className="flex items-center gap-3 px-5 py-3.5 rounded-xl"
                    style={{ background: `${layer.color}10`, border: `1px solid ${layer.color}30` }}
                  >
                    <span style={{ color: layer.color }}>{layer.icon}</span>
                    <div className="flex-1">
                      <div className="text-[12.5px] font-semibold" style={{ color: 'var(--text-1)' }}>{layer.label}</div>
                      <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>{layer.detail}</div>
                    </div>
                    <CheckCircle2 size={12} style={{ color: 'var(--green)' }} />
                  </div>
                  {i < ARCH_LAYERS.length - 1 && (
                    <div className="flex justify-center my-1">
                      <div className="w-px h-5" style={{ background: 'var(--border)' }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Message flow summary */}
          <div className="card p-5">
            <h3 className="text-[13px] font-semibold mb-4" style={{ color: 'var(--text-1)' }}>Message Flow</h3>
            <div className="space-y-3 text-[12px]" style={{ color: 'var(--text-2)' }}>
              {[
                ['Dashboard / Chat', 'POST /manager/interventions', 'MANAGER agent auth'],
                ['Agents ↔ Agents',  'POST /messages',              'Agent auth (Bearer + X-Agent-Id)'],
                ['Admin actions',    'GET /agents, /registrations', 'X-Admin-Secret header'],
                ['Queue peek',       'GET /queue/{recipient}',       'Agent auth, 4s polling'],
                ['Audit trail',      'GET /audit?limit=N',           'Admin auth, 8s polling'],
              ].map(([flow, endpoint, auth]) => (
                <div key={flow} className="flex items-start gap-4 px-3 py-2.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
                  <span className="w-36 flex-shrink-0 font-semibold" style={{ color: 'var(--text-1)' }}>{flow}</span>
                  <span className="font-mono text-[11px] flex-1" style={{ color: 'var(--indigo-2)' }}>{endpoint}</span>
                  <span className="text-[10px] flex-shrink-0" style={{ color: 'var(--text-3)' }}>{auth}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
