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

function projectedTime(value) {
  const item = object(value);
  return text(
    item.occurred_at
      ?? item.known_at
      ?? item.status_occurred_at
      ?? item.requested_at
      ?? item.status_event?.occurred_at
      ?? item.status_event?.known_at
      ?? item.run?.requested_at,
  );
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
  }));
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

export function mountInvestmentReview({ request, notify = () => {} } = {}) {
  if (typeof request !== "function") throw new Error("investment review requires a request function");
  const root = document.querySelector("main");
  if (!root || document.getElementById("investmentReviewSection")) return null;

  const state = {
    reviews: [],
    totalCount: 0,
    health: null,
    selected: null,
    requestVersion: 0,
    scope: "all",
    status: "all",
  };

  const section = element("section", "investment-review-section");
  section.id = "investmentReviewSection";
  section.setAttribute("aria-labelledby", "investmentReviewTitle");
  section.dataset.reveal = "";
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
  const healthLine = element("div", "investment-review-health-line", "复盘健康状态正在读取");
  healthLine.id = "investmentReviewHealthLine";
  healthLine.setAttribute("role", "status");
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
  content.append(healthLine, controls, listStatus, list);
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

  const post = (name, payload) => request(`${REVIEW_API_ROOT}/${name}`, {
    method: "POST",
    headers: { "X-Investment-Review-Action": name },
    body: JSON.stringify(payload),
  });

  function renderHealth() {
    const health = object(state.health);
    const status = statusValue(health.status);
    healthBadge.textContent = status;
    healthBadge.dataset.status = status;
    const counts = object(health.counts);
    const lag = object(health.lag);
    const fees = object(health.fees);
    const reviews = object(health.reviews);
    healthLine.replaceChildren();
    healthLine.append(
      element("span", "", `source ${text(counts.source_seen ?? counts.source, "unknown")}`),
      element("span", "", `sidecar ${text(counts.sidecar_seen ?? counts.sidecar, "unknown")}`),
      element("span", "", `unsynced ${text(lag.unsynced ?? counts.unsynced, "unknown")}`),
      element("span", "", `fees actual ${text(fees.actual, "0")} / estimated ${text(fees.estimated, "0")} / unknown ${text(fees.unknown, "0")}`),
      element("span", "", `reviews ${text(reviews.count ?? reviews.review_count, state.reviews.length)}`),
      element("span", "", `last_success ${projectedTime(health.last_success)}`),
      element("span", "", `last_failure ${projectedTime(health.last_failure)}`),
      element("span", "", `boundary ${boundaryText(health.boundary)}`),
    );
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
      const gaps = element("p", "investment-review-list-gaps", review.gap_codes.length ? review.gap_codes.join(" · ") : "gaps none");
      button.append(top, meta, gaps);
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
    appendList(drawerContent, gapList(summary.gap_codes ?? review.gap_codes), "gaps none");

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
      await Promise.all([loadHealth(), loadReviews()]);
    } finally {
      refreshButton.disabled = false;
    }
  };
  refreshButton.addEventListener("click", () => void refresh());
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
