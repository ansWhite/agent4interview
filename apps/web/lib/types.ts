export type TaskStatus = "pending" | "running" | "completed" | "partial" | "failed";

export interface Evidence {
  id: string;
  document_id: string;
  title: string;
  content: string;
  score: number;
  source: string;
}

export interface Citation {
  marker: string;
  evidence_id: string;
  document_id: string;
  quote: string;
}

export interface AgentState {
  trace_id: string;
  question: string;
  status: TaskStatus;
  answer: string | null;
  evidence: Evidence[];
  citations: Citation[];
  warnings: string[];
  budget: {
    max_steps: number;
    steps_used: number;
    max_tool_calls: number;
    tool_calls_used: number;
    retries_used: number;
  };
}

export interface TaskResponse {
  id: string;
  state: AgentState;
}

export interface AgentEvent {
  sequence: number;
  trace_id: string;
  event_type: string;
  node: string;
  message: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface EvalRun {
  id: string;
  name: string;
  status: string;
  summary: Record<string, number>;
}
