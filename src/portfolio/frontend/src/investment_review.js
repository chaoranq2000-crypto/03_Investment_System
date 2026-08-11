"use strict";

const REVIEW_API_ROOT = "/api/investment-review";
const REVIEW_STATUSES = new Set([
  "ready",
  "partial",
  "blocked",
  "failed",
  "queued",
  "running",
  "unknown",
]);
const FEE_STATUSES = new Set(["actual", "estimated"]);
const HEALTH_STATUSES = new Set([
  "healthy",
  "lagging",
  "missing_sidecar",
  "schema_not_initialized",
  "invalid_sidecar",
  "missing",
  "complete",
  "available",
  "unavailable",
]);
const REVIEW_SCOPES = new Set(["single", "weekly", "monthly"]);
const FACT_ID_PATTERN = /^fact:[0-9a-f]{32}$/;

function element(tagName, className = "", text = undefined) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function text(value, fallback = "unknown") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function values(value) {
  return Array.isArray(value) ? value : [];
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export const OPERATION_REVIEW_AXIS_NAMES = Object.freeze([
  "operation",
  "decision",
  "snapshot_cash_valuation",
  "market",
  "lifecycle",
  "outcome",
]);

const OPERATION_REVIEW_AXIS_LABELS = Object.freeze({
  operation: "操作事实",
  decision: "决策记录",
  snapshot_cash_valuation: "持仓、现金与估值",
  market: "市场信息",
  lifecycle: "持仓回合",
  outcome: "结果成熟度",
});

const OPERATION_REVIEW_STATUS_TEXT = Object.freeze({
  ready: "操作事实已具备复盘条件。",
  not_recorded: "没有找到已记录的当时决策理由；系统不会代为推断。",
  open: "该持仓回合仍在进行。",
  interim: "当前仅为阶段状态，不是最终结果。",
  partial: "已有部分证据，缺失项仍单独保留。",
  available: "对应证据可用。",
  missing: "对应证据缺失，未以零值代替。",
  blocked: "该轴尚未满足校验条件。",
  failed: "该轴处理失败，其他轴仍独立呈现。",
  unknown: "该轴状态尚未确定。",
});

export function operationReviewView(value) {
  const review = object(value);
  if (review.available !== true) {
    return {
      available: false,
      reason: text(
        review.reason,
        "operation_checkpoint_not_generated_for_this_run",
      ),
      axes: [],
    };
  }
  const sourceAxes = object(review.axes);
  return {
    available: true,
    schema_version: text(review.schema_version, ""),
    checkpoint_id: text(review.checkpoint_id, ""),
    content_id: text(review.content_id, ""),
    checkpoint_type: text(review.checkpoint_type, ""),
    perspective: review.perspective === "system" ? "system" : "user",
    as_of: review.as_of ?? null,
    knowledge_cutoff: review.knowledge_cutoff ?? null,
    operation_anchor: object(review.operation_anchor),
    information_time_policy_version: review.information_time_policy_version ?? null,
    actual_user_observation_proven:
      review.actual_user_observation_proven === true,
    gaps: values(review.gaps),
    source_refs: values(review.source_refs),
    axes: OPERATION_REVIEW_AXIS_NAMES.map((name) => {
      const axis = object(sourceAxes[name]);
      return {
        name,
        label: OPERATION_REVIEW_AXIS_LABELS[name],
        status: text(axis.status, "unknown").toLowerCase(),
        summary: axis.summary ?? null,
        source_refs: values(axis.source_refs),
        fields: object(axis.fields),
        evidence: axis,
      };
    }),
  };
}

export function operationReviewHeadline(value) {
  const review = operationReviewView(value);
  if (!review.available) {
    return "本次运行未生成六轴操作检查点；旧版事实复盘仍可核查。";
  }
  const statuses = Object.fromEntries(
    review.axes.map((axis) => [axis.name, axis.status]),
  );
  if (
    statuses.operation === "ready"
    && statuses.lifecycle === "open"
    && statuses.outcome === "interim"
  ) {
    return "操作事实已可复盘；持仓回合仍在进行，当前结果仅为阶段状态。";
  }
  return "六个状态轴按各自证据独立呈现；局部缺失不会被隐藏或补成零。";
}

function operationAxisNarrative(axis) {
  if (typeof axis.summary === "string" && axis.summary.trim()) {
    return axis.summary.trim();
  }
  return OPERATION_REVIEW_STATUS_TEXT[axis.status]
    || OPERATION_REVIEW_STATUS_TEXT.unknown;
}

function unwrap(payload) {
  const envelope = object(payload);
  return Object.prototype.hasOwnProperty.call(envelope, "data")
    ? object(envelope.data)
    : envelope;
}

function statusValue(value) {
  const normalized = String(value || "unknown").toLowerCase();
  return REVIEW_STATUSES.has(normalized)
    || HEALTH_STATUSES.has(normalized)
    || FEE_STATUSES.has(normalized)
    ? normalized
    : "unknown";
}

function statusBadge(value) {
  const status = statusValue(value);
  const badge = element("span", "investment-review-status", status);
  badge.dataset.status = status;
  return badge;
}

function canonicalNow() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function localDateTime(value) {
  const parsed = new Date(value || Date.now());
  if (Number.isNaN(parsed.getTime())) return "";
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function canonicalFromInput(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) throw new Error("时间格式无效");
  return parsed.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function requestId(kind, identity, timestamp, discriminator = "") {
  const material = [
    kind,
    identity.run_id,
    identity.review_id,
    identity.episode_id || "",
    discriminator,
    timestamp,
  ].join(":");
  let hash = 2166136261;
  for (let index = 0; index < material.length; index += 1) {
    hash ^= material.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${kind}_${(hash >>> 0).toString(16).padStart(8, "0")}_${timestamp.replace(/\D/g, "")}`;
}

function runIdentity(item) {
  return {
    run_id: text(item?.run_id, ""),
    review_id: text(item?.review_id, ""),
    episode_id: text(item?.episode_id, ""),
  };
}

function identityQuery(identity) {
  if (!identity.run_id || !identity.review_id) {
    throw new Error("复盘身份缺少 run_id 或 review_id");
  }
  return new URLSearchParams({
    run_id: identity.run_id,
    review_id: identity.review_id,
  }).toString();
}

function gapList(value) {
  return values(value)
    .map((item) => text(typeof item === "string" ? item : item?.code, ""))
    .filter(Boolean);
}

function appendList(parent, items, emptyText) {
  const normalized = values(items);
  if (!normalized.length) {
    parent.appendChild(element("p", "investment-review-empty-copy", emptyText));
    return;
  }
  const list = element("ul", "investment-review-code-list");
  normalized.forEach((item) => list.appendChild(element("li", "", text(item))));
  parent.appendChild(list);
}

function appendPairs(parent, entries) {
  const list = element("dl", "investment-review-pairs");
  entries.forEach(([label, value, sensitive = false]) => {
    const row = element("div", "investment-review-pair");
    row.append(element("dt", "", label), element("dd", sensitive ? "sensitive" : "", text(value)));
    list.appendChild(row);
  });
  parent.appendChild(list);
}

export function projectedTime(value) {
  if (typeof value === "string" || typeof value === "number") {
    return text(value);
  }
  const item = object(value);
  return text(
    item.occurred_at
      ?? item.known_at
      ?? item.status_occurred_at
      ?? item.requested_at
      ?? item.completed_at
      ?? item.started_at
      ?? item.generated_at
      ?? item.status_event?.occurred_at
      ?? item.status_event?.known_at
      ?? item.run?.requested_at,
  );
}

export function periodicOperationTime(value) {
  const raw = projectedTime(value);
  const timestamp = Date.parse(raw);
  if (!Number.isFinite(timestamp)) return raw;
  const shanghai = new Date(timestamp + (8 * 60 * 60 * 1000));
  return `${shanghai.toISOString().slice(0, 19).replace("T", " ")} +08:00`;
}

function boundaryText(value) {
  if (value === null || value === undefined || value === "") return "unknown";
  if (typeof value !== "object") return String(value);
  return Object.entries(value)
    .filter(([, item]) => ["string", "number", "boolean"].includes(typeof item))
    .map(([key, item]) => `${key}=${item}`)
    .join(", ") || "recorded";
}

function renderStructured(value, depth = 0) {
  if (depth > 6) {
    const details = element("details", "investment-review-structured-details");
    details.append(
      element("summary", "", "展开深层结构"),
      element(
        "pre",
        "investment-review-structured-value",
        JSON.stringify(value, null, 2),
      ),
    );
    return details;
  }
  if (Array.isArray(value)) {
    const list = element("ul", "investment-review-structured-list");
    if (!value.length) list.appendChild(element("li", "", "none"));
    value.forEach((item) => {
      const row = element("li");
      row.appendChild(renderStructured(item, depth + 1));
      list.appendChild(row);
    });
    return list;
  }
  if (value && typeof value === "object") {
    const list = element("dl", "investment-review-structured-map");
    const entries = Object.entries(value);
    if (!entries.length) return element("p", "investment-review-structured-value", "none");
    entries.forEach(([key, item]) => {
      const row = element("div");
      row.append(element("dt", "", key), element("dd"));
      row.lastChild.appendChild(renderStructured(item, depth + 1));
      list.appendChild(row);
    });
    return list;
  }
  return element("span", "investment-review-structured-value", text(value));
}

function sectionBlock(title, kicker = "") {
  const section = element("section", "investment-review-detail-block");
  const heading = element("header", "investment-review-detail-heading");
  if (kicker) heading.appendChild(element("p", "section-kicker", kicker));
  heading.appendChild(element("h3", "", title));
  const body = element("div", "investment-review-detail-body");
  section.append(heading, body);
  return { section, body };
}

export function isInvestmentReviewAcceptanceHealth(payload) {
  const health = object(payload);
  return health.review_acceptance_read_only === true
    && health.acceptance_task_id === "investment_review_local_acceptance_readiness_v1"
    && typeof health.review_candidate_sha256 === "string"
    && /^[0-9a-f]{64}$/.test(health.review_candidate_sha256);
}

function renderOperationReview(value) {
  const review = operationReviewView(value);
  const block = sectionBlock("操作复盘结论", "SIX-AXIS CHECKPOINT");
  if (!review.available) {
    block.body.appendChild(element(
      "p",
      "investment-review-empty-copy",
      operationReviewHeadline(value),
    ));
    return block.section;
  }

  block.section.classList.add("investment-review-operation");
  block.body.appendChild(element(
    "p",
    "investment-review-operation-headline",
    operationReviewHeadline(value),
  ));
  block.body.appendChild(element(
    "p",
    "investment-review-perspective-note",
    review.perspective === "user"
      ? "用户视角：按操作前已公开且版本已验证的信息投影；这不证明用户实际阅读过该信息。"
      : "系统视角：只采用系统在操作锚点前实际观测到的信息；之后取得的资料仅作回顾背景。",
  ));
  appendPairs(block.body, [
    ["视角", review.perspective === "user" ? "用户视角" : "系统视角"],
    ["操作锚点", review.operation_anchor.at],
    ["复盘时点", review.as_of],
    ["知识截止", review.knowledge_cutoff],
    ["信息时间规则", review.information_time_policy_version],
  ]);

  const grid = element("div", "investment-review-axis-grid");
  review.axes.forEach((axis) => {
    const card = element(
      "article",
      "investment-review-axis-card",
    );
    card.dataset.axis = axis.name;
    const heading = element("header", "investment-review-axis-heading");
    const badge = element(
      "span",
      "investment-review-status",
      axis.status,
    );
    badge.dataset.status = axis.status;
    heading.append(element("h4", "", axis.label), badge);
    card.append(
      heading,
      element(
        "p",
        "investment-review-axis-summary",
        operationAxisNarrative(axis),
      ),
    );

    if (axis.name === "snapshot_cash_valuation") {
      const fieldLabels = {
        position_quantity: "持仓数量",
        cost_basis: "成本",
        cash: "现金",
        price: "价格",
        nav: "净资产",
        weight: "权重",
        industry: "行业",
      };
      appendPairs(
        card,
        Object.entries(fieldLabels).map(([name, label]) => {
          const field = object(axis.fields[name]);
          const valueText = field.value === null || field.value === undefined
            ? "缺失"
            : `${field.value}${field.unit ? ` ${field.unit}` : ""}`;
          return [label, `${valueText} · ${text(field.status, "unknown")}`];
        }),
      );
    }

    if (axis.name === "market") {
      const evidence = object(axis.evidence);
      const eligibility = object(evidence.perspective_eligibility);
      appendPairs(card, [
        ["信息角色", evidence.temporal_role],
        ["信息生效", evidence.effective_at],
        ["公开时间", evidence.publicly_available_at],
        ["实际抓取", evidence.fetched_at],
        ["系统观测", evidence.system_observed_at],
        ["版本校验", object(evidence.version_provenance).status],
        ["来源", `${axis.source_refs.length} 项，明细见证据抽屉`],
      ]);
      card.appendChild(element(
        "p",
        "investment-review-perspective-note",
        eligibility.actual_user_observation_proven === true
          ? "产物含用户接触证据，但系统仍不推断是否实际阅读或如何理解。"
          : "没有用户实际接触证据；公开可得性不能替代实际阅读证明。",
      ));
    }
    grid.appendChild(card);
  });
  block.body.appendChild(grid);
  return block.section;
}

function normalizeReviews(payload) {
  const data = unwrap(payload);
  return values(data.reviews || data.items).map((item) => ({
    ...object(item),
    run_id: text(item?.run_id, ""),
    review_id: text(item?.review_id, ""),
    episode_id: text(item?.episode_id, ""),
    status: statusValue(item?.status),
    scope: REVIEW_SCOPES.has(item?.scope) ? item.scope : "unknown",
    gap_codes: gapList(item?.gap_codes || item?.gaps),
    operation_review: object(item?.operation_review),
  }));
}

export function periodicReportView(value) {
  const report = object(value);
  const subject = object(report.subject);
  const period = object(report.period);
  const sections = object(report.sections);
  const recommendation = object(
    report.recommendation || sections.recommendation,
  );
  const performance = object(
    object(sections.performance_and_positions).performance,
  );
  const operations = object(sections.operations_and_motives);
  const readerReport = object(report.reader_report);
  return {
    ...report,
    schema_version: text(report.schema_version, ""),
    report_id: text(report.report_id, ""),
    status: statusValue(report.status || "ready"),
    subject: {
      type: ["portfolio", "instrument"].includes(subject.type)
        ? subject.type
        : "unknown",
      id: text(subject.id, ""),
      name: text(subject.name, subject.id),
    },
    period: {
      type: text(period.type, "unknown"),
      start: period.start ?? null,
      end: period.end ?? null,
      report_cutoff_at: period.report_cutoff_at ?? null,
    },
    headline: text(
      readerReport.central_judgment || report.headline,
      "周期报告缺少结论摘要",
    ),
    analysis_brief: object(report.analysis_brief),
    reader_report: {
      ...readerReport,
      central_judgment: text(readerReport.central_judgment, ""),
      narrative_sections: values(readerReport.narrative_sections),
      action_plan: object(readerReport.action_plan),
      major_risks: values(readerReport.major_risks),
      invalidation_conditions: values(readerReport.invalidation_conditions),
      missing_inputs: values(readerReport.missing_inputs),
      appendix: object(readerReport.appendix),
    },
    recommendation,
    performance,
    operation_count: Number(
      report.operation_count ?? operations.operation_count ?? 0,
    ),
    sections,
  };
}

export function periodicRecommendationDisplay(value) {
  const report = object(value);
  const sections = object(report.sections);
  const recommendation = object(
    report.recommendation || sections.recommendation,
  );
  const readerAction = object(object(report.reader_report).action_plan);
  const action = readerAction.action ?? recommendation.action;
  const normalizedAction = typeof action === "string" ? action.trim() : "";
  const target = object(recommendation.target_position);
  const targetPositionNote = text(
    readerAction.target_position_note ?? target.target_position_note,
    "仓位精度受缺失数据限制。",
  );
  const observationOnly = (
    readerAction.mode === "observation_only"
    || recommendation.mode === "observation_only"
    || !normalizedAction
  );
  if (observationOnly) {
    return {
      observationOnly: true,
      mode: "observation_only",
      action: null,
      targetPositionNote: null,
      label: "仅事实与风险观察",
      detail: "未生成交易动作或目标仓位",
      summary: "仅事实与风险观察 · 未生成交易动作或目标仓位",
    };
  }
  const mode = readerAction.mode ?? recommendation.mode;
  const legacySnapshot = mode !== "advice";
  const label = legacySnapshot
    ? "历史建议快照，非当前有效建议"
    : `用户策略触发 · 建议 ${normalizedAction}`;
  const detail = legacySnapshot
    ? `${normalizedAction.toUpperCase()} · ${targetPositionNote}`
    : targetPositionNote;
  return {
    observationOnly: false,
    mode: legacySnapshot ? "historical_snapshot" : "advice",
    action: normalizedAction,
    targetPositionNote,
    label,
    detail,
    summary: `${label} · ${detail}`,
  };
}

export function periodicReportHeadline(value) {
  const report = periodicReportView(value);
  const display = periodicRecommendationDisplay(report);
  if (display.observationOnly) {
    const base = text(
      report.reader_report.central_judgment || report.headline,
      "周期报告缺少结论摘要",
    );
    if (base.includes(display.label) && base.includes(display.detail)) {
      return base;
    }
    return `${base} ${display.label}；${display.detail}。`;
  }
  if (display.mode === "historical_snapshot") {
    const base = text(
      report.reader_report.central_judgment || report.headline,
      "周期报告缺少结论摘要",
    );
    if (base.includes(display.label)) return base;
    return `${base} ${display.label}；${display.detail}。`;
  }
  if (report.reader_report.central_judgment) {
    return report.reader_report.central_judgment;
  }
  return `${report.headline} ${display.label}；${display.detail}`;
}

export function periodicSubjectLabel(value) {
  const subject = object(value?.subject ?? value);
  const id = text(subject.id, "");
  const name = text(subject.name, id || "MISSING_INSTRUMENT_NAME");
  if (subject.type !== "instrument" || !id || name.includes(id)) return name;
  return `${name}（${id}）`;
}

function interpretationTargets(detail) {
  const sections = object(detail.interpretation_sections);
  const targets = [];
  Object.entries(sections).forEach(([sectionName, entries]) => {
    values(entries).forEach((entry) => {
      const item = object(entry);
      const targetId = item.finding_id || item.option_id || item.interpretation_id;
      if (targetId) {
        targets.push({
          target_id: String(targetId),
          label: `${sectionName} · ${targetId}`,
        });
      }
    });
  });
  return targets;
}

function factIdsFromEvidence(detail, evidence) {
  const result = new Set();
  const inspect = (value) => {
    if (Array.isArray(value)) {
      value.forEach(inspect);
      return;
    }
    if (!value || typeof value !== "object") return;
    Object.entries(value).forEach(([key, item]) => {
      if (key === "fact_id" && FACT_ID_PATTERN.test(String(item))) result.add(String(item));
      else inspect(item);
    });
  };
  inspect(detail);
  inspect(evidence);
  return [...result].sort();
}

function actionButton(label, className = "") {
  const button = element("button", `investment-review-button ${className}`.trim(), label);
  button.type = "button";
  return button;
}

function field(labelText, input) {
  const label = element("label", "investment-review-field");
  label.append(element("span", "", labelText), input);
  return label;
}

function inputControl(type, name, required = false) {
  const input = element("input", "investment-review-input");
  input.type = type;
  input.name = name;
  input.required = required;
  input.autocomplete = "off";
  return input;
}

function textareaControl(name, required = false) {
  const input = element("textarea", "investment-review-textarea");
  input.name = name;
  input.required = required;
  input.rows = 3;
  return input;
}

function formMessage(form, message, error = false) {
  let output = form.querySelector("[data-form-message]");
  if (!output) {
    output = element("p", "investment-review-form-message");
    output.dataset.formMessage = "true";
    output.setAttribute("role", "status");
    form.appendChild(output);
  }
  output.textContent = message;
  output.classList.toggle("is-error", error);
}

export function mountInvestmentReview({
  request,
  notify = () => {},
  readOnly = false,
} = {}) {
  if (typeof request !== "function") throw new Error("investment review requires a request function");
  const root = document.querySelector("main");
  if (!root || document.getElementById("investmentReviewSection")) return null;
  const readOnlyMode = readOnly === true;

  const state = {
    periodicReports: [],
    periodicTotalCount: 0,
    periodicSubject: "all",
    periodicPeriod: "all",
    reviews: [],
    totalCount: 0,
    health: null,
    selected: null,
    selectedPeriodic: null,
    requestVersion: 0,
    scope: "all",
    status: "all",
  };

  const section = element("section", "investment-review-section");
  section.id = "investmentReviewSection";
  section.setAttribute("aria-labelledby", "investmentReviewTitle");
  section.dataset.reveal = "";
  section.dataset.readOnly = String(readOnlyMode);
  const heading = element("header", "investment-review-heading");
  const headingText = element("div");
  headingText.append(
    element("p", "section-kicker", "INVESTMENT REVIEW"),
    element("h2", "", "交易复盘"),
  );
  headingText.lastChild.id = "investmentReviewTitle";
  const headingActions = element("div", "investment-review-heading-actions");
  const healthBadge = statusBadge("unknown");
  healthBadge.id = "investmentReviewHealthBadge";
  const refreshButton = actionButton("刷新复盘", "is-primary");
  refreshButton.id = "investmentReviewRefresh";
  const collapseButton = actionButton("收起", "is-quiet");
  collapseButton.setAttribute("aria-expanded", "true");
  collapseButton.setAttribute("aria-controls", "investmentReviewContent");
  headingActions.append(healthBadge, refreshButton, collapseButton);
  heading.append(headingText, headingActions);

  const content = element("div", "investment-review-content");
  content.id = "investmentReviewContent";
  const acceptanceBoundary = element(
    "div",
    "investment-review-acceptance-boundary",
    "只读报告：本页不会写入正式持仓账本或执行交易；普通周期报告仅展示事实与风险观察，只有显式 advice 模式才展示个性化交易动作和仓位目标。可以展示标记为 system_inference 的动机推断；公开可得不等于证明您在操作前实际阅读过。",
  );
  acceptanceBoundary.hidden = !readOnlyMode;
  acceptanceBoundary.setAttribute("role", "note");
  const healthLine = element("div", "investment-review-health-line", "复盘健康状态正在读取");
  healthLine.id = "investmentReviewHealthLine";
  healthLine.setAttribute("role", "status");
  const periodicHeading = element("div", "investment-review-subheading");
  periodicHeading.append(
    element("p", "section-kicker", "PERIODIC REPORTS"),
    element("h3", "", "周期报告"),
  );
  const periodicControls = element("div", "investment-review-controls");
  const periodicSubjectSelect = element("select", "investment-review-select");
  periodicSubjectSelect.setAttribute("aria-label", "按报告对象筛选周期报告");
  [["all", "组合与标的"], ["portfolio", "组合"], ["instrument", "单标的"]]
    .forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      periodicSubjectSelect.appendChild(option);
    });
  const periodicPeriodSelect = element("select", "investment-review-select");
  periodicPeriodSelect.setAttribute("aria-label", "按周期筛选报告");
  [
    ["all", "全部周期"],
    ["daily", "日报"],
    ["weekly", "周报"],
    ["monthly", "月报"],
  ].forEach(([value, label]) => {
    const option = element("option", "", label);
    option.value = value;
    periodicPeriodSelect.appendChild(option);
  });
  periodicControls.append(periodicSubjectSelect, periodicPeriodSelect);
  const periodicListStatus = element(
    "p",
    "investment-review-list-status",
    "正在读取周期报告",
  );
  periodicListStatus.id = "investmentReviewPeriodicListStatus";
  periodicListStatus.setAttribute("role", "status");
  const periodicList = element("ol", "investment-review-list");
  periodicList.id = "investmentReviewPeriodicList";
  const evidenceHeading = element("div", "investment-review-subheading");
  evidenceHeading.append(
    element("p", "section-kicker", "OPERATION EVIDENCE"),
    element("h3", "", "操作级证据复盘"),
  );
  const controls = element("div", "investment-review-controls");
  const scopeSelect = element("select", "investment-review-select");
  scopeSelect.setAttribute("aria-label", "按运行范围筛选复盘");
  [["all", "全部范围"], ["single", "单笔"], ["weekly", "周度"], ["monthly", "月度"]]
    .forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      scopeSelect.appendChild(option);
    });
  const statusSelect = element("select", "investment-review-select");
  statusSelect.setAttribute("aria-label", "按状态筛选复盘");
  [["all", "全部状态"], ...[...REVIEW_STATUSES].map((value) => [value, value])]
    .forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      statusSelect.appendChild(option);
    });
  controls.append(scopeSelect, statusSelect);
  const listStatus = element("p", "investment-review-list-status", "正在读取复盘列表");
  listStatus.id = "investmentReviewListStatus";
  listStatus.setAttribute("role", "status");
  const list = element("ol", "investment-review-list");
  list.id = "investmentReviewList";
  content.append(
    acceptanceBoundary,
    healthLine,
    periodicHeading,
    periodicControls,
    periodicListStatus,
    periodicList,
    evidenceHeading,
    controls,
    listStatus,
    list,
  );
  section.append(heading, content);

  const holdings = root.querySelector(".holdings-section");
  root.insertBefore(section, holdings || null);

  const toolbar = document.querySelector(".toolbar");
  if (toolbar) {
    const entry = actionButton("交易复盘", "investment-review-entry");
    entry.id = "investmentReviewEntry";
    entry.addEventListener("click", () => section.scrollIntoView({ behavior: "smooth", block: "start" }));
    toolbar.insertBefore(entry, toolbar.firstChild);
  }

  const backdrop = element("div", "investment-review-backdrop");
  backdrop.id = "investmentReviewBackdrop";
  backdrop.hidden = true;
  const drawer = element("aside", "investment-review-drawer");
  drawer.id = "investmentReviewDrawer";
  drawer.hidden = true;
  drawer.inert = true;
  drawer.setAttribute("aria-hidden", "true");
  drawer.setAttribute("aria-labelledby", "investmentReviewDrawerTitle");
  const closeButton = actionButton("关闭", "investment-review-close");
  closeButton.id = "investmentReviewClose";
  const drawerContent = element("div", "investment-review-drawer-content");
  drawer.append(closeButton, drawerContent);

  const evidenceBackdrop = element("div", "investment-review-evidence-backdrop");
  evidenceBackdrop.hidden = true;
  const evidenceDrawer = element("aside", "investment-review-evidence-drawer");
  evidenceDrawer.id = "investmentReviewEvidenceDrawer";
  evidenceDrawer.hidden = true;
  evidenceDrawer.inert = true;
  evidenceDrawer.setAttribute("aria-hidden", "true");
  evidenceDrawer.setAttribute("aria-labelledby", "investmentReviewEvidenceTitle");
  const evidenceClose = actionButton("关闭证据", "investment-review-close");
  const evidenceContent = element("div", "investment-review-evidence-content");
  evidenceDrawer.append(evidenceClose, evidenceContent);
  document.body.append(backdrop, drawer, evidenceBackdrop, evidenceDrawer);

  const closeEvidence = () => {
    evidenceBackdrop.hidden = true;
    evidenceDrawer.classList.remove("is-open");
    evidenceDrawer.setAttribute("aria-hidden", "true");
    evidenceDrawer.inert = true;
    evidenceDrawer.hidden = true;
  };
  const closeDrawer = () => {
    state.requestVersion += 1;
    state.selected = null;
    state.selectedPeriodic = null;
    closeEvidence();
    backdrop.hidden = true;
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    drawer.inert = true;
    drawer.hidden = true;
    document.body.classList.remove("investment-review-open");
  };

  closeButton.addEventListener("click", closeDrawer);
  backdrop.addEventListener("click", closeDrawer);
  evidenceClose.addEventListener("click", closeEvidence);
  evidenceBackdrop.addEventListener("click", closeEvidence);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && evidenceDrawer.classList.contains("is-open")) closeEvidence();
    else if (event.key === "Escape" && drawer.classList.contains("is-open")) closeDrawer();
  });

  const post = (name, payload) => {
    if (readOnlyMode) {
      throw new Error("只读人工验收模式不允许保存决策或纠正");
    }
    return request(`${REVIEW_API_ROOT}/${name}`, {
      method: "POST",
      headers: { "X-Investment-Review-Action": name },
      body: JSON.stringify(payload),
    });
  };

  function renderHealth() {
    const health = object(state.health);
    const status = statusValue(health.status);
    healthBadge.textContent = status;
    healthBadge.dataset.status = status;
    const counts = object(health.counts);
    const lag = object(health.lag);
    const fees = object(health.fees);
    const reviews = object(health.reviews);
    const periodicReports = object(health.periodic_reports);
    const periodicAutomation = object(periodicReports.automation);
    const automation = object(health.automation);
    healthLine.replaceChildren();
    healthLine.append(
      element("span", "", `source ${text(counts.source_seen ?? counts.source, "unknown")}`),
      element("span", "", `sidecar ${text(counts.sidecar_seen ?? counts.sidecar, "unknown")}`),
      element("span", "", `unsynced ${text(lag.unsynced ?? counts.unsynced, "unknown")}`),
      element("span", "", `fees actual ${text(fees.actual, "0")} / estimated ${text(fees.estimated, "0")} / unknown ${text(fees.unknown, "0")}`),
      element("span", "", `reviews ${text(reviews.count ?? reviews.review_count, state.reviews.length)}`),
      element("span", "", `periodic ${text(periodicReports.count, state.periodicReports.length)}`),
      element("span", "", `periodic_auto ${text(periodicAutomation.state, "disabled")}`),
      element("span", "", `periodic_success ${projectedTime(periodicAutomation.last_success)}`),
      element("span", "", `periodic_failure ${projectedTime(periodicAutomation.last_failure)}`),
      element("span", "", `automation ${text(automation.state, "disabled")}`),
      element("span", "", `auto_completed ${projectedTime(automation.last_completed)}`),
      element("span", "", `auto_success ${projectedTime(automation.last_success)}`),
      element("span", "", `auto_failure ${projectedTime(automation.last_failure)}`),
      element("span", "", `last_success ${projectedTime(health.last_success)}`),
      element("span", "", `last_failure ${projectedTime(health.last_failure)}`),
      element("span", "", `boundary ${boundaryText(health.boundary)}`),
    );
  }

  function renderPeriodicList() {
    periodicList.replaceChildren();
    const filtered = state.periodicReports.filter((report) => (
      (state.periodicSubject === "all"
        || report.subject.type === state.periodicSubject)
      && (
        state.periodicPeriod === "all"
        || report.period.type === state.periodicPeriod
      )
    ));
    periodicListStatus.textContent = (
      state.periodicTotalCount > state.periodicReports.length
        ? `${filtered.length} / 已载入 ${state.periodicReports.length} / 总计 ${state.periodicTotalCount} 份周期报告`
        : `${filtered.length} / ${state.periodicReports.length} 份周期报告`
    );
    if (!filtered.length) {
      periodicList.appendChild(
        element(
          "li",
          "investment-review-empty",
          "当前筛选下没有周期报告；缺失周期不会被隐藏。",
        ),
      );
      return;
    }
    filtered.forEach((reportValue) => {
      const report = periodicReportView(reportValue);
      const row = element("li", "investment-review-list-item");
      const button = actionButton("", "investment-review-list-button");
      const top = element("div", "investment-review-list-top");
      const identity = element("div");
      identity.append(
        element("strong", "", periodicSubjectLabel(report)),
        element(
          "span",
          "investment-review-mono",
          `${report.period.type} · ${text(report.period.end)}`,
        ),
      );
      top.append(identity, statusBadge(report.status));
      const recommendationDisplay = periodicRecommendationDisplay(report);
      button.append(
        top,
        element(
          "p",
          "investment-review-list-meta",
          `${report.subject.type} · operations ${report.operation_count} · cutoff ${projectedTime(report.period.report_cutoff_at)}`,
        ),
        element(
          "p",
          "investment-review-list-conclusion",
          periodicReportHeadline(report),
        ),
        element(
          "p",
          "investment-review-list-gaps",
          recommendationDisplay.summary,
        ),
      );
      button.disabled = !report.report_id;
      button.addEventListener(
        "click",
        () => void openPeriodicReport(report),
      );
      row.appendChild(button);
      periodicList.appendChild(row);
    });
  }

  function renderList() {
    list.replaceChildren();
    const filtered = state.reviews.filter((review) => (
      (state.scope === "all" || review.scope === state.scope)
      && (state.status === "all" || review.status === state.status)
    ));
    listStatus.textContent = (
      state.totalCount > state.reviews.length
        ? `${filtered.length} / 已载入 ${state.reviews.length} / 总计 ${state.totalCount} 条复盘`
        : `${filtered.length} / ${state.reviews.length} 条复盘`
    );
    if (!filtered.length) {
      list.appendChild(element("li", "investment-review-empty", "当前筛选下没有复盘；缺失状态不会被隐藏。"));
      return;
    }
    filtered.forEach((review) => {
      const row = element("li", "investment-review-list-item");
      const button = actionButton("", "investment-review-list-button");
      const top = element("div", "investment-review-list-top");
      const identity = element("div");
      identity.append(
        element("strong", "", text(review.symbol, review.episode_id || "unknown")),
        element("span", "investment-review-mono", text(review.episode_id)),
      );
      top.append(identity, statusBadge(review.status));
      const dates = [review.opened_at, review.closed_at].filter(Boolean).map(String).join(" → ") || "time unknown";
      const meta = element("p", "investment-review-list-meta", `${review.scope} · ${dates} · facts ${text(review.fact_count, "unknown")} · decision ${text(review.decision_status)}`);
      const conclusion = element(
        "p",
        "investment-review-list-conclusion",
        operationReviewHeadline(review.operation_review),
      );
      const gaps = element(
        "p",
        "investment-review-list-gaps",
        review.gap_codes.length
          ? `有 ${review.gap_codes.length} 项待核查证据，代码与责任信息见证据抽屉。`
          : "当前没有已记录的证据缺口。",
      );
      button.append(top, meta, conclusion, gaps);
      button.disabled = !review.run_id || !review.review_id;
      button.addEventListener("click", () => void openReview(review));
      row.appendChild(button);
      list.appendChild(row);
    });
  }

  function renderEvidence(payload) {
    const data = unwrap(payload);
    evidenceContent.replaceChildren();
    const headingBlock = element("header", "investment-review-evidence-heading");
    headingBlock.append(
      element("p", "section-kicker", "TRACEABLE EVIDENCE"),
      element("h2", "", "证据与来源"),
    );
    headingBlock.lastChild.id = "investmentReviewEvidenceTitle";
    evidenceContent.appendChild(headingBlock);
    const checkpoint = object(data.operation_checkpoint);
    if (checkpoint.available === true) {
      const operation = sectionBlock("操作检查点证据", "SIX-AXIS EVIDENCE");
      operation.body.appendChild(renderStructured({
        schema_version: checkpoint.schema_version,
        checkpoint_id: checkpoint.checkpoint_id,
        content_id: checkpoint.content_id,
        perspective: checkpoint.perspective,
        operation_anchor: checkpoint.operation_anchor,
        as_of: checkpoint.as_of,
        knowledge_cutoff: checkpoint.knowledge_cutoff,
        information_time_policy_version:
          checkpoint.information_time_policy_version,
        actual_user_observation_proven:
          checkpoint.actual_user_observation_proven,
        axes: checkpoint.axes,
        gaps: checkpoint.gaps,
        source_refs: checkpoint.source_refs,
        market_fallback: checkpoint.market_fallback,
        time_provenance: checkpoint.time_provenance,
      }));
      evidenceContent.appendChild(operation.section);
    }
    values(data.sections).forEach((sectionItem) => {
      const item = object(sectionItem);
      const block = sectionBlock(text(item.name, "section"), "EVIDENCE SECTION");
      block.body.append(statusBadge(item.status));
      if (item.reason) block.body.appendChild(element("p", "", text(item.reason)));
      appendList(block.body, gapList(item.gap_codes), "gaps none");
      appendList(block.body, gapList(item.warning_codes), "warnings none");
      values(item.facts).forEach((fact) => block.body.appendChild(renderStructured(fact)));
      evidenceContent.appendChild(block.section);
    });
    const inventory = sectionBlock("来源清单", "SOURCE INVENTORY");
    inventory.body.appendChild(renderStructured(values(data.source_inventory)));
    evidenceContent.appendChild(inventory.section);
    const warnings = sectionBlock("证据警告", "WARNINGS");
    warnings.body.appendChild(renderStructured(values(data.warnings)));
    evidenceContent.appendChild(warnings.section);
  }

  function openEvidence(payload) {
    renderEvidence(payload);
    evidenceBackdrop.hidden = false;
    evidenceDrawer.hidden = false;
    evidenceDrawer.inert = false;
    evidenceDrawer.classList.add("is-open");
    evidenceDrawer.setAttribute("aria-hidden", "false");
    evidenceClose.focus();
  }

  function renderTimeline(payload, review, onSaved) {
    const data = unwrap(payload);
    const block = sectionBlock("成交时间线与费用", "TIMELINE");
    const events = values(data.events);
    const eventList = element("ol", "investment-review-timeline");
    if (!events.length) eventList.appendChild(element("li", "investment-review-empty-copy", "timeline unknown"));
    events.forEach((eventValue) => {
      const eventItem = object(eventValue);
      const eventRow = element("li", "investment-review-timeline-item");
      const eventHeading = element("div", "investment-review-timeline-heading");
      eventHeading.append(
        element("strong", "", `${text(eventItem.event_type)} ${text(eventItem.side, "")}`.trim()),
        element("span", "investment-review-mono", text(eventItem.effective_at)),
      );
      eventRow.appendChild(eventHeading);
      appendPairs(eventRow, [
        ["event_id", eventItem.event_id],
        ["known_at", eventItem.known_at],
        ["quantity", eventItem.signed_quantity ?? eventItem.quantity],
        ["position", `${text(eventItem.quantity_before)} → ${text(eventItem.quantity_after)}`],
      ]);
      const fee = object(eventItem.fee);
      const feeLine = element("div", "investment-review-fee-line");
      feeLine.append(
        element("span", "", "fee"),
        statusBadge(fee.status),
        element("strong", "sensitive", `${text(fee.currency, "CNY")} ${text(fee.amount)}`),
        element("small", "", `${text(fee.method, fee.source)} · samples ${text(fee.sample_count)}`),
      );
      eventRow.appendChild(feeLine);
      const feeTrace = element("details", "investment-review-structured-details");
      feeTrace.append(
        element("summary", "", "费用当前值、冻结值与修订来源"),
        renderStructured({
          current_fee: fee,
          frozen_fee: object(eventItem.frozen_fee),
          decision_refs: values(eventItem.decision_refs),
        }),
      );
      eventRow.appendChild(feeTrace);
      if (readOnlyMode) {
        eventRow.appendChild(
          element(
            "p",
            "investment-review-boundary",
            "只读验收会话：手续费纠正已停用。",
          ),
        );
        eventList.appendChild(eventRow);
        return;
      }
      const feeDetails = element("details", "investment-review-inline-form");
      feeDetails.appendChild(element("summary", "", "追加手续费纠正"));
      const feeForm = element("form", "investment-review-form");
      feeForm.appendChild(
        element(
          "p",
          "investment-review-boundary",
          "纠正从保存时刻起生效，只追加当前认知，不回写原始成交费用。",
        ),
      );
      const feeStatus = element("select", "investment-review-select");
      feeStatus.name = "status";
      [["actual", "actual"], ["unknown", "unknown"]].forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        feeStatus.appendChild(option);
      });
      const amount = inputControl("number", "amount");
      amount.min = "0.01";
      amount.step = "0.01";
      const reason = textareaControl("reason", true);
      reason.maxLength = 2000;
      const submit = actionButton("保存手续费纠正", "is-primary");
      submit.type = "submit";
      feeStatus.addEventListener("change", () => {
        amount.disabled = feeStatus.value === "unknown";
        amount.required = feeStatus.value === "actual";
        if (amount.disabled) amount.value = "";
      });
      amount.required = true;
      feeForm.append(
        field("状态", feeStatus),
        field("实际金额", amount),
        field("纠正原因", reason),
        submit,
      );
      feeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const timestamp = canonicalNow();
        submit.disabled = true;
        try {
          await post("fee-correction", {
            request_id: requestId("fee", runIdentity(review), timestamp, text(eventItem.event_id, "")),
            run_id: review.run_id,
            review_id: review.review_id,
            event_id: text(eventItem.event_id, ""),
            status: feeStatus.value,
            amount: feeStatus.value === "actual" ? amount.value : null,
            currency: text(fee.currency, "CNY"),
            effective_at: timestamp,
            known_at: timestamp,
            reviewer_ref: "workspace_user",
            reason: reason.value.trim(),
            supersedes_correction_id:
              fee.correction_id
              || fee.current_correction_id
              || fee.effective_correction_id
              || null,
          });
          formMessage(feeForm, "手续费纠正已追加保存");
          notify("手续费纠正已保存");
          await onSaved();
        } catch (error) {
          formMessage(feeForm, error.message, true);
        } finally {
          submit.disabled = false;
        }
      });
      feeDetails.appendChild(feeForm);
      eventRow.appendChild(feeDetails);
      eventList.appendChild(eventRow);
    });
    block.body.appendChild(eventList);
    const links = element("details", "investment-review-structured-details");
    links.append(element("summary", "", "snapshot links"), renderStructured(data.snapshot_links));
    block.body.appendChild(links);
    return { block, events };
  }

  function renderDecision(detail, review, events, onSaved) {
    const block = sectionBlock("补充决策并关联", "DECISION");
    block.body.appendChild(
      element(
        "p",
        "investment-review-boundary",
        "这是当前补充的回顾性记录；known_at 使用保存时刻，不改写冻结的历史复盘。",
      ),
    );
    const decisions = values(detail.current_decisions);
    if (decisions.length) block.body.appendChild(renderStructured(decisions));
    else block.body.appendChild(element("p", "investment-review-warning", "decision unknown / unlinked"));
    if (readOnlyMode) {
      block.body.appendChild(
        element(
          "p",
          "investment-review-boundary",
          "只读验收会话：补充决策与关联已停用；缺少记录时可以显示明确标记的系统推断，但不会冒充您的原始理由。",
        ),
      );
      return block;
    }
    const form = element("form", "investment-review-form investment-review-decision-form");
    const occurred = inputControl("datetime-local", "occurred_at", true);
    occurred.value = localDateTime(review.opened_at);
    const thesis = textareaControl("thesis", true);
    thesis.maxLength = 4000;
    const directReason = textareaControl("direct_reason");
    directReason.maxLength = 4000;
    const riskNotes = textareaControl("risk_notes");
    riskNotes.maxLength = 4000;
    const eventSelect = element("select", "investment-review-select");
    eventSelect.name = "event_id";
    values(events).forEach((eventItem) => {
      const option = element("option", "", `${text(eventItem.event_type)} · ${text(eventItem.effective_at)} · ${text(eventItem.event_id)}`);
      option.value = text(eventItem.event_id, "");
      eventSelect.appendChild(option);
    });
    const submit = actionButton("保存决策并关联", "is-primary");
    submit.type = "submit";
    if (!events.length) {
      submit.disabled = true;
      block.body.appendChild(
        element("p", "investment-review-warning", "没有可验证的成交事件，当前不能建立关联。"),
      );
    }
    let pendingLink = null;
    form.append(
      field("当时发生时间", occurred),
      field("当时记录的判断", thesis),
      field("直接原因（可选）", directReason),
      field("风险记录（可选）", riskNotes),
      field("关联成交（retrospective_context）", eventSelect),
      submit,
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const identity = runIdentity(review);
      const knownAt = canonicalNow();
      submit.disabled = true;
      try {
        if (!pendingLink) {
          const selectedEventId = eventSelect.value;
          const created = unwrap(await post("decision", {
            request_id: requestId("decision", identity, knownAt, selectedEventId),
            run_id: identity.run_id,
            review_id: identity.review_id,
            event_id: selectedEventId,
            occurred_at: canonicalFromInput(occurred.value),
            known_at: knownAt,
            thesis: thesis.value.trim(),
            status: "OPEN",
            ...(directReason.value.trim() ? { direct_reason: directReason.value.trim() } : {}),
            ...(riskNotes.value.trim() ? { risk_notes: riskNotes.value.trim() } : {}),
          }));
          const decisionId = text(created.decision_id, "");
          if (!decisionId) throw new Error("决策已返回但缺少 decision_id");
          pendingLink = { decisionId, eventId: selectedEventId };
          formMessage(form, `决策 ${decisionId} 已保存，正在建立回顾性关联`);
        }
        try {
          await post("link", {
            run_id: identity.run_id,
            review_id: identity.review_id,
            event_id: pendingLink.eventId,
            decision_id: pendingLink.decisionId,
            relation: "retrospective_context",
          });
        } catch (error) {
          formMessage(
            form,
            `决策 ${pendingLink.decisionId} 已保存但尚未关联；请保留本页并重试：${error.message}`,
            true,
          );
          return;
        }
        const decisionId = pendingLink.decisionId;
        pendingLink = null;
        formMessage(form, `已保存并关联 ${decisionId}`);
        notify("决策已保存并关联");
        await onSaved();
      } catch (error) {
        formMessage(form, error.message, true);
      } finally {
        submit.disabled = false;
      }
    });
    block.body.appendChild(form);
    return block;
  }

  function renderReviewCorrection(detail, evidence, review, onSaved) {
    const block = sectionBlock("复盘修订", "APPEND-ONLY REVISION");
    const capability = object(detail.correction_capability);
    const generationMode = text(
      detail.summary?.generation_mode
        ?? detail.revision?.generation_mode
        ?? review.generation_mode,
      "facts_only",
    );
    const targets = interpretationTargets(detail);
    const correctable = Boolean(
      capability.correctable
      ?? review.correctable
      ?? (generationMode !== "facts_only" && targets.length),
    );
    block.body.appendChild(element("p", "investment-review-boundary", `generation_mode ${generationMode}`));
    if (readOnlyMode) {
      block.body.appendChild(
        element(
          "p",
          "investment-review-boundary",
          "只读验收会话：复盘修订已停用。",
        ),
      );
      return block;
    }
    if (!correctable || generationMode === "facts_only") {
      const disabled = actionButton("facts_only 不可纠正");
      disabled.disabled = true;
      block.body.append(
        element("p", "investment-review-warning", "facts_only 为不可变事实层；当前没有可纠正的解释修订。"),
        disabled,
      );
      return block;
    }
    const form = element("form", "investment-review-form");
    const action = element("select", "investment-review-select");
    [["accept", "accept"], ["reject", "reject"], ["correct", "correct"]].forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      action.appendChild(option);
    });
    const target = element("select", "investment-review-select");
    const renderTargets = () => {
      const eligible = action.value === "correct"
        ? targets
        : targets.filter((item) => item.target_id.startsWith("finding:"));
      target.replaceChildren();
      eligible.forEach((item) => {
        const option = element("option", "", item.label);
        option.value = item.target_id;
        target.appendChild(option);
      });
      target.disabled = !eligible.length;
      submit.disabled = !eligible.length;
    };
    const reason = textareaControl("reason", true);
    reason.maxLength = 2000;
    const factRefs = textareaControl("fact_refs");
    factRefs.placeholder = "correct 时填写 fact:...，每行一个";
    const availableFacts = factIdsFromEvidence(detail, evidence);
    if (availableFacts.length) factRefs.value = availableFacts.slice(0, 1).join("\n");
    const submit = actionButton("追加复盘修订", "is-primary");
    submit.type = "submit";
    const updateCorrectionState = () => {
      const enabled = action.value === "correct";
      factRefs.disabled = !enabled;
      factRefs.required = enabled;
      renderTargets();
    };
    action.addEventListener("change", updateCorrectionState);
    updateCorrectionState();
    form.append(
      field("动作", action),
      field("目标", target),
      field("原因", reason),
      field("替换后的事实引用", factRefs),
      submit,
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const refs = factRefs.value.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean);
      if (action.value === "correct" && (!refs.length || refs.some((item) => !FACT_ID_PATTERN.test(item)))) {
        formMessage(form, "correct 需要至少一个有效 fact 引用", true);
        return;
      }
      submit.disabled = true;
      try {
        const reviewedAt = canonicalNow();
        await post("review-correction", {
          run_id: review.run_id,
          review_id: review.review_id,
          expected_parent_content_id: detail.revision?.content_id || review.content_id,
          request: {
            schema_version: "p2f.human_review_request.v1",
            action: action.value,
            reviewed_at: reviewedAt,
            actor_ref: "workspace_user",
            reason: reason.value.trim(),
            target_ids: [target.value],
            corrections: action.value === "correct"
              ? [{
                operation: "replace_fact_refs",
                target_id: target.value,
                fact_refs: [...new Set(refs)].sort(),
              }]
              : [],
          },
        });
        formMessage(form, "复盘修订已追加保存");
        notify("复盘修订已保存");
        await onSaved();
      } catch (error) {
        formMessage(form, error.message, true);
      } finally {
        submit.disabled = false;
      }
    });
    block.body.appendChild(form);
    return block;
  }

  function renderPeriodicDetail(value) {
    const report = periodicReportView(value);
    const sections = object(report.sections);
    const facts = object(sections.performance_and_positions);
    const performance = object(facts.performance);
    const risk = object(facts.risk_change);
    const decisionContext = object(sections.decision_context);
    const operationsSection = object(sections.operations_and_motives);
    const operations = values(operationsSection.operations);
    const episodeSummaries = values(operationsSection.episode_summaries);
    const recommendation = object(
      report.recommendation || sections.recommendation,
    );
    const limitations = object(sections.risks_invalidation_and_missing);
    const readerReport = object(report.reader_report);
    const readerSections = values(readerReport.narrative_sections);
    const recommendationDisplay = periodicRecommendationDisplay(report);
    const isReaderReport = (
      report.schema_version === "investment_review.periodic_report.v2"
      && Boolean(readerReport.central_judgment)
      && readerSections.length > 0
    );
    const periodLabel = {
      daily: "日报",
      weekly: "周报",
      monthly: "月报",
    }[report.period.type] || "周期报告";
    const contextLabel = {
      daily: "日报增量",
      weekly: "自然周汇总",
      monthly: "自然月汇总",
    }[report.period.type] || "周期汇总";
    const subjectLabel = periodicSubjectLabel(report);
    drawerContent.replaceChildren();
    const header = element("header", "investment-review-drawer-heading");
    header.append(
      element("p", "section-kicker", "PERIODIC REVIEW"),
      element(
        "h2",
        "",
        `${subjectLabel} · ${text(report.period.end)} ${periodLabel}`,
      ),
      element("p", "investment-review-mono", report.report_id),
      statusBadge(report.status),
    );
    header.querySelector("h2").id = "investmentReviewDrawerTitle";
    drawerContent.append(
      header,
      element(
        "p",
        "investment-review-gap-summary",
        periodicReportHeadline(report),
      ),
    );

    if (isReaderReport) {
      readerSections.forEach((sectionValue) => {
        const readerSection = object(sectionValue);
        const block = sectionBlock(
          text(readerSection.title, "综合分析"),
          "READER ANALYSIS",
        );
        values(readerSection.paragraphs).forEach((paragraph, index) => {
          block.body.appendChild(
            element(
              "p",
              index === 0 ? "investment-review-list-conclusion" : "",
              text(paragraph),
            ),
          );
        });
        drawerContent.appendChild(block.section);
      });

      const readerAction = object(readerReport.action_plan);
      const actionBlock = sectionBlock(
        recommendationDisplay.observationOnly
          ? "事实与风险观察"
          : (
            recommendationDisplay.mode === "historical_snapshot"
              ? "历史建议快照"
              : (
                report.subject.type === "instrument"
                  ? `${subjectLabel}下一步行动`
                  : "下一步行动"
              )
          ),
        recommendationDisplay.observationOnly
          ? "OBSERVATION ONLY"
          : (
            recommendationDisplay.mode === "historical_snapshot"
              ? "LEGACY ADVICE SNAPSHOT"
              : "RECOMMENDATION · NOT AN ORDER"
          ),
      );
      if (recommendationDisplay.observationOnly) {
        actionBlock.body.append(
          element("h3", "", recommendationDisplay.label),
          element("p", "", recommendationDisplay.detail),
          element(
            "p",
            "investment-review-list-gaps",
            text(
              readerAction.text,
              "需要用户明确请求 advice 模式并提供风险策略后，才会生成个性化交易动作和仓位目标。",
            ),
          ),
        );
        const questions = values(readerAction.questions_to_resolve);
        if (questions.length) {
          const questionDetails = element(
            "details",
            "investment-review-structured-details",
          );
          questionDetails.append(
            element("summary", "", "查看待确认问题"),
            renderStructured(questions),
          );
          actionBlock.body.appendChild(questionDetails);
        }
      } else {
        actionBlock.body.append(
          element(
            "p",
            "investment-review-list-gaps",
            recommendationDisplay.label,
          ),
          element(
            "span",
            "investment-review-mono",
            `confidence ${text(readerAction.confidence)}`,
          ),
          element(
            "h3",
            "",
            `${recommendationDisplay.action.toUpperCase()} · ${recommendationDisplay.targetPositionNote}`,
          ),
          element("p", "", `期限：${text(readerAction.time_horizon)}`),
          element(
            "p",
            "investment-review-list-gaps",
            recommendationDisplay.mode === "historical_snapshot"
              ? "该内容仅为历史快照，不是当前有效建议；系统不会连接券商或自动执行交易。"
              : "这是分析建议，不是订单；系统不会连接券商或自动执行交易。",
          ),
        );
      }
      drawerContent.appendChild(actionBlock.section);

      const riskBlock = sectionBlock(
        "风险、失效条件与数据缺口",
        "RISK · INVALIDATION · MISSING",
      );
      values(readerReport.major_risks).forEach((item) => {
        riskBlock.body.appendChild(element("p", "", `主要风险：${text(item)}`));
      });
      values(readerReport.invalidation_conditions).forEach((item) => {
        riskBlock.body.appendChild(element("p", "", `失效条件：${text(item)}`));
      });
      riskBlock.body.appendChild(
        element(
          "p",
          "investment-review-list-gaps",
          `缺失输入：${values(readerReport.missing_inputs).join("、") || "无明确缺失项"}`,
        ),
      );
      drawerContent.appendChild(riskBlock.section);

      const appendix = element(
        "details",
        "investment-review-structured-details",
      );
      appendix.append(
        element("summary", "", "查看完整结构化事实、逐笔操作与来源"),
        renderStructured({
          analysis_brief: report.analysis_brief,
          sections: report.sections,
          source: report.source,
          safety: report.safety,
        }),
      );
      drawerContent.appendChild(appendix);
      return;
    }

    const performanceBlock = sectionBlock(
      "收益、持仓、现金和风险变化",
      "PERIOD FACTS",
    );
    const riskPairs = [
      ["期初总资产", performance.start_total_assets_cny],
      ["期末总资产", performance.end_total_assets_cny],
      ["资产变动", `${text(performance.asset_change_cny)} / ${text(performance.asset_change_pct)}%`],
      ["现金权重", `${text(risk.cash_weight_pct)}%`],
      ["最大单一标的", `${text(risk.top_position_weight_pct)}%`],
      ["前三大合计", `${text(risk.top3_weight_pct)}%`],
    ];
    if (risk.concentration_status !== null
      && risk.concentration_status !== undefined
      && risk.concentration_status !== "") {
      riskPairs.push(["集中度", risk.concentration_status]);
    }
    appendPairs(performanceBlock.body, riskPairs);
    const positionDetails = element(
      "details",
      "investment-review-structured-details",
    );
    positionDetails.append(
      element("summary", "", "查看持仓与现金事实"),
      renderStructured({
        cash: facts.cash,
        positions: facts.positions,
        calculation_method: performance.calculation_method,
      }),
    );
    performanceBlock.body.appendChild(positionDetails);
    drawerContent.appendChild(performanceBlock.section);

    const contextBlock = sectionBlock(
      `四层决策上下文（${contextLabel}）`,
      "FUNDAMENTAL · MARKET · TREND · EXECUTION",
    );
    [
      ["fundamental_and_valuation", "基本面与估值"],
      ["market_and_sector", "大盘与板块"],
      ["technical_and_trend", "技术与趋势"],
      ["position_and_execution", "仓位与执行"],
    ].forEach(([key, label]) => {
      const layer = object(decisionContext[key]);
      const card = element("article", "investment-review-detail-block");
      card.append(
        element("h3", "", label),
        element(
          "p",
          "investment-review-list-conclusion",
          `${text(layer.status, "missing")}：${text(layer.summary, "本期无可核对增量")}`,
        ),
      );
      if (layer.portfolio_scope_note) {
        card.appendChild(
          element(
            "p",
            "investment-review-list-gaps",
            `范围：${text(layer.portfolio_scope_note)}`,
          ),
        );
      }
      const observations = values(layer.observations);
      if (observations.length) {
        const details = element(
          "details",
          "investment-review-structured-details",
        );
        details.append(
          element("summary", "", "查看本层事实与推断"),
          renderStructured({
            scope: layer.scope,
            observations,
            source_refs: layer.source_refs,
          }),
        );
        card.appendChild(details);
      }
      contextBlock.body.appendChild(card);
    });
    drawerContent.appendChild(contextBlock.section);

    const operationsBlock = sectionBlock(
      "操作与交易动机复盘",
      "MOTIVE · SYSTEM INFERENCE",
    );
    if (!operations.length) {
      operationsBlock.body.appendChild(
        element(
          "p",
          "investment-review-empty-copy",
          recommendationDisplay.observationOnly
            ? "本期没有持仓变动操作；表现与风险观察仍正常生成。"
            : "本期没有持仓变动操作；表现、风险与建议仍正常生成。",
        ),
      );
    }
    const feeLabels = {
      reported_actual: "账本实收",
      rule_backfilled: "规则回填",
      formal_exemption: "正式豁免",
      unknown: "来源未知",
    };
    episodeSummaries.forEach((summaryValue) => {
      const summary = object(summaryValue);
      const card = element("article", "investment-review-detail-block");
      const feeBasis = values(summary.fee_statuses)
        .map((item) => feeLabels[item] || text(item))
        .join("、");
      card.append(
        element(
          "h3",
          "",
          `${text(summary.name, summary.ts_code)}（${text(summary.ts_code)}）当日执行摘要`,
        ),
        element(
          "p",
          "investment-review-list-conclusion",
          `仓位 ${text(summary.opening_quantity)} → ${text(summary.peak_quantity)} → ${text(summary.closing_quantity)} 股 · 峰值 +${text(summary.peak_increase_pct)}%`,
        ),
        summary.round_trip_closed
          ? element(
            "p",
            "",
            `闭环毛价差 ${text(summary.gross_round_trip_pnl_cny)} 元 · 费用 ${text(summary.fee_total_cny)} 元（${feeBasis}）· 净结果 ${text(summary.net_round_trip_pnl_cny)} 元`,
          )
          : element(
            "p",
            "",
            `当日非闭环：买入 ${text(summary.bought_quantity)} 股、卖出 ${text(summary.sold_quantity)} 股 · 已知费用 ${text(summary.fee_total_cny)} 元（${feeBasis}）· 不计算日内净收益`,
          ),
        element(
          "p",
          "investment-review-list-gaps",
          text(summary.assessment),
        ),
      );
      operationsBlock.body.appendChild(card);
    });
    if (report.subject.type === "portfolio" && operations.length) {
      const details = element(
        "details",
        "investment-review-structured-details",
      );
      details.appendChild(
        element("summary", "", `查看 ${operations.length} 笔操作时点动机简表`),
      );
      operations.forEach((operationValue) => {
        const operation = object(operationValue);
        const motive = object(operation.motive);
        details.appendChild(
          element(
            "p",
            "",
            `${periodicOperationTime(operation.occurred_at)} · ${text(operation.side)} ${text(operation.name, operation.ts_code)}（${text(operation.ts_code)}）${text(operation.quantity)} 股：${text(motive.most_likely_motive, "见已记录 Decision")}`,
          ),
        );
      });
      operationsBlock.body.appendChild(details);
    } else {
      operations.forEach((operationValue) => {
      const operation = object(operationValue);
      const motive = object(operation.motive);
      const evaluation = object(operation.retrospective_evaluation);
      const card = element("article", "investment-review-detail-block");
      const heading = element("header", "investment-review-detail-heading");
      heading.append(
        element(
          "strong",
          "",
          `${text(operation.side)} ${text(operation.name, operation.ts_code)}（${text(operation.ts_code)}）`,
        ),
        element(
          "span",
          "investment-review-mono",
          periodicOperationTime(operation.occurred_at),
        ),
      );
      card.append(
        heading,
        element(
          "p",
          "",
          `${text(operation.quantity)} 股 × ${text(operation.price_cny)} 元 · 持仓 ${text(operation.quantity_before)} → ${text(operation.quantity_after)} · 费用 ${text(operation.fee_cny)} 元（${text(feeLabels[operation.fee_status], "来源未知")}${operation.fee_rule ? ` / ${text(operation.fee_rule)}` : ""}）`,
        ),
        element(
          "p",
          "investment-review-list-conclusion",
          `${text(motive.label)} / ${text(motive.confidence, "recorded")}：${text(motive.most_likely_motive, "见已记录 Decision")}`,
        ),
        element(
          "p",
          "investment-review-list-gaps",
          `替代解释：${values(motive.alternative_explanations).join("；") || "无"}`,
        ),
        element(
          "p",
          "",
          `事后评价：${text(evaluation.narrative)} 毛价差 ${text(evaluation.gross_mark_to_close_cny)} 元`,
        ),
      );
      const evidence = element(
        "details",
        "investment-review-structured-details",
      );
      evidence.append(
        element("summary", "", "查看推断依据、缺失信息和时间边界"),
        renderStructured({
          input_cutoff_at: motive.input_cutoff_at,
          uses_later_information: motive.uses_later_information,
          supporting_observations: motive.supporting_observations,
          important_missing_information:
            motive.important_missing_information,
        }),
      );
      card.appendChild(evidence);
      operationsBlock.body.appendChild(card);
      });
    }
    drawerContent.appendChild(operationsBlock.section);

    const recommendationBlock = sectionBlock(
      recommendationDisplay.observationOnly
        ? "事实与风险观察"
        : (
            recommendationDisplay.mode === "historical_snapshot"
            ? "历史建议快照"
            : (
              report.subject.type === "instrument"
                ? `${subjectLabel}个性化交易建议与建议仓位`
                : "个性化交易建议与建议仓位"
            )
        ),
      recommendationDisplay.observationOnly
        ? "OBSERVATION ONLY"
        : (
            recommendationDisplay.mode === "historical_snapshot"
            ? "LEGACY ADVICE SNAPSHOT"
            : "RECOMMENDATION · NOT AN ORDER"
        ),
    );
    if (recommendationDisplay.observationOnly) {
      recommendationBlock.body.append(
        element("h3", "", recommendationDisplay.label),
        element("p", "", recommendationDisplay.detail),
        element(
          "p",
          "investment-review-list-gaps",
          "需要用户明确请求 advice 模式并提供风险策略后，才会生成个性化交易动作和仓位目标。",
        ),
      );
    } else {
      recommendationBlock.body.append(
        element(
          "p",
          "investment-review-list-gaps",
          recommendationDisplay.label,
        ),
        element(
          "span",
          "investment-review-mono",
          `confidence ${text(recommendation.confidence)}`,
        ),
        element(
          "h3",
          "",
          `${recommendationDisplay.action.toUpperCase()} · ${recommendationDisplay.targetPositionNote}`,
        ),
        element("p", "", `期限：${text(recommendation.time_horizon)}`),
      );
    }
    values(recommendation.rationale).forEach((itemValue) => {
      const item = object(itemValue);
      recommendationBlock.body.appendChild(
        element("p", "", `${text(item.type)}：${text(item.text)}`),
      );
    });
    recommendationBlock.body.appendChild(
      renderStructured({
        major_downside_risks: recommendation.major_downside_risks,
        invalidation_conditions: recommendation.invalidation_conditions,
        important_missing_inputs: recommendation.important_missing_inputs,
        data_timestamp: recommendation.data_timestamp,
        orders_executed: recommendation.orders_executed,
        guaranteed_return: recommendation.guaranteed_return,
      }),
    );
    drawerContent.appendChild(recommendationBlock.section);

    const limitationsBlock = sectionBlock(
      "风险、失效条件和数据缺失",
      "LIMITATIONS",
    );
    limitationsBlock.body.appendChild(renderStructured(limitations));
    drawerContent.appendChild(limitationsBlock.section);
  }

  async function openPeriodicReport(report, { preserveOpen = false } = {}) {
    const reportId = text(report.report_id, "");
    if (!reportId) return;
    const version = state.requestVersion + 1;
    state.requestVersion = version;
    state.selected = null;
    state.selectedPeriodic = report;
    if (!preserveOpen) {
      backdrop.hidden = false;
      drawer.hidden = false;
      drawer.inert = false;
      drawer.classList.add("is-open");
      drawer.setAttribute("aria-hidden", "false");
      document.body.classList.add("investment-review-open");
      closeButton.focus();
    }
    drawerContent.replaceChildren(
      element("p", "investment-review-loading", "正在读取周期报告"),
    );
    try {
      const payload = await request(
        `${REVIEW_API_ROOT}/periodic-report?${new URLSearchParams({ report_id: reportId }).toString()}`,
      );
      if (version !== state.requestVersion) return;
      const data = unwrap(payload);
      renderPeriodicDetail(object(data.report));
    } catch (error) {
      if (version !== state.requestVersion) return;
      drawerContent.replaceChildren(
        element("h2", "", periodicSubjectLabel(report)),
        statusBadge("failed"),
        element(
          "p",
          "investment-review-warning",
          `periodic-report: ${error.message || "failed"}`,
        ),
      );
    }
  }

  function renderDetail(review, responses) {
    const detail = unwrap(responses.review);
    const timeline = unwrap(responses.timeline);
    const context = unwrap(responses.context);
    const evidence = unwrap(responses.evidence);
    drawerContent.replaceChildren();
    const summary = object(detail.summary);
    const header = element("header", "investment-review-drawer-heading");
    header.append(
      element("p", "section-kicker", "TRACEABLE REVIEW"),
      element("h2", "", text(summary.symbol ?? review.symbol, review.episode_id)),
      element("p", "investment-review-mono", `${review.run_id} · ${review.review_id}`),
      statusBadge(summary.status ?? review.status),
    );
    header.querySelector("h2").id = "investmentReviewDrawerTitle";
    drawerContent.appendChild(header);
    const gapCount = gapList(summary.gap_codes ?? review.gap_codes).length;
    drawerContent.appendChild(element(
      "p",
      "investment-review-gap-summary",
      gapCount
        ? `有 ${gapCount} 项证据缺口；代码、责任人和下一步请在证据抽屉核查。`
        : "当前没有已记录的证据缺口。",
    ));
    drawerContent.appendChild(renderOperationReview(
      detail.operation_review ?? summary.operation_review,
    ));

    const onSaved = async () => {
      await Promise.allSettled([loadHealth(), loadReviews()]);
      if (state.selected) await openReview(state.selected, { preserveOpen: true });
    };

    const timelineResult = renderTimeline(timeline, review, onSaved);
    drawerContent.appendChild(timelineResult.block.section);
    drawerContent.appendChild(renderDecision(detail, review, timelineResult.events, onSaved).section);

    const contextBlock = sectionBlock("组合上下文与快照", "PORTFOLIO CONTEXT");
    contextBlock.body.append(statusBadge(context.status));
    contextBlock.body.appendChild(renderStructured({
      contexts: values(context.contexts),
      deltas: context.deltas,
      warnings: values(context.warnings),
    }));
    drawerContent.appendChild(contextBlock.section);

    const interpretationBlock = sectionBlock("事实与解释记录", "REVIEW CONTENT");
    interpretationBlock.body.appendChild(renderStructured({
      revision: detail.revision,
      frozen_decision_linkage: detail.frozen_decision_linkage,
      interpretation_sections: detail.interpretation_sections,
      warnings: detail.warnings,
    }));
    drawerContent.appendChild(interpretationBlock.section);
    drawerContent.appendChild(renderReviewCorrection(detail, evidence, review, onSaved).section);

    const evidenceButton = actionButton("打开证据抽屉", "is-primary");
    evidenceButton.id = "investmentReviewEvidenceButton";
    evidenceButton.addEventListener("click", () => openEvidence(responses.evidence));
    drawerContent.appendChild(evidenceButton);
  }

  async function openReview(review, { preserveOpen = false } = {}) {
    const identity = runIdentity(review);
    const query = identityQuery(identity);
    const version = state.requestVersion + 1;
    state.requestVersion = version;
    state.selected = review;
    state.selectedPeriodic = null;
    if (!preserveOpen) {
      backdrop.hidden = false;
      drawer.hidden = false;
      drawer.inert = false;
      drawer.classList.add("is-open");
      drawer.setAttribute("aria-hidden", "false");
      document.body.classList.add("investment-review-open");
      closeButton.focus();
    }
    drawerContent.replaceChildren(element("p", "investment-review-loading", "正在验证并读取复盘产物"));
    const paths = ["review", "timeline", "context", "evidence"];
    const settled = await Promise.allSettled(
      paths.map((name) => request(`${REVIEW_API_ROOT}/${name}?${query}`)),
    );
    if (version !== state.requestVersion) return;
    const failed = settled
      .map((result, index) => ({ result, name: paths[index] }))
      .filter(({ result }) => result.status === "rejected");
    if (failed.length) {
      drawerContent.replaceChildren(
        element("h2", "", text(review.symbol, review.episode_id)),
        statusBadge("failed"),
        element(
          "p",
          "investment-review-warning",
          failed.map(({ name, result }) => `${name}: ${result.reason?.message || "failed"}`).join(" · "),
        ),
      );
      return;
    }
    renderDetail(review, Object.fromEntries(
      settled.map((result, index) => [paths[index], result.value]),
    ));
  }

  async function loadHealth() {
    try {
      state.health = unwrap(await request(`${REVIEW_API_ROOT}/health`));
    } catch (error) {
      state.health = { status: "failed", boundary: error.message };
    }
    renderHealth();
  }

  async function loadPeriodicReports() {
    periodicListStatus.textContent = "正在读取周期报告";
    try {
      const payload = await request(
        `${REVIEW_API_ROOT}/periodic-reports?limit=1000`,
      );
      const data = unwrap(payload);
      state.periodicReports = values(data.reports).map(periodicReportView);
      state.periodicTotalCount = Number(
        data.total_count ?? state.periodicReports.length,
      );
      renderPeriodicList();
    } catch (error) {
      state.periodicReports = [];
      state.periodicTotalCount = 0;
      periodicListStatus.textContent = `failed · ${error.message}`;
      periodicList.replaceChildren(
        element(
          "li",
          "investment-review-empty",
          "周期报告 API 不可用；操作级证据复盘仍可独立使用。",
        ),
      );
    }
  }

  async function loadReviews() {
    listStatus.textContent = "正在读取复盘列表";
    try {
      const payload = await request(`${REVIEW_API_ROOT}/reviews?limit=200`);
      const data = unwrap(payload);
      state.reviews = normalizeReviews(payload);
      state.totalCount = Number(data.total_count ?? state.reviews.length);
      renderList();
    } catch (error) {
      state.reviews = [];
      state.totalCount = 0;
      listStatus.textContent = `failed · ${error.message}`;
      list.replaceChildren(element("li", "investment-review-empty", "复盘 API 不可用；持仓页面仍可独立使用。"));
    }
  }

  const refresh = async () => {
    refreshButton.disabled = true;
    try {
      await Promise.all([loadHealth(), loadPeriodicReports(), loadReviews()]);
    } finally {
      refreshButton.disabled = false;
    }
  };
  refreshButton.addEventListener("click", () => void refresh());
  periodicSubjectSelect.addEventListener("change", () => {
    state.periodicSubject = periodicSubjectSelect.value;
    renderPeriodicList();
  });
  periodicPeriodSelect.addEventListener("change", () => {
    state.periodicPeriod = periodicPeriodSelect.value;
    renderPeriodicList();
  });
  scopeSelect.addEventListener("change", () => {
    state.scope = scopeSelect.value;
    renderList();
  });
  statusSelect.addEventListener("change", () => {
    state.status = statusSelect.value;
    renderList();
  });
  collapseButton.addEventListener("click", () => {
    const expanded = collapseButton.getAttribute("aria-expanded") === "true";
    collapseButton.setAttribute("aria-expanded", String(!expanded));
    collapseButton.textContent = expanded ? "展开" : "收起";
    content.hidden = expanded;
  });

  void refresh();
  return {
    section,
    refresh,
    close: closeDrawer,
  };
}
