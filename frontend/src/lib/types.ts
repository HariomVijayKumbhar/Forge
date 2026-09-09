export type AgentStatus =
  | "idle"
  | "running"
  | "success"
  | "error"
  | "stopped"
  | "stuck"
  | "provider_unavailable";

export type StepActionType =
  | "plan"
  | "tool_call"
  | "observation"
  | "reflection"
  | "finish"
  | "error"
  | "stopped"
  | "stuck";

export interface AgentStep {
  id: number;
  run_id: string;
  step_index: number;
  action_type: StepActionType;
  tool_name?: string | null;
  tool_input?: string | null;
  tool_output?: string | null;
  status: "ok" | "error" | "timeout" | "blocked" | "invalid_input";
  provider_used?: string | null;
  timestamp: string;
}

export interface AgentRun {
  id: string;
  repo_url: string;
  task: string;
  status: AgentStatus;
  provider_used?: string | null;
  files_changed?: string[];
  diff?: string | null;
  tests_passed?: boolean | null;
  confidence?: number | null;
  summary?: string | null;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface AuditLogEntry {
  id: number;
  event_type: string;
  actor_ip?: string | null;
  details?: string | null;
  status: string;
  timestamp: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  accessToken: string | null;
  csrfToken: string | null;
}

// ==================== Analytics Types ====================

export interface AnalyticsSummary {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  average_confidence: number;
  total_files_changed: number;
  total_duration_hours: number;
  provider_distribution: Record<string, number>;
  daily_activity: Record<string, number>;
}

export interface RunMetrics {
  id: string;
  repo_url: string;
  task: string;
  status: string;
  provider_used?: string | null;
  confidence?: number | null;
  files_changed_count: number;
  step_count: number;
  duration_seconds?: number | null;
  created_at: string;
  completed_at?: string | null;
}

export interface ProviderMetrics {
  provider: string;
  total_runs: number;
  success_rate: number;
  average_confidence: number;
  average_duration_seconds: number;
  average_files_changed: number;
}

export interface PerformanceMetrics {
  average_step_time_seconds: number;
  average_iterations_per_run: number;
  most_used_tools: Record<string, number>;
  error_breakdown: Record<string, number>;
  peak_usage_hours: Record<string, number>;
}

export interface CostEstimate {
  provider: string;
  estimated_cost_usd: number;
  estimated_tokens: number;
  runs_count: number;
}
