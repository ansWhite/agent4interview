import { describe, expect, it } from "vitest";
import { formatMetric, statusLabel } from "./format";

describe("formatMetric", () => {
  it("formats finite metrics", () => {
    expect(formatMetric(0.91666)).toBe("0.917");
  });

  it("hides invalid metrics", () => {
    expect(formatMetric(Number.NaN)).toBe("—");
  });
});

describe("statusLabel", () => {
  it("uses localized known states", () => {
    expect(statusLabel("completed")).toBe("完成");
    expect(statusLabel("custom")).toBe("custom");
  });
});
