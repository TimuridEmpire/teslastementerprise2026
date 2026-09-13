'use client'

import { useState } from 'react'
import { Settings, Database, ShieldCheck, RefreshCw, Check, AlertCircle } from 'lucide-react'
import { api } from '@/lib/api'

export default function SettingsPage() {
  const [health, setHealth] = useState<'idle' | 'checking' | 'ok' | 'error'>('idle')

  async function checkHealth() {
    setHealth('checking')
    try {
      await api.health()
      setHealth('ok')
    } catch {
      setHealth('error')
    }
  }

  const Section = ({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) => (
    <div className="card" style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, paddingBottom: 14, borderBottom: '1px solid var(--border)' }}>
        <div style={{ color: 'var(--primary-2)' }}>{icon}</div>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>{title}</span>
      </div>
      {children}
    </div>
  )

  return (
    <div className="p-6 space-y-5 max-w-2xl mx-auto">
      <div style={{ marginBottom: 4 }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Configuration</div>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>Settings</h1>
        <p style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 4 }}>
          Kanosei&apos;s backend connection.
        </p>
      </div>

      <Section icon={<Database size={14} />} title="Backend Connection">
        <p style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 14, lineHeight: 1.6 }}>
          The browser never talks to the router directly — every request goes through this
          site&apos;s own server, which is what actually holds the router&apos;s address and
          credentials.
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-secondary" onClick={checkHealth} disabled={health === 'checking'} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {health === 'checking'
              ? <><div className="spinner" style={{ width: 11, height: 11 }} /> Checking…</>
              : <><RefreshCw size={11} /> Check connection</>
            }
          </button>
          {health === 'ok' && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
              <Check size={11} /> api · ok
            </span>
          )}
          {health === 'error' && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>
              <AlertCircle size={11} /> unreachable
            </span>
          )}
        </div>
      </Section>

      <Section icon={<ShieldCheck size={14} />} title="Credentials">
        <p style={{ fontSize: 12.5, color: 'var(--text-2)', marginBottom: 10, lineHeight: 1.6 }}>
          There&apos;s nothing to configure here anymore, on purpose. The admin secret and every
          department&apos;s API key used to be readable straight out of this site&apos;s own
          JavaScript (client-side env vars ship to every visitor&apos;s browser) — including a
          form on this page that let you paste one in and see it again later. Both are gone.
        </p>
        <p style={{ fontSize: 12.5, color: 'var(--text-3)', lineHeight: 1.6 }}>
          Credentials now live only on the server, set once by whoever deployed this instance
          (<code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--card)', padding: '1px 5px', borderRadius: 4 }}>
            ROUTER_URL
          </code>,{' '}
          <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--card)', padding: '1px 5px', borderRadius: 4 }}>
            ENTERPRISE_ROUTER_ADMIN_SECRET
          </code>, and one{' '}
          <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--card)', padding: '1px 5px', borderRadius: 4 }}>
            *_AGENT_API_KEY
          </code>{' '}
          per department — see <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--card)', padding: '1px 5px', borderRadius: 4 }}>.env.example</code> at
          the repo root). Rotating a key means updating it there and restarting the site&apos;s
          server process — not pasting anything into a browser tab.
        </p>
      </Section>
    </div>
  )
}
