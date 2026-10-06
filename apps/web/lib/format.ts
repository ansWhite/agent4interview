export function formatMetric(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(3);
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "等待",
    running: "执行中",
    completed: "完成",
    partial: "部分完成",
    failed: "失败",
  };
  return labels[status] ?? status;
}
