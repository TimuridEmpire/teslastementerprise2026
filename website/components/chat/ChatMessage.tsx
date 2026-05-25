'use client'

import { motion } from 'framer-motion'
import { Zap } from 'lucide-react'

export type ChatMsg = {
  id: string
  role: 'user' | 'agent' | 'system'
  text: string
  agentName?: string
  agentColor?: string
  timestamp: Date
  loading?: boolean
}

function AgentAvatar({ name, color }: { name: string; color: string }) {
  return (
    <div
      className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-[11px] font-bold text-white"
      style={{ background: color, boxShadow: `0 0 12px ${color}40` }}
    >
      {name.slice(0, 2).toUpperCase()}
    </div>
  )
}

function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-0.5">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full"
          style={{
            background: 'var(--text-3)',
            animation: `typing-dot 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </span>
  )
}

export default function ChatMessage({ msg }: { msg: ChatMsg }) {
  if (msg.role === 'system') {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex justify-center py-1"
      >
        <span
          className="text-[11px] px-3 py-1 rounded-full"
          style={{ color: 'var(--text-3)', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}
        >
          {msg.text}
        </span>
      </motion.div>
    )
  }

  if (msg.role === 'user') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex justify-end gap-2.5"
      >
        <div className="max-w-[72%]">
          <div className="chat-bubble-user px-4 py-2.5 text-[13.5px] leading-relaxed">
            {msg.text}
          </div>
          <div className="text-right mt-1 text-[10px]" style={{ color: 'var(--text-3)' }}>
            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-[11px] font-bold text-white self-end"
          style={{ background: 'var(--indigo)' }}
        >
          M
        </div>
      </motion.div>
    )
  }

  // agent
  const color = msg.agentColor ?? 'var(--text-3)'
  const name  = msg.agentName ?? 'Agent'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-2.5"
    >
      {msg.agentColor ? (
        <AgentAvatar name={name} color={color} />
      ) : (
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <Zap size={12} style={{ color: 'var(--indigo)' }} />
        </div>
      )}
      <div className="max-w-[78%]">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[11px] font-semibold" style={{ color }}>{name}</span>
          <span className="text-[10px]" style={{ color: 'var(--text-3)' }}>
            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <div className="chat-bubble-agent px-4 py-2.5 text-[13.5px] leading-relaxed" style={{ color: 'var(--text-1)' }}>
          {msg.loading ? <TypingDots /> : msg.text}
        </div>
      </div>
    </motion.div>
  )
}
