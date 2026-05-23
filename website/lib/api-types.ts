// Exact TypeScript mirror of enterprise_router API contracts (see UI-Team.md §10)

export type RegistrationStatus = 'pending' | 'approved' | 'rejected'
export type MessageStatus      = 'pending' | 'in_progress' | 'done' | 'error'
export type DeliveryState      =
  | 'pending' | 'leased' | 'blocked' | 'expired' | 'dead_lettered' | 'done'

// ─── Agent ────────────────────────────────────────────────────────────────────
export interface ApiAgent {
  agent_name:          string
  role:                string
  hierarchy_level:     number
  trust_level:         number
  file_path:           string | null
  endpoint:            string | null
  active:              boolean
  registration_status: RegistrationStatus
  allowed_senders:     string[]
  allowed_task_types:  string[]
  created_at:          string
  approved_at:         string | null
}

// ─── Registration ─────────────────────────────────────────────────────────────
export interface ApiRegistration {
  agent_name:       string
  role:             string
  status:           RegistrationStatus
  requested_at:     string
  reviewed_at:      string | null
  reviewed_by:      string | null
  rejection_reason: string | null
  endpoint:         string | null
  file_path:        string | null
  metadata:         Record<string, unknown>
}

// ─── Message envelope ─────────────────────────────────────────────────────────
export interface ApiEnvelope {
  id:        string
  timestamp: string
  sender:    string
  recipient: string
  task_type: string
  context:   Record<string, unknown>
  payload:   Record<string, unknown>
  status:    MessageStatus
  error:     string
}

// ─── Queue item (QueuedMessage from service) ──────────────────────────────────
export interface ApiQueueItem {
  envelope:               ApiEnvelope
  computed_priority:      number
  attempt_count:          number
  lease_until:            string | null
  delivery_state:         DeliveryState
  blocked_reason:         string
  provenance_source:      string | null
  provenance_agent:       string | null
  provenance_trust_level: number | null
  ttl_seconds:            number | null
  dedupe_key:             string | null
}

// ─── Audit event ──────────────────────────────────────────────────────────────
export interface ApiAuditEvent {
  id:         string
  event_type: string
  subject_id: string
  actor:      string
  details:    Record<string, unknown>
  created_at: string
}

// ─── Health ───────────────────────────────────────────────────────────────────
export interface ApiHealth {
  status:  string
  backend: 'sqlite' | 'mongo'
}

// ─── Manager intervention ─────────────────────────────────────────────────────
export interface ApiInterventionBody {
  recipient:         string
  instruction:       string
  priority?:         'low' | 'normal' | 'high' | 'critical'
  context?:          Record<string, unknown>
  payload?:          Record<string, unknown>
  requires_response?: boolean
  ttl_seconds?:      number
  dedupe_key?:       string
}
