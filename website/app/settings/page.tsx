'use client'

import { useState, useEffect } from 'react'
import { Settings, Database, Key, Zap, Check, AlertCircle, RefreshCw, Eye, EyeOff, Save } from 'lucide-react'
import { api } from '@/lib/api'
import { saveAdminSecret, saveManagerKey, initCredentialsFromCookies, getCachedAdminSecret, getCachedManagerKey } from '@/lib/memory'

interface FieldState { value: string; show?: boolean; saved?: boolean; error?: string }

export default function SettingsPage() {
  const [apiUrl,       setApiUrl]       = useState<FieldState>({ value: '' })
  const [adminSecret,  setAdminSecret]  = useState<FieldState>({ value: '', show: false })
  const [managerKey,   setManagerKey]   = useState<FieldState>({ value: '', show: false })
  const [health,       setHealth]       = useState<'idle' | 'checking' | 'ok' | 'error'>('idle')
  const [saved,        setSaved]        = useState(false)

  useEffect(() => {
    setApiUrl({ value: getLocalApiUrl() })
    // A value saved here previously (encrypted cookie) takes precedence over
    // the build-time env var placeholder.
    initCredentialsFromCookies().then(() => {
      setAdminSecret({ value: getCachedAdminSecret() ?? process.env.NEXT_PUBLIC_ADMIN_SECRET ?? '', show: false })
      setManagerKey({ value: getCachedManagerKey() ?? process.env.NEXT_PUBLIC_MANAGER_API_KEY ?? '', show: false })
    })
  }, [])

  function getLocalApiUrl(): string {
    return process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  }

  async function checkHealth() {
    setHealth('checking')
    try {
      await api.health()
      setHealth('ok')
    } catch {
      setHealth('error')
    }
  }

  async function handleSave() {
    await Promise.all([
      saveAdminSecret(adminSecret.value),
      saveManagerKey(managerKey.value),
    ])
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
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

  const Field = ({
    label, desc, value, type = 'text', show, onToggleShow, onChange, mono = false,
    status,
  }: {
    label: string; desc?: string; value: string; type?: string; show?: boolean
    onToggleShow?: () => void; onChange: (v: string) => void; mono?: boolean
    status?: React.ReactNode
  }) => (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)' }}>{label}</label>
        {status}
      </div>
      {desc && <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6, lineHeight: 1.4 }}>{desc}</div>}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          type={show === false ? 'password' : 'text'}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="input"
          style={{
            fontFamily: mono ? 'var(--font-mono)' : undefined,
            fontSize: mono ? 12 : 13,
            paddingRight: onToggleShow ? 40 : undefined,
          }}
        />
        {onToggleShow && (
          <button
            onClick={onToggleShow}
            style={{ position: 'absolute', right: 10, color: 'var(--text-3)', cursor: 'pointer' }}
          >
            {show === false ? <Eye size={13} /> : <EyeOff size={13} />}
          </button>
        )}
      </div>
    </div>
  )

  return (
    <div className="p-6 space-y-5 max-w-2xl mx-auto">
      <div style={{ marginBottom: 4 }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Configuration</div>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>Settings</h1>
        <p style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 4 }}>
          Manage your Kanosei backend connection and API credentials.
          Saved credentials persist in this browser (encrypted at rest) across reloads until cleared.
          Configure your runtime environment using{' '}
          <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--card)', padding: '1px 5px', borderRadius: 4 }}>
            .env.local.example
          </code>{' '}
          as the template.
        </p>
      </div>

      {/* Backend */}
      <Section icon={<Database size={14} />} title="Backend Connection">
        <Field
          label="API URL"
          desc="Base URL of the enterprise_router FastAPI server."
          value={apiUrl.value}
          onChange={v => setApiUrl({ value: v })}
          mono
        />
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

      {/* Auth */}
      <Section icon={<Key size={14} />} title="Authentication">
        <Field
          label="Admin Secret"
          desc="Matches ENTERPRISE_ROUTER_ADMIN_SECRET on the backend. Required for agent registration."
          value={adminSecret.value}
          show={adminSecret.show}
          onToggleShow={() => setAdminSecret(s => ({ ...s, show: !s.show }))}
          onChange={v => setAdminSecret(s => ({ ...s, value: v }))}
          mono
        />
        <Field
          label="Manager API Key"
          desc="API key for the MANAGER agent. Issued via POST /agents/MANAGER/issue-api-key."
          value={managerKey.value}
          show={managerKey.show}
          onToggleShow={() => setManagerKey(s => ({ ...s, show: !s.show }))}
          onChange={v => setManagerKey(s => ({ ...s, value: v }))}
          mono
        />
      </Section>

      {/* environment instructions */}
      <Section icon={<Settings size={14} />} title="Permanent Configuration">
        <p style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 14, lineHeight: 1.6 }}>
          Set these in the website runtime environment. Use <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--card)', padding: '1px 5px', borderRadius: 4 }}>website/.env.local.example</code> as the non-secret template:
        </p>
        <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.8, color: 'var(--text-2)' }}>
          <div><span style={{ color: 'var(--text-4)' }}># Backend URL</span></div>
          <div><span style={{ color: 'var(--green)' }}>NEXT_PUBLIC_API_URL</span>=<span style={{ color: 'var(--primary-2)' }}>{apiUrl.value || 'http://localhost:8000'}</span></div>
          <div style={{ marginTop: 4 }}><span style={{ color: 'var(--text-4)' }}># Admin secret (matches ENTERPRISE_ROUTER_ADMIN_SECRET)</span></div>
          <div><span style={{ color: 'var(--green)' }}>NEXT_PUBLIC_ADMIN_SECRET</span>=<span style={{ color: 'var(--primary-2)' }}>{adminSecret.value || 'changeme'}</span></div>
          <div style={{ marginTop: 4 }}><span style={{ color: 'var(--text-4)' }}># MANAGER agent API key</span></div>
          <div><span style={{ color: 'var(--green)' }}>NEXT_PUBLIC_MANAGER_API_KEY</span>=<span style={{ color: 'var(--primary-2)' }}>{managerKey.value || '<paste key here>'}</span></div>
        </div>
      </Section>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
        {saved && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
            <Check size={11} /> Changes noted
          </span>
        )}
        <button className="btn btn-primary" onClick={handleSave} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Save size={12} /> Save
        </button>
      </div>
    </div>
  )
}
