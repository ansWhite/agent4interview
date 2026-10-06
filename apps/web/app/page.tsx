"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { addDocument, createTask, getEvaluation, getTask, runEvaluation, subscribeToTask } from "../lib/api";
import type { AgentEvent, EvalRun, TaskResponse } from "../lib/types";
import { formatMetric, statusLabel } from "../lib/format";

const NODE_LABELS: Record<string, string> = {
  intake: "问题接收",
  planner: "任务规划",
  retriever: "混合检索",
  evidence_grader: "证据评分",
  synthesizer: "答案合成",
  verifier: "引用校验",
  workflow: "工作流",
};

export default function Home() {
  const [question, setQuestion] = useState("为什么可靠的 Agent 需要显式状态、执行预算和离线评测？");
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [documentNotice, setDocumentNotice] = useState("");
  const [evaluation, setEvaluation] = useState<EvalRun | null>(null);
  const unsubscribe = useRef<(() => void) | null>(null);

  useEffect(() => () => unsubscribe.current?.(), []);

  async function refreshTask(id: string) {
    const nextTask = await getTask(id);
    setTask(nextTask);
    setBusy(false);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    unsubscribe.current?.();
    setBusy(true);
    setError("");
    setEvents([]);
    try {
      const created = await createTask(question.trim());
      setTask(created);
      unsubscribe.current = subscribeToTask(
        created.id,
        (nextEvent) => setEvents((current) => [...current, nextEvent]),
        () => void refreshTask(created.id),
        () => {
          setError("事件流中断，请检查 API 服务后重试。");
          setBusy(false);
        },
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建任务失败");
      setBusy(false);
    }
  }

  async function handleDocument(event: FormEvent) {
    event.preventDefault();
    setDocumentNotice("");
    try {
      const result = await addDocument(documentTitle, documentContent);
      setDocumentNotice(`已索引 ${result.chunks} 个片段`);
      setDocumentTitle("");
      setDocumentContent("");
    } catch (reason) {
      setDocumentNotice(reason instanceof Error ? reason.message : "索引失败");
    }
  }

  async function handleEvaluation() {
    setError("");
    try {
      const created = await runEvaluation();
      setEvaluation(created);
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 300));
        const current = await getEvaluation(created.id);
        setEvaluation(current);
        if (current.status !== "running") break;
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "评测失败");
    }
  }

  const state = task?.state;
  const status = state?.status ?? "idle";

  return (
    <main>
      <header className="topbar">
        <div className="brand"><span className="brandMark">IA</span><span>InsightAgent</span></div>
        <div className="environment"><span className="pulse" /> LOCAL CONTROL ROOM</div>
      </header>

      <section className="hero">
        <p className="eyebrow">EVIDENCE-FIRST AGENT SYSTEM</p>
        <h1>让每一次推理<br /><span>可控制、可追踪、可验证。</span></h1>
        <p className="subtitle">一个带检索、预算、引用校验和离线评测的 Deep Research Agent。</p>
      </section>

      <section className="workspace">
        <div className="primaryColumn">
          <form className="queryPanel" onSubmit={handleSubmit}>
            <div className="panelHeader"><span>RESEARCH QUERY</span><span className={`status ${status}`}>{statusLabel(status)}</span></div>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={4000} />
            <div className="queryActions">
              <span>{question.length} / 4000</span>
              <button type="submit" disabled={busy}>{busy ? "执行中…" : "启动研究 →"}</button>
            </div>
          </form>

          {error && <div className="errorBanner">{error}</div>}

          <section className="answerPanel">
            <div className="panelHeader"><span>SYNTHESIZED ANSWER</span><span>{state?.citations.length ?? 0} CITATIONS</span></div>
            {state?.answer ? (
              <pre className="answer">{state.answer}</pre>
            ) : (
              <div className="emptyState">提交问题后，答案与引用会显示在这里。</div>
            )}
            {!!state?.warnings.length && <div className="warnings">{state.warnings.join(" · ")}</div>}
          </section>

          {!!state?.evidence.length && (
            <section className="evidenceGrid">
              {state.evidence.map((item, index) => (
                <article className="evidenceCard" key={item.id}>
                  <div><span className="citation">[{index + 1}]</span><span className="score">{item.score.toFixed(3)}</span></div>
                  <h3>{item.title}</h3>
                  <p>{item.content}</p>
                  <small>{item.source}</small>
                </article>
              ))}
            </section>
          )}
        </div>

        <aside className="sideColumn">
          <section className="tracePanel">
            <div className="panelHeader"><span>LIVE TRACE</span><span>{events.length} EVENTS</span></div>
            <div className="traceList">
              {events.length ? events.map((item) => (
                <div className="traceItem" key={`${item.sequence}-${item.node}`}>
                  <span className="traceIndex">{String(item.sequence).padStart(2, "0")}</span>
                  <div><strong>{NODE_LABELS[item.node] ?? item.node}</strong><p>{item.message}</p></div>
                </div>
              )) : <div className="emptyState compact">等待执行轨迹。</div>}
            </div>
            <div className="budget">
              <span>STEP BUDGET</span>
              <strong>{state?.budget.steps_used ?? 0} / {state?.budget.max_steps ?? 8}</strong>
            </div>
          </section>

          <section className="utilityPanel">
            <div className="panelHeader"><span>LOCAL KNOWLEDGE</span></div>
            <form onSubmit={handleDocument}>
              <input placeholder="文档标题" value={documentTitle} onChange={(event) => setDocumentTitle(event.target.value)} required />
              <textarea placeholder="粘贴本地文本内容" value={documentContent} onChange={(event) => setDocumentContent(event.target.value)} required />
              <button type="submit" className="secondary">索引文档</button>
              {documentNotice && <small>{documentNotice}</small>}
            </form>
          </section>

          <section className="utilityPanel">
            <div className="panelHeader"><span>OFFLINE EVALUATION</span></div>
            <p className="utilityCopy">运行检索、引用和任务成功率的内置基准。</p>
            <button type="button" className="secondary" onClick={handleEvaluation}>运行评测</button>
            {evaluation && (
              <div className="metrics">
                <span className="evalStatus">{evaluation.status}</span>
                {Object.entries(evaluation.summary).map(([name, value]) => (
                  <div key={name}><span>{name}</span><strong>{formatMetric(value)}</strong></div>
                ))}
              </div>
            )}
          </section>
        </aside>
      </section>
    </main>
  );
}
