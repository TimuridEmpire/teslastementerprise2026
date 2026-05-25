'use client'

import { SLASH_COMMANDS } from '@/lib/chat-router'

interface SlashMenuProps {
  suggestions: typeof SLASH_COMMANDS
  onSelect: (command: string) => void
  activeIndex: number
}

export default function SlashMenu({ suggestions, onSelect, activeIndex }: SlashMenuProps) {
  if (suggestions.length === 0) return null

  return (
    <div
      className="absolute bottom-full mb-2 left-0 right-0 rounded-xl overflow-hidden z-50"
      style={{
        background: 'var(--card)',
        border: '1px solid var(--border)',
        boxShadow: '0 -8px 32px rgba(0,0,0,0.4)',
      }}
    >
      <div
        className="px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase"
        style={{ color: 'var(--text-3)', borderBottom: '1px solid var(--border)' }}
      >
        Route to agent
      </div>
      {suggestions.map((s, i) => (
        <button
          key={s.command}
          onClick={() => onSelect(s.command + ' ')}
          className="w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors cursor-pointer"
          style={{
            background: i === activeIndex ? 'rgba(255,255,255,0.05)' : 'transparent',
          }}
        >
          <span
            className="font-mono text-[12px] font-semibold w-14 flex-shrink-0"
            style={{ color: s.color }}
          >
            {s.command}
          </span>
          <span className="text-[12px] font-medium" style={{ color: 'var(--text-1)' }}>{s.label}</span>
          <span className="text-[11px] ml-1" style={{ color: 'var(--text-3)' }}>{s.description}</span>
        </button>
      ))}
    </div>
  )
}
