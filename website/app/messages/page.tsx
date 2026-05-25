'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Filter, ChevronRight, Copy, CheckCircle2, Circle } from 'lucide-react'
import { MESSAGES, AGENTS } from '@/lib/mock-data'
import { useQueue } from '@/lib/hooks'
import type { AgentId } from '@/lib/types'

const AGENT_COLOR: Record<AgentId, string> = {
  ceo: 'var(--agent-ceo)', product: 'var(--agent-product)', engineering: 'var(--agent-engineering)',
  hr: 'var(--agent-hr)', sales: 'var(--agent-sales)', marketing: 'var(--agent-marketing)', finance: 'var(--agent-finance)',
}

const ALL_AGENTS = ['all', ...AGENTS.map(a => a.id)]

type FilterState = { agent: string; status: string }

export default function MessagesPage() {
  const [filter, setFilter]           = useState<FilterState>({ agent: 'all', status: 'all' })
  const [selected, setSelected]       = useState<string | null>(null)
  const [copied, setCopied]           = useState(false)

  // Live MANAGER queue (gracefully empty when API key not set)
  const { data: liveQueue, enabled: queueEnabled, error: queueError } = useQueue('MANAGER', process.env.NEXT_PUBLIC_MANAGER_API_KEY ?? '')
  const hasRouterData = liveQueue !== null

  const messages = hasRouterData
    ? liveQueue.map(item => ({
      id:          item.envelope.id,
      sender:      item.envelope.sender.toLowerCase(),
      recipient:   item.envelope.recipient.toLowerCase(),
      task_type:   item.envelope.task_type,
      status:      item.envelope.status,
      delivery:    item.delivery_state,
      priority:    item.computed_priority,
      timestamp:   item.envelope.timestamp,
      payload:     item.envelope.payload,
      context:     item.envelope.context,
      error:       item.envelope.error,
      attempts:    item.attempt_count,
      blocked:     item.blocked_reason,
      lease_until: item.lease_until,
      dedupe_key:  item.dedupe_key,
      isLive:      true,
    }))
    : MESSAGES.map(m => ({
      id:        m.id,
      sender:    m.sender,
      recipient: m.recipient,
      task_type: m.task_type,
      status:    m.status,
      delivery:  m.delivery_state,
      priority:  m.urgency === 'critical' ? 10 : m.urgency === 'high' ? 7 : m.urgency === 'normal' ? 5 : 2,
      timestamp: m.timestamp,
      payload:   m.payload,
      context:   m.context,
      error:     m.error,
      attempts:  m.attempt_count,
      blocked:   m.error ?? '',
      lease_until: null,
      dedupe_key: null,
      isLive:    false,
    }))

  const filtered = messages.filter(m => {
    const agentMatch  = filter.agent  === 'all' || m.sender === filter.agent || m.recipient === filter.agent
    const statusMatch = filter.status === 'all' || m.status === filter.status
    return agentMatch && statusMatch
  })

  const sel = selected ? messages.find(m => m.id === selected) : null

  function copyJSON() {
    if (!sel) return
    navigator.clipboard.writeText(JSON.stringify(sel, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const statusColor: Record<string, string> = {
    done: 'var(--green)', in_progress: 'var(--indigo-2)', pending: 'var(--sky)', error: 'var(--red)',
  }
  const deliveryColor: Record<string, string> = {
    done: 'var(--green)', pending: 'var(--sky)', leased: 'var(--indigo-2)',
    blocked: 'var(--amber)', expired: 'var(--text-3)', dead_lettered: 'var(--red)',
  }

  return (
    <div className="p-6 space-y-5 h-full flex flex-col max-w-[1600px] mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-[16px] font-bold" style={{ color: 'var(--text-1)' }}>Messages</h1>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-3)' }}>
            {hasRouterData
              ? `${liveQueue.length} live queue ${liveQueue.length === 1 ? 'item' : 'items'}`
              : `${MESSAGES.length} mock messages${queueEnabled && queueError ? ' - router unavailable' : ''}`}
          </p>
        </div>
        {hasRouterData && (
          <span className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--green)' }}>
            <span className="live-dot" style={{ width: 6, height: 6 }} />
            Live queue active
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-shrink-0 flex-wrap">
        <div className="flex items-center gap-1.5" style={{ color: 'var(--text-3)' }}>
          <Filter size={12} />
          <span className="text-[11px]">Filter:</span>
        </div>
        {/* Agent filter */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {ALL_AGENTS.map(a => (
            <button
              key={a}
              onClick={() => setFilter(f => ({ ...f, agent: a }))}
              className="text-[11px] px-2.5 py-1 rounded-lg capitalize cursor-pointer transition-colors"
              style={{
                background: filter.agent === a ? 'var(--indigo)' : 'var(--card)',
                color:      filter.agent === a ? 'white' : 'var(--text-3)',
                border:     '1px solid var(--border)',
              }}
            >
              {a}
            </button>
          ))}
        </div>
        <div className="w-px h-4" style={{ background: 'var(--border)' }} />
        {/* Status filter */}
        {['all', 'pending', 'in_progress', 'done', 'error'].map(s => (
          <button
            key={s}
            onClick={() => setFilter(f => ({ ...f, status: s }))}
            className="text-[11px] px-2.5 py-1 rounded-lg capitalize cursor-pointer transition-colors"
            style={{
              background: filter.status === s ? 'var(--indigo)' : 'var(--card)',
              color:      filter.status === s ? 'white' : 'var(--text-3)',
              border:     '1px solid var(--border)',
            }}
          >
            {s.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 flex gap-5 min-h-0">

        {/* Message list */}
        <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
          {filtered.length === 0 && (
            <div className="text-center py-12 text-[12px]" style={{ color: 'var(--text-3)' }}>No messages match your filter</div>
          )}
          {filtered.map((msg, i) => {
            const isSelected = selected === msg.id
            const senderColor = AGENT_COLOR[msg.sender as AgentId] ?? 'var(--text-3)'
            return (
              <motion.button
                key={msg.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.02 }}
                onClick={() => setSelected(isSelected ? null : msg.id)}
                className="w-full text-left flex items-start gap-3 px-3 py-3 rounded-xl transition-colors cursor-pointer"
                style={{
                  background: isSelected ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.02)',
                  border: isSelected ? '1px solid rgba(255,255,255,0.14)' : '1px solid var(--border)',
                }}
              >
                {/* Sender dot */}
                <Circle size={7} fill={senderColor} style={{ color: senderColor, marginTop: 4, flexShrink: 0 }} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-[12px] font-semibold capitalize" style={{ color: senderColor }}>{msg.sender}</span>
                    <ChevronRight size={10} style={{ color: 'var(--text-3)' }} />
                    <span className="text-[12px] font-semibold capitalize" style={{ color: 'var(--text-2)' }}>{msg.recipient}</span>
                    <span className="font-mono text-[10px]" style={{ color: 'var(--text-3)' }}>{msg.task_type}</span>
                    {msg.isLive && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded font-bold" style={{ background: 'rgba(34,197,94,0.1)', color: 'var(--green)', border: '1px solid rgba(34,197,94,0.2)' }}>
                        LIVE
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="badge" style={{ fontSize: 9, color: statusColor[msg.status] ?? 'var(--text-3)', background: `${statusColor[msg.status] ?? 'var(--text-3)'}12`, borderColor: `${statusColor[msg.status] ?? 'var(--text-3)'}25` }}>
                      {msg.status.replace('_', ' ')}
                    </span>
                    {msg.delivery && (
                      <span className="text-[10px]" style={{ color: deliveryColor[msg.delivery] ?? 'var(--text-3)' }}>
                        {msg.delivery}
                      </span>
                    )}
                    <span className="text-[10px] ml-auto" style={{ color: 'var(--text-3)' }}>
                      {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              </motion.button>
            )
          })}
        </div>

        {/* Inspector panel */}
        <AnimatePresence>
          {sel && (
            <motion.div
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 16 }}
              className="w-80 flex-shrink-0 card flex flex-col overflow-hidden"
            >
              <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <span className="text-[12px] font-semibold" style={{ color: 'var(--text-1)' }}>Inspector</span>
                <button
                  onClick={copyJSON}
                  className="flex items-center gap-1.5 text-[11px] cursor-pointer"
                  style={{ color: copied ? 'var(--green)' : 'var(--text-3)' }}
                >
                  {copied ? <CheckCircle2 size={11} /> : <Copy size={11} />}
                  {copied ? 'Copied' : 'Copy JSON'}
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                {[
                  { label: 'Envelope', data: { id: sel.id, sender: sel.sender, recipient: sel.recipient, task_type: sel.task_type, timestamp: sel.timestamp } },
                  { label: 'State',    data: { status: sel.status, delivery: sel.delivery, priority: sel.priority, attempts: sel.attempts, blocked_reason: sel.blocked || '', lease_until: sel.lease_until, dedupe_key: sel.dedupe_key, error: sel.error || '—' } },
                  { label: 'Payload',  data: sel.payload },
                  { label: 'Context',  data: sel.context },
                ].map(section => (
                  <div key={section.label}>
                    <div className="section-label mb-2">{section.label}</div>
                    <div className="card-inner px-3 py-2.5">
                      <pre className="font-mono text-[10px] leading-relaxed whitespace-pre-wrap break-all" style={{ color: 'var(--text-2)' }}>
                        {JSON.stringify(section.data, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}


