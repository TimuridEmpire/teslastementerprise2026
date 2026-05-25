import type { ApiAuditEvent, ApiQueueItem } from './api-types'

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
