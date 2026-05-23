export type AgentId = 'ceo' | 'product' | 'engineering' | 'hr' | 'sales' | 'marketing' | 'finance'

export type AgentStatus = 'active' | 'idle' | 'busy' | 'error' | 'offline'

export type TaskStatus = 'pending' | 'in_progress' | 'done' | 'blocked' | 'failed'

export type MessageStatus = 'pending' | 'in_progress' | 'done' | 'error'

export type DeliveryState = 'pending' | 'leased' | 'blocked' | 'expired' | 'dead_lettered' | 'done'

export type Urgency = 'low' | 'normal' | 'high' | 'critical'

export type WorkflowStatus = 'active' | 'paused' | 'completed' | 'failed' | 'draft'

export type SimulationStatus = 'running' | 'paused' | 'completed' | 'idle'

export interface Agent {
  id: AgentId
  name: string
  role: string
  status: AgentStatus
  hierarchyLevel: number    // 1 = CEO, higher = lower
  trustLevel: number        // 0–100
  specialization: string
  autonomousActions: string[]
  decisionCriteria: string[]
  tools: string[]
  escalationRules: string[]
  communicationStyle: string
  activeTaskCount: number
  completedTasks: number
  successRate: number
  totalMessages: number
  resourceUsage: number    // percent
  color: string
  gradient: string
}

export interface Task {
  id: string
  title: string
  assignedTo: AgentId
  delegatedBy?: AgentId
  status: TaskStatus
  priority: 'low' | 'medium' | 'high' | 'critical'
  dueDate: string
  createdAt: string
  description: string
  tags: string[]
  progress: number   // 0–100
  blockedReason?: string
}

export interface Message {
  id: string
  timestamp: string
  sender: AgentId
  recipient: AgentId
  task_type: string
  context: Record<string, unknown>
  payload: Record<string, unknown>
  status: MessageStatus
  delivery_state: DeliveryState
  urgency: Urgency
  computed_priority: number
  attempt_count: number
  error?: string
}

export interface WorkflowStage {
  id: string
  name: string
  assignedAgent: AgentId
  status: TaskStatus
  requiresApproval: boolean
  dependencies: string[]
  description: string
  duration?: number  // hours
}

export interface Workflow {
  id: string
  name: string
  status: WorkflowStatus
  goal: string
  initiatedBy: AgentId
  stages: WorkflowStage[]
  currentStageIndex: number
  createdAt: string
  updatedAt: string
  tags: string[]
  progress: number
}

export interface Resource {
  id: string
  name: string
  category: 'budget' | 'capacity' | 'tools' | 'compute' | 'time'
  ownedBy: AgentId
  total: number
  used: number
  unit: string
  forecastBurn?: number
  warning?: boolean
  critical?: boolean
}

export interface BudgetAllocation {
  department: string
  agentId: AgentId
  allocated: number
  spent: number
  remaining: number
  forecastedOverrun?: number
}

export interface KPIMetric {
  label: string
  value: string | number
  delta?: number
  trend: 'up' | 'down' | 'flat'
  unit?: string
  description?: string
}

export interface ActivityEvent {
  id: string
  timestamp: string
  agentId: AgentId
  type: 'message' | 'task' | 'approval' | 'escalation' | 'simulation' | 'workflow'
  title: string
  description: string
  severity?: 'info' | 'warning' | 'error' | 'success'
}

export interface Alert {
  id: string
  timestamp: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  title: string
  description: string
  agentId?: AgentId
  resolved: boolean
  actionRequired?: string
}

export interface Simulation {
  id: string
  name: string
  goal: string
  status: SimulationStatus
  mode: 'single' | 'multi'
  participatingAgents: AgentId[]
  startedAt?: string
  completedAt?: string
  budget: number
  timeHorizon: string
  targetCustomer?: string
  progress: number
  outcomes?: Record<string, unknown>
  events: SimulationEvent[]
}

export interface SimulationEvent {
  id: string
  timestamp: string
  agentId: AgentId
  action: string
  decision: string
  impact?: string
}

export interface KanoseiNotification {
  id: string
  section: string
  sectionPath: string
  severity: 'error' | 'warning' | 'pending' | 'info'
  title: string
  desc: string
  when: string
  unread: boolean
  agentId: AgentId
}

export interface AgentLoad {
  name: string
  agentId: AgentId
  value: number
  color: string
}

export interface PipelineStage {
  stage: string
  count: number
  value: number
  color: string
}

export interface MessageFlow {
  from: AgentId
  to: AgentId
  count: number
}

export interface KanoseiWorkflow {
  id: string
  name: string
  progress: number
  status: 'active' | 'paused' | 'completed'
  owner: AgentId
  stages: { name: string; agent: AgentId; status: 'done' | 'active' | 'pending' }[]
}

export interface ApprovalRequest {
  id: string
  requestedBy: AgentId
  approvedBy?: AgentId
  type: string
  title: string
  description: string
  amount?: number
  status: 'pending' | 'approved' | 'rejected'
  createdAt: string
  resolvedAt?: string
  reason?: string
}
