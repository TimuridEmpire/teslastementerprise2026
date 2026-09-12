'use client'

import { notFound } from 'next/navigation'
import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Crown, Package, Code2, Users, TrendingUp, Megaphone,
  DollarSign, CheckCircle2, AlertCircle,
  Send, ChevronRight, Zap, Shield, Activity, BarChart3,
  MessageSquare, FileText, Target, Circle,
} from 'lucide-react'
import { AGENTS, MESSAGES } from '@/lib/mock-data'
import { useArtifacts, useQueue, useAudit } from '@/lib/hooks'
import { auditToAgentStats, auditToThroughput } from '@/lib/live-metrics'
import type { AgentId } from '@/lib/types'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'
import { api } from '@/lib/api'

// Agent metadata
const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={20} />, product: <Package size={20} />, engineering: <Code2 size={20} />,
  hr: <Users size={20} />, sales: <TrendingUp size={20} />, marketing: <Megaphone size={20} />,
  finance: <DollarSign size={20} />,
}

const AGENT_COLORS: Record<AgentId, string> = {
  ceo:         'var(--agent-ceo)',
  product:     'var(--agent-product)',
  engineering: 'var(--agent-engineering)',
  hr:          'var(--agent-hr)',
  sales:       'var(--agent-sales)',
  marketing:   'var(--agent-marketing)',
  finance:     'var(--agent-finance)',
}

// Matches README "Current implemented runtime workers" vs "Registered but
// not implemented" — Sales and Finance are registered with the router so
// they can be selected and messaged, but run_agents.py has no worker
// process for them, so nothing ever consumes what's sent. Shown as an
// explicit banner below rather than left for the numbers to imply.
const LIVE_WORKER_AGENT_IDS = new Set<AgentId>(['ceo', 'product', 'engineering', 'hr', 'marketing'])

const ROUTER_AGENT_BY_UI_ID: Record<string, string> = {
  ceo: 'CEO',
  product: 'PM',
  engineering: 'Engineering',
  hr: 'HR',
  sales: 'Sales',
  marketing: 'Marketing',
  finance: 'Finance',
}

const ROUTER_AGENT_KEYS: Record<string, string> = {
  CEO: process.env.NEXT_PUBLIC_CEO_API_KEY ?? '',
  PM: process.env.NEXT_PUBLIC_PM_API_KEY ?? process.env.NEXT_PUBLIC_PRODUCT_API_KEY ?? '',
  Engineering: process.env.NEXT_PUBLIC_ENGINEERING_API_KEY ?? '',
  HR: process.env.NEXT_PUBLIC_HR_API_KEY ?? '',
  Sales: process.env.NEXT_PUBLIC_SALES_API_KEY ?? '',
  Marketing: process.env.NEXT_PUBLIC_MARKETING_API_KEY ?? '',
  Finance: process.env.NEXT_PUBLIC_FINANCE_API_KEY ?? '',
}

export default function AgentPage({ params }: { params: { agent: string } }) {
  const { agent: agentId } = params
  const agent = AGENTS.find(a => a.id === agentId)
  if (!agent) notFound()

  const color = AGENT_COLORS[agent.id as AgentId]
  const isLiveWorker = LIVE_WORKER_AGENT_IDS.has(agent.id as AgentId)
  const routerRecipient = ROUTER_AGENT_BY_UI_ID[agent.id] ?? agent.name
  const routerApiKey = ROUTER_AGENT_KEYS[routerRecipient] ?? ''

  const [instruction, setInstruction] = useState('')
  const [sending, setSending]         = useState(false)
  const [sent, setSent]               = useState(false)
  const [sendError, setSendError]     = useState('')

  // Live queue; skips fetching when this agent has no configured key.
  const { data: queue, enabled: queueEnabled, error: queueError } = useQueue(routerRecipient, routerApiKey)
  const { data: artifacts, error: artifactError } = useArtifacts(routerRecipient, 10)
  const { data: audit } = useAudit(200)
  const hasRouterQueue = queue !== null
  const latestArtifact = artifacts?.[0] ?? null

  // Real per-agent numbers from the router's own audit log — replaces the
  // fabricated Tasks Done / Success / Messages / Resource Usage /
  // Performance Profile / Weekly Activity that used to come from
  // mock-data.ts's static AGENTS/TASKS arrays regardless of what this
  // agent (or its router worker, if one exists) had actually done.
  const stats = auditToAgentStats(audit)[agent.id as AgentId]
  const agentThroughput = auditToThroughput(
    (audit ?? []).filter(e => {
      const d = e.details as Record<string, unknown> | undefined
      return d?.sender === routerRecipient || d?.recipient === routerRecipient
    }),
    7,
  )

  const agentMessages = hasRouterQueue
    ? queue.map(item => ({
      id: item.envelope.id,
      sender: item.envelope.sender.toLowerCase(),
      recipient: item.envelope.recipient.toLowerCase(),
      task_type: item.envelope.task_type,
      status: item.envelope.status,
      delivery_state: item.delivery_state,
      computed_priority: item.computed_priority,
      attempt_count: item.attempt_count,
      payload: item.envelope.payload,
    }))
    : MESSAGES.filter(m => m.sender === agent.id || m.recipient === agent.id)

  const radarData = [
    { subject: 'Success',  value: stats.successRate ?? 0 },
    { subject: 'Messages', value: Math.min(stats.messages * 5, 100) },
    { subject: 'Completed', value: Math.min(stats.completed * 10, 100) },
  ]

  const statusCounts = {
    completed: stats.completed,
    pending:   hasRouterQueue ? queue.length : 0,
    failed:    stats.failed,
  }

  async function handleSend() {
    if (!instruction.trim() || sending) return
    setSending(true)
    setSendError('')
    try {
      await api.manager.intervene({
        recipient: routerRecipient,
        instruction: instruction.trim(),
        task_type: routerRecipient === 'CEO' ? 'CEO_REASONING_LOOP' : 'MANAGER_INTERVENTION',
        priority: 'normal',
        context: { source: 'agent_page', ui_agent_id: agentId },
      })
      setSent(true)
      setInstruction('')
      setTimeout(() => setSent(false), 8000)
    } catch (e) {
      setSendError(e instanceof Error ? e.message : 'Failed to send')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto">

      {/* Hero */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card p-6 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: `radial-gradient(ellipse at top left, ${color.replace('var(','').replace(')','') ? color : '#6366f1'}18, transparent 55%)` }} />
        <div className="relative flex items-start gap-6 flex-wrap">
          {/* Avatar */}
          <div
            className="w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: `${color}18`, border: `1.5px solid ${color}35`, color }}
          >
            <span style={{ transform: 'scale(1.5)', display: 'flex' }}>{AGENT_ICONS[agent.id as AgentId]}</span>
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap mb-1">
              <h1 className="font-display text-xl font-bold" style={{ color }}>{agent.name}</h1>
              <span className={`badge status-${agent.status}`}>
                <Circle size={5} fill="currentColor" />
                {agent.status}
              </span>
            </div>
            <div className="text-[13px] mb-1" style={{ color: 'var(--text-2)' }}>{agent.role}</div>
            <div className="text-[12px] leading-relaxed max-w-xl" style={{ color: 'var(--text-3)' }}>{agent.specialization}</div>
          </div>

          {/* KPIs — real, from the router's own audit log (message_submitted/acked/nacked) */}
          <div className="flex gap-3 flex-wrap">
            {[
              { label: 'Completed', value: stats.completed, icon: <CheckCircle2 size={11} /> },
              { label: 'Success',   value: stats.successRate != null ? `${stats.successRate}%` : '—', icon: <Target size={11} /> },
              { label: 'Pending',   value: hasRouterQueue ? queue.length : '—', icon: <Activity size={11} /> },
              { label: 'Messages',  value: stats.messages, icon: <MessageSquare size={11} /> },
            ].map(k => (
              <div key={k.label} className="card-inner px-4 py-3 text-center">
                <div className="flex justify-center mb-0.5" style={{ color }}>{k.icon}</div>
                <div className="font-display text-lg font-bold" style={{ color: 'var(--text-1)' }}>{k.value}</div>
                <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>{k.label}</div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* No-live-worker banner — this agent is registered with the router
          (so it can be messaged) but run_agents.py has no worker process
          for it, so nothing ever consumes what's sent here. */}
      {!isLiveWorker && (
        <div
          className="card p-4 flex items-start gap-3"
          style={{ background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.25)' }}
        >
          <AlertCircle size={16} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: 2 }} />
          <div className="text-[12px] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            <strong style={{ color: 'var(--amber)' }}>No live worker for {agent.name}.</strong> This department is
            registered with the router, so messages sent below will queue — but no process is running to pick them
            up, so they'll stay queued rather than produce a real response or artifact.
          </div>
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Left: tasks + queue + chart + messaging */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
          className="xl:col-span-2 space-y-5">

          {/* Message status summary — real, from the router's audit log + live queue */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { key: 'completed', label: 'Completed', value: statusCounts.completed },
              { key: 'pending',   label: 'Pending',   value: statusCounts.pending },
              { key: 'failed',    label: 'Failed',    value: statusCounts.failed },
            ].map(s => (
              <div key={s.key} className="card p-3 text-center">
                <div className="font-display text-xl font-bold" style={{ color: 'var(--text-1)' }}>{s.value}</div>
                <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-3)' }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Live queue (from API) */}
          {hasRouterQueue && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Live Queue</h3>
                <span className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--green)' }}>
                  <span className="live-dot" style={{ width: 6, height: 6 }} />
                  {queue.length} {queue.length === 1 ? 'item' : 'items'}
                </span>
              </div>
              <div className="space-y-2">
                {queue.length === 0 && (
                  <div className="text-center py-6 text-[12px]" style={{ color: 'var(--text-3)' }}>Queue is empty</div>
                )}
                {queue.slice(0, 5).map(item => (
                  <div
                    key={item.envelope.id}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg"
                    style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-mono text-[11px]" style={{ color }}>{item.envelope.task_type}</span>
                        <span className="text-[10px]" style={{ color: 'var(--text-3)' }}>from {item.envelope.sender}</span>
                      </div>
                      <div className="text-[10px] truncate" style={{ color: 'var(--text-3)' }}>
                        {JSON.stringify(item.envelope.payload).slice(0, 60)}
                      </div>
                      {item.blocked_reason && (
                        <div className="text-[10px] truncate mt-0.5" style={{ color: 'var(--amber)' }}>
                          {item.blocked_reason}
                        </div>
                      )}
                    </div>
                    <span
                      className="badge flex-shrink-0"
                      style={{
                        background: `${color}15`,
                        color,
                        borderColor: `${color}30`,
                        fontSize: 9,
                      }}
                    >
                      {item.delivery_state} / p:{item.computed_priority}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Activity — real, from the router's audit log for this agent specifically */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Activity</h3>
              <span className="text-[10.5px] font-mono" style={{ color: agentThroughput.length ? 'var(--green)' : 'var(--text-3)' }}>
                {agentThroughput.length ? 'live' : 'no activity yet'}
              </span>
            </div>
            {agentThroughput.length > 0 ? (
              <ResponsiveContainer width="100%" height={150}>
                <BarChart data={agentThroughput} margin={{ top: 4, right: 4, bottom: 0, left: -20 }} barSize={12}>
                  <XAxis dataKey="day" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11 }}
                    cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  />
                  <Bar dataKey="completed" name="Completed" fill={color} radius={[2,2,0,0]} opacity={0.85} />
                  <Bar dataKey="blocked"   name="Blocked"   fill="var(--red)" radius={[2,2,0,0]} opacity={0.7} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center py-8 text-[12px]" style={{ color: 'var(--text-3)' }}>
                No router audit events for {agent.name} yet.
              </div>
            )}
          </div>

          {/* Recent messages */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Recent Messages</h3>
              <span className="text-[10.5px] font-mono" style={{ color: hasRouterQueue ? 'var(--green)' : 'var(--text-3)' }}>
                {hasRouterQueue ? 'live inbound' : queueEnabled && queueError ? 'mock fallback' : 'mock'}
              </span>
            </div>
            <div className="space-y-2">
              {agentMessages.length === 0 && (
                <div className="text-center py-6 text-[12px]" style={{ color: 'var(--text-3)' }}>No recent messages</div>
              )}
              {agentMessages.slice(0, 4).map((msg, i) => {
                const isSender = msg.sender === agent.id
                const other    = AGENTS.find(a => a.id === (isSender ? msg.recipient : msg.sender))
                return (
                  <div key={msg.id} className="p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2 text-[11px]">
                        <span style={{ color: isSender ? color : 'var(--text-3)' }}>{isSender ? '↑' : '↓'}</span>
                        <span className="font-semibold" style={{ color: 'var(--text-2)' }}>{other?.name ?? 'Unknown'}</span>
                        <span className="font-mono text-[10px]" style={{ color: 'var(--text-3)' }}>{msg.task_type}</span>
                      </div>
                      <span className={`badge status-${msg.status}`} style={{ fontSize: 9 }}>{msg.status}</span>
                    </div>
                    <div className="text-[10px] font-mono truncate" style={{ color: 'var(--text-3)' }}>
                      {JSON.stringify(msg.payload).slice(0, 70)}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Instruction input */}
            <div className="mt-4 flex gap-2">
              <input
                value={instruction}
                onChange={e => setInstruction(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSend()}
                placeholder={`Send instruction to ${agent.name}…`}
                className="flex-1 rounded-lg px-3 py-2.5 text-[12.5px] outline-none"
                style={{
                  background: 'var(--card)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-1)',
                }}
              />
              <button
                onClick={handleSend}
                disabled={sending || !instruction.trim()}
                className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-white disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
                style={{ background: color }}
              >
                {sent ? <CheckCircle2 size={14} /> : <Send size={14} />}
              </button>
            </div>
            {sent && (
              <div className="text-[11px] mt-1.5 flex items-center gap-1" style={{ color: 'var(--green)' }}>
                <CheckCircle2 size={10} /> Delivered to {agent.name} — its response will appear in Recent Artifacts below (usually within a few seconds; longer if it calls a local model)
              </div>
            )}
            {sendError && (
              <div className="text-[11px] mt-1.5" style={{ color: 'var(--red)' }}>{sendError}</div>
            )}
          </div>
        </motion.div>

        {/* Right column */}
        <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.12 }}
          className="xl:col-span-1 space-y-5">

          {/* Radar */}
          <div className="card p-5">
            <h3 className="text-[13px] font-semibold mb-2" style={{ color: 'var(--text-1)' }}>Performance Profile</h3>
            <ResponsiveContainer width="100%" height={190}>
              <RadarChart data={radarData} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
                <PolarGrid stroke="rgba(255,255,255,0.06)" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                <Radar dataKey="value" stroke={color} fill={color} fillOpacity={0.12} strokeWidth={1.5} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Profile */}
          <div className="card p-5 space-y-4">
            <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Agent Profile</h3>

            <div>
              <div className="section-label mb-2 flex items-center gap-1.5">
                <Zap size={9} style={{ color: 'var(--amber)' }} /> Autonomous Actions
              </div>
              <div className="space-y-1.5">
                {agent.autonomousActions.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px]" style={{ color: 'var(--text-2)' }}>
                    <div className="w-1 h-1 rounded-full mt-1.5 flex-shrink-0" style={{ background: color }} />{a}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="section-label mb-2 flex items-center gap-1.5">
                <Shield size={9} style={{ color: 'var(--red)' }} /> Escalation Rules
              </div>
              <div className="space-y-1.5">
                {agent.escalationRules.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px]" style={{ color: 'var(--text-2)' }}>
                    <ChevronRight size={9} className="mt-0.5 flex-shrink-0" style={{ color: 'var(--red)' }} />{r}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="section-label mb-2 flex items-center gap-1.5">
                <BarChart3 size={9} style={{ color: 'var(--indigo-2)' }} /> Tools
              </div>
              <div className="flex flex-wrap gap-1.5">
                {agent.tools.map((t, i) => (
                  <span key={i} className="badge"
                    style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--text-2)', borderColor: 'rgba(255,255,255,0.10)', fontSize: 10 }}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Agent outputs */}
          <div className="card p-5">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <FileText size={12} style={{ color }} />
                <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Agent Outputs</h3>
              </div>
              <span className="text-[10.5px] font-mono" style={{ color: latestArtifact ? 'var(--green)' : 'var(--text-3)' }}>
                {latestArtifact ? 'live' : 'waiting'}
              </span>
            </div>
            {latestArtifact ? (
              <div className="space-y-3">
                <div>
                  <div className="text-[12px] font-semibold leading-snug" style={{ color: 'var(--text-1)' }}>
                    {latestArtifact.title}
                  </div>
                  <div className="text-[10px] font-mono mt-1 flex flex-wrap gap-x-2 gap-y-1" style={{ color: 'var(--text-3)' }}>
                    <span>{latestArtifact.artifact_type}</span>
                    <span>·</span>
                    <span>{new Date(latestArtifact.created_at).toLocaleString()}</span>
                    {latestArtifact.source_task_type && (
                      <>
                        <span>·</span>
                        <span>{latestArtifact.source_task_type}</span>
                      </>
                    )}
                  </div>
                </div>
                <pre
                  className="rounded-lg p-3 text-[11px] leading-relaxed overflow-auto"
                  style={{
                    maxHeight: 360,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: 'var(--text-2)',
                    background: 'rgba(255,255,255,0.025)',
                    border: '1px solid var(--border)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {latestArtifact.content ?? 'Artifact content is loading...'}
                </pre>
                {artifacts && artifacts.length > 1 && (
                  <div className="text-[10.5px] font-mono" style={{ color: 'var(--text-3)' }}>
                    {artifacts.length - 1} older {artifacts.length - 1 === 1 ? 'output' : 'outputs'} available
                  </div>
                )}
              </div>
            ) : (
              <div
                className="rounded-lg text-center px-4 py-8 text-[11px] leading-relaxed"
                style={{ color: 'var(--text-3)', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}
              >
                {artifactError ? 'Unable to load agent outputs from the router.' : 'No outputs yet. Send an instruction or run the initiation workflow.'}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
