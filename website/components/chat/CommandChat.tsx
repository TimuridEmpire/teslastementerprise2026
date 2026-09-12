'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '@/lib/api'
import { parseCommand, routerAgentName } from '@/lib/chat-router'
import { SLASH_COMMANDS } from '@/lib/chat-router'
import ChatMessage, { type ChatMsg } from './ChatMessage'
import ChatInput from './ChatInput'
import { Zap, ChevronDown } from 'lucide-react'

const AGENT_COLORS: Record<string, string> = Object.fromEntries(
  SLASH_COMMANDS.map(c => [c.agentId, c.color])
)

let msgCounter = 0
function uid() { return `msg-${++msgCounter}-${Date.now()}` }

// Built inside an effect (client-only, post-mount) rather than as module-level
// constants. `timestamp: new Date()` rendered via `toLocaleTimeString()` during
// the initial render caused a hydration mismatch: the server render and the
// client's first render evaluate `new Date()` at different real moments (and
// Node's default ICU locale data can format it differently than the browser's
// `Intl` anyway), so the server-rendered HTML and the client's first render
// disagreed on the displayed time — "Text content does not match
// server-rendered HTML." Seeding `messages` as `[]` means the server and the
// client's first render both show nothing, so they always match; these two
// bootstrap messages are then added afterward, strictly client-side.
function makeWelcomeMessages(): ChatMsg[] {
  const now = new Date()
  return [
    {
      id: 'welcome',
      role: 'system',
      text: 'BRAIN Enterprise Lab — Command interface active',
      timestamp: now,
    },
    {
      id: 'intro',
      role: 'agent',
      text: 'Welcome. I\'m your company\'s command interface. Type a message to broadcast to all departments, or use /ceo /prod /eng /hr /sales /mkt /fin to route directly to an agent.',
      agentName: 'BRAIN',
      agentColor: 'var(--indigo)',
      timestamp: now,
    },
  ]
}

const ARTIFACT_POLL_INTERVAL_MS = 2000
const ARTIFACT_POLL_TIMEOUT_MS = 90_000

// POST /manager/interventions only ever confirms a message was *queued* —
// nothing polls it back with the agent's actual reply, so the chat bubble
// used to say "Instruction queued..." and then never change, no matter what
// happened. Artifacts are the visible signal of completed work (see
// enterprise_router/agent_artifacts.py), and every fixed handler (CEO, PM,
// Marketing, HR, Engineering) now stamps source_message_id with the id
// /manager/interventions returned, so we can find "the artifact this agent
// just wrote for this request" and show it as the reply instead.
function extractArtifactBody(content: string): string {
  const afterHeader = content.split(/\n---\n\n/).slice(1).join('\n---\n\n')
  const body = (afterHeader || content).split(/\n## Metadata\n/)[0].trim()
  return body.length > 3000
    ? `${body.slice(0, 3000)}\n\n…(truncated — see the full artifact on /dashboard or /artifacts)`
    : body
}

async function waitForArtifactReply(
  recipient: string,
  messageId: string,
  onTick?: (elapsedMs: number) => void,
): Promise<{ title: string; body: string } | null> {
  const start = Date.now()
  const deadline = start + ARTIFACT_POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    try {
      const artifacts = await api.artifacts.list(recipient, 5)
      const match = artifacts.find(a => a.source_message_id === messageId)
      if (match) {
        const detail = await api.artifacts.get(match.artifact_id)
        return { title: match.title, body: extractArtifactBody(detail.content ?? '') }
      }
    } catch {
      // Transient fetch error — keep polling until the deadline instead of
      // giving up on the first hiccup.
    }
    onTick?.(Date.now() - start)
    await new Promise(resolve => setTimeout(resolve, ARTIFACT_POLL_INTERVAL_MS))
  }
  return null
}

export default function CommandChat() {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [sending, setSending] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback((smooth = true) => {
    bottomRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' })
  }, [])

  useEffect(() => { setMessages(makeWelcomeMessages()) }, [])
  useEffect(() => { scrollToBottom(false) }, [])
  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  function handleScroll() {
    const el = scrollRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setShowScrollBtn(distFromBottom > 120)
  }

  async function handleSend(raw: string) {
    if (sending) return
    const parsed = parseCommand(raw)

    // Add user bubble
    const userMsg: ChatMsg = {
      id: uid(),
      role: 'user',
      text: raw,
      timestamp: new Date(),
    }

    // Add loading agent bubble
    const loadingId = uid()
    const agentName  = parsed.type === 'agent' ? parsed.agentName  : 'CEO'
    const agentColor = parsed.type === 'agent'
      ? AGENT_COLORS[parsed.agentId] ?? 'var(--indigo)'
      : AGENT_COLORS['ceo']

    const loadingMsg: ChatMsg = {
      id: loadingId,
      role: 'agent',
      text: '',
      agentName,
      agentColor,
      timestamp: new Date(),
      loading: true,
    }

    setMessages(prev => [...prev, userMsg, loadingMsg])
    setSending(true)

    const recipient = parsed.type === 'agent' ? routerAgentName(parsed.agentId) : 'CEO'
    let messageId: string | null = null

    try {
      const instruction = parsed.type === 'agent' ? parsed.text || raw : raw
      const taskType = recipient === 'CEO' ? 'CEO_REASONING_LOOP' : 'MANAGER_INTERVENTION'

      const result = await api.manager.intervene({
        recipient,
        instruction,
        task_type: taskType,
        priority: 'normal',
        context: { source: 'command_chat' },
      })
      messageId = result.message_id
    } catch (err) {
      const errText = err instanceof Error ? err.message : 'Failed to deliver message'
      setMessages(prev => prev.map(m =>
        m.id === loadingId
          ? {
              ...m,
              loading: false,
              text: `[Offline mode] Message logged locally. ${errText.includes('401') ? 'API key not configured.' : ''}`,
              agentColor: 'var(--text-3)',
            }
          : m
      ))
      setSending(false)
      return
    }

    // Submission succeeded — unblock the input right away so the user can
    // keep chatting while this agent's real reply is polled for in the
    // background. Real replies (especially CEO's local-model calls) can
    // take anywhere from under a second to 30+ seconds.
    setSending(false)

    const reply = await waitForArtifactReply(recipient, messageId, elapsedMs => {
      // Without this, the bubble sits on bare typing dots for however long
      // the agent takes (CEO makes real sequential local-model calls and can
      // take 20-40s) with zero feedback — which reads as "stuck," not "slow."
      const seconds = Math.round(elapsedMs / 1000)
      if (seconds < 5) return
      setMessages(prev => prev.map(m =>
        m.id === loadingId
          ? { ...m, text: `Still waiting on ${agentName} (${seconds}s)… local-model calls can take 20-40s.` }
          : m
      ))
    })
    setMessages(prev => prev.map(m =>
      m.id === loadingId
        ? {
            ...m,
            loading: false,
            text: reply
              ? reply.body
              : `${agentName} hasn't produced a visible artifact yet. Check /observability for audit history or /dashboard for the latest artifacts.`,
          }
        : m
    ))
  }

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-6 py-6 space-y-5"
      >
        {messages.map(msg => (
          <ChatMessage key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Scroll-to-bottom button */}
      <AnimatePresence>
        {showScrollBtn && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            onClick={() => scrollToBottom()}
            className="absolute bottom-28 right-8 w-8 h-8 rounded-full flex items-center justify-center cursor-pointer z-10"
            style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text-2)' }}
          >
            <ChevronDown size={14} />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Input */}
      <div
        className="px-6 pb-6 pt-3 flex-shrink-0"
        style={{ borderTop: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <ChatInput onSend={handleSend} disabled={sending} />
      </div>
    </div>
  )
}
