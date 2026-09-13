import type { ApiArtifact, ApiAuditEvent, ApiQueueItem } from './api-types'
import type { AgentId, MessageFlow } from './types'

// Engineering artifact titles are all the generic "Engineering Feature
// Implementation" string, so a list of them is indistinguishable by title
// alone. metadata.generated_files carries the actual filenames the build
// produced (e.g. "weather_app.py" vs "calculator.py") -- surface the most
// identifying one instead so past builds are actually findable.
export function artifactLabel(a: Pick<ApiArtifact, 'title' | 'metadata'>): string {
  const files = Array.isArray(a.metadata?.generated_files) ? (a.metadata.generated_files as unknown[]) : []
  const named = files
    .filter((f): f is string => typeof f === 'string')
    .filter(f => !f.startsWith('__pycache__') && f !== 'plan.md')
    .sort((x, y) => (x.startsWith('test') ? 1 : 0) - (y.startsWith('test') ? 1 : 0))
  return named[0] ?? a.title
}

// Router-side agent names (message_submitted/acked/nacked audit events carry
// these in `details.sender`/`details.recipient` — see
// enterprise_router/service.py's _audit() calls) mapped to the website's UI
// AgentId. Names not in this map (MANAGER, Strategic Advisor) are ignored
// for these aggregates — they're not one of the seven department cards.
const ROUTER_NAME_TO_AGENT_ID: Record<string, AgentId> = {
  CEO: 'ceo',
  PM: 'product',
  Product: 'product',
  Engineering: 'engineering',
  HR: 'hr',
  Sales: 'sales',
  Marketing: 'marketing',
  Finance: 'finance',
}

const ALL_AGENT_IDS: AgentId[] = ['ceo', 'product', 'engineering', 'hr', 'sales', 'marketing', 'finance']

function detailString(event: ApiAuditEvent, key: string): string | null {
  const value = event.details?.[key]
  return typeof value === 'string' && value ? value : null
}

export type ThroughputPoint = {
  day: string
  completed: number
  blocked: number
  total: number
}

export type CountPoint = {
  name: string
  value: number
}

function safeDate(value: string): Date | null {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function bucketLabel(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function isFailureEvent(eventType: string): boolean {
  const value = eventType.toLowerCase()
  return value.includes('nack') || value.includes('error') || value.includes('fail') || value.includes('blocked') || value.includes('dead')
}

function isSuccessEvent(eventType: string): boolean {
  const value = eventType.toLowerCase()
  return value.includes('ack') || value.includes('submit') || value.includes('fetch') || value.includes('lease') || value.includes('done') || value.includes('register')
}

export function auditToThroughput(audit: ApiAuditEvent[] | null | undefined, limit = 7): ThroughputPoint[] {
  if (!audit?.length) return []
  const buckets = new Map<string, ThroughputPoint>()

  for (const event of audit) {
    const date = safeDate(event.created_at)
    if (!date) continue
    const label = bucketLabel(date)
    const existing = buckets.get(label) ?? { day: label, completed: 0, blocked: 0, total: 0 }
    existing.total += 1
    if (isFailureEvent(event.event_type)) existing.blocked += 1
    else if (isSuccessEvent(event.event_type)) existing.completed += 1
    else existing.completed += 1
    buckets.set(label, existing)
  }

  return Array.from(buckets.values()).slice(-limit)
}

export function auditToActorCounts(audit: ApiAuditEvent[] | null | undefined, limit = 8): CountPoint[] {
  if (!audit?.length) return []
  const counts = new Map<string, number>()
  for (const event of audit) {
    const actor = event.actor || 'unknown'
    counts.set(actor, (counts.get(actor) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit)
}

export function auditToTaskTypeCounts(audit: ApiAuditEvent[] | null | undefined, limit = 8): CountPoint[] {
  if (!audit?.length) return []
  const counts = new Map<string, number>()
  for (const event of audit) {
    const rawTask = event.details?.task_type
    const taskType = typeof rawTask === 'string' && rawTask ? rawTask : event.event_type || 'event'
    counts.set(taskType, (counts.get(taskType) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit)
}

export function queueToDeliveryStates(queue: ApiQueueItem[] | null | undefined): CountPoint[] {
  if (!queue?.length) return []
  const counts = new Map<string, number>()
  for (const item of queue) {
    counts.set(item.delivery_state, (counts.get(item.delivery_state) ?? 0) + 1)
  }
  return Array.from(counts.entries()).map(([name, value]) => ({ name, value }))
}

export function queueToPriorityDistribution(queue: ApiQueueItem[] | null | undefined): CountPoint[] {
  if (!queue?.length) return []
  const buckets = new Map<string, number>([
    ['critical', 0],
    ['high', 0],
    ['normal', 0],
    ['low', 0],
  ])
  for (const item of queue) {
    const priority = item.computed_priority
    const bucket = priority >= 175 ? 'critical' : priority >= 125 ? 'high' : priority >= 75 ? 'normal' : 'low'
    buckets.set(bucket, (buckets.get(bucket) ?? 0) + 1)
  }
  return Array.from(buckets.entries())
    .map(([name, value]) => ({ name, value }))
    .filter(point => point.value > 0)
}

export function withThroughputFallback<T extends ThroughputPoint>(live: ThroughputPoint[], fallback: T[]): ThroughputPoint[] | T[] {
  return live.length ? live : fallback
}

export type AgentStat = {
  id: AgentId
  messages: number
  completed: number
  failed: number
  /** null = no acked/nacked events yet for this agent (not "0%") */
  successRate: number | null
}

/**
 * Real per-agent activity derived from the router's own audit log, replacing
 * the fabricated successRate/completedTasks/totalMessages/activeTaskCount
 * fields on the static mock-data.ts Agent records. `messages` counts every
 * message_submitted event naming this agent as sender or recipient;
 * `completed`/`failed` count message_acked/message_nacked events where this
 * agent was the recipient (the only place the router's own audit trail
 * records a pass/fail outcome).
 */
export function auditToAgentStats(audit: ApiAuditEvent[] | null | undefined): Record<AgentId, AgentStat> {
  const stats = Object.fromEntries(
    ALL_AGENT_IDS.map(id => [id, { id, messages: 0, completed: 0, failed: 0, successRate: null as number | null }]),
  ) as Record<AgentId, AgentStat>

  for (const event of audit ?? []) {
    const sender = detailString(event, 'sender')
    const recipient = detailString(event, 'recipient')

    if (event.event_type === 'message_submitted') {
      const senderId = sender ? ROUTER_NAME_TO_AGENT_ID[sender] : undefined
      const recipientId = recipient ? ROUTER_NAME_TO_AGENT_ID[recipient] : undefined
      if (senderId) stats[senderId].messages += 1
      if (recipientId && recipientId !== senderId) stats[recipientId].messages += 1
    }

    if (recipient) {
      const recipientId = ROUTER_NAME_TO_AGENT_ID[recipient]
      if (recipientId) {
        if (event.event_type === 'message_acked') stats[recipientId].completed += 1
        if (event.event_type === 'message_nacked') stats[recipientId].failed += 1
      }
    }
  }

  for (const id of ALL_AGENT_IDS) {
    const s = stats[id]
    const total = s.completed + s.failed
    s.successRate = total > 0 ? Math.round((s.completed / total) * 100) : null
  }

  return stats
}

// Matches README "Current implemented runtime workers" vs "Registered but
// not implemented" -- Sales and Finance are registered with the router so
// they can be selected and messaged, but run_agents.py has no worker
// process for them, so nothing ever consumes what's sent. Kept here (not
// just on the agent detail page) because the sidebar's status dot needs
// the same distinction.
const LIVE_WORKER_AGENT_IDS = new Set<AgentId>(['ceo', 'product', 'engineering', 'hr', 'marketing'])

// An ack/nack/fetch in the last 90s reads as "working right now" rather
// than "idle" -- long enough to survive normal polling gaps, short enough
// that it doesn't call a two-hour-old event "busy".
const BUSY_WINDOW_MS = 90_000

export type AgentActivityStatus = 'working' | 'idle' | 'no-worker'

export type AgentActivity = {
  status: AgentActivityStatus
  lastEventAt: string | null
}

/**
 * Real per-agent status derived from the router's own audit log, replacing
 * the hardcoded, never-changing AGENT_STATUS map that used to sit in
 * Sidebar.tsx (and the equally-static `agent.status` field on mock-data.ts
 * records shown as the big pill at the top of each agent page) -- neither
 * ever reflected whether that agent's worker process had done anything
 * recently, or existed at all for Sales/Finance.
 *
 * This can't fully distinguish "idle, worker is fine, just nothing to do"
 * from "worker process crashed" -- the router has no heartbeat concept,
 * only a record of messages actually sent/acked/nacked. "idle" means
 * exactly that: no recent audit activity, not a claim the process is up.
 */
export function auditToAgentActivity(
  audit: ApiAuditEvent[] | null | undefined,
  now: number = Date.now(),
): Record<AgentId, AgentActivity> {
  const lastEventAt: Record<AgentId, string | null> = Object.fromEntries(
    ALL_AGENT_IDS.map(id => [id, null]),
  ) as Record<AgentId, string | null>

  for (const event of audit ?? []) {
    const sender = detailString(event, 'sender')
    const recipient = detailString(event, 'recipient')
    for (const name of [sender, recipient]) {
      if (!name) continue
      const id = ROUTER_NAME_TO_AGENT_ID[name]
      if (!id) continue
      if (!lastEventAt[id] || event.created_at > (lastEventAt[id] as string)) {
        lastEventAt[id] = event.created_at
      }
    }
  }

  const result = {} as Record<AgentId, AgentActivity>
  for (const id of ALL_AGENT_IDS) {
    if (!LIVE_WORKER_AGENT_IDS.has(id)) {
      result[id] = { status: 'no-worker', lastEventAt: lastEventAt[id] }
      continue
    }
    const at = lastEventAt[id]
    const recent = at ? now - new Date(at).getTime() < BUSY_WINDOW_MS : false
    result[id] = { status: recent ? 'working' : 'idle', lastEventAt: at }
  }
  return result
}

export type SwarmStep = {
  id: string
  role: string
  phase: string
  detail: string
  at: string
}

export type SwarmRun = {
  runId: string
  steps: SwarmStep[]
  startedAt: string
  latestAt: string
  status: 'running' | 'succeeded' | 'failed'
}

// Matches the three real CrewAI Agent roles defined in FullSystem
// (eng-agents/engineering_agent.py) -- not a fixed enum on the frontend's
// side, just the vocabulary the backend actually emits.
export const SWARM_ROLES = ['Lead Developer', 'Software Developer', 'Testing Engineer'] as const

/**
 * Groups the router's "swarm_activity" audit events (written by
 * eng-agents/engineering_agent.py's log_swarm_event(), one per phase
 * transition of the real Lead Developer / Software Developer / Testing
 * Engineer CrewAI agents that plan, write, and test each Engineering
 * build) into per-build timelines, most recently active first.
 *
 * This is the only place in the product where multiple distinct AI
 * agents actually collaborate turn-by-turn on one artifact -- the seven
 * department cards are a fixed roster, not agents spawning new agents.
 */
export function auditToSwarmRuns(audit: ApiAuditEvent[] | null | undefined, limit = 10): SwarmRun[] {
  const runs = new Map<string, SwarmStep[]>()
  for (const event of audit ?? []) {
    if (event.event_type !== 'swarm_activity') continue
    const runId = event.subject_id
    if (!runId) continue
    const phase = detailString(event, 'phase') ?? event.event_type
    const detail = typeof event.details?.detail === 'string' ? event.details.detail : ''
    const steps = runs.get(runId) ?? []
    steps.push({ id: event.id, role: event.actor || 'unknown', phase, detail, at: event.created_at })
    runs.set(runId, steps)
  }

  const result: SwarmRun[] = []
  for (const [runId, stepsUnsorted] of Array.from(runs.entries())) {
    const steps = [...stepsUnsorted].sort((a, b) => (a.at < b.at ? -1 : 1))
    const last = steps[steps.length - 1]
    const status: SwarmRun['status'] =
      last.phase === 'build_succeeded' ? 'succeeded' : last.phase === 'build_failed' ? 'failed' : 'running'
    result.push({ runId, steps, startedAt: steps[0].at, latestAt: last.at, status })
  }
  return result.sort((a, b) => (a.latestAt < b.latestAt ? 1 : -1)).slice(0, limit)
}

/**
 * Real inter-agent message counts from message_submitted audit events,
 * replacing the fabricated mock-data.ts MESSAGE_FLOW table.
 */
export function auditToMessageFlow(audit: ApiAuditEvent[] | null | undefined): MessageFlow[] {
  const counts = new Map<string, number>()
  for (const event of audit ?? []) {
    if (event.event_type !== 'message_submitted') continue
    const sender = detailString(event, 'sender')
    const recipient = detailString(event, 'recipient')
    if (!sender || !recipient) continue
    const from = ROUTER_NAME_TO_AGENT_ID[sender]
    const to = ROUTER_NAME_TO_AGENT_ID[recipient]
    if (!from || !to) continue
    const key = `${from} ${to}`
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return Array.from(counts.entries()).map(([key, count]) => {
    const [from, to] = key.split(' ') as [AgentId, AgentId]
    return { from, to, count }
  })
}
