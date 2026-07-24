import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("./investment_review.js", import.meta.url),
  "utf8",
);

describe("investment review automation health", () => {
  it("keeps partial completion distinct from success and failure", () => {
    expect(source).toContain("automation ${text(automation.state");
    expect(source).toContain("auto_completed ${projectedTime(automation.last_completed)");
    expect(source).toContain("auto_success ${projectedTime(automation.last_success)");
    expect(source).toContain("auto_failure ${projectedTime(automation.last_failure)");
  });
});
