"use strict";

const state = {
  payload: null,
  filter: "all",
  query: "",
  sortKey: "market_value",
  sortDirection: "desc",
  asOf: null,
  privacy: localStorage.getItem("portfolioPrivacy") === "true",
  liveLoading: false,
  liveTimer: null,
};

const allocationColors = [
  "#e5484d",
  "#30a46c",
  "#f5d90a",
  "#3e63dd",
  "#8e4ec6",
  "#8d8d86",
];

const moneyFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const quantityFormatter = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 4,
});

const elements = {
  pageShell: document.getElementById("pageShell"),
  marketValue: document.getElementById("marketValue"),
  remainingCost: document.getElementById("remainingCost"),
  unrealizedPnl: document.getElementById("unrealizedPnl"),
  unrealizedReturn: document.getElementById("unrealizedReturn"),
  realizedPnl: document.getElementById("realizedPnl"),
  positionCount: document.getElementById("positionCount"),
  priceDate: document.getElementById("priceDate"),
  dataStatus: document.getElementById("dataStatus"),
  winLossCount: document.getElementById("winLossCount"),
  assetMix: document.getElementById("assetMix"),
  topWeight: document.getElementById("topWeight"),
  donutSegments: document.getElementById("donutSegments"),
  allocationLegend: document.getElementById("allocationLegend"),
  contributionChart: document.getElementById("contributionChart"),
  industryCoverage: document.getElementById("industryCoverage"),
  industryRefreshButton: document.getElementById("industryRefreshButton"),
  industryList: document.getElementById("industryList"),
  topIndustry: document.getElementById("topIndustry"),
  topIndustryWeight: document.getElementById("topIndustryWeight"),
  top3IndustryWeight: document.getElementById("top3IndustryWeight"),
  unclassifiedIndustryCount: document.getElementById("unclassifiedIndustryCount"),
  industryNote: document.getElementById("industryNote"),
  clearanceCoverage: document.getElementById("clearanceCoverage"),
  clearancePnl: document.getElementById("clearancePnl"),
  clearanceReturn: document.getElementById("clearanceReturn"),
  clearanceCycleCount: document.getElementById("clearanceCycleCount"),
  clearanceWinLoss: document.getElementById("clearanceWinLoss"),
  clearanceWinRate: document.getElementById("clearanceWinRate"),
  latestClearanceDate: document.getElementById("latestClearanceDate"),
  clearanceTableWrap: document.getElementById("clearanceTableWrap"),
  clearanceBody: document.getElementById("clearanceBody"),
  clearanceEmpty: document.getElementById("clearanceEmpty"),
  clearanceNote: document.getElementById("clearanceNote"),
  holdingsBody: document.getElementById("holdingsBody"),
  emptyState: document.getElementById("emptyState"),
  filterTabs: document.getElementById("filterTabs"),
  searchInput: document.getElementById("searchInput"),
  asOfInput: document.getElementById("asOfInput"),
  latestButton: document.getElementById("latestButton"),
  privacyButton: document.getElementById("privacyButton"),
  exportButton: document.getElementById("exportButton"),
  refreshButton: document.getElementById("refreshButton"),
  footerStatus: document.getElementById("footerStatus"),
  footerStatusDot: document.getElementById("footerStatusDot"),
  drawerBackdrop: document.getElementById("drawerBackdrop"),
  detailDrawer: document.getElementById("detailDrawer"),
  drawerContent: document.getElementById("drawerContent"),
  drawerClose: document.getElementById("drawerClose"),
  toast: document.getElementById("toast"),
};

function numberValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function money(value, signed = false) {
  const numeric = numberValue(value);
  if (numeric === null) return "MISSING";
  const absolute = moneyFormatter.format(Math.abs(numeric));
  if (numeric < 0) return `-¥${absolute}`;
  if (signed && numeric > 0) return `+¥${absolute}`;
  return `¥${absolute}`;
}

function percent(value, signed = false, digits = 2) {
  const numeric = numberValue(value);
  if (numeric === null) return "—";
  const prefix = signed && numeric > 0 ? "+" : "";
  return `${prefix}${numeric.toFixed(digits)}%`;
}

function price(value, assetType) {
  const numeric = numberValue(value);
  if (numeric === null) return "—";
  return numeric.toLocaleString("zh-CN", {
    minimumFractionDigits: assetType === "etf" ? 3 : 2,
    maximumFractionDigits: assetType === "etf" ? 4 : 3,
  });
}

function quantity(value) {
  const numeric = numberValue(value);
  return numeric === null ? "—" : quantityFormatter.format(numeric);
}

function toneClass(value) {
  const numeric = numberValue(value);
  if (numeric === null || numeric === 0) return "neutral";
  return numeric > 0 ? "gain" : "loss";
}

function setTone(element, value) {
  element.classList.remove("gain", "loss", "neutral");
  element.classList.add(toneClass(value));
}

function makeElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function formatFetchTime(value) {
  if (!value) return "尚无在线行情刷新记录";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function showToast(message, isError = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("is-error", isError);
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, isError ? 5200 : 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = { error: `HTTP ${response.status}` };
  }
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

async function loadPortfolio({ announce = false } = {}) {
  const query = state.asOf ? `?as_of=${encodeURIComponent(state.asOf)}` : "";
  elements.dataStatus.textContent = "正在读取本地账本";
  try {
    state.payload = await api(`/api/portfolio${query}`);
    renderAll();
    elements.footerStatusDot.classList.add("is-ready");
    if (!state.asOf) await refreshRealtime();
    if (announce) showToast(state.asOf ? `已切换到 ${state.asOf}` : "已恢复最新持仓");
  } catch (error) {
    elements.dataStatus.textContent = "读取失败";
    elements.footerStatus.textContent = `本地账本错误 · ${error.message}`;
    showToast(error.message, true);
  } finally {
    document.body.classList.add("page-ready");
  }
}

async function refreshRealtime() {
  if (state.asOf || state.liveLoading || document.hidden) return;
  state.liveLoading = true;
  elements.dataStatus.textContent = "正在更新盘中行情";
  try {
    state.payload = await api("/api/realtime-portfolio");
    renderAll();
  } catch (error) {
    elements.dataStatus.textContent = "盘中行情不可用 · 保留最近数据";
    elements.footerStatus.textContent = `盘中行情错误 · ${error.message}`;
  } finally {
    state.liveLoading = false;
  }
}

function startRealtimeTimer() {
  window.clearInterval(state.liveTimer);
  state.liveTimer = window.setInterval(refreshRealtime, 60_000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !state.asOf) refreshRealtime();
  });
}

function renderAll() {
  if (!state.payload) return;
  renderSummary();
  renderAllocation();
  renderContribution();
  renderIndustries();
  renderClearance();
  renderTable();
}

function renderSummary() {
  const { summary, metadata } = state.payload;
  const marketData = metadata.market_data || {};
  elements.marketValue.textContent = money(summary.market_value).replace("¥", "");
  elements.remainingCost.textContent = money(summary.remaining_cost);
  elements.unrealizedPnl.textContent = money(summary.unrealized_pnl, true);
  elements.unrealizedReturn.textContent = percent(summary.unrealized_return_pct, true);
  elements.realizedPnl.textContent = money(summary.realized_pnl_since_baseline, true);
  elements.positionCount.textContent = `${summary.position_count} 支持仓`;
  const isIntraday = ["intraday", "mixed"].includes(marketData.mode);
  const quoteTime = marketData.quote_time ? formatFetchTime(marketData.quote_time) : "—";
  if (state.asOf) {
    elements.priceDate.textContent = `收盘日 ${summary.latest_price_date || "MISSING"}`;
    elements.dataStatus.textContent = `历史回看 ${state.asOf}`;
  } else if (isIntraday) {
    elements.priceDate.textContent = `盘中 ${quoteTime}`;
    elements.dataStatus.textContent = `${marketData.live_quote_count}/${marketData.requested_count} 实时报价 · 每60秒`;
  } else {
    elements.priceDate.textContent = `收盘日 ${summary.latest_price_date || "MISSING"}`;
    elements.dataStatus.textContent = marketData.mode === "closing_fallback"
      ? "实时源暂不可用 · 使用正式收盘价"
      : "正式收盘价";
  }
  elements.winLossCount.textContent = `${summary.gain_count} / ${summary.loss_count}`;
  elements.assetMix.textContent = `${summary.equity_count} 只股票 · ${summary.etf_count} 只 ETF`;
  setTone(elements.unrealizedPnl, summary.unrealized_pnl);
  setTone(elements.unrealizedReturn, summary.unrealized_return_pct);
  setTone(elements.realizedPnl, summary.realized_pnl_since_baseline);

  const providerLabels = {
    "tencent.quote": "腾讯行情",
    "sina.quote": "新浪备用",
  };
  const providers = (marketData.providers || [])
    .map((item) => providerLabels[item] || item)
    .join(" + ");
  const fetchTime = formatFetchTime(
    isIntraday ? marketData.fetched_at : metadata.last_tushare_fetch_at,
  );
  elements.footerStatus.textContent = isIntraday
    ? `本地 SQLite · ${providers || "盘中行情"} ${fetchTime} · 60秒自动刷新`
    : `本地 SQLite · Tushare收盘价 ${fetchTime} · ${metadata.reconciliation_count} 条期初核对`;
}

function allocationGroups() {
  const positions = [...state.payload.positions]
    .filter((item) => numberValue(item.market_value) !== null)
    .sort((a, b) => numberValue(b.market_value) - numberValue(a.market_value));
  const head = positions.slice(0, 5).map((item) => ({
    name: item.name,
    weight: numberValue(item.weight_pct) || 0,
  }));
  const restWeight = positions
    .slice(5)
    .reduce((total, item) => total + (numberValue(item.weight_pct) || 0), 0);
  if (restWeight > 0.001) head.push({ name: "其他持仓", weight: restWeight });
  return head;
}

function renderAllocation() {
  const groups = allocationGroups();
  elements.donutSegments.replaceChildren();
  elements.allocationLegend.replaceChildren();
  let offset = 0;
  const svgNamespace = "http://www.w3.org/2000/svg";
  groups.forEach((group, index) => {
    const color = allocationColors[index % allocationColors.length];
    const circle = document.createElementNS(svgNamespace, "circle");
    circle.setAttribute("class", "donut-segment");
    circle.setAttribute("cx", "60");
    circle.setAttribute("cy", "60");
    circle.setAttribute("r", "45");
    circle.setAttribute("pathLength", "100");
    circle.setAttribute("stroke", color);
    circle.setAttribute("stroke-dasharray", `${group.weight} ${100 - group.weight}`);
    circle.setAttribute("stroke-dashoffset", String(-offset));
    const title = document.createElementNS(svgNamespace, "title");
    title.textContent = `${group.name} ${group.weight.toFixed(2)}%`;
    circle.appendChild(title);
    elements.donutSegments.appendChild(circle);
    offset += group.weight;

    const listItem = makeElement("li", "legend-item");
    const swatch = makeElement("span", "legend-swatch");
    swatch.style.backgroundColor = color;
    listItem.append(
      swatch,
      makeElement("span", "legend-name", group.name),
      makeElement("strong", "legend-weight sensitive", percent(group.weight)),
    );
    elements.allocationLegend.appendChild(listItem);
  });
  elements.topWeight.textContent = groups.length ? percent(groups[0].weight) : "—";
}

function renderContribution() {
  const positions = [...state.payload.positions]
    .filter((item) => numberValue(item.unrealized_pnl) !== null)
    .sort(
      (a, b) =>
        Math.abs(numberValue(b.unrealized_pnl)) - Math.abs(numberValue(a.unrealized_pnl)),
    )
    .slice(0, 10);
  const maxAbsolute = Math.max(
    ...positions.map((item) => Math.abs(numberValue(item.unrealized_pnl))),
    1,
  );
  elements.contributionChart.replaceChildren();
  positions.forEach((position) => {
    const value = numberValue(position.unrealized_pnl);
    const row = makeElement("div", "contribution-row");
    const name = makeElement("span", "contribution-name", position.name);
    const track = makeElement("div", "contribution-track");
    const bar = makeElement("span", `contribution-bar ${value >= 0 ? "is-gain" : "is-loss"}`);
    bar.style.width = `${Math.max((Math.abs(value) / maxAbsolute) * 50, 0.8)}%`;
    track.appendChild(bar);
    const amount = makeElement(
      "strong",
      `contribution-value sensitive ${toneClass(value)}`,
      money(value, true).replace("¥", ""),
    );
    row.append(name, track, amount);
    elements.contributionChart.appendChild(row);
  });
}

function renderIndustries() {
  const industries = state.payload.industries || [];
  const summary = state.payload.industry_summary || {};
  const metadata = state.payload.metadata || {};
  const maxWeight = Math.max(
    ...industries.map((item) => numberValue(item.weight_pct) || 0),
    1,
  );
  elements.industryList.replaceChildren();

  industries.forEach((industry) => {
    const weight = numberValue(industry.weight_pct);
    const pnl = numberValue(industry.unrealized_pnl);
    const row = makeElement("div", "industry-row");
    row.setAttribute(
      "aria-label",
      `${industry.industry_name}，${industry.position_count} 支持仓，权重 ${percent(weight)}`,
    );
    const nameWrap = makeElement("div", "industry-name-wrap");
    const memberText = industry.etf_count
      ? `${industry.position_count} 只 · ${industry.etf_count} 只 ETF`
      : `${industry.position_count} 只`;
    nameWrap.append(
      makeElement("span", "industry-name", industry.industry_name),
      makeElement("span", "industry-members", memberText),
    );
    const track = makeElement("div", "industry-track");
    const bar = makeElement("span", "industry-bar");
    bar.style.width = `${Math.max(((weight || 0) / maxWeight) * 100, 0.7)}%`;
    track.appendChild(bar);
    const weightValue = makeElement(
      "span",
      "industry-weight sensitive",
      percent(weight),
    );
    const marketValue = makeElement(
      "span",
      "industry-market sensitive",
      money(industry.market_value).replace("¥", ""),
    );
    const pnlValue = makeElement(
      "strong",
      `industry-pnl sensitive ${toneClass(pnl)}`,
      money(pnl, true).replace("¥", ""),
    );
    row.append(nameWrap, track, weightValue, marketValue, pnlValue);
    elements.industryList.appendChild(row);
  });

  const classified = numberValue(summary.classified_position_count) || 0;
  const total = state.payload.summary.position_count || 0;
  elements.industryCoverage.textContent = `${classified}/${total} 已分类 · ${summary.industry_count || 0} 个行业`;
  elements.topIndustry.textContent = summary.top_industry || "—";
  elements.topIndustryWeight.textContent = percent(summary.top_industry_weight_pct);
  elements.top3IndustryWeight.textContent = percent(summary.top3_weight_pct);
  elements.unclassifiedIndustryCount.textContent = String(
    summary.unclassified_position_count ?? "—",
  );
  const updatedAt = formatFetchTime(metadata.last_industry_update_at);
  elements.industryNote.textContent = `${summary.classification_note || "行业分类来源未记录。"} 最近更新 ${updatedAt}。历史回看使用当前行业标签。`;
}

function renderClearance() {
  const cycles = state.payload.closed_positions || [];
  const summary = state.payload.clearance_summary || {};
  const cycleCount = numberValue(summary.cycle_count) || 0;
  const securityCount = numberValue(summary.security_count) || 0;
  elements.clearanceCoverage.textContent = `${cycleCount} 次完整清仓 · ${securityCount} 支证券`;
  elements.clearancePnl.textContent = money(summary.total_realized_pnl, true);
  elements.clearanceReturn.textContent = percent(summary.return_pct, true);
  elements.clearanceCycleCount.textContent = String(cycleCount);
  elements.clearanceWinLoss.textContent = `${summary.gain_count || 0} / ${summary.loss_count || 0}`;
  elements.clearanceWinRate.textContent = percent(summary.win_rate_pct);
  elements.latestClearanceDate.textContent = summary.latest_close_date || "—";
  setTone(elements.clearancePnl, summary.total_realized_pnl);
  setTone(elements.clearanceReturn, summary.return_pct);

  elements.clearanceBody.replaceChildren();
  elements.clearanceTableWrap.hidden = cycles.length === 0;
  elements.clearanceEmpty.hidden = cycles.length !== 0;
  cycles.forEach((cycle) => {
    const row = document.createElement("tr");
    const securityCell = makeElement("td");
    const security = makeElement("div", "security-cell");
    const cycleLabel = cycle.cycle_number > 1 ? ` · 第 ${cycle.cycle_number} 轮` : "";
    security.append(
      makeElement("span", "security-name", cycle.name),
      makeElement("span", "security-code", `${cycle.ts_code}${cycleLabel}`),
    );
    securityCell.appendChild(security);

    const intervalCell = makeElement("td");
    const interval = makeElement("div", "clearance-interval");
    interval.append(
      makeElement("span", "clearance-dates", `${cycle.opened_on} → ${cycle.closed_on}`),
      makeElement("small", "", `${cycle.holding_days} 天 · ${cycle.sell_count} 笔卖出`),
    );
    intervalCell.appendChild(interval);

    row.append(
      securityCell,
      intervalCell,
      dataCell(quantity(cycle.sold_quantity), "numeric sensitive"),
      dataCell(money(cycle.cost_basis).replace("¥", ""), "numeric sensitive"),
      dataCell(money(cycle.net_sale_proceeds).replace("¥", ""), "numeric sensitive"),
      dataCell(
        money(cycle.realized_pnl, true).replace("¥", ""),
        `numeric sensitive ${toneClass(cycle.realized_pnl)}`,
      ),
      dataCell(
        percent(cycle.return_pct, true),
        `numeric ${toneClass(cycle.return_pct)}`,
      ),
    );
    elements.clearanceBody.appendChild(row);
  });

  const outside = numberValue(summary.realized_pnl_outside_closed_cycles) || 0;
  const outsideNote = outside === 0
    ? ""
    : ` 另有 ${money(outside, true)} 已实现盈亏来自未完成清仓周期或周期外现金项目，未计入本区。`;
  elements.clearanceNote.textContent = `${summary.calculation_note || "仅统计完整清仓周期。"}${outsideNote}`;
}

function visiblePositions() {
  if (!state.payload) return [];
  const query = state.query.trim().toLocaleLowerCase("zh-CN");
  const filtered = state.payload.positions.filter((item) => {
    const pnl = numberValue(item.unrealized_pnl);
    const filterMatch =
      state.filter === "all" ||
      (state.filter === "profit" && pnl > 0) ||
      (state.filter === "loss" && pnl < 0) ||
      (state.filter === "etf" && item.asset_type === "etf");
    const queryMatch =
      !query ||
      item.name.toLocaleLowerCase("zh-CN").includes(query) ||
      item.ts_code.toLocaleLowerCase("zh-CN").includes(query);
    return filterMatch && queryMatch;
  });
  return filtered.sort((a, b) => {
    const left = state.sortKey === "name" ? a.name : numberValue(a[state.sortKey]);
    const right = state.sortKey === "name" ? b.name : numberValue(b[state.sortKey]);
    let order;
    if (state.sortKey === "name") {
      order = String(left).localeCompare(String(right), "zh-CN");
    } else if (left === null && right === null) {
      order = 0;
    } else if (left === null) {
      order = 1;
    } else if (right === null) {
      order = -1;
    } else {
      order = left - right;
    }
    return state.sortDirection === "asc" ? order : -order;
  });
}

function dataCell(text, className = "") {
  const cell = makeElement("td", className, text);
  return cell;
}

function renderTable() {
  const positions = visiblePositions();
  elements.holdingsBody.replaceChildren();
  elements.emptyState.hidden = positions.length !== 0;
  positions.forEach((position) => {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.setAttribute("aria-label", `查看 ${position.name} 详情`);
    const securityCell = makeElement("td");
    const security = makeElement("div", "security-cell");
    security.append(
      makeElement("span", "security-name", position.name),
      makeElement("span", "security-code", position.ts_code),
    );
    securityCell.appendChild(security);

    const closeCell = dataCell(price(position.close, position.asset_type), "numeric");
    const dayChange = dataCell(
      percent(position.pct_chg, true),
      `numeric ${toneClass(position.pct_chg)}`,
    );
    const quantityCell = dataCell(quantity(position.quantity), "numeric sensitive");
    const costCell = dataCell(price(position.average_cost, position.asset_type), "numeric sensitive");
    const marketCell = dataCell(
      money(position.market_value).replace("¥", ""),
      "numeric sensitive",
    );
    const pnlCell = dataCell(
      money(position.unrealized_pnl, true).replace("¥", ""),
      `numeric sensitive ${toneClass(position.unrealized_pnl)}`,
    );
    const returnCell = dataCell(
      percent(position.return_pct, true),
      `numeric ${toneClass(position.return_pct)}`,
    );
    const weightCell = dataCell(
      percent(position.weight_pct),
      "numeric weight-cell sensitive",
    );
    row.append(
      securityCell,
      closeCell,
      dayChange,
      quantityCell,
      costCell,
      marketCell,
      pnlCell,
      returnCell,
      weightCell,
    );
    row.addEventListener("click", () => openDrawer(position));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDrawer(position);
      }
    });
    elements.holdingsBody.appendChild(row);
  });
  updateSortIndicators();
}

function drawerRow(label, value, extraClass = "") {
  const row = makeElement("div", "drawer-row");
  row.append(makeElement("dt", "", label), makeElement("dd", extraClass, value));
  return row;
}

function openDrawer(position) {
  elements.drawerContent.replaceChildren();
  const kicker = makeElement("p", "section-kicker", "POSITION DETAIL");
  const title = makeElement("h2", "", position.name);
  title.id = "drawerTitle";
  const code = makeElement("p", "drawer-code", `${position.ts_code} · ${position.asset_type.toUpperCase()}`);
  const pnl = makeElement(
    "p",
    `drawer-pnl sensitive ${toneClass(position.unrealized_pnl)}`,
    money(position.unrealized_pnl, true),
  );
  const returnValue = makeElement(
    "p",
    `drawer-return ${toneClass(position.return_pct)}`,
    `${percent(position.return_pct, true)} 浮动收益率`,
  );
  const grid = makeElement("dl", "drawer-grid");
  grid.append(
    drawerRow("行业分类", position.industry_name || "未分类"),
    drawerRow("持仓数量", quantity(position.quantity), "sensitive"),
    drawerRow("平均成本", price(position.average_cost, position.asset_type), "sensitive"),
    drawerRow("剩余成本", money(position.remaining_cost), "sensitive"),
    drawerRow(
      position.is_live ? "盘中最新价" : "最新收盘价",
      price(position.close, position.asset_type),
    ),
    drawerRow("最新市值", money(position.market_value), "sensitive"),
    drawerRow("组合权重", percent(position.weight_pct), "sensitive"),
    drawerRow("当日涨跌", percent(position.pct_chg, true), toneClass(position.pct_chg)),
    drawerRow("基准日后已实现", money(position.realized_pnl, true), "sensitive"),
  );
  const source = makeElement(
    "p",
    "drawer-source",
    `行情日期 ${position.price_date || "MISSING"}\n行情时间 ${position.quote_time || "正式收盘"}\n行情来源 ${position.price_source || "MISSING"}\n行业来源 ${position.industry_source || "MISSING"}`,
  );
  source.style.whiteSpace = "pre-line";
  elements.drawerContent.append(kicker, title, code, pnl, returnValue, grid, source);
  elements.drawerBackdrop.hidden = false;
  elements.detailDrawer.classList.add("is-open");
  elements.detailDrawer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  elements.drawerClose.focus();
}

function closeDrawer() {
  elements.detailDrawer.classList.remove("is-open");
  elements.detailDrawer.setAttribute("aria-hidden", "true");
  elements.drawerBackdrop.hidden = true;
  document.body.style.overflow = "";
}

function updateSortIndicators() {
  document.querySelectorAll("[data-sort]").forEach((button) => {
    const active = button.dataset.sort === state.sortKey;
    button.classList.toggle("is-sorted", active);
    button.dataset.direction = active ? (state.sortDirection === "asc" ? "↑" : "↓") : "";
    button.closest("th").setAttribute(
      "aria-sort",
      active ? (state.sortDirection === "asc" ? "ascending" : "descending") : "none",
    );
  });
}

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function exportCsv() {
  if (!state.payload) return;
  const fields = [
    ["证券代码", "ts_code"],
    ["证券名称", "name"],
    ["资产类型", "asset_type"],
    ["行业分类", "industry_name"],
    ["行业来源", "industry_source"],
    ["数量", "quantity"],
    ["平均成本", "average_cost"],
    ["最新价", "close"],
    ["行情日期", "price_date"],
    ["行情时间", "quote_time"],
    ["行情来源", "price_source"],
    ["市值", "market_value"],
    ["浮动盈亏", "unrealized_pnl"],
    ["收益率", "return_pct"],
    ["组合权重", "weight_pct"],
  ];
  const rows = [
    fields.map(([label]) => label).join(","),
    ...state.payload.positions.map((position) =>
      fields.map(([, key]) => csvValue(position[key])).join(","),
    ),
  ];
  const blob = new Blob(["\ufeff", rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `portfolio_${state.asOf || state.payload.summary.latest_price_date || "latest"}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("持仓 CSV 已导出");
}

async function refreshPrices() {
  elements.refreshButton.disabled = true;
  elements.refreshButton.classList.add("is-loading");
  elements.refreshButton.lastChild.textContent = " 刷新中";
  try {
    const result = await api("/api/refresh-prices", {
      method: "POST",
      headers: { "X-Portfolio-Action": "refresh-prices" },
      body: JSON.stringify({ as_of: state.asOf, lookback_days: 60 }),
    });
    await loadPortfolio();
    showToast(`已刷新 ${result.fetched} 支证券，最新交易日 ${result.latest_trade_date || "—"}`);
  } catch (error) {
    showToast(`刷新失败：${error.message}`, true);
  } finally {
    elements.refreshButton.disabled = false;
    elements.refreshButton.classList.remove("is-loading");
    elements.refreshButton.lastChild.textContent = " 刷新收盘价";
  }
}

async function refreshIndustries() {
  elements.industryRefreshButton.disabled = true;
  elements.industryRefreshButton.textContent = "更新中";
  try {
    const result = await api("/api/refresh-industries", {
      method: "POST",
      headers: { "X-Portfolio-Action": "refresh-industries" },
      body: "{}",
    });
    await loadPortfolio();
    const missing = result.missing?.length ? `，${result.missing.length} 支未分类` : "";
    showToast(`已读取 ${result.fetched} 支证券行业${missing}`);
  } catch (error) {
    showToast(`行业更新失败：${error.message}`, true);
  } finally {
    elements.industryRefreshButton.disabled = false;
    elements.industryRefreshButton.textContent = "更新行业";
  }
}

function applyPrivacyState() {
  document.body.classList.toggle("privacy-on", state.privacy);
  elements.privacyButton.textContent = state.privacy ? "显示金额" : "隐藏金额";
  elements.privacyButton.setAttribute("aria-pressed", String(state.privacy));
}

function bindEvents() {
  elements.filterTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    state.filter = button.dataset.filter;
    elements.filterTabs.querySelectorAll(".filter-tab").forEach((item) => {
      item.classList.toggle("is-active", item === button);
    });
    renderTable();
  });

  elements.searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    renderTable();
  });

  document.querySelector(".holdings-table thead").addEventListener("click", (event) => {
    const button = event.target.closest("[data-sort]");
    if (!button) return;
    const nextKey = button.dataset.sort;
    if (state.sortKey === nextKey) {
      state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
    } else {
      state.sortKey = nextKey;
      state.sortDirection = nextKey === "name" ? "asc" : "desc";
    }
    renderTable();
  });

  elements.asOfInput.addEventListener("change", async (event) => {
    state.asOf = event.target.value || null;
    await loadPortfolio({ announce: true });
  });

  elements.latestButton.addEventListener("click", async () => {
    state.asOf = null;
    elements.asOfInput.value = "";
    await loadPortfolio({ announce: true });
  });

  elements.privacyButton.addEventListener("click", () => {
    state.privacy = !state.privacy;
    localStorage.setItem("portfolioPrivacy", String(state.privacy));
    applyPrivacyState();
  });

  elements.exportButton.addEventListener("click", exportCsv);
  elements.refreshButton.addEventListener("click", refreshPrices);
  elements.industryRefreshButton.addEventListener("click", refreshIndustries);
  elements.drawerClose.addEventListener("click", closeDrawer);
  elements.drawerBackdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.detailDrawer.classList.contains("is-open")) {
      closeDrawer();
    }
  });
}

applyPrivacyState();
bindEvents();
startRealtimeTimer();
loadPortfolio();
