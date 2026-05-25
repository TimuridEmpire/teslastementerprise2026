'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, Pause, RotateCcw, ChevronRight, Cpu, Target, Clock,
  DollarSign, Users, Zap, CheckCircle2, Circle, AlertCircle,
  Crown, Package, Code2, TrendingUp, Megaphone, Activity
} from 'lucide-react'
import { SIMULATIONS, AGENTS } from '@/lib/mock-data'
import type { AgentId, SimulationEvent } from '@/lib/types'
import { cn } from '@/lib/utils'

const AGENT_COLORS: Record<AgentId, string> = {
  ceo: '#D4A44C', product: '#5A8CB8', engineering: '#5CB88A',
  hr: '#C87A7A', sales: '#7A9CB8', marketing: '#B8905A', finance: '#8CB878',
}
const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={12} />, product: <Package size={12} />, engineering: <Code2 size={12} />,
  hr: <Users size={12} />, sales: <TrendingUp size={12} />, marketing: <Megaphone size={12} />,
  finance: <DollarSign size={12} />,
}

const EXAMPLE_GOALS = [
  'Launch SaaS product to first 50 enterprise customers',
  'Increase quarterly revenue by 15%',
  'Hire virtual support team (5 agents)',
  'Run quarterly performance review',
  'Optimize marketing spend for Q3',
]

export default function SimulationPage() {
  const [activeSimId, setActiveSimId] = useState(SIMULATIONS[0].id)
  const [mode, setMode] = useState<'single' | 'multi'>('multi')
  const [selectedAgents, setSelectedAgents] = useState<AgentId[]>(['ceo', 'product', 'engineering', 'marketing', 'sales', 'finance'])
  const [goal, setGoal] = useState(EXAMPLE_GOALS[0])
  const [budget, setBudget] = useState('500000')
  const [status, setStatus] = useState<'running' | 'paused' | 'idle'>('running')

  const activeSim = SIMULATIONS.find(s => s.id === activeSimId) ?? SIMULATIONS[0]

  const toggleAgent = (id: AgentId) => {
    setSelectedAgents(prev =>
      prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-display text-2xl font-bold tracking-wide text-[#f1f5f9]">Simulation Control</h1>
        <p className="text-sm text-[#475569] mt-1">Configure and run multi-agent business cycle simulations</p>
      </motion.div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Config panel */}
        <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}
          className="glass-card p-6 space-y-5 xl:col-span-1">
          <h2 className="text-[13px] font-semibold text-[#e2e8f0]">New Simulation</h2>

          {/* Mode toggle */}
          <div>
            <label className="text-[11px] uppercase tracking-wider text-[#475569] mb-2 block">Mode</label>
            <div className="flex gap-2">
              {(['single', 'multi'] as const).map(m => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={cn(
                    'flex-1 py-2 rounded-lg text-[12px] font-semibold transition-all capitalize',
                    mode === m
                      ? 'bg-[rgba(255,255,255,0.10)] text-[#AAAAAA] border border-[rgba(255,255,255,0.18)]'
                      : 'bg-[rgba(255,255,255,0.03)] text-[#475569] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.10)]'
                  )}
                >
                  {m === 'single' ? 'Single Agent' : 'Multi-Agent'}
                </button>
              ))}
            </div>
          </div>

          {/* Goal */}
          <div>
            <label className="text-[11px] uppercase tracking-wider text-[#475569] mb-2 block">Business Goal</label>
            <textarea
              value={goal}
              onChange={e => setGoal(e.target.value)}
              rows={3}
              className="w-full rounded-lg p-3 text-[12px] resize-none outline-none focus:border-[rgba(255,255,255,0.25)] transition-colors"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', color: '#e2e8f0' }}
            />
            <div className="mt-1.5 flex flex-wrap gap-1">
              {EXAMPLE_GOALS.map(g => (
                <button key={g} onClick={() => setGoal(g)}
                  className="text-[10px] px-2 py-1 rounded text-[#475569] hover:text-[#CCCCCC] transition-colors"
                  style={{ background: 'rgba(255,255,255,0.03)' }}>
                  {g.split(' ').slice(0, 4).join(' ')}…
                </button>
              ))}
            </div>
          </div>

          {/* Budget */}
          <div>
            <label className="text-[11px] uppercase tracking-wider text-[#475569] mb-2 block">Budget ($)</label>
            <div className="relative">
              <DollarSign size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#475569]" />
              <input
                type="number"
                value={budget}
                onChange={e => setBudget(e.target.value)}
                className="w-full rounded-lg pl-8 pr-3 py-2.5 text-[13px] outline-none focus:border-[rgba(255,255,255,0.25)] transition-colors font-mono"
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', color: '#e2e8f0' }}
              />
            </div>
          </div>

          {/* Agent selection */}
          {mode === 'multi' && (
            <div>
              <label className="text-[11px] uppercase tracking-wider text-[#475569] mb-2 block">Participating Agents</label>
              <div className="grid grid-cols-2 gap-2">
                {AGENTS.map(agent => {
                  const selected = selectedAgents.includes(agent.id)
                  return (
                    <button
                      key={agent.id}
                      onClick={() => toggleAgent(agent.id)}
                      className={cn(
                        'flex items-center gap-2 p-2.5 rounded-lg text-[12px] font-medium transition-all',
                        selected
                          ? 'border'
                          : 'bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] text-[#475569]'
                      )}
                      style={selected ? {
                        background: `${AGENT_COLORS[agent.id]}12`,
                        borderColor: `${AGENT_COLORS[agent.id]}30`,
                        color: AGENT_COLORS[agent.id],
                      } : {}}
                    >
                      <span style={{ color: selected ? AGENT_COLORS[agent.id] : '#475569' }}>{AGENT_ICONS[agent.id]}</span>
                      {agent.name}
                      {selected && <CheckCircle2 size={10} className="ml-auto" />}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Launch button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="w-full py-3 rounded-lg font-semibold text-[13px] text-white flex items-center justify-center gap-2"
            style={{ background: 'rgba(255,255,255,0.10)', boxShadow: 'none' }}
          >
            <Play size={14} />
            Launch Simulation
          </motion.button>
        </motion.div>

        {/* Active simulation */}
        <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}
          className="xl:col-span-2 space-y-5">

          {/* Sim selector */}
          <div className="flex gap-3">
            {SIMULATIONS.map(sim => (
              <button
                key={sim.id}
                onClick={() => setActiveSimId(sim.id)}
                className={cn(
                  'flex-1 p-4 rounded-xl text-left transition-all border',
                  activeSimId === sim.id
                    ? 'bg-[rgba(255,255,255,0.05)] border-[rgba(255,255,255,0.14)]'
                    : 'glass-card opacity-60 hover:opacity-90'
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] font-bold text-[#e2e8f0] truncate">{sim.name}</span>
                  <span className={cn('text-[10px] px-2 py-0.5 rounded-full font-semibold',
                    sim.status === 'running' ? 'bg-[rgba(16,185,129,0.12)] text-[#10b981]' :
                    sim.status === 'paused' ? 'bg-[rgba(245,158,11,0.12)] text-[#f59e0b]' : 'bg-[rgba(71,85,105,0.12)] text-[#475569]'
                  )}>
                    {sim.status}
                  </span>
                </div>
                <div className="text-[11px] text-[#475569] line-clamp-1">{sim.goal}</div>
                <div className="mt-2 h-1 rounded-full bg-[rgba(255,255,255,0.05)]">
                  <div className="h-full rounded-full transition-all"
                    style={{ width: `${sim.progress}%`, background: 'rgba(255,255,255,0.12)' }} />
                </div>
              </button>
            ))}
          </div>

          {/* Sim details card */}
          <div className="glass-card p-5">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-[14px] font-semibold text-[#e2e8f0]">{activeSim.name}</h3>
                <p className="text-[12px] text-[#475569] mt-0.5 max-w-md">{activeSim.goal}</p>
              </div>
              {/* Controls */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setStatus(s => s === 'running' ? 'paused' : 'running')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-colors"
                  style={{ background: 'rgba(255,255,255,0.06)', color: '#AAAAAA', border: '1px solid rgba(255,255,255,0.10)' }}
                >
                  {status === 'running' ? <><Pause size={12} /> Pause</> : <><Play size={12} /> Resume</>}
                </button>
                <button className="p-1.5 rounded-lg transition-colors hover:bg-[rgba(255,255,255,0.05)]"
                  style={{ color: '#475569' }}>
                  <RotateCcw size={13} />
                </button>
              </div>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-4 mb-5">
              {[
                { label: 'Progress', value: `${activeSim.progress}%`, icon: <Activity size={13} /> },
                { label: 'Budget', value: `$${(activeSim.budget/1000).toFixed(0)}K`, icon: <DollarSign size={13} /> },
                { label: 'Horizon', value: activeSim.timeHorizon, icon: <Clock size={13} /> },
              ].map(stat => (
                <div key={stat.label} className="p-3 rounded-lg text-center"
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <div className="flex items-center justify-center gap-1 text-[#475569] mb-1">{stat.icon}<span className="text-[10px] uppercase tracking-wider">{stat.label}</span></div>
                  <div className="font-display text-[15px] font-bold text-[#e2e8f0]">{stat.value}</div>
                </div>
              ))}
            </div>

            {/* Progress bar */}
            <div className="mb-4">
              <div className="flex justify-between text-[11px] text-[#475569] mb-1">
                <span>Execution Progress</span>
                <span>{activeSim.progress}%</span>
              </div>
              <div className="h-2 rounded-full bg-[rgba(255,255,255,0.05)]">
                <motion.div
                  className="h-full rounded-full relative overflow-hidden"
                  style={{ width: `${activeSim.progress}%`, background: 'rgba(255,255,255,0.12)' }}
                  initial={{ width: 0 }}
                  animate={{ width: `${activeSim.progress}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse" />
                </motion.div>
              </div>
            </div>

            {/* Participating agents */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] text-[#475569]">Agents:</span>
              {activeSim.participatingAgents.map(agentId => {
                const agent = AGENTS.find(a => a.id === agentId)!
                return (
                  <span key={agentId} className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-full"
                    style={{ background: `${agent.color}12`, color: agent.color, border: `1px solid ${agent.color}25` }}>
                    {AGENT_ICONS[agentId]}{agent.name}
                  </span>
                )
              })}
            </div>
          </div>

          {/* Event Timeline */}
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[13px] font-semibold text-[#e2e8f0]">Execution Timeline</h3>
              <div className="flex items-center gap-1.5 text-[11px]" style={{ color: '#10b981' }}>
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                Live
              </div>
            </div>
            <div className="space-y-0 relative">
              <div className="absolute left-[18px] top-0 bottom-0 w-px bg-[rgba(255,255,255,0.06)]" />
              {activeSim.events.map((event, i) => {
                const agent = AGENTS.find(a => a.id === event.agentId)!
                return (
                  <motion.div
                    key={event.id}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.08 }}
                    className="flex gap-4 pb-5 relative"
                  >
                    <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 z-10"
                      style={{ background: `${agent.color}15`, border: `2px solid ${agent.color}30`, color: agent.color }}>
                      {AGENT_ICONS[event.agentId]}
                    </div>
                    <div className="flex-1 pt-1">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span className="text-[12px] font-semibold" style={{ color: agent.color }}>{agent.name}</span>
                          <span className="text-[12px] text-[#94a3b8] ml-2">{event.action}</span>
                        </div>
                        <span className="text-[10px] text-[#334155] flex-shrink-0">
                          {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-[12px] text-[#e2e8f0] mt-1 font-medium">"{event.decision}"</p>
                      {event.impact && (
                        <p className="text-[11px] text-[#475569] mt-0.5 flex items-center gap-1">
                          <ChevronRight size={10} />{event.impact}
                        </p>
                      )}
                    </div>
                  </motion.div>
                )
              })}
              {/* Blinking cursor at end */}
              <div className="flex gap-4 relative">
                <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 z-10 border-dashed"
                  style={{ border: '2px dashed rgba(255,255,255,0.14)' }}>
                  <div className="w-2 h-2 rounded-full bg-[#CCCCCC] animate-pulse" />
                </div>
                <div className="pt-2.5">
                  <span className="text-[12px] text-[#475569] italic">Agents processing next decision...</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}



