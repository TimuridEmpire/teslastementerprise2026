'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import {
  LayoutDashboard, MessageSquare, FlaskConical, GitBranch,
  Database, Eye, Crown, Package, Code2, Users, TrendingUp,
  Megaphone, DollarSign, ChevronDown, ChevronRight,
  Menu, X, Circle, Settings, Zap, Activity,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { AGENTS } from '@/lib/mock-data'
import { useHealth } from '@/lib/hooks'
import type { AgentId } from '@/lib/types'

const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo:         <Crown size={13} />,
  product:     <Package size={13} />,
  engineering: <Code2 size={13} />,
  hr:          <Users size={13} />,
  sales:       <TrendingUp size={13} />,
  marketing:   <Megaphone size={13} />,
  finance:     <DollarSign size={13} />,
}

const AGENT_COLOR: Record<AgentId, string> = {
  ceo:         'var(--agent-ceo)',
  product:     'var(--agent-product)',
  engineering: 'var(--agent-engineering)',
  hr:          'var(--agent-hr)',
  sales:       'var(--agent-sales)',
  marketing:   'var(--agent-marketing)',
  finance:     'var(--agent-finance)',
}

const STATUS_COLOR: Record<string, string> = {
  active:  'var(--green)',
  busy:    'var(--amber)',
  idle:    'var(--sky)',
  error:   'var(--red)',
  offline: 'var(--text-3)',
}

const AGENT_STATUS: Record<AgentId, string> = {
  ceo:         'active',
  product:     'busy',
  engineering: 'busy',
  hr:          'idle',
  sales:       'active',
  marketing:   'active',
  finance:     'idle',
}

const CORE_NAV = [
  { href: '/dashboard',    label: 'Overview',      icon: <LayoutDashboard size={14} /> },
  { href: '/chat',         label: 'Command',        icon: <MessageSquare size={14} />, tag: 'Chat' },
  { href: '/workflows',    label: 'Workflows',      icon: <GitBranch size={14} /> },
  { href: '/observability',label: 'Observability',  icon: <Eye size={14} /> },
]

const OPS_NAV = [
  { href: '/resources',     label: 'Resources',     icon: <Database size={14} /> },
  { href: '/messages',      label: 'Messages',      icon: <MessageSquare size={14} /> },
  { href: '/lab',           label: 'Lab',           icon: <FlaskConical size={14} /> },
]

function SidebarContent({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname()
  const router   = useRouter()
  const [agentsOpen, setAgentsOpen] = useState(true)
  const { data: health } = useHealth()

  const isSettings = pathname === '/settings'

  return (
    <aside
      className="flex flex-col h-full"
      style={{
        width: 'var(--sidebar-w)',
        background: 'var(--surface)',
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* Logo / brand */}
      <div
        className="flex items-center gap-3 px-4"
        style={{ height: 'var(--topbar-h)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}
      >
        {/* Kanosei logo mark */}
        <div
          className="flex items-center justify-center flex-shrink-0"
          style={{
            width: 30, height: 30,
            borderRadius: 8,
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.12)',
          }}
        >
          <Zap size={14} style={{ color: 'var(--primary-2)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="kanosei-mark">KANOSEI</div>
          <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.16em', color: 'var(--text-3)', textTransform: 'uppercase' }}>
            Autonomous Co.
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="lg:hidden" style={{ color: 'var(--text-3)' }}>
            <X size={15} />
          </button>
        )}
      </div>

      {/* Company status */}
      <div
        className="flex items-center justify-between px-4"
        style={{ height: 36, borderBottom: '1px solid var(--border)', flexShrink: 0 }}
      >
        <span style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Company
        </span>
        {health ? (
          <span className="flex items-center gap-1.5" style={{ fontSize: 11, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
            <span className="live-dot" style={{ width: 6, height: 6 }} />
            operating
          </span>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>offline</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">

        {/* Core */}
        <div>
          <div className="section-label px-2 mb-2">Core</div>
          <div className="space-y-0.5">
            {CORE_NAV.map(item => {
              const active = pathname === item.href
              return (
                <Link key={item.href} href={item.href}
                  className={cn('nav-item', active && 'active')}
                  style={active ? { color: 'var(--primary-2)' } : {}}
                >
                  <span style={{ color: active ? 'var(--primary-2)' : 'var(--text-3)' }}>
                    {item.icon}
                  </span>
                  <span className="flex-1">{item.label}</span>
                  {item.tag && !active && (
                    <span
                      style={{
                        fontSize: 9,
                        padding: '1px 6px',
                        borderRadius: 3,
                        background: 'rgba(255,255,255,0.06)',
                        color: 'var(--primary-2)',
                        fontWeight: 600,
                        letterSpacing: '0.05em',
                        textTransform: 'uppercase',
                      }}
                    >
                      {item.tag}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>
        </div>

        {/* Agents */}
        <div>
          <button
            onClick={() => setAgentsOpen(o => !o)}
            className="w-full flex items-center justify-between px-2 mb-2 cursor-pointer"
          >
            <span className="section-label">Agents</span>
            {agentsOpen
              ? <ChevronDown size={11} style={{ color: 'var(--text-3)' }} />
              : <ChevronRight size={11} style={{ color: 'var(--text-3)' }} />}
          </button>
          {agentsOpen && (
            <div className="space-y-0.5">
              {AGENTS.map(agent => {
                const active = pathname === `/agents/${agent.id}`
                const color  = AGENT_COLOR[agent.id as AgentId]
                const status = AGENT_STATUS[agent.id as AgentId] ?? agent.status
                return (
                  <Link
                    key={agent.id}
                    href={`/agents/${agent.id}`}
                    className={cn('nav-item', active && 'active')}
                    style={active ? { color: 'var(--text-1)', background: 'rgba(255,255,255,0.06)', borderColor: 'var(--border)' } : {}}
                  >
                    <span style={{ color: active ? 'var(--text-2)' : 'var(--text-3)' }}>{AGENT_ICONS[agent.id as AgentId]}</span>
                    <span className="flex-1">{agent.name}</span>
                    <span style={{ fontSize: 10, color: STATUS_COLOR[status] ?? 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                      {status}
                    </span>
                  </Link>
                )
              })}
            </div>
          )}
        </div>

        {/* Operations */}
        <div>
          <div className="section-label px-2 mb-2">Operations</div>
          <div className="space-y-0.5">
            {OPS_NAV.map(item => {
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn('nav-item', active && 'active')}
                  style={active ? { color: 'var(--primary-2)' } : {}}
                >
                  <span style={{ color: active ? 'var(--primary-2)' : 'var(--text-3)' }}>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>
        </div>
      </nav>

      {/* Settings + user */}
      <div style={{ borderTop: '1px solid var(--border)', padding: '10px 12px 12px' }}>
        <Link
          href="/settings"
          className={cn('nav-item', isSettings && 'active')}
          style={{ marginBottom: 8, ...(isSettings ? { color: 'var(--primary-2)' } : {}) }}
        >
          <Settings size={14} style={{ color: isSettings ? 'var(--primary-2)' : 'var(--text-3)' }} />
          <span className="flex-1">Settings</span>
        </Link>
        <div className="flex items-center gap-2.5 px-2">
          <div
            className="flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0"
            style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--primary) 0%, var(--primary-3) 100%)',
            }}
          >
            M
          </div>
          <div className="min-w-0 flex-1">
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-1)' }}>Manager</div>
            <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>founder · admin</div>
          </div>
        </div>
      </div>
    </aside>
  )
}

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      {/* Desktop */}
      <div className="hidden lg:flex h-full flex-shrink-0">
        <SidebarContent />
      </div>

      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-3 left-3 z-50 w-9 h-9 flex items-center justify-center rounded-lg cursor-pointer"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        aria-label="Open navigation"
      >
        <Menu size={15} style={{ color: 'var(--text-2)' }} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <div className="relative z-50 h-full">
            <SidebarContent onClose={() => setMobileOpen(false)} />
          </div>
        </div>
      )}
    </>
  )
}

