import { type Metadata } from 'next'
import CommandChat from '@/components/chat/CommandChat'
import { Zap, Users, ArrowRight } from 'lucide-react'

export const metadata: Metadata = { title: 'Command — BRAIN Enterprise Lab' }

const AGENT_CHIPS = [
  { label: 'CEO',         cmd: '/ceo',   color: 'var(--agent-ceo)' },
  { label: 'Product',     cmd: '/prod',  color: 'var(--agent-product)' },
  { label: 'Engineering', cmd: '/eng',   color: 'var(--agent-engineering)' },
  { label: 'HR',          cmd: '/hr',    color: 'var(--agent-hr)' },
  { label: 'Sales',       cmd: '/sales', color: 'var(--agent-sales)' },
  { label: 'Marketing',   cmd: '/mkt',   color: 'var(--agent-marketing)' },
  { label: 'Finance',     cmd: '/fin',   color: 'var(--agent-finance)' },
]

export default function ChatPage() {
  return (
    <div className="flex h-full" style={{ background: 'var(--bg)' }}>
      {/* Main chat panel */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Header */}
        <div
          className="flex items-center gap-3 px-6 py-4 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}
        >
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: 'var(--indigo)', boxShadow: '0 0 16px rgba(255,255,255,0.12)' }}
          >
            <Zap size={16} className="text-white" />
          </div>
          <div>
            <div className="text-[14px] font-semibold" style={{ color: 'var(--text-1)' }}>Central Command</div>
            <div className="text-[11px]" style={{ color: 'var(--text-3)' }}>Direct line to your company's agents</div>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="live-dot" style={{ width: 6, height: 6 }} />
            <span className="text-[11px]" style={{ color: 'var(--green)' }}>7 agents online</span>
          </div>
        </div>

        {/* Chat */}
        <CommandChat />
      </div>

      {/* Right sidebar — agent quick-access */}
      <div
        className="hidden xl:flex flex-col w-64 flex-shrink-0"
        style={{ borderLeft: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <div
          className="px-4 py-4"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <Users size={13} style={{ color: 'var(--text-3)' }} />
            <span className="section-label">Agent Roster</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {AGENT_CHIPS.map(a => (
            <div
              key={a.cmd}
              className="flex items-center justify-between px-3 py-2.5 rounded-lg"
              style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-2.5">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: a.color }} />
                <span className="text-[12.5px] font-medium" style={{ color: 'var(--text-1)' }}>{a.label}</span>
              </div>
              <span className="font-mono text-[10px]" style={{ color: 'var(--text-3)' }}>{a.cmd}</span>
            </div>
          ))}
        </div>

        {/* Quick prompts */}
        <div
          className="px-4 py-4"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <div className="section-label mb-3">Quick actions</div>
          <div className="space-y-2">
            {[
              { label: 'Status report', hint: 'Ask CEO for company overview' },
              { label: 'Sprint review', hint: '/prod sprint summary' },
              { label: 'Budget check',  hint: '/fin current burn rate' },
            ].map(q => (
              <div
                key={q.label}
                className="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer group"
                style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}
              >
                <div>
                  <div className="text-[12px] font-medium" style={{ color: 'var(--text-2)' }}>{q.label}</div>
                  <div className="font-mono text-[10px]" style={{ color: 'var(--text-3)' }}>{q.hint}</div>
                </div>
                <ArrowRight size={11} style={{ color: 'var(--text-3)' }} className="group-hover:opacity-100 opacity-40 transition-opacity" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}


