import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  OPERATION_REVIEW_AXIS_NAMES,
  isInvestmentReviewAcceptanceHealth,
  operationReviewHeadline,
  operationReviewView,
  periodicOperationTime,
  periodicRecommendationDisplay,
  periodicReportHeadline,
  periodicReportView,
  periodicSubjectLabel,
  projectedTime,
} from "./investment_review.js";

const source = readFileSync(
  new URL("./investment_review.js", import.meta.url),
  "utf8",
);
const mainSource = readFileSync(
  new URL("./main.js", import.meta.url),
  "utf8",
);

describe("periodic investment reports", () => {
  const report = {
    schema_version: "investment_review.periodic_report.v2",
    report_id: `periodic_${"a".repeat(32)}`,
    status: "ready",
    subject: { type: "instrument", id: "000813.SZ", name: "德展健康" },
    period: {
      type: "daily",
      start: "2026-07-15",
      end: "2026-07-15",
      report_cutoff_at: "2026-07-15T15:00:00+08:00",
    },
    headline: "无 Decision 日报样本。",
    analysis_brief: {
      central_judgment: {
        text: "短期趋势转强，但执行和基本面约束仍在。",
      },
    },
    reader_report: {
      schema_version: "investment_review.reader_report.v1",
      central_judgment: "短期趋势转强，但执行和基本面约束仍在。",
      narrative_sections: [{
        key: "judgment_basis",
        title: "趋势、基本面与仓位约束",
        paragraphs: ["短期上涨不足以证明基本面反转。"],
        source_refs: ["fixture:reader"],
      }],
      action_plan: {
        action: "reduce",
        confidence: "medium",
        target_position_note: "把单标的权重降至 8%–12%。",
        time_horizon: "下一交易周",
      },
      major_risks: ["减仓后继续上涨会产生机会成本"],
      invalidation_conditions: ["新基本面证据改变判断"],
      missing_inputs: ["MISSING_DECISION"],
      appendix: {
        collapsed_by_default: true,
      },
    },
    sections: {
      performance_and_positions: {
        performance: { asset_change_pct: "3.22" },
      },
      decision_context: {
        report_depth: "daily_delta_only",
        fundamental_and_valuation: {
          status: "available",
          summary: "最新财务仍为亏损。",
        },
        market_and_sector: {
          status: "available",
          summary: "板块上涨不直接证明交易动机。",
        },
        technical_and_trend: {
          status: "available",
          summary: "短线偏强但不保证收益。",
        },
        position_and_execution: {
          status: "available",
          summary: "日内新增仓位已撤回。",
        },
      },
      operations_and_motives: {
        operation_count: 3,
        operations: [{
          ts_code: "000813.SZ",
          name: "德展健康",
          fee_cny: "5.06",
          fee_status: "rule_backfilled",
          fee_rule: "historical_fee_rule_v1",
          motive: {
            label: "system_inference",
            input_cutoff_at: "2026-07-15T01:38:45Z",
            uses_later_information: false,
          },
        }],
        episode_summaries: [{
          ts_code: "000813.SZ",
          name: "德展健康",
          opening_quantity: "17200",
          peak_quantity: "23000",
          closing_quantity: "17200",
          peak_increase_pct: "33.72",
          gross_round_trip_pnl_cny: "3",
          fee_total_cny: "25.43",
          net_round_trip_pnl_cny: "-22.43",
          fee_statuses: ["rule_backfilled"],
          assessment: "毛价差没有覆盖费用。",
        }],
      },
      recommendation: {
        action: "reduce",
        target_position: {
          target_position_range_pct: ["8", "12"],
          target_position_note: "把单标的权重降至 8%–12%。",
        },
      },
    },
  };

  it("keeps a mode-less historical action as a labeled legacy snapshot", () => {
    const view = periodicReportView(report);
    const display = periodicRecommendationDisplay(report);
    expect(view.subject.type).toBe("instrument");
    expect(view.period.type).toBe("daily");
    expect(view.operation_count).toBe(3);
    expect(view.recommendation.action).toBe("reduce");
    expect(display).toMatchObject({
      observationOnly: false,
      mode: "historical_snapshot",
      action: "reduce",
      targetPositionNote: "把单标的权重降至 8%–12%。",
      label: "历史建议快照，非当前有效建议",
    });
    expect(view.reader_report.central_judgment).toContain("执行和基本面");
    expect(periodicSubjectLabel(view)).toBe("德展健康（000813.SZ）");
    expect(periodicReportHeadline(report)).toContain(
      "历史建议快照，非当前有效建议",
    );
    expect(projectedTime(view.period.report_cutoff_at)).toBe(
      "2026-07-15T15:00:00+08:00",
    );
    expect(projectedTime({ occurred_at: "2026-07-15T01:38:45Z" })).toBe(
      "2026-07-15T01:38:45Z",
    );
    expect(projectedTime({ completed_at: "2026-07-28T08:00:00Z" })).toBe(
      "2026-07-28T08:00:00Z",
    );
    expect(periodicOperationTime("2026-07-15T01:38:45Z")).toBe(
      "2026-07-15 09:38:45 +08:00",
    );
  });

  it("keeps an explicitly advice-capable report distinct from legacy", () => {
    const adviceReport = {
      ...report,
      reader_report: {
        ...report.reader_report,
        action_plan: {
          ...report.reader_report.action_plan,
          mode: "advice",
        },
      },
      sections: {
        ...report.sections,
        recommendation: {
          ...report.sections.recommendation,
          mode: "advice",
          decision_basis: "user_policy_trigger",
        },
      },
    };
    const display = periodicRecommendationDisplay(adviceReport);
    expect(display).toMatchObject({
      observationOnly: false,
      mode: "advice",
      action: "reduce",
      label: "用户策略触发 · 建议 reduce",
    });
    expect(periodicReportHeadline(adviceReport)).toBe(
      "短期趋势转强，但执行和基本面约束仍在。",
    );
  });

  it("renders missing-policy reports as observations without inventing an action", () => {
    const observationReport = {
      ...report,
      headline: "当前未取得显式用户风险策略，仅陈述事实与风险观察。",
      reader_report: {
        ...report.reader_report,
        central_judgment: "短期趋势转强，但风险策略尚未确认。",
        action_plan: {
          type: "observation",
          mode: "observation_only",
          action: null,
          target_position: null,
          target_position_note: null,
          time_horizon: null,
          confidence: "not_applicable",
          text: "当前仅形成事实与风险观察。",
        },
      },
      sections: {
        ...report.sections,
        recommendation: {
          type: "observation",
          mode: "observation_only",
          action: null,
          target_position: null,
          time_horizon: null,
          confidence: "not_applicable",
        },
      },
    };
    const display = periodicRecommendationDisplay(observationReport);
    expect(display).toEqual({
      observationOnly: true,
      mode: "observation_only",
      action: null,
      targetPositionNote: null,
      label: "仅事实与风险观察",
      detail: "未生成交易动作或目标仓位",
      summary: "仅事实与风险观察 · 未生成交易动作或目标仓位",
    });
    const headline = periodicReportHeadline(observationReport);
    expect(headline).toContain("仅事实与风险观察");
    expect(headline).toContain("未生成交易动作或目标仓位");
    expect(headline).not.toMatch(/建议\s+(hold|unknown|none)/i);
  });

  it("loads the periodic list and detail before operation-level evidence", () => {
    expect(source).toContain("/periodic-reports?limit=1000");
    expect(source).toContain("/periodic-report?");
    expect(source.indexOf("PERIODIC REPORTS")).toBeLessThan(
      source.indexOf("OPERATION EVIDENCE"),
    );
    expect(source).toContain("MOTIVE · SYSTEM INFERENCE");
    expect(source).toContain("weekly: \"自然周汇总\"");
    expect(source).toContain("monthly: \"自然月汇总\"");
    expect(source).toContain("[\"weekly\", \"周报\"]");
    expect(source).toContain("[\"monthly\", \"月报\"]");
    expect(source).toContain("FUNDAMENTAL · MARKET · TREND · EXECUTION");
    expect(source).toContain("operation.name, operation.ts_code");
    expect(source).toContain("rule_backfilled");
    expect(source).toContain("RECOMMENDATION · NOT AN ORDER");
    expect(source).toContain("OBSERVATION ONLY");
    expect(source).toContain("仅事实与风险观察");
    expect(source).toContain("未生成交易动作或目标仓位");
    expect(source).toContain("历史建议快照，非当前有效建议");
    expect(source).toContain("LEGACY ADVICE SNAPSHOT");
    expect(source).not.toContain("建议 ${text(recommendation.action)}");
    expect(source).not.toContain("${text(recommendation.action).toUpperCase()}");
    expect(source).toContain('riskPairs.push(["集中度", risk.concentration_status])');
    expect(source).toContain("READER ANALYSIS");
    expect(source).toContain("查看完整结构化事实、逐笔操作与来源");
    expect(source).toContain("investment_review.periodic_report.v2");
  });
});

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
    expect(source).toContain("只读报告");
    expect(source).toContain("不会冒充您的原始理由");
    expect(source).toContain("只有显式 advice 模式才展示个性化交易动作和仓位目标");
  });
});

describe("investment review automation health", () => {
  it("keeps partial completion distinct from success and failure", () => {
    expect(source).toContain("periodic_auto ${text(periodicAutomation.state");
    expect(source).toContain("periodic_success ${projectedTime(periodicAutomation.last_success)");
    expect(source).toContain("periodic_failure ${projectedTime(periodicAutomation.last_failure)");
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
