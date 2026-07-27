import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  OPERATION_REVIEW_AXIS_NAMES,
  isInvestmentReviewAcceptanceHealth,
  operationReviewHeadline,
  operationReviewView,
} from "./investment_review.js";

const source = readFileSync(
  new URL("./investment_review.js", import.meta.url),
  "utf8",
);
const mainSource = readFileSync(
  new URL("./main.js", import.meta.url),
  "utf8",
);

describe("investment review read-only acceptance", () => {
  it("requires the exact bounded health identity", () => {
    expect(isInvestmentReviewAcceptanceHealth({
      review_acceptance_read_only: true,
      acceptance_task_id: "investment_review_local_acceptance_readiness_v1",
      review_candidate_sha256: "a".repeat(64),
    })).toBe(true);
    expect(isInvestmentReviewAcceptanceHealth({
      review_acceptance_read_only: true,
      acceptance_task_id: "another-task",
      review_candidate_sha256: "a".repeat(64),
    })).toBe(false);
    expect(isInvestmentReviewAcceptanceHealth({
      review_acceptance_read_only: false,
      acceptance_task_id: "investment_review_local_acceptance_readiness_v1",
      review_candidate_sha256: "a".repeat(64),
    })).toBe(false);
  });

  it("boots review-only before any portfolio or realtime work", () => {
    expect(mainSource).toContain("if (isInvestmentReviewAcceptanceHealth(health))");
    expect(mainSource).toContain("enterInvestmentReviewAcceptance(health)");
    expect(mainSource.indexOf("if (isInvestmentReviewAcceptanceHealth(health))"))
      .toBeLessThan(mainSource.lastIndexOf("loadPortfolio();"));
    expect(mainSource).toContain('readOnly: true');
    expect(source).toContain("只读人工验收");
    expect(source).toContain("系统不会替您编造当时理由");
    expect(source).toContain("不提供买卖或仓位建议");
  });
});

describe("investment review automation health", () => {
  it("keeps partial completion distinct from success and failure", () => {
    expect(source).toContain("automation ${text(automation.state");
    expect(source).toContain("auto_completed ${projectedTime(automation.last_completed)");
    expect(source).toContain("auto_success ${projectedTime(automation.last_success)");
    expect(source).toContain("auto_failure ${projectedTime(automation.last_failure)");
  });
});

describe("investment review six-axis checkpoint", () => {
  const checkpoint = {
    available: true,
    schema_version: "investment_review.operation_checkpoint.v2",
    checkpoint_id: "review_checkpoint_0123456789abcdef0123456789abcdef",
    content_id: `sha256:${"1".repeat(64)}`,
    checkpoint_type: "active_checkpoint",
    perspective: "user",
    as_of: "2026-07-17T06:00:00Z",
    knowledge_cutoff: "2026-07-26T06:00:00Z",
    operation_anchor: {
      event_id: "evt_0123456789abcdef0123456789abcdef",
      at: "2026-07-17T05:55:28Z",
    },
    actual_user_observation_proven: false,
    axes: {
      operation: { status: "ready", summary: "操作事实已核验。", source_refs: ["event:1"] },
      decision: { status: "not_recorded", summary: null, source_refs: [] },
      snapshot_cash_valuation: {
        status: "partial",
        summary: null,
        source_refs: ["event:1"],
        fields: {
          position_quantity: { status: "available", value: "8100", unit: "shares" },
          cost_basis: { status: "partial", value: "29931.6", unit: "CNY" },
          cash: { status: "partial", value: "961.4", unit: "CNY" },
          price: { status: "missing", value: null, unit: "CNY/share" },
          nav: { status: "missing", value: null, unit: "CNY" },
          weight: { status: "missing", value: null, unit: "ratio" },
          industry: { status: "missing", value: null, unit: null },
        },
      },
      market: {
        status: "partial",
        summary: null,
        source_refs: ["market_source:1"],
        perspective_eligibility: {
          actual_user_observation_proven: false,
        },
      },
      lifecycle: { status: "open", summary: null, source_refs: ["episode:1"] },
      outcome: { status: "interim", summary: null, source_refs: ["episode:1"] },
    },
    gaps: [{
      code: "SNAPSHOT_PRICE_MISSING",
      severity: "warning",
      owner: "data",
      next_step: "补充价格证据。",
      source_refs: [],
    }],
    source_refs: ["event:1", "market_source:1"],
  };

  it("keeps all axes independent and preserves missing values", () => {
    const view = operationReviewView(checkpoint);
    expect(view.available).toBe(true);
    expect(view.axes.map((axis) => axis.name)).toEqual(
      OPERATION_REVIEW_AXIS_NAMES,
    );
    expect(Object.fromEntries(
      view.axes.map((axis) => [axis.name, axis.status]),
    )).toEqual({
      operation: "ready",
      decision: "not_recorded",
      snapshot_cash_valuation: "partial",
      market: "partial",
      lifecycle: "open",
      outcome: "interim",
    });
    const snapshot = view.axes.find(
      (axis) => axis.name === "snapshot_cash_valuation",
    );
    expect(snapshot.fields.position_quantity.value).toBe("8100");
    expect(snapshot.fields.price.value).toBeNull();
    expect(snapshot.fields.nav.value).toBeNull();
    expect(snapshot.fields.weight.value).toBeNull();
    expect(snapshot.fields.industry.value).toBeNull();
    expect(view.actual_user_observation_proven).toBe(false);
  });

  it("states the open interim conclusion without inventing a motive", () => {
    expect(operationReviewHeadline(checkpoint)).toBe(
      "操作事实已可复盘；持仓回合仍在进行，当前结果仅为阶段状态。",
    );
    expect(operationReviewHeadline({
      available: false,
      reason: "legacy",
    })).toContain("未生成六轴操作检查点");
    expect(JSON.stringify(operationReviewView(checkpoint))).not.toMatch(
      /motive|psychology|diagnosis|recommendation|actually_read/i,
    );
  });

  it("uses text-only DOM construction and keeps raw codes in evidence details", () => {
    expect(source).toContain("node.textContent = String(text)");
    expect(source).not.toMatch(
      /innerHTML|outerHTML|insertAdjacentHTML|eval\(|new Function/,
    );
    expect(source).not.toContain("review.gap_codes.join");
    expect(source).toContain("checkpoint.gaps");
    expect(source).toContain("checkpoint.source_refs");
  });
});
