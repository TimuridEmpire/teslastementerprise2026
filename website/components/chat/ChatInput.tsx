'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { Send, Slash } from 'lucide-react'
import { getSlashSuggestions, SLASH_COMMANDS } from '@/lib/chat-router'
import SlashMenu from './SlashMenu'

interface ChatInputProps {
  onSend: (text: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [suggestions, setSuggestions] = useState<typeof SLASH_COMMANDS>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [value])

  function handleChange(v: string) {
    setValue(v)
    // Only check slash commands in the first word
    const firstWord = v.split(' ')[0]
    if (firstWord.startsWith('/') && v === firstWord) {
      setSuggestions(getSlashSuggestions(firstWord))
      setActiveIndex(0)
    } else {
      setSuggestions([])
    }
  }

  function handleSelect(cmd: string) {
    setValue(cmd)
    setSuggestions([])
    textareaRef.current?.focus()
  }

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    setSuggestions([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (suggestions.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIndex(i => (i + 1) % suggestions.length) }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setActiveIndex(i => (i - 1 + suggestions.length) % suggestions.length) }
      if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault()
        handleSelect(suggestions[activeIndex].command + ' ')
        return
      }
      if (e.key === 'Escape') { setSuggestions([]); return }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const hasContent = value.trim().length > 0

  return (
    <div className="relative">
      <SlashMenu suggestions={suggestions} onSelect={handleSelect} activeIndex={activeIndex} />
      <div
        className="flex items-end gap-3 rounded-xl px-4 py-3"
        style={{
          background: 'var(--card)',
          border: '1px solid var(--border)',
          transition: 'border-color 0.15s',
        }}
        onFocus={() => {}}
      >
        {/* Slash hint */}
        <button
          onClick={() => handleChange('/')}
          className="flex-shrink-0 mb-0.5 cursor-pointer opacity-40 hover:opacity-70 transition-opacity"
          style={{ color: 'var(--indigo-2)' }}
          tabIndex={-1}
          title="Use slash commands to route to an agent"
        >
          <Slash size={15} />
        </button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Message your company… or type / to route to an agent"
          rows={1}
          className="flex-1 bg-transparent resize-none outline-none text-[13.5px] leading-relaxed placeholder:text-[var(--text-3)]"
          style={{ color: 'var(--text-1)', maxHeight: 160, minHeight: 24 }}
        />

        <button
          onClick={submit}
          disabled={!hasContent || disabled}
          className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mb-0.5 transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
          style={{
            background: hasContent && !disabled ? 'var(--indigo)' : 'var(--card)',
            color: hasContent && !disabled ? 'white' : 'var(--text-3)',
            border: '1px solid var(--border)',
          }}
        >
          <Send size={13} />
        </button>
      </div>
      <div className="flex items-center justify-between mt-1.5 px-1">
        <span className="text-[10px]" style={{ color: 'var(--text-3)' }}>
          <span className="font-mono" style={{ color: 'var(--indigo-2)' }}>/agent</span> to route · Shift+Enter for new line
        </span>
        <span className="text-[10px]" style={{ color: 'var(--text-3)' }}>
          {value.length > 0 ? `${value.length} chars` : ''}
        </span>
      </div>
    </div>
  )
}
