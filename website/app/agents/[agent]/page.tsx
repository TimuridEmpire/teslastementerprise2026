'use client'

import { notFound } from 'next/navigation'
import { use, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Crown, Package, Code2, Users, TrendingUp, Megaphone,
  DollarSign, CheckCircle2, Clock, AlertCircle, XCircle,
  Send, ChevronRight, Zap, Shield, Activity, BarChart3,
  MessageSquare, History, Target, Circle,
} from 'lucide-react'
import { AGENTS, TASKS, MESSAGES, ACTIVITY_FEED } from '@/lib/mock-data'
import { useQueue } from '@/lib/hooks'
import type { AgentId, TaskStatus } from '@/lib/types'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'
import WorkerAgentsDropdown, { type WorkerAgent } from '@/components/agents/WorkerAgentsDropdown'
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

// Mock worker agents per department
const WORKER_MAP: Record<AgentId, WorkerAgent[]> = {
  ceo: [
    { id: 'ceo-w1', name: 'Strategy Analyst',   role: 'Market analysis & reports', status: 'active', taskCount: 3 },
    { id: 'ceo-w2', name: 'Board Liaison',       role: 'Investor communications',  status: 'idle',   taskCount: 0 },
  ],
  product: [
    { id: 'prod-w1', name: 'UX Researcher',      role: 'User interviews & studies', status: 'busy',   taskCount: 5 },
    { id: 'prod-w2', name: 'Data Analyst',       role: 'Metrics & A/B testing',     status: 'active', taskCount: 2 },
    { id: 'prod-w3', name: 'Backlog Curator',    role: 'Ticket management',         status: 'idle',   taskCount: 1 },
  ],
  engineering: [
    { id: 'eng-w1', name: 'Backend Worker',      role: 'API & database services',  status: 'busy',   taskCount: 6 },
    { id: 'eng-w2', name: 'Frontend Worker',     role: 'UI components & routing',  status: 'active', taskCount: 4 },
    { id: 'eng-w3', name: 'DevOps Agent',        role: 'CI/CD & infrastructure',   status: 'active', taskCount: 2 },
    { id: 'eng-w4', name: 'QA Agent',            role: 'Testing & bug tracking',   status: 'idle',   taskCount: 1 },
  ],
  hr: [
    { id: 'hr-w1', name: 'Recruiter Agent',      role: 'Candidate sourcing',       status: 'active', taskCount: 7 },
    { id: 'hr-w2', name: 'Onboarding Agent',     role: 'New hire process',         status: 'idle',   taskCount: 0 },
  ],
  sales: [
    { id: 'sales-w1', name: 'Lead Qualifier',    role: 'Inbound lead processing',  status: 'active', taskCount: 11 },
    { id: 'sales-w2', name: 'Account Manager',   role: 'Existing client relations',status: 'busy',   taskCount: 4 },
    { id: 'sales-w3', name: 'Proposal Writer',   role: 'RFP responses',            status: 'idle',   taskCount: 2 },
  ],
  marketing: [
    { id: 'mkt-w1', name: 'Content Agent',       role: 'Blog & social content',    status: 'busy',   taskCount: 8 },
    { id: 'mkt-w2', name: 'Campaign Manager',    role: 'Paid & email campaigns',   status: 'active', taskCount: 3 },
  ],
  finance: [
    { id: 'fin-w1', name: 'Expense Tracker',     role: 'Invoice & receipt logging',status: 'active', taskCount: 5 },
    { id: 'fin-w2', name: 'Forecast Agent',      role: 'Revenue modeling',         status: 'idle',   taskCount: 1 },
  ],
}

const TASK_STATUS_CONFIG: Record<TaskStatus, { label: string; icon: React.ReactNode }> = {
  done:        { label: 'Done',        icon: <CheckCircle2 size={11} /> },
  in_progress: { label: 'In Progress', icon: <Activity size={11} /> },
  pending:     { label: 'Pending',     icon: <Clock size={11} /> },
  blocked:     { label: 'Blocked',     icon: <AlertCircle size={11} /> },
  failed:      { label: 'Failed',      icon: <XCircle size={11} /> },
}

const STATUS_DOT: Record<string, string> = {
  active: 'var(--green)', busy: 'var(--amber)', idle: 'var(--sky)', error: 'var(--red)', offline: 'var(--text-3)',
}

const weeklyData = [
  { day: 'Mon', tasks: 3, msgs: 12 }, { day: 'Tue', tasks: 5, msgs: 18 },
  { day: 'Wed', tasks: 2, msgs: 9 },  { day: 'Thu', tasks: 6, msgs: 21 },
  { day: 'Fri', tasks: 4, msgs: 15 }, { day: 'Sat', tasks: 1, msgs: 4 },
  { day: 'Sun', tasks: 2, msgs: 6 },
]

export default function AgentPage({ params }: { params: Promise<{ agent: string }> }) {
  const { agent: agentId } = use(params)
  const agent = AGENTS.find(a => a.id === agentId)
  if (!agent) notFound()

  const color   = AGENT_COLORS[agent.id as AgentId]
  const workers = WORKER_MAP[agent.id as AgentId] ?? []
  const routerRecipient = agent.id.toUpperCase()

  const [instruction, setInstruction] = useState('')
  const [sending, setSending]         = useState(false)
  const [sent, setSent]               = useState(false)
  const [sendError, setSendError]     = useState('')

  // Live queue — API key empty by default; skips fetching gracefully
  const { data: queue } = useQueue(routerRecipient, process.env.NEXT_PUBLIC_MANAGER_API_KEY ?? '')

  const agentTasks    = TASKS.filter(t => t.assignedTo === agent.id)
  const agentMessages = MESSAGES.filter(m => m.sender === agent.id || m.recipient === agent.id)
  const agentActivity = ACTIVITY_FEED.filter(e => e.agentId === agent.id)

  const radarData = [
    { subject: 'Execution',   value: agent.successRate },
    { subject: 'Throughput',  value: Math.min(agent.activeTaskCount * 12, 100) },
    { subject: 'Trust',       value: agent.trustLevel },
    { subject: 'Messages',    value: Math.min(agent.totalMessages / 4, 100) },
    { subject: 'Efficiency',  value: 100 - agent.resourceUsage },
  ]

  const statusCounts = {
    done:        agentTasks.filter(t => t.status === 'done').length,
    in_progress: agentTasks.filter(t => t.status === 'in_progress').length,
    blocked:     agentTasks.filter(t => t.status === 'blocked').length,
    pending:     agentTasks.filter(t => t.status === 'pending').length,
  }

  async function handleSend() {
    if (!instruction.trim() || sending) return
    setSending(true)
    setSendError('')
    try {
      await api.manager.intervene({ recipient: routerRecipient, instruction: instruction.trim(), priority: 'normal' })
      setSent(true)
      setInstruction('')
      setTimeout(() => setSent(false), 3000)
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

          {/* KPIs */}
          <div className="flex gap-3 flex-wrap">
            {[
              { label: 'Tasks Done',   value: agent.completedTasks,   icon: <CheckCircle2 size={11} /> },
              { label: 'Success',      value: `${agent.successRate}%`, icon: <Target size={11} /> },
              { label: 'Active',       value: agent.activeTaskCount,   icon: <Activity size={11} /> },
              { label: 'Messages',     value: agent.totalMessages,     icon: <MessageSquare size={11} /> },
            ].map(k => (
              <div key={k.label} className="card-inner px-4 py-3 text-center">
                <div className="flex justify-center mb-0.5" style={{ color }}>{k.icon}</div>
                <div className="font-display text-lg font-bold" style={{ color: 'var(--text-1)' }}>{k.value}</div>
                <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>{k.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Resource bar */}
        <div className="relative mt-5">
          <div className="flex justify-between text-[11px] mb-1.5" style={{ color: 'var(--text-3)' }}>
            <span>Resource Usage</span>
            <span style={{ color: agent.resourceUsage > 85 ? 'var(--amber)' : color }}>{agent.resourceUsage}%</span>
          </div>
          <div className="progress">
            <motion.div
              className="progress-fill"
              initial={{ width: 0 }}
              animate={{ width: `${agent.resourceUsage}%` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              style={{ background: color }}
            />
          </div>
        </div>
      </motion.div>

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Left: tasks + queue + chart + messaging */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
          className="xl:col-span-2 space-y-5">

          {/* Worker agents dropdown */}
          <WorkerAgentsDropdown workers={workers} agentColor={color} />

          {/* Task status summary */}
          <div className="grid grid-cols-4 gap-3">
            {(Object.entries(statusCounts) as [TaskStatus, number][]).map(([status, count]) => (
              <div key={status} className="card p-3 text-center">
                <div className="font-display text-xl font-bold" style={{ color: 'var(--text-1)' }}>{count}</div>
                <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-3)' }}>{TASK_STATUS_CONFIG[status].label}</div>
              </div>
            ))}
          </div>

          {/* Live queue (from API) */}
          {queue && queue.length > 0 && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Live Queue</h3>
                <span className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--green)' }}>
                  <span className="live-dot" style={{ width: 6, height: 6 }} />
                  {queue.length} pending
                </span>
              </div>
              <div className="space-y-2">
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
                      p:{item.computed_priority}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Task list */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Task List</h3>
              <span className="text-[11px]" style={{ color: 'var(--text-3)' }}>{agentTasks.length} total</span>
            </div>
            <div className="space-y-2">
              {agentTasks.length === 0 && (
                <div className="text-center py-8 text-[12px]" style={{ color: 'var(--text-3)' }}>No tasks assigned</div>
              )}
              {agentTasks.map((task, i) => (
                <motion.div key={task.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
                  className="flex items-center gap-3 p-3 rounded-lg"
                  style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
                  <div style={{ color: 'var(--text-3)', flexShrink: 0 }}>{TASK_STATUS_CONFIG[task.status].icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[12.5px] font-medium truncate" style={{ color: 'var(--text-1)' }}>{task.title}</span>
                      <span className="badge flex-shrink-0" style={{ fontSize: 9, color, background: `${color}12`, borderColor: `${color}25` }}>
                        {task.priority}
                      </span>
                    </div>
                    {task.blockedReason && (
                      <div className="text-[10px] flex items-center gap-1 mb-1" style={{ color: 'var(--amber)' }}>
                        <AlertCircle size={9} />{task.blockedReason}
                      </div>
                    )}
                    <div className="flex items-center gap-3">
                      <div className="flex-1 progress" style={{ height: 2 }}>
                        <div className="progress-fill" style={{ width: `${task.progress}%`, background: color }} />
                      </div>
                      <span className="text-[10px] font-mono flex-shrink-0" style={{ color: 'var(--text-3)' }}>{task.progress}%</span>
                      <span className="text-[10px] flex-shrink-0" style={{ color: 'var(--text-3)' }}>
                        {new Date(task.dueDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Weekly chart */}
          <div className="card p-5">
            <h3 className="text-[13px] font-semibold mb-4" style={{ color: 'var(--text-1)' }}>Weekly Activity</h3>
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={weeklyData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }} barSize={8}>
                <XAxis dataKey="day" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11 }}
                  cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                />
                <Bar dataKey="tasks" name="Tasks"    fill={color}              radius={[2,2,0,0]} opacity={0.85} />
                <Bar dataKey="msgs"  name="Messages" fill="var(--indigo)"      radius={[2,2,0,0]} opacity={0.5} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Recent messages */}
          <div className="card p-5">
            <h3 className="text-[13px] font-semibold mb-4" style={{ color: 'var(--text-1)' }}>Recent Messages</h3>
            <div className="space-y-2">
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
                <CheckCircle2 size={10} /> Instruction delivered to {agent.name}
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

          {/* Activity */}
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-3">
              <History size={12} style={{ color: 'var(--text-3)' }} />
              <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>Recent Activity</h3>
            </div>
            <div className="space-y-3">
              {agentActivity.slice(0, 4).map((e) => (
                <div key={e.id} className="flex gap-2.5">
                  <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                    style={{ background: e.severity === 'error' ? 'var(--red)' : e.severity === 'warning' ? 'var(--amber)' : color }} />
                  <div>
                    <div className="text-[11px] font-medium" style={{ color: 'var(--text-1)' }}>{e.title}</div>
                    <div className="text-[10px] mt-0.5 leading-relaxed" style={{ color: 'var(--text-3)' }}>{e.description}</div>
                  </div>
                </div>
              ))}
              {agentActivity.length === 0 && (
                <div className="text-center py-4 text-[11px]" style={{ color: 'var(--text-3)' }}>No recent activity</div>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
