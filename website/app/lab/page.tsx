'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FlaskConical, Crown, Package, Code2, Users, TrendingUp,
  Megaphone, DollarSign, Play, Zap, Brain, ChevronRight,
  CheckCircle2, Cpu, MessageSquare, Shield, BarChart3
} from 'lucide-react'
import { AGENTS } from '@/lib/mock-data'
import type { AgentId } from '@/lib/types'
import { cn } from '@/lib/utils'

const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={16} />, product: <Package size={16} />, engineering: <Code2 size={16} />,
  hr: <Users size={16} />, sales: <TrendingUp size={16} />, marketing: <Megaphone size={16} />,
  finance: <DollarSign size={16} />,
}

const HOW_IT_WORKS = [
  { icon: <Cpu size={16} />, title: 'Initialize', desc: 'Agent loads its role context, tools, and decision rules into working memory.' },
  { icon: <Brain size={16} />, title: 'Reason', desc: 'Agent processes the task using its criteria, past context, and available data.' },
  { icon: <MessageSquare size={16} />, title: 'Coordinate', desc: 'In multi-agent mode, agents exchange structured JSON messages via the message bus.' },
  { icon: <Shield size={16} />, title: 'Escalate', desc: 'Actions above authority thresholds are automatically routed to the CEO for approval.' },
  { icon: <BarChart3 size={16} />, title: 'Report', desc: 'Outcomes and KPI impacts are logged to the audit trail and surfaced in the dashboard.' },
]

export default function LabPage() {
  const [mode, setMode] = useState<'single' | 'multi'>('single')
  const [selectedAgent, setSelectedAgent] = useState<AgentId>('ceo')
  const [initialized, setInitialized] = useState(false)
  const [initializing, setInitializing] = useState(false)

  const agent = AGENTS.find(a => a.id === selectedAgent)!

  const handleInit = () => {
    setInitializing(true)
    setInitialized(false)
    setTimeout(() => { setInitializing(false); setInitialized(true) }, 1800)
  }

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.14), rgba(255,255,255,0.08))', border: '1px solid rgba(255,255,255,0.14)' }}>
            <FlaskConical size={16} className="text-[#AAAAAA]" />
          </div>
          <h1 className="font-display text-2xl font-bold tracking-wide text-[#f1f5f9]">BRAIN Lab</h1>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold tracking-wider uppercase"
            style={{ background: 'rgba(255,255,255,0.07)', color: '#AAAAAA', border: '1px solid rgba(255,255,255,0.12)' }}>
            Experimental
          </span>
        </div>
        <p className="text-sm text-[#475569]">Sandbox for testing agents individually or in coordinated experiments</p>
      </motion.div>

      {/* Mode Toggle */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
        className="glass-card p-1 flex w-fit rounded-xl">
        {(['single', 'multi'] as const).map(m => (
          <button key={m} onClick={() => setMode(m)}
            className={cn('px-5 py-2 rounded-lg text-[12px] font-semibold transition-all',
              mode === m ? 'text-white' : 'text-[#475569] hover:text-[#94a3b8]'
            )}
            style={mode === m ? { background: 'rgba(255,255,255,0.10)' } : {}}>
            {m === 'single' ? 'Single Agent' : 'Multi-Agent'}
          </button>
        ))}
      </motion.div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Agent Tabs (left) */}
        <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}
          className="xl:col-span-1 space-y-3">
          <div className="glass-card p-4">
            <div className="text-[11px] uppercase tracking-widest text-[#334155] mb-3 font-semibold">Select Agent</div>
            <div className="space-y-1">
              {AGENTS.map(a => (
                <button key={a.id} onClick={() => { setSelectedAgent(a.id); setInitialized(false) }}
                  className={cn('w-full flex items-center gap-3 p-3 rounded-lg transition-all text-left',
                    selectedAgent === a.id ? 'border' : 'hover:bg-[rgba(255,255,255,0.03)]'
                  )}
                  style={selectedAgent === a.id ? {
                    background: `${a.color}10`, borderColor: `${a.color}30`, color: a.color
                  } : { color: '#475569' }}>
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: `${a.color}${selectedAgent === a.id ? '20' : '10'}`, color: a.color }}>
                    {AGENT_ICONS[a.id]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold" style={{ color: selectedAgent === a.id ? a.color : '#e2e8f0' }}>{a.name}</div>
                    <div className="text-[11px] truncate" style={{ color: '#475569' }}>{a.role}</div>
                  </div>
                  {selectedAgent === a.id && <ChevronRight size={12} style={{ color: a.color }} />}
                </button>
              ))}
            </div>
          </div>

          {/* How it works */}
          <div className="glass-card p-4">
            <div className="text-[11px] uppercase tracking-widest text-[#334155] mb-3 font-semibold">How it works</div>
            <div className="space-y-3">
              {HOW_IT_WORKS.map((step, i) => (
                <div key={step.title} className="flex gap-3">
                  <div className="w-6 h-6 rounded flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ background: 'rgba(255,255,255,0.05)', color: '#CCCCCC' }}>
                    {step.icon}
                  </div>
                  <div>
                    <div className="text-[12px] font-semibold text-[#e2e8f0]">{step.title}</div>
                    <div className="text-[11px] text-[#475569] leading-relaxed mt-0.5">{step.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Agent Profile (right) */}
        <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}
          className="xl:col-span-2 space-y-5">

          {/* Agent header */}
          <div className="glass-card p-6 relative overflow-hidden">
            <div className="absolute inset-0 opacity-30"
              style={{ background: `radial-gradient(ellipse at top right, ${agent.color}18, transparent 60%)` }} />
            <div className="relative flex items-start gap-5">
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center flex-shrink-0"
                style={{ background: `linear-gradient(135deg, ${agent.color}30, ${agent.color}10)`, border: `2px solid ${agent.color}30`, color: agent.color }}>
                <span className="scale-150">{AGENT_ICONS[agent.id]}</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="font-display text-xl font-bold" style={{ color: agent.color }}>{agent.name}</h2>
                  <span className="text-[11px] px-2.5 py-1 rounded-full font-semibold"
                    style={{ background: `${agent.color}12`, color: agent.color, border: `1px solid ${agent.color}25` }}>
                    Level {agent.hierarchyLevel}
                  </span>
                  <span className="text-[11px] px-2.5 py-1 rounded-full" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)' }}>
                    Trust {agent.trustLevel}/100
                  </span>
                </div>
                <div className="text-[13px] text-[#94a3b8] mt-1">{agent.role}</div>
                <div className="text-[12px] text-[#475569] mt-2 max-w-lg leading-relaxed">{agent.specialization}</div>
              </div>
              <motion.button
                onClick={handleInit}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                disabled={initializing}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-[12px] font-bold text-white flex-shrink-0"
                style={{
                  background: initializing ? 'rgba(255,255,255,0.14)' : `linear-gradient(135deg, ${agent.color}, ${agent.color}99)`,
                  boxShadow: initializing ? 'none' : `0 0 20px ${agent.color}30`
                }}>
                {initializing
                  ? <><div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />Initializing…</>
                  : initialized
                    ? <><CheckCircle2 size={13} />Initialized</>
                    : <><Play size={13} />Initialize Agent</>}
              </motion.button>
            </div>
          </div>

          {/* Initialized state */}
          <AnimatePresence>
            {initialized && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="glass-card p-4 overflow-hidden"
                style={{ borderColor: `${agent.color}30`, background: `${agent.color}06` }}>
                <div className="flex items-center gap-2 text-[12px] font-semibold mb-2" style={{ color: 'var(--text-2)' }}>
                  <Zap size={13} />
                  Agent {agent.name} initialized — ready to receive tasks
                </div>
                <div className="font-code text-[11px] space-y-1" style={{ color: 'var(--text-3)' }}>
                  <div><span style={{ color: 'var(--text-2)' }}>role:</span> <span style={{ color: 'var(--text-1)' }}>"{agent.role}"</span></div>
                  <div><span style={{ color: 'var(--text-2)' }}>trust_level:</span> <span style={{ color: 'var(--text-1)' }}>{agent.trustLevel}</span></div>
                  <div><span style={{ color: 'var(--text-2)' }}>hierarchy_level:</span> <span style={{ color: 'var(--text-1)' }}>{agent.hierarchyLevel}</span></div>
                  <div><span style={{ color: 'var(--text-2)' }}>status:</span> <span style={{ color: 'var(--text-1)' }}>"ready"</span></div>
                  <div><span style={{ color: 'var(--text-2)' }}>tools_loaded:</span> <span style={{ color: 'var(--text-1)' }}>[{agent.tools.map(t => `"${t}"`).join(', ')}]</span></div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Profile grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Autonomous Actions */}
            <div className="glass-card p-4">
              <div className="text-[11px] uppercase tracking-wider text-[#334155] mb-3 font-semibold flex items-center gap-2">
                <Zap size={11} style={{ color: '#f59e0b' }} /> Autonomous Actions
              </div>
              <div className="space-y-2">
                {agent.autonomousActions.map((action, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <CheckCircle2 size={12} className="mt-0.5 flex-shrink-0" style={{ color: '#10b981' }} />
                    <span className="text-[12px] text-[#94a3b8]">{action}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Decision Criteria */}
            <div className="glass-card p-4">
              <div className="text-[11px] uppercase tracking-wider text-[#334155] mb-3 font-semibold flex items-center gap-2">
                <Brain size={11} style={{ color: '#CCCCCC' }} /> Decision Criteria
              </div>
              <div className="space-y-2">
                {agent.decisionCriteria.map((c, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: '#CCCCCC' }} />
                    <span className="text-[12px] text-[#94a3b8]">{c}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Tools */}
            <div className="glass-card p-4">
              <div className="text-[11px] uppercase tracking-wider text-[#334155] mb-3 font-semibold flex items-center gap-2">
                <Cpu size={11} style={{ color: '#888888' }} /> Tools & Integrations
              </div>
              <div className="flex flex-wrap gap-2">
                {agent.tools.map((tool, i) => (
                  <span key={i} className="text-[11px] px-2.5 py-1 rounded-full font-medium"
                    style={{ background: 'rgba(107,174,212,0.1)', color: 'var(--sky)', border: '1px solid rgba(107,174,212,0.2)' }}>
                    {tool}
                  </span>
                ))}
              </div>
            </div>

            {/* Escalation Rules */}
            <div className="glass-card p-4">
              <div className="text-[11px] uppercase tracking-wider text-[#334155] mb-3 font-semibold flex items-center gap-2">
                <Shield size={11} style={{ color: '#ef4444' }} /> Escalation Rules
              </div>
              <div className="space-y-2">
                {agent.escalationRules.map((r, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <ChevronRight size={11} className="mt-0.5 flex-shrink-0" style={{ color: '#ef4444' }} />
                    <span className="text-[12px] text-[#94a3b8]">{r}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Communication Style */}
          <div className="glass-card p-4">
            <div className="text-[11px] uppercase tracking-wider text-[#334155] mb-2 font-semibold flex items-center gap-2">
              <MessageSquare size={11} style={{ color: '#22d3ee' }} /> Communication Style
            </div>
            <p className="text-[12px] text-[#94a3b8] leading-relaxed">{agent.communicationStyle}</p>
          </div>

          {/* Performance Stats */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Completed Tasks', value: agent.completedTasks, color: '#10b981' },
              { label: 'Success Rate', value: `${agent.successRate}%`, color: agent.color },
              { label: 'Total Messages', value: agent.totalMessages, color: '#888888' },
            ].map(stat => (
              <div key={stat.label} className="glass-card p-4 text-center">
                <div className="font-display text-2xl font-bold mb-1" style={{ color: stat.color }}>{stat.value}</div>
                <div className="text-[11px] text-[#475569]">{stat.label}</div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  )
}



