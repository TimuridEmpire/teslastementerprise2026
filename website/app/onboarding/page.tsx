'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Crown, Package, Code2, Users, TrendingUp, Megaphone, DollarSign,
  Sparkles, ArrowRight, ChevronLeft, Check, Send, Zap,
} from 'lucide-react'
import type { AgentId } from '@/lib/types'

/* ─── Agent definitions ─────────────────────────────────────────────────── */
interface AgentDef {
  id: AgentId
  name: string
  role: string
  hex: string   // actual hex for alpha compositing in inline styles
  cssVar: string
  icon: React.ReactNode
  desc: string
}

const AGENT_DEFS: AgentDef[] = [
  { id: 'ceo',         name: 'Atlas',  role: 'Chief Executive',    hex: '#F59E0B', cssVar: 'var(--agent-ceo)',         icon: <Crown size={18} />,     desc: 'Strategic decisions, cross-team conflicts, board reporting' },
  { id: 'product',     name: 'Vera',   role: 'Product Manager',    hex: '#888888', cssVar: 'var(--agent-product)',     icon: <Package size={18} />,   desc: 'Roadmap, PRDs, user research, prioritization' },
  { id: 'engineering', name: 'Kano',   role: 'Engineering Lead',   hex: '#60A5FA', cssVar: 'var(--agent-engineering)', icon: <Code2 size={18} />,     desc: 'Architecture, code review, deployments, CI/CD' },
  { id: 'hr',          name: 'Iris',   role: 'People Ops',         hex: '#34D399', cssVar: 'var(--agent-hr)',          icon: <Users size={18} />,     desc: 'Hiring, onboarding, performance, culture' },
  { id: 'sales',       name: 'Orion',  role: 'Sales Manager',      hex: '#22D3EE', cssVar: 'var(--agent-sales)',       icon: <TrendingUp size={18} />,desc: 'Pipeline, deals, forecasting, customer relations' },
  { id: 'marketing',   name: 'Nova',   role: 'Marketing Director', hex: '#F472B6', cssVar: 'var(--agent-marketing)',   icon: <Megaphone size={18} />, desc: 'Brand, content, demand gen, campaigns' },
  { id: 'finance',     name: 'Sable',  role: 'Chief Financial',    hex: '#FB923C', cssVar: 'var(--agent-finance)',     icon: <DollarSign size={18} />,desc: 'Budget, forecasts, spend approval, compliance' },
]

function hexAlpha(hex: string, alpha: number) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

/* ─── Questions ─────────────────────────────────────────────────────────── */
interface Question {
  id: string
  prompt: string
  placeholder: string
  single: boolean
}
const QUESTIONS: Question[] = [
  { id: 'name',     prompt: "Welcome. I'm Atlas — your founding executive. To get us started, what would you like to call this company?", placeholder: 'e.g. Northwind Robotics', single: true },
  { id: 'oneliner', prompt: "Got it — {name}. In one sentence, what does {name} do?", placeholder: 'e.g. We build autonomous warehouse robots for mid-market logistics.', single: false },
  { id: 'customer', prompt: "Clear. Who is this for — what does an ideal customer look like?", placeholder: 'e.g. Operations leaders at 100–500-employee logistics companies', single: false },
  { id: 'goal',     prompt: "Last one for now: what's the most important goal for the next 90 days?", placeholder: 'e.g. Ship pilot with 3 design-partner customers and close a $2M seed round.', single: false },
]

/* ─── Boot lines ────────────────────────────────────────────────────────── */
const bootLine = (stage: number, agent: AgentDef): string => {
  switch (stage) {
    case 0: return `[ boot ] allocating runtime for ${agent.name}`
    case 1: return `[ load ] tools: ${
      agent.id === 'engineering' ? 'repo, ci/cd, monitoring'
      : agent.id === 'finance'   ? 'ledger, invoices, forecaster'
      : agent.id === 'sales'     ? 'crm, sequencer, forecaster'
      : agent.id === 'marketing' ? 'studio, scheduler, analytics'
      : agent.id === 'hr'        ? 'ats, hr database, onboarding'
      : agent.id === 'product'   ? 'backlog, analytics, roadmap'
      : 'budget, performance, board'
    }`
    case 2: return `[ sync ] linking ${agent.name} → atlas via priority bus`
    case 3: return `[  ok  ] ${agent.name} operational`
    default: return ''
  }
}

/* ─── Step bar ──────────────────────────────────────────────────────────── */
const STEP_LABELS = ['Define', 'Team', 'Spin up']

function StepBar({ step }: { step: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      {STEP_LABELS.map((label, i) => {
        const state = i < step ? 'done' : i === step ? 'active' : ''
        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <div className={`step-dot ${state}`}>
                {i < step ? <Check size={11} strokeWidth={2.5} /> : i + 1}
              </div>
              <span style={{
                fontSize: 11.5,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: state === 'active' ? 'var(--text-1)' : state === 'done' ? 'var(--indigo-2)' : 'var(--text-3)',
              }}>
                {label}
              </span>
            </div>
            {i < STEP_LABELS.length - 1 && (
              <div style={{ width: 36, height: 1, background: i < step ? 'var(--indigo)' : 'var(--border)' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ─── Welcome screen ────────────────────────────────────────────────────── */
function WelcomeStep({ onStart }: { onStart: () => void }) {
  return (
    <div style={{ textAlign: 'center', maxWidth: 680 }}>
      <div style={{
        width: 64, height: 64, borderRadius: 16, marginBottom: 28,
        background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.14)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 28px',
        boxShadow: '0 0 40px rgba(255,255,255,0.12)',
      }}>
        <Zap size={28} style={{ color: 'var(--primary-2)' }} />
      </div>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 10, marginBottom: 28,
        padding: '8px 16px', borderRadius: 999,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.16)',
      }}>
        <Sparkles size={13} style={{ color: 'var(--primary-2)' }} />
        <span style={{ fontSize: 11.5, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--primary-2)' }}>
          Kanosei · v1.0
        </span>
      </div>
      <h1 style={{ fontSize: 56, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.05, color: 'var(--text-1)', marginBottom: 22 }}>
        Define a company.<br />
        <span style={{ color: 'var(--text-2)' }}>Spin up a team.</span><br />
        <span style={{ color: 'var(--indigo-2)' }}>Operate together.</span>
      </h1>
      <p style={{ fontSize: 15.5, color: 'var(--text-2)', maxWidth: 540, margin: '0 auto 36px', lineHeight: 1.6 }}>
        Kanosei is an autonomous company runtime. Tell Atlas what you&apos;re building.
        He&apos;ll assemble a team of agents — engineering, product, marketing, sales, finance, HR —
        and they&apos;ll coordinate, deliver, and report back to you.
      </p>
      <button className="btn btn-primary" onClick={onStart} style={{ padding: '14px 26px', fontSize: 14 }}>
        Begin onboarding <ArrowRight size={14} />
      </button>
      <div style={{ marginTop: 38, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 36, color: 'var(--text-3)', fontSize: 11.5, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
          7 agent roles
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--indigo-2)', display: 'inline-block' }} />
          trust-bounded
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--amber)', display: 'inline-block' }} />
          humans in the loop
        </span>
      </div>
    </div>
  )
}

/* ─── Step 1: Define ────────────────────────────────────────────────────── */
interface Message { role: 'atlas' | 'user'; text: string }
type Answers = Record<string, string>

function DefineStep({
  answers, setAnswers, onComplete,
}: {
  answers: Answers
  setAnswers: (a: Answers) => void
  onComplete: () => void
}) {
  const [qi, setQi] = useState(0)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [typing, setTyping] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messages.length === 0) {
      const t = setTimeout(() => {
        setMessages([{ role: 'atlas', text: QUESTIONS[0].prompt }])
        setTyping(false)
      }, 700)
      return () => clearTimeout(t)
    }
  }, [])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, typing])

  const submit = () => {
    if (!draft.trim() || typing || qi >= QUESTIONS.length) return
    const q = QUESTIONS[qi]
    const newAns: Answers = { ...answers, [q.id]: draft.trim() }
    setAnswers(newAns)
    const next: Message[] = [...messages, { role: 'user', text: draft.trim() }]
    setMessages(next)
    setDraft('')

    if (qi < QUESTIONS.length - 1) {
      setTyping(true)
      setTimeout(() => {
        const nq = QUESTIONS[qi + 1]
        const filled = nq.prompt.replace(/\{name\}/g, newAns.name || 'your company')
        setMessages([...next, { role: 'atlas', text: filled }])
        setTyping(false)
        setQi(qi + 1)
      }, 900)
    } else {
      setTyping(true)
      setTimeout(() => {
        setMessages([...next, { role: 'atlas', text: `Excellent. I have what I need to recommend an initial team for ${newAns.name}. Let's review who I'm bringing on.` }])
        setTyping(false)
        setTimeout(() => onComplete(), 1400)
      }, 1100)
    }
  }

  const q = QUESTIONS[qi]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', maxWidth: 760, width: '100%' }}>
      {/* Atlas card */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24, padding: '12px 14px', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
        <div className="agent-glyph" style={{ width: 36, height: 36, borderRadius: 9, background: 'rgba(245,158,11,0.14)', border: '1px solid rgba(245,158,11,0.3)' }}>
          <Crown size={18} style={{ color: 'var(--agent-ceo)' }} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>
            Atlas <span style={{ color: 'var(--text-3)', fontWeight: 400, marginLeft: 6 }}>· Chief Executive</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
            <span className="live-dot" style={{ width: 6, height: 6, background: 'var(--agent-ceo)', boxShadow: '0 0 6px rgba(245,158,11,0.5)', marginRight: 6 }} />
            online · ready to onboard
          </div>
        </div>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          question {Math.min(qi + 1, QUESTIONS.length)} / {QUESTIONS.length}
        </span>
      </div>

      {/* Chat */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '4px 4px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.map((m, i) => (
          <div key={i} className="fade-up" style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            {m.role === 'atlas' && (
              <div className="agent-glyph" style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(245,158,11,0.14)', border: '1px solid rgba(245,158,11,0.3)', marginRight: 10, alignSelf: 'flex-end', flexShrink: 0 }}>
                <Crown size={13} style={{ color: 'var(--agent-ceo)' }} />
              </div>
            )}
            <div className={`chat-bubble ${m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-agent'}`}>
              {m.text}
            </div>
          </div>
        ))}
        {typing && (
          <div className="fade-in" style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div className="agent-glyph" style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(245,158,11,0.14)', border: '1px solid rgba(245,158,11,0.3)', marginRight: 10, alignSelf: 'flex-end', flexShrink: 0 }}>
              <Crown size={13} style={{ color: 'var(--agent-ceo)' }} />
            </div>
            <div className="chat-bubble chat-bubble-agent typing-dots">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ padding: '14px 0 4px', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: 10 }}>
          {q?.single ? (
            <input
              className="input"
              placeholder={q.placeholder}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') submit() }}
              disabled={typing || qi >= QUESTIONS.length}
              autoFocus
            />
          ) : (
            <textarea
              className="input"
              placeholder={q ? q.placeholder : 'Atlas is finishing up…'}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit() }}
              disabled={typing || qi >= QUESTIONS.length}
              rows={3}
              style={{ minHeight: 72, resize: 'none' }}
              autoFocus
            />
          )}
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={!draft.trim() || typing}
            style={{ alignSelf: 'flex-end', height: 40, opacity: draft.trim() && !typing ? 1 : 0.5 }}
          >
            <Send size={13} />
            {q?.single ? '' : 'Send'}
          </button>
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginTop: 6, letterSpacing: '0.05em' }}>
          {q?.single ? 'enter ↵' : '⌘+↵ to send · your answers shape the team Atlas spins up'}
        </div>
      </div>
    </div>
  )
}

/* ─── Step 2: Team ──────────────────────────────────────────────────────── */
type Selection = Record<AgentId, boolean>

function TeamStep({
  answers, selected, setSelected, onBack, onNext,
}: {
  answers: Answers
  selected: Selection
  setSelected: (fn: (s: Selection) => Selection) => void
  onBack: () => void
  onNext: () => void
}) {
  const toggle = (id: AgentId) => setSelected(s => ({ ...s, [id]: !s[id] }))

  return (
    <div style={{ maxWidth: 880, width: '100%' }}>
      <div style={{ marginBottom: 28 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Recommended team</div>
        <h1 style={{ fontSize: 30, fontWeight: 600, color: 'var(--text-1)', marginBottom: 10, letterSpacing: '-0.02em' }}>
          The seven Atlas recommends for{' '}
          <span style={{ color: 'var(--indigo-2)' }}>{answers.name || 'your company'}</span>
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text-2)', maxWidth: 600 }}>
          Each agent operates autonomously within trust boundaries you set.
          Toggle anyone off — you can change them later under Agents.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
        {AGENT_DEFS.map(a => {
          const on = selected[a.id]
          const isCeo = a.id === 'ceo'
          return (
            <div
              key={a.id}
              className={`agent-tile${on ? ' selected' : ''}`}
              onClick={() => !isCeo && toggle(a.id)}
              style={isCeo ? { cursor: 'default' } : {}}
            >
              <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
                <div className="agent-glyph" style={{ width: 36, height: 36, borderRadius: 9, background: hexAlpha(a.hex, 0.15), border: `1px solid ${hexAlpha(a.hex, 0.3)}`, color: a.cssVar }}>
                  {a.icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>{a.name}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-3)' }}>· {a.role}</span>
                  </div>
                </div>
                {isCeo ? (
                  <span className="badge" style={{ background: 'rgba(245,158,11,0.12)', borderColor: 'rgba(245,158,11,0.3)', color: 'var(--agent-ceo)', alignSelf: 'flex-start' }}>core</span>
                ) : (
                  <div style={{
                    width: 18, height: 18, borderRadius: 5, flexShrink: 0, alignSelf: 'flex-start',
                    border: `1.5px solid ${on ? 'var(--indigo)' : 'var(--border-strong)'}`,
                    background: on ? 'var(--indigo)' : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {on && <Check size={11} strokeWidth={3} color="white" />}
                  </div>
                )}
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.55 }}>{a.desc}</p>
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button className="btn btn-ghost" onClick={onBack}>
          <ChevronLeft size={13} /> Back
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
            {Object.values(selected).filter(Boolean).length} agents selected
          </span>
          <button className="btn btn-primary" onClick={onNext}>
            Spin up team <ArrowRight size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Step 3: Spin up ───────────────────────────────────────────────────── */
interface LogLine { agentId?: string; text: string; color?: string }

function SpinUpStep({
  answers, selected, onDone,
}: {
  answers: Answers
  selected: Selection
  onDone: () => void
}) {
  const team = AGENT_DEFS.filter(a => selected[a.id])
  const [progress, setProgress] = useState(0)
  const [lines, setLines] = useState<LogLine[]>([])
  const linesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    const delay = (ms: number) => new Promise<void>(r => setTimeout(r, ms))

    const run = async () => {
      setLines(l => [...l, { text: `[ init ] kanosei runtime · spawning ${team.length} agents for ${answers.name || 'company'}` }])
      await delay(600)
      for (let i = 0; i < team.length; i++) {
        if (cancelled) return
        const a = team[i]
        for (let j = 0; j < 4; j++) {
          if (cancelled) return
          setLines(l => [...l, { agentId: a.id, text: bootLine(j, a), color: a.cssVar }])
          await delay(180 + Math.random() * 140)
        }
        setProgress(i + 1)
        await delay(180)
      }
      if (cancelled) return
      setLines(l => [...l, { text: `[ ready ] company operating · ${team.length} agents online · atlas in command` }])
      await delay(1100)
      onDone()
    }
    run()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (linesRef.current) linesRef.current.scrollTop = linesRef.current.scrollHeight
  }, [lines])

  return (
    <div style={{ maxWidth: 980, width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'stretch' }}>
      {/* Left: agent status */}
      <div className="card-flat" style={{ padding: 24, display: 'flex', flexDirection: 'column' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Booting</div>
        <h2 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-1)', marginBottom: 16, letterSpacing: '-0.01em' }}>
          {answers.name || 'Your company'} is coming online
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
          {team.map((a, i) => {
            const done = i < progress
            const active = i === progress
            return (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: active ? 'var(--card)' : 'transparent', border: '1px solid', borderColor: active ? hexAlpha(a.hex, 0.4) : 'var(--border)', borderRadius: 8, transition: 'all 0.2s' }}>
                <div className="agent-glyph" style={{ width: 30, height: 30, borderRadius: 8, background: hexAlpha(a.hex, 0.15), border: `1px solid ${hexAlpha(a.hex, 0.3)}`, color: a.cssVar }}>
                  {a.icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-1)' }}>{a.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                    {done ? 'ready' : active ? 'booting…' : 'queued'}
                  </div>
                </div>
                {done ? (
                  <div style={{ color: 'var(--green)' }}><Check size={15} strokeWidth={2.5} /></div>
                ) : active ? (
                  <div className="spinner" />
                ) : (
                  <div style={{ width: 14, height: 14, borderRadius: '50%', border: '1.5px dashed var(--border-strong)' }} />
                )}
              </div>
            )
          })}
        </div>
        <div style={{ marginTop: 16 }}>
          <div className="progress" style={{ height: 5 }}>
            <div className="progress-fill" style={{ width: `${(progress / team.length) * 100}%`, background: 'var(--indigo)' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>
            <span>{progress} / {team.length} agents operational</span>
            <span>{Math.round((progress / team.length) * 100)}%</span>
          </div>
        </div>
      </div>

      {/* Right: console */}
      <div className="card-flat" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 11.5, fontFamily: 'var(--font-mono)', color: 'var(--text-2)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>runtime · stdout</span>
          <span style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{lines.length} lines</span>
        </div>
        <div ref={linesRef} style={{ flex: 1, padding: 16, overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.65, color: 'var(--text-2)', minHeight: 320, maxHeight: 460 }}>
          {lines.map((l, i) => (
            <div key={i} className="fade-in" style={{ color: l.color || 'var(--text-2)' }}>{l.text}</div>
          ))}
          <span style={{ display: 'inline-block', width: 7, height: 13, background: 'var(--indigo-2)', verticalAlign: -2, animation: 'dot-pulse 1.2s ease-in-out infinite' }} />
        </div>
        <div className="boot-bar" />
      </div>
    </div>
  )
}

/* ─── Root page ─────────────────────────────────────────────────────────── */
type Phase = 'welcome' | 'step'

export default function OnboardingPage() {
  const router = useRouter()
  const [phase, setPhase] = useState<Phase>('welcome')
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Answers>({})
  const [selected, setSelected] = useState<Selection>({
    ceo: true, product: true, engineering: true, hr: true, sales: true, marketing: true, finance: true,
  })

  const finish = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('kanosei_onboarded', 'true')
      if (answers.name) localStorage.setItem('kanosei_company', answers.name)
    }
    router.push('/dashboard')
  }

  const skip = () => {
    if (typeof window !== 'undefined') localStorage.setItem('kanosei_onboarded', 'true')
    router.push('/dashboard')
  }

  return (
    <div style={{ position: 'fixed', inset: 0, overflow: 'hidden', zIndex: 9999 }}>
      <div className="onboarding-bg" />
      <div className="onboarding-grid" />

      {/* Header */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, padding: '22px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', zIndex: 2 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 26, height: 26, borderRadius: 7, background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.14)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Zap size={13} style={{ color: 'var(--primary-2)' }} />
          </div>
          <span className="kanosei-mark" style={{ fontSize: 13, color: 'var(--text-1)' }}>KANOSEI</span>
        </div>
        {phase === 'step' && <StepBar step={step} />}
        <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={skip}>
          Skip onboarding →
        </button>
      </div>

      {/* Content */}
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '88px 32px 32px', zIndex: 2 }}>
        {phase === 'welcome' && (
          <WelcomeStep onStart={() => setPhase('step')} />
        )}
        {phase === 'step' && step === 0 && (
          <DefineStep answers={answers} setAnswers={setAnswers} onComplete={() => setStep(1)} />
        )}
        {phase === 'step' && step === 1 && (
          <TeamStep answers={answers} selected={selected} setSelected={setSelected} onBack={() => setStep(0)} onNext={() => setStep(2)} />
        )}
        {phase === 'step' && step === 2 && (
          <SpinUpStep answers={answers} selected={selected} onDone={finish} />
        )}
      </div>
    </div>
  )
}


