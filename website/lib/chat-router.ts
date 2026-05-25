import type { AgentId } from './types'

// Slash-command → agent mapping
export const SLASH_COMMANDS: {
  command: string
  agentId: AgentId
  label: string
  description: string
  color: string
}[] = [
  { command: '/ceo',  agentId: 'ceo',         label: 'CEO',         description: 'Executive decisions & strategy',   color: 'var(--agent-ceo)' },
  { command: '/prod', agentId: 'product',      label: 'Product',     description: 'Roadmap, features & backlog',      color: 'var(--agent-product)' },
  { command: '/eng',  agentId: 'engineering',  label: 'Engineering', description: 'Tech specs & implementation',      color: 'var(--agent-engineering)' },
  { command: '/hr',   agentId: 'hr',           label: 'HR',          description: 'Hiring, culture & team ops',       color: 'var(--agent-hr)' },
  { command: '/sales',agentId: 'sales',        label: 'Sales',       description: 'Pipeline, deals & revenue',        color: 'var(--agent-sales)' },
  { command: '/mkt',  agentId: 'marketing',    label: 'Marketing',   description: 'Campaigns, brand & growth',        color: 'var(--agent-marketing)' },
  { command: '/fin',  agentId: 'finance',      label: 'Finance',     description: 'Budget, forecasting & reporting',  color: 'var(--agent-finance)' },
]

export type ParsedCommand =
  | { type: 'agent'; agentId: AgentId; agentName: string; text: string; color: string }
  | { type: 'broadcast'; text: string }

/** Parse a user message. Slash prefix routes to specific agent; no prefix = broadcast to CEO. */
export function parseCommand(raw: string): ParsedCommand {
  const trimmed = raw.trim()
  const match = SLASH_COMMANDS.find(c => trimmed.toLowerCase().startsWith(c.command + ' ') || trimmed.toLowerCase() === c.command)
  if (match) {
    const text = trimmed.slice(match.command.length).trim()
    return { type: 'agent', agentId: match.agentId, agentName: match.label, text, color: match.color }
  }
  return { type: 'broadcast', text: trimmed }
}

/** Return slash suggestions matching a partial `/xyz` prefix the user is typing */
export function getSlashSuggestions(partial: string) {
  const lower = partial.toLowerCase()
  if (!lower.startsWith('/')) return []
  return SLASH_COMMANDS.filter(c => c.command.startsWith(lower))
}
