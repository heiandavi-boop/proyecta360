import type { PublicUser } from "@/api/client";

export type Project = {
  id: number;
  name: string;
  description: string;
  project_manager: string;
  sponsor: string;
  start_date: string;
  end_date: string;
  contractual_end_date?: string;
  methodology: string;
  status: string;
  budget: number;
  currency: string;
  parameters: Record<string, unknown>;
};

export type ProjectMetrics = {
  progress: number;
  expected_progress: number;
  progress_variance_pp: number;
  health: string;
  phs: number;
  schedule_score: number;
  budget_score: number;
  risk_score: number;
  budget: number;
  spent: number;
  planned_spent: number;
  total_planned_budget: number;
  budget_source: string;
  budget_executed_percent: number;
  budget_expected_percent: number;
  budget_variance_pp: number;
  remaining_budget: number;
  open_risks: number;
  high_risks: number;
  delayed_tasks: number;
  critical_path_tasks: number;
  at_risk_milestones: number;
  next_milestone?: { title?: string; end_date?: string } | null;
};

export type Task = {
  id: number;
  project_id: number;
  parent_id?: number | null;
  predecessor_id?: number | null;
  title: string;
  task_type: string;
  start_date: string;
  end_date: string;
  duration_days?: number;
  progress: number;
  owner: string;
  status: string;
  outline_level?: number;
  order_index?: number;
  is_expanded?: number;
  is_critical_path?: boolean;
};

export type Sprint = {
  id: number;
  project_id: number;
  name: string;
  goal: string;
  start_date: string;
  end_date: string;
  status: string;
  velocity: number;
  cycle_type?: string;
  capacity?: number;
  close_summary?: string;
};

export type Risk = {
  id: number;
  project_id: number;
  title: string;
  probability: number;
  impact: number;
  level: string;
  response?: string;
  mitigation_plan?: string;
  contingency_plan?: string;
  status: string;
  owner: string;
  materialized_date?: string;
  actual_impact?: string;
  observations?: string;
};

export type Resource = {
  id: number;
  project_id: number;
  name: string;
  role: string;
  email: string;
  capacity: number;
};

export type BudgetEntry = {
  id: number;
  project_id: number;
  month: string;
  category: string;
  planned_amount: number;
  executed_amount: number;
  notes?: string;
};

export type Story = {
  id: number;
  project_id: number;
  sprint_id?: number;
  master_task_id?: number | null;
  component_id?: number | null;
  deliverable_id?: number | null;
  title: string;
  description?: string;
  work_type?: string;
  status: string;
  points: number;
  assignee: string;
  priority: string;
  blocked_reason?: string;
  started_at?: string;
  completed_at?: string;
  labels?: string[];
  labels_json?: string;
  board_order?: number;
  created_at?: string;
};

export type Component = {
  id: number;
  project_id: number;
  name: string;
  methodology: string;
  owner: string;
  objective: string;
  progress: number;
};

export type Deliverable = {
  id: number;
  project_id: number;
  component_id?: number;
  name: string;
  deliverable_type: string;
  status: string;
  owner: string;
  due_date?: string;
  evidence_url: string;
  description: string;
};

export type Evidence = {
  id: number;
  project_id: number;
  entity_type: string;
  entity_id?: number | null;
  original_filename: string;
  content_type?: string;
  size_bytes: number;
  uploaded_by: string;
  description: string;
  created_at?: string;
  download_url: string;
};

export type ConversationThread = {
  id: number;
  project_id: number;
  title: string;
  context_type: string;
  category: string;
  status: string;
  created_by: string;
};

export type ConversationMessage = {
  id: number;
  thread_id: number;
  project_id: number;
  author: string;
  message: string;
  mentions?: string;
  evidence_url?: string;
  message_type: string;
  created_at?: string;
};

export type ChangeLogEntry = {
  id: number;
  project_id: number;
  entity_type: string;
  entity_name: string;
  action: string;
  notes: string;
  actor: string;
  created_at?: string;
};

export type BootstrapPayload = {
  projects: Project[];
  portfolio: Array<Record<string, unknown>>;
  current_project: Project;
  tasks: Task[];
  risks: Risk[];
  resources: Resource[];
  budget_entries: BudgetEntry[];
  sprints: Sprint[];
  stories: Story[];
  agile_cycles?: Sprint[];
  work_items?: Story[];
  components: Component[];
  deliverables: Deliverable[];
  evidences: Evidence[];
  conversation_threads: ConversationThread[];
  conversation_messages: ConversationMessage[];
  history: ChangeLogEntry[];
  intelligence: Record<string, unknown>;
  metrics: ProjectMetrics;
  current_user: PublicUser | null;
  defaults: Record<string, unknown>;
};

export function asBootstrapPayload(value: unknown): BootstrapPayload {
  return value as BootstrapPayload;
}
