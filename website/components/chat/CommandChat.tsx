'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '@/lib/api'
import { parseCommand } from '@/lib/chat-router'
import { SLASH_COMMANDS } from '@/lib/chat-router'
import ChatMessage, { type ChatMsg } from './ChatMessage'
import ChatInput from './ChatInput'
import { Zap, ChevronDown } from 'lucide-react'

const AGENT_COLORS: Record<string, string> = Object.fromEntries(
  SLASH_COMMANDS.map(c => [c.agentId, c.color])
)

let msgCounter = 0
function uid() { return `msg-${++msgCounter}-${Date.now()}` }

const WELCOME: ChatMsg = {
  id: 'welcome',
  role: 'system',
  text: 'BRAIN Enterprise Lab — Command interface active',
  timestamp: new Date(),
}

const INTRO: ChatMsg = {
  id: 'intro',
  role: 'agent',
  text: 'Welcome. I\'m your company\'s command interface. Type a message to broadcast to all departments, or use /ceo /prod /eng /hr /sales /mkt /fin to route directly to an agent.',
  agentName: 'BRAIN',
  agentColor: 'var(--indigo)',
  timestamp: new Date(),
}

export default function CommandChat() {
  const [messages, setMessages] = useState<ChatMsg[]>([WELCOME, INTRO])
  const [sending, setSending] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback((smooth = true) => {
    bottomRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' })
  }, [])

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

    try {
      const recipient = parsed.type === 'agent' ? parsed.agentId.toUpperCase() : 'CEO'
      const instruction = parsed.type === 'agent' ? parsed.text || raw : raw

      await api.manager.intervene({
        recipient,
        instruction,
        priority: 'normal',
        context: { source: 'command_chat' },
      })

      // Replace loading bubble with success
      setMessages(prev => prev.map(m =>
        m.id === loadingId
          ? { ...m, loading: false, text: `Instruction sent to ${agentName}. The agent will process this and respond shortly.` }
          : m
      ))
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
    } finally {
      setSending(false)
    }
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
