'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  GitBranch, CheckCircle2, Clock, Activity, AlertCircle,
  Crown, Package, Code2, Users, TrendingUp, Megaphone,
  DollarSign, ChevronRight, Plus, Shield, ArrowRight,
  Play, Pause, LayoutGrid, List
} from 'lucide-react'
import { WORKFLOWS, AGENTS } from '@/lib/mock-data'
import type { AgentId, WorkflowStatus, TaskStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={11} />, product: <Package size={11} />, engineering: <Code2 size={11} />,
  hr: <Users size={11} />, sales: <TrendingUp size={11} />, marketing: <Megaphone size={11} />,
  finance: <DollarSign size={11} />,
}

const STATUS_CONFIG: Record<WorkflowStatus, { color: string; bg: string; label: string }> = {
  active:    { color: '#10b981', bg: 'rgba(16,185,129,0.1)',  label: 'Active' },
  paused:    { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  label: 'Paused' },
  completed: { color: '#888888', bg: 'rgba(107,174,212,0.1)',  label: 'Completed' },
  failed:    { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   label: 'Failed' },
  draft:     { color: '#475569', bg: 'rgba(71,85,105,0.1)',   label: 'Draft' },
}

const STAGE_STATUS_CONFIG: Record<TaskStatus, { color: string; bg: string; icon: React.ReactNode }> = {
  done:        { color: '#10b981', bg: 'rgba(16,185,129,0.15)',  icon: <CheckCircle2 size={12} /> },
  in_progress: { color: '#CCCCCC', bg: 'rgba(255,255,255,0.07)', icon: <Activity size={12} /> },
  pending:     { color: '#475569', bg: 'rgba(71,85,105,0.12)',   icon: <Clock size={12} /> },
  blocked:     { color: '#f59e0b', bg: 'rgba(245,158,11,0.15)',  icon: <AlertCircle size={12} /> },
  failed:      { color: '#ef4444', bg: 'rgba(239,68,68,0.15)',   icon: <AlertCircle size={12} /> },
}

const KANBAN_COLUMNS: { key: WorkflowStatus; label: string; color: string }[] = [
  { key: 'active',    label: 'Active',    color: '#10b981' },
  { key: 'paused',    label: 'Paused',    color: '#f59e0b' },
  { key: 'completed', label: 'Completed', color: '#888888' },
  { key: 'draft',     label: 'Draft',     color: '#475569' },
]

export default function WorkflowsPage() {
  const [view, setView] = useState<'list' | 'kanban'>('list')
  const [selectedWf, setSelectedWf] = useState(WORKFLOWS[0].id)

  const activeWf = WORKFLOWS.find(w => w.id === selectedWf) ?? WORKFLOWS[0]
  const initiator = AGENTS.find(a => a.id === activeWf.initiatedBy)!

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-wide text-[#f1f5f9]">Workflows</h1>
          <p className="text-sm text-[#475569] mt-1">Cross-agent workflow orchestration and dependency tracking</p>
        </div>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="glass-card p-0.5 flex rounded-lg">
            {([['list', <List size={13} />], ['kanban', <LayoutGrid size={13} />]] as const).map(([v, icon]) => (
              <button key={v} onClick={() => setView(v)}
                className={cn('px-3 py-1.5 rounded-md text-[11px] font-semibold flex items-center gap-1.5 transition-all capitalize',
                  view === v ? 'text-white' : 'text-[#475569] hover:text-[#94a3b8]'
                )}
                style={view === v ? { background: 'rgba(255,255,255,0.10)' } : {}}>
                {icon}{v}
              </button>
            ))}
          </div>
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-[12px] font-semibold text-white"
            style={{ background: 'rgba(255,255,255,0.10)', boxShadow: 'none' }}>
            <Plus size={13} />New Workflow
          </motion.button>
        </div>
      </motion.div>

      {view === 'list' ? (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* Workflow list */}
          <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.08 }}
            className="xl:col-span-1 space-y-3">
            {WORKFLOWS.map((wf, i) => {
              const cfg = STATUS_CONFIG[wf.status]
              const isActive = selectedWf === wf.id
              return (
                <motion.div key={wf.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
                  onClick={() => setSelectedWf(wf.id)}
                  className={cn('glass-card p-4 cursor-pointer transition-all', isActive && 'border-[rgba(255,255,255,0.18)]')}
                  style={isActive ? { background: 'rgba(255,255,255,0.04)' } : {}}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[13px] font-semibold text-[#e2e8f0] truncate flex-1">{wf.name}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold ml-2 flex-shrink-0"
                      style={{ color: cfg.color, background: cfg.bg }}>{cfg.label}</span>
                  </div>
                  <p className="text-[11px] text-[#475569] line-clamp-2 mb-3">{wf.goal}</p>
                  <div className="flex items-center gap-2 mb-2">
                    {wf.tags.map(t => (
                      <span key={t} className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: 'rgba(255,255,255,0.04)', color: '#888888' }}>{t}</span>
                    ))}
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-1 text-[#475569]">
                      <GitBranch size={10} />{wf.stages.length} stages
                    </div>
                    <span style={{ color: cfg.color }}>{wf.progress}%</span>
                  </div>
                  <div className="mt-2 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.05)' }}>
                    <div className="h-full rounded-full transition-all" style={{ width: `${wf.progress}%`, background: `linear-gradient(90deg, ${cfg.color}88, ${cfg.color})` }} />
                  </div>
                </motion.div>
              )
            })}
          </motion.div>

          {/* Workflow detail + graph */}
          <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.12 }}
            className="xl:col-span-2 space-y-5">

            {/* Header */}
            <div className="glass-card p-5">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1 flex-wrap">
                    <h2 className="text-[15px] font-bold text-[#e2e8f0]">{activeWf.name}</h2>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                      style={{ color: STATUS_CONFIG[activeWf.status].color, background: STATUS_CONFIG[activeWf.status].bg }}>
                      {STATUS_CONFIG[activeWf.status].label}
                    </span>
                  </div>
                  <p className="text-[12px] text-[#475569] mb-3">{activeWf.goal}</p>
                  <div className="flex items-center gap-4 text-[11px] flex-wrap">
                    <span className="flex items-center gap-1 text-[#475569]">
                      <span>Initiated by</span>
                      <span style={{ color: initiator.color }} className="font-semibold">{initiator.name}</span>
                    </span>
                    <span className="text-[#334155]">Stage {activeWf.currentStageIndex + 1}/{activeWf.stages.length}</span>
                    <span className="text-[#334155]">{activeWf.progress}% complete</span>
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold"
                    style={{ background: 'rgba(255,255,255,0.05)', color: '#AAAAAA', border: '1px solid rgba(255,255,255,0.10)' }}>
                    <Pause size={11} />Pause
                  </button>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold"
                    style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)' }}>
                    <Play size={11} />Resume
                  </button>
                </div>
              </div>

              {/* Overall progress */}
              <div className="mt-4">
                <div className="h-2 rounded-full" style={{ background: 'rgba(255,255,255,0.05)' }}>
                  <motion.div initial={{ width: 0 }} animate={{ width: `${activeWf.progress}%` }} transition={{ duration: 0.9, ease: 'easeOut' }}
                    className="h-full rounded-full" style={{ background: 'rgba(255,255,255,0.12)' }} />
                </div>
              </div>
            </div>

            {/* Stage pipeline visualization */}
            <div className="glass-card p-5">
              <h3 className="text-[13px] font-semibold text-[#e2e8f0] mb-5">Pipeline</h3>
              <div className="relative">
                {/* Connecting line */}
                <div className="absolute top-5 left-5 right-5 h-px" style={{ background: 'rgba(255,255,255,0.06)' }} />

                {/* Stages */}
                <div className="flex items-start gap-1 overflow-x-auto pb-2">
                  {activeWf.stages.map((stage, i) => {
                    const cfg = STAGE_STATUS_CONFIG[stage.status]
                    const agent = AGENTS.find(a => a.id === stage.assignedAgent)!
                    const isCurrent = i === activeWf.currentStageIndex
                    return (
                      <div key={stage.id} className="flex items-center flex-shrink-0">
                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.07 }}
                          className={cn('relative flex flex-col items-center text-center w-28 group cursor-pointer')}
                        >
                          {/* Node */}
                          <div className="w-10 h-10 rounded-full flex items-center justify-center z-10 mb-2 transition-all"
                            style={{
                              background: cfg.bg,
                              border: `2px solid ${cfg.color}${isCurrent ? '' : '60'}`,
                              color: cfg.color,
                              boxShadow: isCurrent ? `0 0 20px ${cfg.color}40` : 'none',
                            }}>
                            {cfg.icon}
                          </div>
                          {/* Stage number */}
                          <div className="text-[10px] font-bold mb-1" style={{ color: cfg.color }}>S{i + 1}</div>
                          {/* Name */}
                          <div className="text-[10px] font-medium leading-tight text-center mb-1" style={{ color: isCurrent ? '#e2e8f0' : '#94a3b8' }}>
                            {stage.name}
                          </div>
                          {/* Agent chip */}
                          <div className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full"
                            style={{ background: `${agent.color}12`, color: agent.color, border: `1px solid ${agent.color}20` }}>
                            {AGENT_ICONS[agent.id]}{agent.name}
                          </div>
                          {/* Approval badge */}
                          {stage.requiresApproval && (
                            <div className="flex items-center gap-0.5 text-[9px] mt-1" style={{ color: '#f59e0b' }}>
                              <Shield size={8} />CEO req.
                            </div>
                          )}
                        </motion.div>

                        {/* Arrow between stages */}
                        {i < activeWf.stages.length - 1 && (
                          <ArrowRight size={12} className="mx-0.5 flex-shrink-0 mt-0.5" style={{ color: 'rgba(255,255,255,0.12)' }} />
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Stage detail list */}
            <div className="glass-card p-5">
              <h3 className="text-[13px] font-semibold text-[#e2e8f0] mb-4">Stage Details</h3>
              <div className="space-y-2.5">
                {activeWf.stages.map((stage, i) => {
                  const cfg = STAGE_STATUS_CONFIG[stage.status]
                  const agent = AGENTS.find(a => a.id === stage.assignedAgent)!
                  return (
                    <motion.div key={stage.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                      className="flex items-start gap-3 p-3 rounded-lg"
                      style={{ background: i === activeWf.currentStageIndex ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.04)' }}>
                      <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: cfg.bg, color: cfg.color }}>
                        {cfg.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[12px] font-semibold text-[#e2e8f0]">{stage.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                            style={{ background: `${agent.color}12`, color: agent.color }}>{agent.name}</span>
                          {stage.requiresApproval && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5"
                              style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b' }}>
                              <Shield size={9} />CEO Approval
                            </span>
                          )}
                          {stage.dependencies.length > 0 && (
                            <span className="text-[10px] text-[#334155]">
                              depends on {stage.dependencies.join(', ')}
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-[#475569] mt-0.5">{stage.description}</div>
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            </div>
          </motion.div>
        </div>
      ) : (
        /* Kanban view */
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-1 md:grid-cols-4 gap-5">
          {KANBAN_COLUMNS.map(col => {
            const colWorkflows = WORKFLOWS.filter(w => w.status === col.key)
            return (
              <div key={col.key}>
                <div className="flex items-center gap-2 mb-3 px-1">
                  <div className="w-2 h-2 rounded-full" style={{ background: col.color }} />
                  <span className="text-[12px] font-semibold" style={{ color: col.color }}>{col.label}</span>
                  <span className="text-[11px] text-[#334155] ml-auto">{colWorkflows.length}</span>
                </div>
                <div className="space-y-3">
                  {colWorkflows.map(wf => (
                    <div key={wf.id} className="glass-card p-4 cursor-pointer hover:border-[rgba(255,255,255,0.12)] transition-all">
                      <div className="text-[12px] font-semibold text-[#e2e8f0] mb-1">{wf.name}</div>
                      <div className="text-[11px] text-[#475569] line-clamp-2 mb-2">{wf.goal}</div>
                      <div className="h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.05)' }}>
                        <div className="h-full rounded-full" style={{ width: `${wf.progress}%`, background: col.color }} />
                      </div>
                    </div>
                  ))}
                  {colWorkflows.length === 0 && (
                    <div className="text-center py-8 text-[#334155] text-[12px] rounded-xl border border-dashed" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                      No workflows
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </motion.div>
      )}
    </div>
  )
}



