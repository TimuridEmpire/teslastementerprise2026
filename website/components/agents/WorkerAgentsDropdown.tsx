'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Circle, Cpu } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export type WorkerAgent = {
  id: string
  name: string
  role: string
  status: 'active' | 'busy' | 'idle' | 'offline'
  taskCount: number
}

interface WorkerAgentsDropdownProps {
  workers: WorkerAgent[]
  agentColor: string
}

const STATUS_COLOR: Record<string, string> = {
  active:  'var(--green)',
  busy:    'var(--amber)',
  idle:    'var(--sky)',
  offline: 'var(--text-3)',
}

export default function WorkerAgentsDropdown({ workers, agentColor }: WorkerAgentsDropdownProps) {
  const [open, setOpen] = useState(false)
  if (workers.length === 0) return null

  const activeCount = workers.filter(w => w.status === 'active' || w.status === 'busy').length

  return (
    <div className="card">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 cursor-pointer"
      >
        <div className="flex items-center gap-2.5">
          <Cpu size={13} style={{ color: 'var(--text-3)' }} />
          <span className="text-[12.5px] font-semibold" style={{ color: 'var(--text-1)' }}>
            Worker Agents
          </span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: `${agentColor}18`,
              color: agentColor,
              border: `1px solid ${agentColor}30`,
            }}
          >
            {activeCount}/{workers.length} active
          </span>
        </div>
        {open
          ? <ChevronDown size={13} style={{ color: 'var(--text-3)' }} />
          : <ChevronRight size={13} style={{ color: 'var(--text-3)' }} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            style={{ overflow: 'hidden', borderTop: '1px solid var(--border)' }}
          >
            <div className="px-4 py-3 space-y-2">
              {workers.map(w => (
                <div
                  key={w.id}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg"
                  style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}
                >
                  <Circle
                    size={6}
                    fill={STATUS_COLOR[w.status]}
                    style={{ color: STATUS_COLOR[w.status], flexShrink: 0 }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-medium truncate" style={{ color: 'var(--text-1)' }}>{w.name}</div>
                    <div className="text-[10px] truncate" style={{ color: 'var(--text-3)' }}>{w.role}</div>
                  </div>
                  <div className="text-[10px] flex-shrink-0" style={{ color: 'var(--text-3)' }}>
                    {w.taskCount} tasks
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
