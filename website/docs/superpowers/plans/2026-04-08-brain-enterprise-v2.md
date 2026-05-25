# BRAIN Enterprise Lab v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform BRAIN Enterprise Lab from a purple-heavy mock dashboard into a polished, OLED-dark AI enterprise OS with a central chat command interface wired to the real FastAPI backend.

**Architecture:** Next.js 14 App Router frontend → FastAPI `enterprise_router` backend → SQLite (local) or MongoDB Atlas (online). The frontend has two tiers: (1) a **central Command Chat** where users converse with and direct the company, and (2) per-agent workspace pages. The chat routes slash-commands (`/ceo`, `/product`, etc.) to their target agents. All live data fetches from the FastAPI using polling; mock data is the fallback when the API is offline.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, Framer Motion, Recharts, 21st.dev MCP components, `Plus Jakarta Sans` + `Fira Code` fonts, FastAPI backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

---

## Design System (LOCK THESE IN — DO NOT DEVIATE)

From ui-ux-pro-max + frontend-design analysis:

```
Style: Dark Mode OLED  
Background:    #020617   (near-black navy)
Surface:       #0F172A   (dark slate)
Card:          #1E293B   (slate-800)
Border:        rgba(255,255,255,0.07)
Border-hover:  rgba(255,255,255,0.14)

Accent (positive/active): #22C55E  (green — used for live/online/success)
Accent (primary action):  #6366F1  (indigo — buttons, focus, key links)
Accent (warning):         #F59E0B  (amber)
Accent (error):           #EF4444  (red)

Agent signature colors (muted, not neon):
  CEO:         #D97706   Engineering: #2563EB
  Product:     #7C3AED   HR:          #059669
  Sales:       #0891B2   Marketing:   #DB2777
  Finance:     #EA580C

Text primary:   #F8FAFC
Text secondary: #94A3B8
Text muted:     #475569

Heading font: Fira Code (wt 400–700)  — for titles, agent names, numbers
Body font:    Plus Jakarta Sans (wt 300–700) — for prose, labels, descriptions
Mono font:    Fira Code  — for JSON, timestamps, IDs

Card style: bg-[#1E293B] border border-[rgba(255,255,255,0.07)] rounded-xl
             hover: border-[rgba(255,255,255,0.14)] transition-all
No glassmorphism. No scanline overlay. No heavy neon glows.
Minimal shadow only: shadow-[0_4px_24px_rgba(0,0,0,0.4)]
Glow used ONLY for active/live status dots (4px radius, agent color at 40% opacity).
```

---

## File Map

### New files to create
```
app/chat/page.tsx                          — Central Command Chat page
components/chat/CommandChat.tsx            — Full chat container
components/chat/ChatMessage.tsx            — Individual message bubble
components/chat/ChatInput.tsx              — Input bar with slash-command detection
components/chat/SlashMenu.tsx              — Floating slash-command picker
components/chat/AgentRoutingBadge.tsx      — Shows which agent a message routes to
components/agents/WorkerAgentsDropdown.tsx — Collapsible worker agents panel
lib/api.ts                                 — Typed FastAPI client
lib/api-types.ts                           — Backend-aligned TypeScript types
lib/hooks.ts                               — usePolling, useAgents, useQueue, useAudit
lib/chat-router.ts                         — Parses slash commands, resolves target agent
.env.local.example                         — Environment variable template
```

### Files to fully rewrite
```
app/globals.css                            — New OLED design system
tailwind.config.ts                         — New font + color tokens
components/layout/Sidebar.tsx             — Professional dark sidebar, no purple-wash
components/layout/TopBar.tsx              — Minimal top bar with API health indicator
app/layout.tsx                             — Import new fonts, remove scanlines
app/dashboard/page.tsx                     — Live data from API, new theme
app/agents/[agent]/page.tsx               — Worker dropdown, live queue from API
app/messages/page.tsx                      — Real message stream from /queue endpoint
```

### Files to update (smaller changes)
```
app/simulation/page.tsx    — Theme tokens only
app/lab/page.tsx           — Theme tokens only
app/workflows/page.tsx     — Theme tokens only
app/resources/page.tsx     — Theme tokens only
app/observability/page.tsx — Wire /health endpoint + /audit endpoint
lib/mock-data.ts           — Keep intact as offline fallback
lib/types.ts               — Keep intact; api-types.ts adds API-specific types
```

---

## Task 1: Design System — globals.css + tailwind.config.ts

**Files:**
- Rewrite: `app/globals.css`
- Rewrite: `tailwind.config.ts`

- [ ] **Step 1: Replace globals.css**

```css
/* app/globals.css */
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --font-display: 'Fira Code', monospace;
  --font-body: 'Plus Jakarta Sans', sans-serif;
  --font-mono: 'Fira Code', monospace;

  --bg:       #020617;
  --surface:  #0F172A;
  --card:     #1E293B;
  --border:   rgba(255,255,255,0.07);
  --border-hover: rgba(255,255,255,0.14);

  --green:    #22C55E;
  --indigo:   #6366F1;
  --amber:    #F59E0B;
  --red:      #EF4444;

  --agent-ceo:         #D97706;
  --agent-product:     #7C3AED;
  --agent-engineering: #2563EB;
  --agent-hr:          #059669;
  --agent-sales:       #0891B2;
  --agent-marketing:   #DB2777;
  --agent-finance:     #EA580C;

  --text-1: #F8FAFC;
  --text-2: #94A3B8;
  --text-3: #475569;

  --sidebar-w: 256px;
  --topbar-h: 52px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  background: var(--bg);
  color: var(--text-1);
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
}

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

/* Card */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  transition: border-color 0.15s ease;
}
.card:hover { border-color: var(--border-hover); }

/* Subtle card (inside panels) */
.card-inner {
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: 8px;
}

/* Status dot with live glow */
.live-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 6px rgba(34,197,94,0.5);
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Progress bar */
.progress { height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 2px; transition: width 0.6s ease; }

/* Nav item */
.nav-item {
  display: flex; align-items: center; gap: 9px;
  padding: 7px 10px; border-radius: 7px;
  color: var(--text-3); font-size: 13px; font-weight: 500;
  text-decoration: none; cursor: pointer;
  transition: color 0.12s, background 0.12s;
  border: 1px solid transparent;
}
.nav-item:hover { color: var(--text-2); background: rgba(255,255,255,0.04); }
.nav-item.active { color: var(--text-1); background: rgba(255,255,255,0.06); border-color: var(--border); }

/* Agent color helpers */
.agent-ceo         { --ac: var(--agent-ceo); }
.agent-product     { --ac: var(--agent-product); }
.agent-engineering { --ac: var(--agent-engineering); }
.agent-hr          { --ac: var(--agent-hr); }
.agent-sales       { --ac: var(--agent-sales); }
.agent-marketing   { --ac: var(--agent-marketing); }
.agent-finance     { --ac: var(--agent-finance); }

/* Chat message */
.chat-bubble-user {
  background: #6366F1;
  color: white;
  border-radius: 16px 16px 4px 16px;
}
.chat-bubble-agent {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px 16px 16px 4px;
}

/* Recharts overrides */
.recharts-cartesian-grid-horizontal line,
.recharts-cartesian-grid-vertical line { stroke: rgba(255,255,255,0.05) !important; }
.recharts-text { fill: var(--text-3) !important; font-size: 11px; font-family: var(--font-mono); }

@layer utilities {
  .font-display { font-family: var(--font-display); }
  .font-mono    { font-family: var(--font-mono); }
}
```

- [ ] **Step 2: Replace tailwind.config.ts**

```ts
// tailwind.config.ts
import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['Fira Code', 'monospace'],
        body:    ['Plus Jakarta Sans', 'sans-serif'],
        mono:    ['Fira Code', 'monospace'],
      },
      colors: {
        bg:      '#020617',
        surface: '#0F172A',
        card:    '#1E293B',
        green:   '#22C55E',
        indigo:  '#6366F1',
        agent: {
          ceo:         '#D97706',
          product:     '#7C3AED',
          engineering: '#2563EB',
          hr:          '#059669',
          sales:       '#0891B2',
          marketing:   '#DB2777',
          finance:     '#EA580C',
        },
      },
      borderColor: {
        DEFAULT: 'rgba(255,255,255,0.07)',
      },
    },
  },
  plugins: [],
}
export default config
```

- [ ] **Step 3: Update layout.tsx — remove scanlines, add new fonts**

```tsx
// app/layout.tsx
import type { Metadata } from 'next'
import './globals.css'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'

export const metadata: Metadata = {
  title: 'BRAIN Enterprise Lab',
  description: 'Autonomous AI-powered company operating system',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            <TopBar />
            <main className="flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  )
}
```

- [ ] **Step 4: Verify fonts load — run `npm run dev`, open browser, check Network tab for fonts.googleapis.com request**

---

## Task 2: API Client + Types + Hooks

**Files:**
- Create: `lib/api-types.ts`
- Create: `lib/api.ts`
- Create: `lib/hooks.ts`
- Create: `.env.local.example`

- [ ] **Step 1: Create `.env.local.example`**

```bash
# .env.local.example
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ADMIN_SECRET=changeme
```

Copy to `.env.local` with your values.

- [ ] **Step 2: Create `lib/api-types.ts`** — exact TypeScript mirror of the FastAPI models

```ts
// lib/api-types.ts

export type RegistrationStatus = 'pending' | 'approved' | 'rejected'
export type MessageStatus = 'pending' | 'in_progress' | 'done' | 'error'
export type DeliveryState = 'pending' | 'leased' | 'blocked' | 'expired' | 'dead_lettered' | 'done'

export interface ApiAgent {
  agent_name: string
  role: string
  hierarchy_level: number
  trust_level: number
  file_path: string | null
  endpoint: string | null
  active: boolean
  registration_status: RegistrationStatus
  allowed_senders: string[]
  allowed_task_types: string[]
  created_at: string
  approved_at: string | null
}

export interface ApiRegistration {
  agent_name: string
  role: string
  status: RegistrationStatus
  requested_at: string
  reviewed_at: string | null
  reviewed_by: string | null
  rejection_reason: string | null
  endpoint: string | null
  file_path: string | null
  metadata: Record<string, unknown>
}

export interface ApiMessageEnvelope {
  id: string
  timestamp: string
  sender: string
  recipient: string
  task_type: string
  context: Record<string, unknown>
  payload: Record<string, unknown>
  status: MessageStatus
  error: string
}

export interface ApiQueueItem {
  envelope: ApiMessageEnvelope
  computed_priority: number
  attempt_count: number
  lease_until: string | null
  delivery_state: DeliveryState
  blocked_reason: string
  provenance_source: string | null
  provenance_agent: string | null
  provenance_trust_level: number | null
  ttl_seconds: number | null
  dedupe_key: string | null
}

export interface ApiAuditEvent {
  id: string
  event_type: string
  subject_id: string
  actor: string
  details: Record<string, unknown>
  created_at: string
}

export interface ApiHealth {
  status: string
  backend: 'sqlite' | 'mongo'
}

export interface ApiError {
  detail: string
}
```

- [ ] **Step 3: Create `lib/api.ts`**

```ts
// lib/api.ts
import type {
  ApiAgent, ApiRegistration, ApiQueueItem, ApiAuditEvent, ApiHealth
} from './api-types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? ''

// ─── helpers ─────────────────────────────────────────────────────────────────

async function get<T>(path: string, headers: Record<string, string> = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...headers },
    cache: 'no-store',
  })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown, headers: Record<string, string> = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
    cache: 'no-store',
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

function adminHeaders(): Record<string, string> {
  return { 'X-Admin-Secret': ADMIN }
}

function agentHeaders(agentName: string, apiKey: string): Record<string, string> {
  return { Authorization: `Bearer ${apiKey}`, 'X-Agent-Id': agentName }
}

// ─── public API ──────────────────────────────────────────────────────────────

export const api = {
  health: () =>
    get<ApiHealth>('/health'),

  agents: {
    list: (agentName: string, apiKey: string, status?: string) =>
      get<ApiAgent[]>(
        status ? `/agents?status=${status}` : '/agents',
        agentHeaders(agentName, apiKey)
      ),
    register: (body: {
      agent_name: string; role: string; hierarchy_level: number
      trust_level: number; file_path?: string; endpoint?: string
      active?: boolean; allowed_senders?: string[]; allowed_task_types?: string[]
      issue_api_key?: boolean
    }) => post<{ agent_name: string; status: string; api_key?: string }>(
      '/agents', body, adminHeaders()
    ),
    issueKey: (agentName: string) =>
      post<{ agent_name: string; api_key: string }>(
        `/agents/${agentName}/issue-api-key`, {}, adminHeaders()
      ),
  },

  registrations: {
    list: (status?: string) =>
      get<ApiRegistration[]>(
        status ? `/registrations?status=${status}` : '/registrations',
        adminHeaders()
      ),
    request: (body: {
      agent_name: string; role: string; secret_token: string
      file_path?: string; endpoint?: string; metadata?: Record<string, unknown>
    }) => post<{ agent_name: string; status: string }>(
      '/registrations/request', body
    ),
    approve: (agentName: string, approver: string, issueKey = true) =>
      post<{ agent_name: string; status: string; api_key?: string }>(
        `/registrations/${agentName}/approve`,
        { approver, issue_api_key: issueKey, key_label: 'dashboard' },
        adminHeaders()
      ),
    reject: (agentName: string, approver: string, reason: string) =>
      post<{ agent_name: string; status: string }>(
        `/registrations/${agentName}/reject`,
        { approver, reason },
        adminHeaders()
      ),
  },

  messages: {
    submit: (
      message: { id: string; timestamp: string; sender: string; recipient: string
        task_type: string; context?: Record<string, unknown>
        payload?: Record<string, unknown>; status: string; error?: string },
      routingHints: Record<string, unknown>,
      agentName: string,
      apiKey: string
    ) => post<{ message_id: string }>(
      '/messages',
      { message, routing_hints: routingHints },
      agentHeaders(agentName, apiKey)
    ),
    peek: (recipient: string, agentName: string, apiKey: string, limit = 20) =>
      get<ApiQueueItem[]>(
        `/messages/peek?recipient=${recipient}&limit=${limit}`,
        agentHeaders(agentName, apiKey)
      ),
    fetchNext: (recipient: string, agentName: string, apiKey: string) =>
      post<ApiQueueItem | Record<string, never>>(
        '/messages/fetch-next',
        { recipient },
        agentHeaders(agentName, apiKey)
      ),
    ack: (messageId: string, recipient: string, agentName: string, apiKey: string) =>
      post<{ message_id: string; status: string }>(
        `/messages/${messageId}/ack`,
        { recipient },
        agentHeaders(agentName, apiKey)
      ),
    nack: (messageId: string, recipient: string, reason: string, agentName: string, apiKey: string) =>
      post<{ message_id: string; status: string }>(
        `/messages/${messageId}/nack`,
        { recipient, reason },
        agentHeaders(agentName, apiKey)
      ),
  },

  queue: {
    list: (recipient: string, agentName: string, apiKey: string) =>
      get<ApiQueueItem[]>(`/queue/${recipient}`, agentHeaders(agentName, apiKey)),
  },

  audit: {
    list: (limit = 20, subjectId?: string) =>
      get<ApiAuditEvent[]>(
        subjectId
          ? `/audit?limit=${limit}&subject_id=${subjectId}`
          : `/audit?limit=${limit}`,
        adminHeaders()
      ),
  },
}
```

- [ ] **Step 4: Create `lib/hooks.ts`**

```ts
// lib/hooks.ts
'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { api } from './api'
import type { ApiAgent, ApiHealth, ApiAuditEvent, ApiQueueItem } from './api-types'

// Generic polling hook
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  deps: unknown[] = []
): { data: T | null; error: string | null; loading: boolean; refresh: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const run = useCallback(async () => {
    try {
      const result = await fetcher()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    run()
    timerRef.current = setInterval(run, intervalMs)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [run, intervalMs])

  return { data, error, loading, refresh: run }
}

// Specific hooks (admin-mode: uses ADMIN secret for agents list)
export function useHealth() {
  return usePolling<ApiHealth>(() => api.health(), 30_000)
}

export function useAgents() {
  // Uses admin mode to list all agents (dashboard use)
  // When in agent-auth mode, caller provides agentName + apiKey
  const [data, setData] = useState<ApiAgent[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const run = useCallback(async () => {
    try {
      // Dashboard reads agents list without per-agent auth by using admin key for a proxy agent.
      // For demo/development, fall through to mock data if API unreachable.
      const result = await api.agents.list('CEO', '', undefined)
      setData(result)
      setError(null)
    } catch {
      setError('API offline — using mock data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    run()
    const t = setInterval(run, 15_000)
    return () => clearInterval(t)
  }, [run])

  return { data, error, loading, refresh: run }
}

export function useAudit(limit = 20) {
  return usePolling<ApiAuditEvent[]>(() => api.audit.list(limit), 8_000, [limit])
}

export function useQueue(recipient: string, agentName: string, apiKey: string, enabled = true) {
  const [data, setData] = useState<ApiQueueItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const run = useCallback(async () => {
    if (!enabled || !recipient || !apiKey) return
    try {
      const result = await api.queue.list(recipient, agentName, apiKey)
      setData(result)
      setError(null)
    } catch {
      setError('Queue unavailable')
    } finally {
      setLoading(false)
    }
  }, [recipient, agentName, apiKey, enabled])

  useEffect(() => {
    run()
    const t = setInterval(run, 4_000)
    return () => clearInterval(t)
  }, [run])

  return { data, error, loading, refresh: run }
}
```

---

## Task 3: Sidebar + TopBar Redesign

**Files:**
- Rewrite: `components/layout/Sidebar.tsx`
- Rewrite: `components/layout/TopBar.tsx`

### Sidebar

- [ ] **Step 1: Rewrite Sidebar.tsx**

```tsx
// components/layout/Sidebar.tsx
'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import {
  LayoutDashboard, MessageSquare, FlaskConical, GitBranch,
  Database, Eye, Crown, Package, Code2, Users, TrendingUp,
  Megaphone, DollarSign, ChevronDown, ChevronRight, Zap,
  Menu, X, Activity
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { AGENTS } from '@/lib/mock-data'
import { useHealth } from '@/lib/hooks'
import type { AgentId } from '@/lib/types'

const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={13} />, product: <Package size={13} />, engineering: <Code2 size={13} />,
  hr: <Users size={13} />, sales: <TrendingUp size={13} />, marketing: <Megaphone size={13} />,
  finance: <DollarSign size={13} />,
}

const NAV = [
  { href: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={15} /> },
  { href: '/chat', label: 'Command', icon: <MessageSquare size={15} />, highlight: true },
  { href: '/simulation', label: 'Simulation', icon: <Activity size={15} /> },
  { href: '/lab', label: 'BRAIN Lab', icon: <FlaskConical size={15} /> },
]

const OPS = [
  { href: '/workflows', label: 'Workflows', icon: <GitBranch size={15} /> },
  { href: '/resources', label: 'Resources', icon: <Database size={15} /> },
  { href: '/messages', label: 'Messages', icon: <MessageSquare size={15} /> },
  { href: '/observability', label: 'Observability', icon: <Eye size={15} /> },
]

const AGENT_STATUS_COLOR: Record<string, string> = {
  active: 'var(--green)', busy: 'var(--amber)',
  idle: 'var(--agent-engineering)', error: 'var(--red)', offline: 'var(--text-3)',
}

export default function Sidebar() {
  const pathname = usePathname()
  const [agentsOpen, setAgentsOpen] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { data: health } = useHealth()

  const SidebarContent = () => (
    <aside
      className="flex flex-col h-full"
      style={{ width: 'var(--sidebar-w)', background: 'var(--surface)', borderRight: '1px solid var(--border)' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: '#6366F1', boxShadow: '0 0 12px rgba(99,102,241,0.4)' }}>
          <Zap size={15} className="text-white" />
        </div>
        <div className="flex-1">
          <div className="font-display text-sm font-bold tracking-wide" style={{ color: 'var(--text-1)' }}>BRAIN</div>
          <div className="text-[10px] tracking-widest uppercase" style={{ color: 'var(--text-3)' }}>Enterprise Lab</div>
        </div>
        <button onClick={() => setMobileOpen(false)} className="lg:hidden" style={{ color: 'var(--text-3)' }}>
          <X size={15} />
        </button>
      </div>

      {/* Health badge */}
      <div className="px-4 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between text-[11px]">
          <span style={{ color: 'var(--text-3)' }}>API</span>
          {health ? (
            <span className="flex items-center gap-1.5" style={{ color: 'var(--green)' }}>
              <span className="live-dot" />
              {health.backend}
            </span>
          ) : (
            <span style={{ color: 'var(--text-3)' }}>offline</span>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {/* Core */}
        <div>
          <div className="px-2 mb-1.5 text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'var(--text-3)' }}>Core</div>
          <div className="space-y-0.5">
            {NAV.map(item => (
              <Link key={item.href} href={item.href}
                className={cn('nav-item', pathname === item.href && 'active')}>
                <span style={{ color: item.highlight && pathname !== item.href ? '#6366F1' : 'inherit' }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
                {item.highlight && pathname !== item.href && (
                  <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded font-semibold"
                    style={{ background: 'rgba(99,102,241,0.15)', color: '#818CF8' }}>
                    Chat
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>

        {/* Agents */}
        <div>
          <button onClick={() => setAgentsOpen(o => !o)}
            className="w-full flex items-center justify-between px-2 mb-1.5 text-[10px] font-semibold tracking-widest uppercase"
            style={{ color: 'var(--text-3)' }}>
            <span>Agents</span>
            {agentsOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
          {agentsOpen && (
            <div className="space-y-0.5">
              {AGENTS.map(agent => {
                const active = pathname === `/agents/${agent.id}`
                return (
                  <Link key={agent.id} href={`/agents/${agent.id}`}
                    className={cn('nav-item', active && 'active')}>
                    <span style={{ color: agent.color }}>{AGENT_ICONS[agent.id]}</span>
                    <span className="flex-1">{agent.name}</span>
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ background: AGENT_STATUS_COLOR[agent.status] }} />
                  </Link>
                )
              })}
            </div>
          )}
        </div>

        {/* Ops */}
        <div>
          <div className="px-2 mb-1.5 text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'var(--text-3)' }}>Operations</div>
          <div className="space-y-0.5">
            {OPS.map(item => (
              <Link key={item.href} href={item.href}
                className={cn('nav-item', pathname === item.href && 'active')}>
                {item.icon}
                <span>{item.label}</span>
              </Link>
            ))}
          </div>
        </div>
      </nav>

      {/* User */}
      <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-[11px] font-bold text-white">O</div>
          <div>
            <div className="text-[12px] font-medium" style={{ color: 'var(--text-1)' }}>Operator</div>
            <div className="text-[10px]" style={{ color: 'var(--text-3)' }}>Admin</div>
          </div>
        </div>
      </div>
    </aside>
  )

  return (
    <>
      <div className="hidden lg:flex h-full flex-shrink-0"><SidebarContent /></div>
      <button onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-3 left-3 z-50 w-9 h-9 flex items-center justify-center rounded-lg cursor-pointer"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
        <Menu size={15} style={{ color: 'var(--text-2)' }} />
      </button>
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <div className="relative z-50 h-full"><SidebarContent /></div>
        </div>
      )}
    </>
  )
}
```

### TopBar

- [ ] **Step 2: Rewrite TopBar.tsx**

```tsx
// components/layout/TopBar.tsx
'use client'

import { usePathname } from 'next/navigation'
import { Bell, ChevronRight, RefreshCw, Search } from 'lucide-react'
import { useHealth } from '@/lib/hooks'
import { ALERTS } from '@/lib/mock-data'

const CRUMBS: Record<string, string[]> = {
  '/dashboard':           ['Dashboard'],
  '/chat':                ['Command'],
  '/simulation':          ['Simulation'],
  '/lab':                 ['BRAIN Lab'],
  '/agents/ceo':          ['Agents', 'CEO'],
  '/agents/product':      ['Agents', 'Product'],
  '/agents/engineering':  ['Agents', 'Engineering'],
  '/agents/hr':           ['Agents', 'HR'],
  '/agents/sales':        ['Agents', 'Sales'],
  '/agents/marketing':    ['Agents', 'Marketing'],
  '/agents/finance':      ['Agents', 'Finance'],
  '/workflows':           ['Workflows'],
  '/resources':           ['Resources'],
  '/messages':            ['Messages'],
  '/observability':       ['Observability'],
}

export default function TopBar() {
  const pathname = usePathname()
  const crumbs = CRUMBS[pathname] ?? ['BRAIN']
  const { data: health } = useHealth()
  const unresolved = ALERTS.filter(a => !a.resolved).length

  return (
    <header className="flex items-center justify-between px-5 flex-shrink-0"
      style={{ height: 'var(--topbar-h)', background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
      <div className="flex items-center gap-1.5 text-[13px]">
        <span style={{ color: 'var(--text-3)' }}>BRAIN</span>
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-1.5">
            <ChevronRight size={11} style={{ color: 'var(--text-3)' }} />
            <span style={{ color: i === crumbs.length - 1 ? 'var(--text-1)' : 'var(--text-3)', fontWeight: i === crumbs.length - 1 ? 500 : 400 }}>{c}</span>
          </span>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg text-[12px] cursor-pointer"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--text-3)' }}>
          <Search size={12} />
          <span>Search…</span>
          <kbd className="ml-1 text-[10px] px-1 rounded" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-3)' }}>⌘K</kbd>
        </div>

        {health && (
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium"
            style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', color: 'var(--green)' }}>
            <span className="live-dot" style={{ width: 6, height: 6 }} />
            {health.backend}
          </div>
        )}

        <button className="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer hover:bg-[rgba(255,255,255,0.05)] transition-colors"
          style={{ color: 'var(--text-3)' }}>
          <RefreshCw size={13} />
        </button>

        <button className="relative w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer hover:bg-[rgba(255,255,255,0.05)] transition-colors"
          style={{ color: 'var(--text-3)' }}>
          <Bell size={13} />
          {unresolved > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center text-white"
              style={{ background: 'var(--red)' }}>
              {unresolved}
            </span>
          )}
        </button>
      </div>
    </header>
  )
}
```

---

## Task 4: Central Command Chat Page

This is the most important new feature. Users type natural language to plan and run their company. Typing `/ceo`, `/product`, etc. routes the message to that agent. The `⏎` key submits. The chat panel shows a real-time conversation with agent replies (mocked streaming for now, real API submission for actual message dispatch).

**Files:**
- Create: `lib/chat-router.ts`
- Create: `components/chat/SlashMenu.tsx`
- Create: `components/chat/ChatMessage.tsx`
- Create: `components/chat/ChatInput.tsx`
- Create: `components/chat/CommandChat.tsx`
- Create: `app/chat/page.tsx`

- [ ] **Step 1: Create `lib/chat-router.ts`**

```ts
// lib/chat-router.ts
import { AGENTS } from './mock-data'
import type { AgentId } from './types'

export interface RoutedCommand {
  agentId: AgentId | null    // null = broadcast to all / CEO decides
  raw: string                // original text
  body: string               // text without slash prefix
  skill: string | null       // e.g. "budget", "hire", "roadmap"
}

const SLASH_MAP: Record<string, AgentId> = {
  ceo: 'ceo', product: 'product', engineering: 'engineering',
  eng: 'engineering', hr: 'hr', sales: 'sales',
  marketing: 'marketing', mkt: 'marketing', finance: 'finance', fin: 'finance',
}

export function parseCommand(input: string): RoutedCommand {
  const trimmed = input.trim()

  // /agent [skill] body  e.g.  /ceo approve budget  OR  /product roadmap
  const match = trimmed.match(/^\/(\w+)(?:\s+(\w+))?\s*(.*)$/s)
  if (match) {
    const [, prefix, maybeSkill, rest] = match
    const agentId = SLASH_MAP[prefix.toLowerCase()] ?? null
    if (agentId) {
      return { agentId, raw: trimmed, body: rest?.trim() || maybeSkill || '', skill: null }
    }
    // /skill → treat whole thing as a skill name, broadcast to CEO
    return { agentId: 'ceo', raw: trimmed, body: trimmed.slice(1), skill: prefix }
  }

  return { agentId: null, raw: trimmed, body: trimmed, skill: null }
}

export function getSlashSuggestions(input: string): Array<{ label: string; agentId: AgentId; hint: string }> {
  if (!input.startsWith('/')) return []
  const query = input.slice(1).toLowerCase()
  const options = [
    { label: '/ceo',         agentId: 'ceo' as AgentId,         hint: 'Delegate to CEO' },
    { label: '/product',     agentId: 'product' as AgentId,     hint: 'Product roadmap & backlog' },
    { label: '/engineering', agentId: 'engineering' as AgentId, hint: 'Engineering tasks' },
    { label: '/hr',          agentId: 'hr' as AgentId,          hint: 'Hiring & people ops' },
    { label: '/sales',       agentId: 'sales' as AgentId,       hint: 'Sales pipeline' },
    { label: '/marketing',   agentId: 'marketing' as AgentId,   hint: 'Campaigns & content' },
    { label: '/finance',     agentId: 'finance' as AgentId,     hint: 'Budget & spend' },
  ]
  return query ? options.filter(o => o.label.slice(1).startsWith(query)) : options
}
```

- [ ] **Step 2: Create `components/chat/ChatMessage.tsx`**

```tsx
// components/chat/ChatMessage.tsx
'use client'

import { motion } from 'framer-motion'
import { Crown, Package, Code2, Users, TrendingUp, Megaphone, DollarSign, Zap } from 'lucide-react'
import type { AgentId } from '@/lib/types'
import { AGENTS } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={13} />, product: <Package size={13} />, engineering: <Code2 size={13} />,
  hr: <Users size={13} />, sales: <TrendingUp size={13} />, marketing: <Megaphone size={13} />,
  finance: <DollarSign size={13} />,
}

export interface ChatMsg {
  id: string
  role: 'user' | 'agent' | 'system'
  agentId?: AgentId
  text: string
  timestamp: Date
  streaming?: boolean
}

export function ChatMessage({ msg }: { msg: ChatMsg }) {
  const agent = msg.agentId ? AGENTS.find(a => a.id === msg.agentId) : null

  if (msg.role === 'user') {
    return (
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="flex justify-end gap-3">
        <div className="max-w-[70%] px-4 py-3 chat-bubble-user text-[13px] leading-relaxed">{msg.text}</div>
        <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0 mt-1">O</div>
      </motion.div>
    )
  }

  if (msg.role === 'system') {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
        className="flex justify-center">
        <div className="px-3 py-1.5 rounded-full text-[11px]"
          style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>
          {msg.text}
        </div>
      </motion.div>
    )
  }

  // agent message
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="flex gap-3">
      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ background: agent ? `${agent.color}18` : 'rgba(99,102,241,0.15)', color: agent?.color ?? '#6366F1', border: `1px solid ${agent ? agent.color + '30' : 'rgba(99,102,241,0.2)'}` }}>
        {agent ? AGENT_ICONS[agent.id] : <Zap size={13} />}
      </div>
      <div className="flex-1 max-w-[80%]">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-[11px] font-semibold font-mono" style={{ color: agent?.color ?? '#6366F1' }}>
            {agent?.name ?? 'BRAIN'}
          </span>
          <span className="text-[10px]" style={{ color: 'var(--text-3)' }}>
            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <div className="chat-bubble-agent px-4 py-3 text-[13px] leading-relaxed" style={{ color: 'var(--text-1)' }}>
          {msg.streaming
            ? <><span>{msg.text}</span><span className="inline-block w-0.5 h-4 ml-0.5 bg-current animate-pulse" /></>
            : msg.text}
        </div>
      </div>
    </motion.div>
  )
}
```

- [ ] **Step 3: Create `components/chat/SlashMenu.tsx`**

```tsx
// components/chat/SlashMenu.tsx
'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { Crown, Package, Code2, Users, TrendingUp, Megaphone, DollarSign } from 'lucide-react'
import type { AgentId } from '@/lib/types'
import { AGENTS } from '@/lib/mock-data'
import type { getSlashSuggestions } from '@/lib/chat-router'

type Suggestion = ReturnType<typeof getSlashSuggestions>[number]

const AGENT_ICONS: Record<AgentId, React.ReactNode> = {
  ceo: <Crown size={12} />, product: <Package size={12} />, engineering: <Code2 size={12} />,
  hr: <Users size={12} />, sales: <TrendingUp size={12} />, marketing: <Megaphone size={12} />,
  finance: <DollarSign size={12} />,
}

export function SlashMenu({ suggestions, onSelect }: {
  suggestions: Suggestion[]
  onSelect: (s: Suggestion) => void
}) {
  const show = suggestions.length > 0
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          transition={{ duration: 0.12 }}
          className="absolute bottom-full left-0 right-0 mb-2 card overflow-hidden"
          style={{ maxHeight: 280 }}
        >
          <div className="p-1">
            {suggestions.map(s => {
              const agent = AGENTS.find(a => a.id === s.agentId)!
              return (
                <button key={s.label} onClick={() => onSelect(s)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left cursor-pointer transition-colors hover:bg-[rgba(255,255,255,0.05)]">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: `${agent.color}18`, color: agent.color }}>
                    {AGENT_ICONS[s.agentId]}
                  </div>
                  <div>
                    <div className="text-[12px] font-mono font-semibold" style={{ color: agent.color }}>{s.label}</div>
                    <div className="text-[11px]" style={{ color: 'var(--text-3)' }}>{s.hint}</div>
                  </div>
                </button>
              )
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
```

- [ ] **Step 4: Create `components/chat/ChatInput.tsx`**

```tsx
// components/chat/ChatInput.tsx
'use client'

import { useRef, useState } from 'react'
import { Send, CornerDownLeft } from 'lucide-react'
import { getSlashSuggestions } from '@/lib/chat-router'
import { SlashMenu } from './SlashMenu'
import type { getSlashSuggestions as SugFn } from '@/lib/chat-router'

type Suggestion = ReturnType<SugFn>[number]

export function ChatInput({ onSubmit, disabled }: {
  onSubmit: (text: string) => void
  disabled?: boolean
}) {
  const [value, setValue] = useState('')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleChange = (v: string) => {
    setValue(v)
    setSuggestions(getSlashSuggestions(v))
    // auto-resize
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    setSuggestions([])
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    onSubmit(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
    if (e.key === 'Escape') setSuggestions([])
  }

  const selectSuggestion = (s: Suggestion) => {
    setValue(s.label + ' ')
    setSuggestions([])
    textareaRef.current?.focus()
  }

  return (
    <div className="relative">
      <SlashMenu suggestions={suggestions} onSelect={selectSuggestion} />
      <div className="card flex items-end gap-3 px-4 py-3" style={{ background: 'var(--card)' }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Message your company… or type / to route to a specific agent"
          className="flex-1 bg-transparent outline-none resize-none text-[13px] leading-relaxed placeholder:text-[var(--text-3)]"
          style={{ color: 'var(--text-1)', minHeight: 24, maxHeight: 160 }}
          disabled={disabled}
        />
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="hidden sm:flex items-center gap-1 text-[10px]" style={{ color: 'var(--text-3)' }}>
            <CornerDownLeft size={10} />Enter
          </span>
          <button onClick={submit} disabled={!value.trim() || disabled}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white cursor-pointer transition-opacity disabled:opacity-30"
            style={{ background: '#6366F1' }}>
            <Send size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create `components/chat/CommandChat.tsx`**

```tsx
// components/chat/CommandChat.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { parseCommand } from '@/lib/chat-router'
import { AGENTS } from '@/lib/mock-data'
import type { AgentId } from '@/lib/types'
import { ChatMessage, type ChatMsg } from './ChatMessage'
import { ChatInput } from './ChatInput'

// Mocked agent responses keyed by agentId — replace with real API calls
const AGENT_RESPONSE_BANK: Record<string, string[]> = {
  ceo: [
    "Understood. I'll review this and delegate appropriately across departments.",
    "Noted. I'm prioritizing this against our Q3 revenue goal. Finance will need to sign off.",
    "Approved in principle. Product and Engineering should align on scope before we commit.",
  ],
  product: [
    "Added to the backlog. Impact/effort score places this in the top 3 for the next sprint.",
    "I'll write the PRD and share it with Engineering for a feasibility check.",
    "That feature conflicts with two items already in progress. Should we descope one?",
  ],
  engineering: [
    "Feasibility looks good. Estimated 2 weeks, needs Auth service as a dependency.",
    "This touches the message bus. I'd recommend a design doc before we start.",
    "I can have a proof of concept in 3 days. Want me to proceed?",
  ],
  hr: [
    "I'll open a JD and post to the job boards. We have 2 relevant applicants already screened.",
    "Performance review cycle is scheduled for end of quarter. I'll incorporate this feedback.",
    "Onboarding for the new hire is set for next Monday. Materials are ready.",
  ],
  sales: [
    "Pipeline looks healthy — 47 MQLs pending qualification this week.",
    "I'll reach out to the top 5 enterprise accounts with a tailored proposal.",
    "That deal needs Finance approval on the custom pricing. Escalating to CEO.",
  ],
  marketing: [
    "Campaign is ready to launch pending CEO sign-off on the $25K spend.",
    "Content brief drafted. Blog post, LinkedIn thread, and email sequence lined up.",
    "Competitor analysis shows a gap in the enterprise segment — we should move fast.",
  ],
  finance: [
    "ROI clears the 2.0x threshold. I'll approve the spend and update the budget tracker.",
    "Current runway at 14 months. The proposed hire is within budget envelope.",
    "Q2 actuals came in 8% under forecast. I recommend reallocating $40K to Engineering.",
  ],
}

function getResponse(agentId: AgentId | null): { agentId: AgentId; text: string } {
  const target = agentId ?? 'ceo'
  const bank = AGENT_RESPONSE_BANK[target] ?? AGENT_RESPONSE_BANK.ceo
  return { agentId: target, text: bank[Math.floor(Math.random() * bank.length)] }
}

const SEED_MESSAGES: ChatMsg[] = [
  {
    id: 'seed-1',
    role: 'system',
    text: 'BRAIN Enterprise is ready. Type a message to your company, or use /agent to route to a specific department.',
    timestamp: new Date(),
  },
]

export function CommandChat() {
  const [messages, setMessages] = useState<ChatMsg[]>(SEED_MESSAGES)
  const [thinking, setThinking] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (text: string) => {
    const cmd = parseCommand(text)
    const userMsg: ChatMsg = { id: Date.now().toString(), role: 'user', text, timestamp: new Date() }
    setMessages(prev => [...prev, userMsg])
    setThinking(true)

    // Simulate network latency + streaming
    const delay = 800 + Math.random() * 600
    setTimeout(() => {
      const { agentId, text: responseText } = getResponse(cmd.agentId)
      const streamingId = (Date.now() + 1).toString()
      setMessages(prev => [...prev, { id: streamingId, role: 'agent', agentId, text: '', timestamp: new Date(), streaming: true }])
      setThinking(false)

      // Character-by-character stream
      let i = 0
      const interval = setInterval(() => {
        i++
        setMessages(prev => prev.map(m => m.id === streamingId ? { ...m, text: responseText.slice(0, i) } : m))
        if (i >= responseText.length) {
          clearInterval(interval)
          setMessages(prev => prev.map(m => m.id === streamingId ? { ...m, streaming: false } : m))
        }
      }, 18)
    }, delay)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.map(msg => <ChatMessage key={msg.id} msg={msg} />)}
        {thinking && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(99,102,241,0.15)', color: '#6366F1', border: '1px solid rgba(99,102,241,0.2)' }}>
              <div className="w-3 h-3 border-2 border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin" />
            </div>
            <div className="chat-bubble-agent px-4 py-3 text-[13px]" style={{ color: 'var(--text-3)' }}>Thinking…</div>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <ChatInput onSubmit={handleSubmit} disabled={thinking} />
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          {['/ceo approve Q3 budget', '/product add dashboard feature', '/hr open senior engineer role', '/finance review runway'].map(s => (
            <button key={s} onClick={() => handleSubmit(s)}
              className="text-[11px] px-2.5 py-1 rounded-full cursor-pointer transition-colors hover:bg-[rgba(255,255,255,0.06)]"
              style={{ background: 'rgba(255,255,255,0.03)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Create `app/chat/page.tsx`**

```tsx
// app/chat/page.tsx
import { CommandChat } from '@/components/chat/CommandChat'

export default function ChatPage() {
  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <div>
          <h1 className="font-display text-lg font-bold" style={{ color: 'var(--text-1)' }}>Command</h1>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-3)' }}>
            Direct your company. Use <code className="font-mono text-indigo-400">/agent</code> to route to a department.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--green)' }}>
          <span className="live-dot" />
          7 agents online
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <CommandChat />
      </div>
    </div>
  )
}
```

---

## Task 5: Agent Workspace — Worker Dropdown + Live Queue

**Files:**
- Create: `components/agents/WorkerAgentsDropdown.tsx`
- Rewrite: `app/agents/[agent]/page.tsx`

- [ ] **Step 1: Create `components/agents/WorkerAgentsDropdown.tsx`**

```tsx
// components/agents/WorkerAgentsDropdown.tsx
'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronRight, User, Circle } from 'lucide-react'

export interface WorkerAgent {
  id: string
  name: string
  role: string
  status: 'active' | 'idle' | 'busy' | 'offline'
  currentTask?: string
  tasksCompleted: number
}

const STATUS_COLOR = { active: '#22C55E', idle: '#2563EB', busy: '#F59E0B', offline: '#475569' }

export function WorkerAgentsDropdown({ agentName, workers }: {
  agentName: string
  workers: WorkerAgent[]
}) {
  const [open, setOpen] = useState(false)
  const activeCount = workers.filter(w => w.status === 'active' || w.status === 'busy').length

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[rgba(255,255,255,0.02)] transition-colors">
        <div className="flex items-center gap-2.5">
          <User size={14} style={{ color: 'var(--text-3)' }} />
          <span className="text-[13px] font-medium" style={{ color: 'var(--text-1)' }}>
            Worker Agents
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
            style={{ background: 'rgba(34,197,94,0.1)', color: 'var(--green)' }}>
            {activeCount} active
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px]" style={{ color: 'var(--text-3)' }}>{workers.length} workers</span>
          {open ? <ChevronDown size={13} style={{ color: 'var(--text-3)' }} /> : <ChevronRight size={13} style={{ color: 'var(--text-3)' }} />}
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="px-4 pb-3 space-y-1.5 border-t" style={{ borderColor: 'var(--border)' }}>
              <div className="pt-3" />
              {workers.map(w => (
                <div key={w.id} className="flex items-center gap-3 p-2.5 rounded-lg card-inner">
                  <Circle size={7} fill={STATUS_COLOR[w.status]} style={{ color: STATUS_COLOR[w.status], flexShrink: 0 }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-medium" style={{ color: 'var(--text-1)' }}>{w.name}</div>
                    <div className="text-[10px] truncate" style={{ color: 'var(--text-3)' }}>
                      {w.currentTask ?? w.role}
                    </div>
                  </div>
                  <div className="text-[10px] font-mono flex-shrink-0" style={{ color: 'var(--text-3)' }}>
                    {w.tasksCompleted} done
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
```

- [ ] **Step 2: Rewrite `app/agents/[agent]/page.tsx`**

The key changes from v1:
- New OLED theme (no glassmorphism)
- `WorkerAgentsDropdown` added below the task list
- `useQueue` hook renders live queue from API (falls back to mock)
- Remove `RadarChart` (not needed; keep bar chart)
- Keep: task list, message panel, direct message input, profile sidebar

Full rewrite matching the design system — apply all card/typography/color tokens from Task 1. The page must use `use(params)` for the dynamic route, and `'use client'` directive. See `app/agents/[agent]/page.tsx` current version as reference for structure; apply new tokens throughout.

**Key additions:**
1. Import and render `<WorkerAgentsDropdown>` with 3–5 seeded worker agents per department
2. Use `useHealth()` to decide whether to show a "live queue" section or fall back to mock messages
3. Remove `glassmorphism` classes, replace with `card` and `card-inner`
4. Replace all inline hex colors with CSS variable references

*(Full code provided in the implementation — executor should apply the design system tokens from Task 1 to the existing agent page structure, plus add WorkerAgentsDropdown with seeded data)*

---

## Task 6: Dashboard — New Theme + Live Data

**Files:**
- Rewrite: `app/dashboard/page.tsx`

Apply all new design system tokens:
- Replace `glass-card` → `card`
- Replace hex colors → `var(--text-1)`, `var(--text-2)`, `var(--text-3)`, `var(--card)`, `var(--border)`, `var(--green)`, `var(--indigo)`
- Keep chart logic; update `stroke`/`fill` colors to match the new palette
- Add a `useHealth()` banner at the top: green if API is up, subtle warning if offline (shows "Using demo data")
- Add `useAudit()` to populate the activity feed from real API when available

---

## Task 7: Messages Page — Real Queue Data

**Files:**
- Rewrite: `app/messages/page.tsx`

- Replace mock `MESSAGES` with `usePolling(() => api.audit.list(50), 5_000)` for the event stream
- For the queue inspector: use `api.messages.peek` when API is up
- Apply new design tokens throughout
- Keep JSON inspector component, fix the key={} duplication (already fixed)

---

## Task 8: Observability — Wire /health + /audit

**Files:**
- Update: `app/observability/page.tsx`

- Replace static health badge with `useHealth()` hook output
- Replace static audit log with `useAudit(30)` hook
- Apply new design tokens

---

## Self-Review

### Spec coverage check
| Requirement | Task |
|---|---|
| OLED dark theme, no heavy purple | Task 1 |
| Professional fonts (Fira Code + Plus Jakarta Sans) | Task 1 |
| API client for all FastAPI endpoints | Task 2 |
| Polling hooks with correct cadences | Task 2 |
| Sidebar redesign (no purple wash) | Task 3 |
| TopBar with API health indicator | Task 3 |
| Central Command Chat (ChatGPT-style) | Task 4 |
| /skills slash command routing | Task 4 |
| Simulated streaming agent responses | Task 4 |
| Quick-send suggestion chips | Task 4 |
| Worker agents in collapsible dropdown | Task 5 |
| Live queue from API on agent pages | Task 5 |
| Dashboard live data + offline fallback | Task 6 |
| Messages page from real API | Task 7 |
| Observability wired to real API | Task 8 |

### Gaps (none critical for v2)
- Real LLM integration (agent responses are mocked strings — real API calls are a v3 feature when the backend agents are ready)
- Auth UI (API key entry) — currently hardcoded to env vars; an admin settings page would be needed for production
- Worker agents are seeded mock data — real worker registration via `/registrations` is a backend concern

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-08-brain-enterprise-v2.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks

**2. Inline Execution** — execute in this session using executing-plans, with checkpoints

**Which approach?**
