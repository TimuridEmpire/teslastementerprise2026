'use client'

import { motion } from 'framer-motion'
import {
  Database, AlertTriangle, TrendingUp, DollarSign,
  Cpu, Clock, Wrench, Crown, Package, Code2, Users,
  Megaphone, ChevronRight, CheckCircle2
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, AreaChart, Area, PieChart, Pie, Cell, Legend
} from 'recharts'
import { RESOURCES, BUDGET_ALLOCATIONS, RESOURCE_OVER_TIME, AGENTS, APPROVAL_REQUESTS } from '@/lib/mock-data'
import type { AgentId } from '@/lib/types'
import { cn } from '@/lib/utils'

const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={12} />, product: <Package size={12} />, engineering: <Code2 size={12} />,
  hr: <Users size={12} />, sales: <TrendingUp size={12} />, marketing: <Megaphone size={12} />,
  finance: <DollarSign size={12} />,
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  budget:   <DollarSign size={14} />,
  capacity: <TrendingUp size={14} />,
  compute:  <Cpu size={14} />,
  tools:    <Wrench size={14} />,
  time:     <Clock size={14} />,
}

const CATEGORY_COLOR: Record<string, string> = {
  budget: '#C8953A', capacity: '#5CB88A', compute: '#5A8CB8', tools: '#3A9C9C', time: '#8CB878'
}

const PIE_COLORS = ['#C8953A', '#5CB88A', '#5A8CB8', '#8CB878', '#C87A7A', '#3A9C9C']

const stagger = (i: number) => ({
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: 'easeOut', delay: i * 0.06 },
})

export default function ResourcesPage() {
  const pieData = BUDGET_ALLOCATIONS.map(b => ({
    name: b.department, value: b.allocated
  }))

  const radarData = AGENTS.map(a => ({
    subject: a.name,
    usage: a.resourceUsage,
    messages: Math.min(a.totalMessages / 5, 100),
    tasks: Math.min(a.activeTaskCount * 10, 100),
  }))

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto">

      {/* Header */}
      <motion.div {...stagger(0)}>
        <h1 className="font-display text-2xl font-bold tracking-wide text-[#f1f5f9]">Resources</h1>
        <p className="text-sm text-[#475569] mt-1">Operational resource allocation, utilization, and burn-rate across all departments</p>
      </motion.div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Budget', value: '$2.4M', sub: 'Q3 allocated', color: '#f59e0b', icon: <DollarSign size={15} /> },
          { label: 'Total Spent', value: '$1.14M', sub: '47.5% of budget', color: '#10b981', icon: <TrendingUp size={15} /> },
          { label: 'Warnings', value: '3', sub: 'Over 85% utilized', color: '#f59e0b', icon: <AlertTriangle size={15} /> },
          { label: 'Remaining', value: '$1.26M', sub: '52.5% remaining', color: '#10b981', icon: <CheckCircle2 size={15} /> },
        ].map((kpi, i) => (
          <motion.div key={kpi.label} {...stagger(i + 1)} className="glass-card p-4 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-16 h-16 opacity-5 flex items-end justify-end" style={{ color: kpi.color }}>
              <div className="scale-[3] mr-2 mb-2">{kpi.icon}</div>
            </div>
            <div className="relative">
              <div className="flex items-center gap-2 mb-2" style={{ color: kpi.color }}>{kpi.icon}
                <span className="text-[11px] uppercase tracking-wider text-[#475569]">{kpi.label}</span>
              </div>
              <div className="font-display text-2xl font-bold" style={{ color: kpi.color }}>{kpi.value}</div>
              <div className="text-[11px] text-[#475569] mt-1">{kpi.sub}</div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Budget by department pie */}
        <motion.div {...stagger(5)} className="glass-card p-5">
          <h3 className="text-[13px] font-semibold text-[#e2e8f0] mb-4">Budget Allocation</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3} dataKey="value">
                {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} opacity={0.85} />)}
              </Pie>
              <Tooltip
                contentStyle={{ background: 'var(--card)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', fontSize: '11px' }}
                formatter={(v: number) => [`$${(v/1000).toFixed(0)}K`, '']}
              />
              <Legend formatter={(v) => <span style={{ fontSize: '11px', color: '#94a3b8' }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Resource utilization over time */}
        <motion.div {...stagger(6)} className="glass-card p-5 xl:col-span-2">
          <h3 className="text-[13px] font-semibold text-[#e2e8f0] mb-4">Utilization Over Time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={RESOURCE_OVER_TIME} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
              <defs>
                {AGENTS.map(a => (
                  <linearGradient key={a.id} id={`grad-${a.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={a.color} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={a.color} stopOpacity={0.02} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="week" tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip
                contentStyle={{ background: 'var(--card)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', fontSize: '11px' }}
                formatter={(v: number) => [`${v}%`, '']}
              />
              {(['engineering','marketing','sales','product'] as const).map((key, i) => {
                const agent = AGENTS.find(a => a.id === key)!
                return (
                  <Area key={key} type="monotone" dataKey={key} stroke={agent.color} strokeWidth={1.5}
                    fill={`url(#grad-${key})`} name={agent.name} dot={false} />
                )
              })}
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Resource cards grid */}
      <motion.div {...stagger(7)}>
        <h3 className="text-[13px] font-semibold text-[#e2e8f0] mb-4">Resource Inventory</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {RESOURCES.map((res, i) => {
            const agent = AGENTS.find(a => a.id === res.ownedBy)!
            const pct = Math.round((res.used / res.total) * 100)
            const catColor = CATEGORY_COLOR[res.category]
            const isWarning = res.warning
            const isCritical = res.critical
            return (
              <motion.div key={res.id} {...stagger(i + 8)}
                className={cn('glass-card p-4 relative overflow-hidden transition-all hover:border-[rgba(255,255,255,0.12)]',
                  isCritical && 'border-[rgba(239,68,68,0.25)]',
                  isWarning && !isCritical && 'border-[rgba(245,158,11,0.2)]'
                )}>
                {(isWarning || isCritical) && (
                  <div className="absolute top-2 right-2">
                    <AlertTriangle size={11} style={{ color: isCritical ? '#ef4444' : '#f59e0b' }} />
                  </div>
                )}
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${catColor}12`, color: catColor }}>
                    {CATEGORY_ICONS[res.category]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-semibold text-[#e2e8f0] truncate">{res.name}</div>
                    <div className="text-[10px] flex items-center gap-1" style={{ color: agent.color }}>
                      {AGENT_ICONS[res.ownedBy]}{agent.name}
                    </div>
                  </div>
                </div>

                <div className="flex items-end justify-between mb-1">
                  <span className="font-display text-lg font-bold" style={{ color: isCritical ? '#ef4444' : isWarning ? '#f59e0b' : catColor }}>
                    {pct}%
                  </span>
                  <span className="text-[10px] font-mono" style={{ color: '#475569' }}>
                    {res.unit === '$' || res.unit === '$/mo'
                      ? `$${(res.used/1000).toFixed(0)}K / $${(res.total/1000).toFixed(0)}K`
                      : `${res.used} / ${res.total} ${res.unit}`}
                  </span>
                </div>

                <div className="h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.04)' }}>
                  <motion.div
                    initial={{ width: 0 }} animate={{ width: `${Math.min(pct, 100)}%` }}
                    transition={{ duration: 0.8, delay: i * 0.05, ease: 'easeOut' }}
                    className="h-full rounded-full"
                    style={{ background: isCritical ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : isWarning ? '#f59e0b' : catColor }}
                  />
                </div>

                {res.forecastBurn && (
                  <div className="mt-2 text-[10px]" style={{ color: res.forecastBurn > res.total ? '#ef4444' : '#475569' }}>
                    Forecast: {res.unit === '$' || res.unit === '$/mo' ? `$${(res.forecastBurn/1000).toFixed(0)}K` : `${res.forecastBurn} ${res.unit}`}
                    {res.forecastBurn > res.total && ' ⚠ Overrun'}
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>
      </motion.div>

      {/* Budget bars + Approvals */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

        {/* Spend vs allocation bars */}
        <motion.div {...stagger(16)} className="glass-card p-5">
          <h3 className="text-[13px] font-semibold text-[#e2e8f0] mb-4">Spend vs Allocation by Department</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={BUDGET_ALLOCATIONS.map(b => ({ dept: b.department, allocated: b.allocated/1000, spent: b.spent/1000 }))}
              margin={{ top: 4, right: 4, bottom: 0, left: -8 }} barSize={14}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="dept" tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} tickLine={false} unit="K" />
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', fontSize: '11px' }}
                formatter={(v: number) => [`$${v.toFixed(0)}K`, '']} />
              <Bar dataKey="allocated" fill="rgba(107,174,212,0.25)" name="Allocated" radius={[2, 2, 0, 0]} />
              <Bar dataKey="spent" fill="#5CB88A" name="Spent" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Approval requests */}
        <motion.div {...stagger(17)} className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[13px] font-semibold text-[#e2e8f0]">Approval Requests</h3>
            <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b' }}>
              {APPROVAL_REQUESTS.filter(a => a.status === 'pending').length} pending
            </span>
          </div>
          <div className="space-y-3">
            {APPROVAL_REQUESTS.map((req, i) => {
              const requester = AGENTS.find(a => a.id === req.requestedBy)!
              return (
                <motion.div key={req.id} {...stagger(i)} className="p-3 rounded-lg"
                  style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div>
                      <span className="text-[12px] font-semibold text-[#e2e8f0]">{req.title}</span>
                      {req.amount && (
                        <span className="ml-2 text-[11px] font-mono" style={{ color: '#f59e0b' }}>
                          ${req.amount.toLocaleString()}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0"
                      style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)' }}>
                      {req.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-[#475569] mb-2 line-clamp-2">{req.description}</div>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] flex items-center gap-1" style={{ color: requester.color }}>
                      {AGENT_ICONS[req.requestedBy]}Requested by {requester.name}
                    </span>
                    <div className="flex gap-2">
                      <button className="text-[10px] px-2.5 py-1 rounded font-semibold"
                        style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)' }}>
                        Approve
                      </button>
                      <button className="text-[10px] px-2.5 py-1 rounded font-semibold"
                        style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
                        Reject
                      </button>
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      </div>
    </div>
  )
}


