'use client'

import { useEffect, useRef, useState } from 'react'
import { usePathname } from 'next/navigation'
import { Bell, Search, ChevronRight, AlertCircle, AlertTriangle, Clock, Info, ArrowRight, X } from 'lucide-react'
import { useHealth } from '@/lib/hooks'
import { NOTIFICATIONS } from '@/lib/mock-data'
import type { KanoseiNotification } from '@/lib/types'

const PAGE_LABELS: Record<string, string[]> = {
  '/dashboard':          ['Overview'],
  '/chat':               ['Command'],
  '/simulation':         ['Simulation'],
  '/lab':                ['Lab'],
  '/agents/ceo':         ['Agents', 'CEO'],
  '/agents/product':     ['Agents', 'Product'],
  '/agents/engineering': ['Agents', 'Engineering'],
  '/agents/hr':          ['Agents', 'HR'],
  '/agents/sales':       ['Agents', 'Sales'],
  '/agents/marketing':   ['Agents', 'Marketing'],
  '/agents/finance':     ['Agents', 'Finance'],
  '/workflows':          ['Workflows'],
  '/resources':          ['Resources'],
  '/messages':           ['Messages'],
  '/observability':      ['Observability'],
  '/settings':           ['Settings'],
  '/onboarding':         ['Setup'],
}

const SEVERITY_META = {
  error:   { icon: AlertCircle,   color: 'var(--red)' },
  warning: { icon: AlertTriangle, color: 'var(--amber)' },
  pending: { icon: Clock,         color: 'var(--primary-2)' },
  info:    { icon: Info,          color: 'var(--sky)' },
} as const

function NotifItem({ n, onClick }: { n: KanoseiNotification; onClick: () => void }) {
  const meta = SEVERITY_META[n.severity as keyof typeof SEVERITY_META] ?? SEVERITY_META.info
  const Icon = meta.icon
  return (
    <div
      className={`notif-item${n.unread ? ' unread' : ''}`}
      onClick={onClick}
    >
      <div style={{ display: 'flex', gap: 11 }}>
        <div style={{ marginTop: 1, flexShrink: 0, color: meta.color }}>
          <Icon size={14} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <span style={{
              fontSize: 9.5,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: meta.color,
              fontWeight: 600,
            }}>
              {n.section}
            </span>
            <span style={{ width: 3, height: 3, borderRadius: '50%', background: 'var(--text-4)' }} />
            <span style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{n.when}</span>
            {n.unread && (
              <span style={{ marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%', background: 'var(--primary)' }} />
            )}
          </div>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-1)', marginBottom: 2, lineHeight: 1.35 }}>
            {n.title}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--text-3)', lineHeight: 1.5 }}>
            {n.desc}
          </div>
        </div>
      </div>
    </div>
  )
}

function NotificationsPanel({
  notifications, onClose, onMarkAll,
}: {
  notifications: KanoseiNotification[]
  onClose: () => void
  onMarkAll: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const unread = notifications.filter(n => n.unread).length

  return (
    <div className="notif-panel" ref={ref}>
      {/* Header */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>Notifications</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
            {unread} unread · grouped by section
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {unread > 0 && (
            <button
              className="btn btn-ghost"
              style={{ padding: '4px 10px', fontSize: 11 }}
              onClick={onMarkAll}
            >
              Mark all read
            </button>
          )}
          <button className="btn-icon" style={{ width: 28, height: 28 }} onClick={onClose}>
            <X size={12} />
          </button>
        </div>
      </div>

      {/* Items */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {notifications.map(n => (
          <NotifItem key={n.id} n={n} onClick={() => {}} />
        ))}
        {notifications.length === 0 && (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>
            All caught up
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '10px 16px',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: 11,
        color: 'var(--text-3)',
      }}>
        <span style={{ fontFamily: 'var(--font-mono)' }}>showing {notifications.length}</span>
        <span style={{ color: 'var(--primary-2)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          View all <ArrowRight size={11} />
        </span>
      </div>
    </div>
  )
}

export default function TopBar() {
  const pathname = usePathname()
  const { data: health } = useHealth()
  const crumbs = PAGE_LABELS[pathname] ?? ['KANOSEI']

  const [notifOpen, setNotifOpen]   = useState(false)
  const [notifications, setNotifs]  = useState<KanoseiNotification[]>(NOTIFICATIONS)
  const unread = notifications.filter(n => n.unread).length

  const markAll = () => setNotifs(ns => ns.map(n => ({ ...n, unread: false })))

  return (
    <header
      style={{
        height: 'var(--topbar-h)',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        flexShrink: 0,
      }}
    >
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
        <span style={{ color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>KANOSEI</span>
        {crumbs.map((crumb, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ChevronRight size={11} style={{ color: 'var(--text-4)' }} />
            <span style={{
              color: i === crumbs.length - 1 ? 'var(--text-1)' : 'var(--text-3)',
              fontWeight: i === crumbs.length - 1 ? 500 : 400,
            }}>
              {crumb}
            </span>
          </span>
        ))}
      </div>

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* Search */}
        <div
          className="hidden md:flex"
          style={{
            alignItems: 'center',
            gap: 8,
            padding: '7px 12px',
            borderRadius: 7,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            color: 'var(--text-3)',
            fontSize: 12,
            cursor: 'pointer',
            minWidth: 220,
          }}
        >
          <Search size={12} />
          <span style={{ flex: 1 }}>Search agents, tasks, workflows…</span>
          <kbd style={{
            fontSize: 10, padding: '1px 6px', borderRadius: 4,
            background: 'var(--surface)', border: '1px solid var(--border)',
            fontFamily: 'var(--font-mono)',
          }}>⌘K</kbd>
        </div>

        {/* API health */}
        {health ? (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '6px 11px', borderRadius: 999,
            background: 'rgba(52,211,153,0.08)',
            border: '1px solid rgba(52,211,153,0.22)',
            color: 'var(--green)', fontSize: 11,
            fontFamily: 'var(--font-mono)',
          }}>
            <span className="live-dot" style={{ width: 6, height: 6 }} />
            api · ok
          </div>
        ) : (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '6px 11px', borderRadius: 999,
            background: 'rgba(74,84,117,0.08)',
            border: '1px solid var(--border)',
            color: 'var(--text-3)', fontSize: 11,
            fontFamily: 'var(--font-mono)',
          }}>
            offline
          </div>
        )}

        {/* Notifications */}
        <div style={{ position: 'relative' }}>
          <button
            className="btn-icon"
            onClick={() => setNotifOpen(o => !o)}
            style={{ position: 'relative' }}
          >
            <Bell size={14} />
            {unread > 0 && (
              <span style={{
                position: 'absolute', top: -4, right: -4,
                minWidth: 16, height: 16, padding: '0 4px',
                borderRadius: 999,
                background: 'var(--red)',
                color: 'white', fontSize: 9.5, fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '2px solid var(--surface)',
              }}>
                {unread}
              </span>
            )}
          </button>

          {notifOpen && (
            <NotificationsPanel
              notifications={notifications}
              onClose={() => setNotifOpen(false)}
              onMarkAll={markAll}
            />
          )}
        </div>
      </div>
    </header>
  )
}
