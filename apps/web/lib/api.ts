import type { AgentEvent, EvalRun, TaskResponse } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.text();
    throw new Error(payload || `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function createTask(question: string): Promise<TaskResponse> {
  return request("/tasks", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function getTask(id: string): Promise<TaskResponse> {
  return request(`/tasks/${id}`, { cache: "no-store" });
}

export function addDocument(title: string, content: string): Promise<{ document_ids: string[]; chunks: number }> {
  return request("/documents", {
    method: "POST",
    body: JSON.stringify({ title, content, source: "local://workbench" }),
  });
}

export function runEvaluation(): Promise<EvalRun> {
  return request("/evaluations/runs", {
    method: "POST",
    body: JSON.stringify({
      name: "内置基准",
      cases: [
        {
          id: "eval-retrieval",
          question: "为什么 Agent 检索要组合 BM25、向量召回和 RRF？",
          relevant_document_ids: ["seed-hybrid-retrieval"],
          required_document_ids: ["seed-hybrid-retrieval"],
          tags: ["retrieval"],
        },
        {
          id: "eval-safety",
          question: "Agent 工具调用如何设置安全边界？",
          relevant_document_ids: ["seed-agent-security"],
          required_document_ids: ["seed-agent-security"],
          tags: ["safety"],
        },
      ],
    }),
  });
}

export function getEvaluation(id: string): Promise<EvalRun> {
  return request(`/evaluations/runs/${id}`, { cache: "no-store" });
}

export function subscribeToTask(
  id: string,
  onEvent: (event: AgentEvent) => void,
  onClosed: () => void,
  onError: () => void,
): () => void {
  const source = new EventSource(`${API_BASE}/tasks/${id}/events`);
  const eventNames = [
    "task_started",
    "node_started",
    "node_completed",
    "tool_started",
    "tool_completed",
    "task_failed",
    "task_finished",
  ];
  const listeners = eventNames.map((name) => {
    const listener = (message: MessageEvent<string>) => onEvent(JSON.parse(message.data) as AgentEvent);
    source.addEventListener(name, listener as EventListener);
    return [name, listener] as const;
  });
  source.addEventListener("stream_closed", () => {
    source.close();
    onClosed();
  });
  source.onerror = () => {
    source.close();
    onError();
  };
  return () => {
    listeners.forEach(([name, listener]) => source.removeEventListener(name, listener as EventListener));
    source.close();
  };
}
