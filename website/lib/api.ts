/**
 * enterprise_router API client.
 * All calls go through FastAPI — never directly to MongoDB.
 * See UI-Team.md §5 and §8 for endpoint contracts.
 */
import type {
  ApiAgent, ApiRegistration, ApiQueueItem, ApiAuditEvent,
  ApiHealth, ApiInterventionBody, ApiEnvelope,
} from './api-types'

const BASE         = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? ''
const MANAGER_KEY  = process.env.NEXT_PUBLIC_MANAGER_API_KEY ?? ''

// ─── Low-level helpers ────────────────────────────────────────────────────────

async function request<T>(
  method: string,
  path: string,
  headers: Record<string, string> = {},
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${method} ${path} → ${res.status}: ${text}`)
  }
  const text = await res.text()
  return text ? JSON.parse(text) : ({} as T)
}

const get  = <T>(path: string, h?: Record<string,string>) => request<T>('GET',  path, h)
const post = <T>(path: string, body: unknown, h?: Record<string,string>) => request<T>('POST', path, h, body)

// Auth header factories
function adminH(): Record<string,string> {
  return { 'X-Admin-Secret': ADMIN_SECRET }
}
function agentH(agentName: string, apiKey: string): Record<string,string> {
  return { Authorization: `Bearer ${apiKey}`, 'X-Agent-Id': agentName }
}
function managerH(): Record<string,string> {
  return agentH('MANAGER', MANAGER_KEY)
}

// ─── Public API ───────────────────────────────────────────────────────────────

export const api = {

  // GET /health
  health: () => get<ApiHealth>('/health'),

  agents: {
    // GET /agents  (agent auth — uses MANAGER key when called from dashboard)
    list: (agentName = 'MANAGER', apiKey = MANAGER_KEY, status?: string) =>
      get<ApiAgent[]>(status ? `/agents?status=${status}` : '/agents', agentH(agentName, apiKey)),

    // POST /agents  (admin)
    register: (body: {
      agent_name: string; role: string; hierarchy_level: number; trust_level: number
      file_path?: string | null; endpoint?: string | null; active?: boolean
      allowed_senders?: string[]; allowed_task_types?: string[]; issue_api_key?: boolean
    }) => post<{ agent_name: string; status: string; api_key?: string }>(
      '/agents', body, adminH()
    ),

    // POST /agents/{name}/issue-api-key  (admin)
    issueKey: (agentName: string) =>
      post<{ agent_name: string; api_key: string }>(
        `/agents/${agentName}/issue-api-key`, {}, adminH()
      ),
  },

  registrations: {
    // GET /registrations  (admin)
    list: (status?: string) =>
      get<ApiRegistration[]>(
        status ? `/registrations?status=${status}` : '/registrations',
        adminH()
      ),

    // POST /registrations/request  (no auth)
    request: (body: {
      agent_name: string; role: string; secret_token: string
      file_path?: string; endpoint?: string; metadata?: Record<string,unknown>
    }) => post<{ agent_name: string; status: string }>('/registrations/request', body),

    // POST /registrations/{name}/approve  (admin)
    approve: (agentName: string, approver: string, issueKey = true) =>
      post<{ agent_name: string; status: string; api_key?: string }>(
        `/registrations/${agentName}/approve`,
        { approver, issue_api_key: issueKey, key_label: 'dashboard' },
        adminH()
      ),

    // POST /registrations/{name}/reject  (admin)
    reject: (agentName: string, approver: string, reason: string) =>
      post<{ agent_name: string; status: string }>(
        `/registrations/${agentName}/reject`,
        { approver, reason },
        adminH()
      ),
  },

  messages: {
    // POST /messages  (agent auth)
    submit: (
      envelope: Omit<ApiEnvelope, 'error'> & { error?: string },
      routingHints: Record<string,unknown>,
      agentName: string,
      apiKey: string,
    ) => post<{ message_id: string }>(
      '/messages',
      { message: { ...envelope, error: envelope.error ?? '' }, routing_hints: routingHints },
      agentH(agentName, apiKey)
    ),

    // GET /messages/peek  (agent auth — agents can only peek own queue)
    peek: (recipient: string, apiKey: string, limit = 20) =>
      get<ApiQueueItem[]>(
        `/messages/peek?recipient=${recipient}&limit=${limit}`,
        agentH(recipient, apiKey)
      ),

    // POST /messages/fetch-next  (agent auth)
    fetchNext: (recipient: string, apiKey: string) =>
      post<ApiQueueItem | Record<string, never>>(
        '/messages/fetch-next', { recipient }, agentH(recipient, apiKey)
      ),

    // POST /messages/{id}/ack  (agent auth)
    ack: (messageId: string, recipient: string, apiKey: string) =>
      post<{ message_id: string; status: string }>(
        `/messages/${messageId}/ack`, { recipient }, agentH(recipient, apiKey)
      ),

    // POST /messages/{id}/nack  (agent auth)
    nack: (messageId: string, recipient: string, reason: string, apiKey: string) =>
      post<{ message_id: string; status: string }>(
        `/messages/${messageId}/nack`, { recipient, reason }, agentH(recipient, apiKey)
      ),
  },

  queue: {
    // GET /queue/{recipient}  (agent auth)
    list: (recipient: string, apiKey: string) =>
      get<ApiQueueItem[]>(`/queue/${recipient}`, agentH(recipient, apiKey)),
  },

  manager: {
    // POST /manager/interventions  (MANAGER agent auth)
    // This is the primary entry point for dashboard-originated commands
    intervene: (body: ApiInterventionBody) =>
      post<{ message_id: string }>(
        '/manager/interventions', body, managerH()
      ),
  },

  audit: {
    // GET /audit  (admin)
    list: (limit = 20, subjectId?: string) =>
      get<ApiAuditEvent[]>(
        subjectId ? `/audit?limit=${limit}&subject_id=${subjectId}` : `/audit?limit=${limit}`,
        adminH()
      ),
  },
}
