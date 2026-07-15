"use strict";

import { dispose, init, registerIndicator, registerOverlay } from "klinecharts";

import "./app.css";
import { selectContributionPositions } from "./contribution.js";
import {
  DEFAULT_TECHNICAL_INDICATORS,
  TECHNICAL_INDICATOR_GROUPS,
  TECHNICAL_INDICATOR_NAMES,
  buildIntradayMarkers,
  buildOperationMarkers,
  candleClickTradeDate,
  intradayBarSpaceLimit,
  intradayFitBarSpace,
  intradayAverageSeries,
  latestLedgerTradeDate,
  normalizeBars,
  normalizeTechnicalIndicatorSelection,
  operationDomId,
  rangeLabel,
  setTechnicalIndicatorVisibility,
  technicalIndicatorChartHeight,
  tradeDateOnOrBeforeAsOf,
} from "./kline.js";

const DAILY_INDICATOR_STORAGE_KEY = "portfolioKlineIndicators";
const INTRADAY_INDICATOR_STORAGE_KEY = "portfolioIntradayIndicators";
const TECHNICAL_INDICATOR_LABELS = new Map(
  TECHNICAL_INDICATOR_GROUPS.flatMap((group) =>
    group.items.map((item) => [item.name, item.label]),
  ),
);

const state = {
  payload: null,
  filter: "all",
  query: "",
  sortKey: "market_value",
  sortDirection: "desc",
  clearanceSortKey: "closed_on",
  clearanceSortDirection: "desc",
  performanceRange: "month",
  performanceLookbackMonths: localStorage.getItem("portfolioPerformanceLookbackMonths") || "3",
  performanceRefreshStarted: false,
  performanceRefreshLoading: false,
  performanceRefreshMessage: "",
  asOf: null,
  privacy: localStorage.getItem("portfolioPrivacy") === "true",
  liveLoading: false,
  liveTimer: null,
  collapsedModules: readStoredSet("portfolioCollapsedModules"),
  expandedIndustries: new Set(),
  expandedClearanceGroups: new Set(),
  drawerContext: null,
  drawerRequestId: 0,
  chart: null,
  chartResizeObserver: null,
  chartView: "daily",
  klinePayload: null,
  intradayPayload: null,
  klineIndicators: readKlineIndicatorSelection(DAILY_INDICATOR_STORAGE_KEY),
  intradayIndicators: readKlineIndicatorSelection(INTRADAY_INDICATOR_STORAGE_KEY),
};

const allocationColors = [
  "#e5484d",
  "#30a46c",
  "#f5d90a",
  "#3e63dd",
  "#8e4ec6",
  "#8d8d86",
];

const industryColors = [
  "#3e63dd",
  "#e5484d",
  "#30a46c",
  "#f5d90a",
  "#8e4ec6",
  "#e57a00",
  "#2b9a9a",
  "#8d8d86",
];

registerOverlay({
  name: "portfolioOperation",
  totalStep: 2,
  needDefaultPointFigure: false,
  needDefaultXAxisFigure: false,
  needDefaultYAxisFigure: false,
  createPointFigures: ({ coordinates, overlay }) => {
    const anchor = coordinates[0];
    const marker = overlay.extendData;
    if (!anchor || !marker) return [];
    const labelY = anchor.y + marker.verticalOffset;
    return [
      {
        type: "line",
        attrs: {
          coordinates: [anchor, { x: anchor.x, y: labelY }],
        },
        styles: { style: "dashed", size: 1, color: marker.color, dashedValue: [3, 3] },
        ignoreEvent: true,
      },
      {
        type: "circle",
        attrs: { x: anchor.x, y: anchor.y, r: 4 },
        styles: {
          style: "fill",
          color: marker.color,
          borderColor: "#f8f8f2",
          borderSize: 1,
        },
      },
      {
        type: "text",
        attrs: {
          x: anchor.x,
          y: labelY,
          text: marker.text,
          align: "center",
          baseline: marker.verticalOffset < 0 ? "bottom" : "top",
        },
        styles: {
          style: "fill",
          color: "#ffffff",
          size: 12,
          family: "IBM Plex Sans, Noto Sans SC, sans-serif",
          weight: 700,
          backgroundColor: marker.color,
          borderColor: marker.color,
          borderSize: 1,
          borderRadius: 4,
          paddingLeft: 6,
          paddingRight: 6,
          paddingTop: 3,
          paddingBottom: 3,
        },
      },
    ];
  },
});

registerIndicator({
  name: "INTRADAY_AVG",
  shortName: "日内均价",
  series: "price",
  precision: 4,
  figures: [
    {
      key: "average",
      title: "均价: ",
      type: "line",
      styles: () => ({ color: "#f5d90a", size: 1.5 }),
    },
  ],
  calc: (dataList) => intradayAverageSeries(dataList),
});

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
  cashBalance: document.getElementById("cashBalance"),
  unrealizedPnl: document.getElementById("unrealizedPnl"),
  unrealizedReturn: document.getElementById("unrealizedReturn"),
  monthPnl: document.getElementById("monthPnl"),
  yearPnl: document.getElementById("yearPnl"),
  allPnl: document.getElementById("allPnl"),
  lookbackPnl: document.getElementById("lookbackPnl"),
  performanceLookbackPicker: document.getElementById("performanceLookbackPicker"),
  performanceLookbackSelect: document.getElementById("performanceLookbackSelect"),
  performanceChart: document.getElementById("performanceChart"),
  performanceChartShell: document.getElementById("performanceChartShell"),
  performanceZeroLine: document.getElementById("performanceZeroLine"),
  performanceArea: document.getElementById("performanceArea"),
  performanceLine: document.getElementById("performanceLine"),
  performancePoints: document.getElementById("performancePoints"),
  performanceEmpty: document.getElementById("performanceEmpty"),
  performanceTooltip: document.getElementById("performanceTooltip"),
  performanceRangeDates: document.getElementById("performanceRangeDates"),
  performanceNote: document.getElementById("performanceNote"),
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
  industryPie: document.getElementById("industryPie"),
  industryPieSegments: document.getElementById("industryPieSegments"),
  industryPieLegend: document.getElementById("industryPieLegend"),
  industryPieEmpty: document.getElementById("industryPieEmpty"),
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
  clearanceTable: document.querySelector(".clearance-table"),
  clearanceStickyHeader: document.getElementById("clearanceStickyHeader"),
  clearanceStickyViewport: document.getElementById("clearanceStickyViewport"),
  clearanceBody: document.getElementById("clearanceBody"),
  clearanceEmpty: document.getElementById("clearanceEmpty"),
  clearanceNote: document.getElementById("clearanceNote"),
  topbar: document.querySelector(".topbar"),
  holdingsTable: document.querySelector(".holdings-table"),
  holdingsContent: document.getElementById("holdingsContent"),
  holdingsStickyHeader: document.getElementById("holdingsStickyHeader"),
  holdingsStickyViewport: document.getElementById("holdingsStickyViewport"),
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

function compactMoney(value, signed = false) {
  const numeric = numberValue(value);
  if (numeric === null) return "MISSING";
  const absolute = Math.abs(numeric);
  const prefix = numeric < 0 ? "-" : signed && numeric > 0 ? "+" : "";
  if (absolute >= 100_000_000) {
    return `${prefix}¥${(absolute / 100_000_000).toFixed(2).replace(/\.00$/, "")}亿`;
  }
  if (absolute >= 10_000) {
    return `${prefix}¥${(absolute / 10_000).toFixed(2).replace(/\.00$/, "")}万`;
  }
  return money(numeric, signed);
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

function readStoredSet(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return new Set(Array.isArray(value) ? value : []);
  } catch {
    return new Set();
  }
}

function readKlineIndicatorSelection(storageKey) {
  const stored = localStorage.getItem(storageKey);
  if (stored === null) return new Set(DEFAULT_TECHNICAL_INDICATORS);
  try {
    return new Set(normalizeTechnicalIndicatorSelection(JSON.parse(stored)));
  } catch {
    return new Set(DEFAULT_TECHNICAL_INDICATORS);
  }
}

function setModuleCollapsed(module, collapsed) {
  const button = module.querySelector("[data-collapse-button]");
  if (!button) return;
  const target = document.getElementById(button.getAttribute("aria-controls"));
  if (!target) return;
  const moduleName = module.dataset.collapsible;
  const label = button.querySelector("[data-collapse-label]");
  module.classList.toggle("is-collapsed", collapsed);
  target.hidden = collapsed;
  button.setAttribute("aria-expanded", String(!collapsed));
  if (label) label.textContent = collapsed ? "展开" : "收起";
  button.setAttribute("aria-label", `${collapsed ? "展开" : "收起"}${module.querySelector("h2")?.textContent || "模块"}`);
  if (collapsed) state.collapsedModules.add(moduleName);
  else state.collapsedModules.delete(moduleName);
}

function initializeCollapsibleModules() {
  document.querySelectorAll("[data-collapsible]").forEach((module) => {
    const collapsed = state.collapsedModules.has(module.dataset.collapsible);
    setModuleCollapsed(module, collapsed);
    const button = module.querySelector("[data-collapse-button]");
    button?.addEventListener("click", () => {
      setModuleCollapsed(module, button.getAttribute("aria-expanded") === "true");
      localStorage.setItem(
        "portfolioCollapsedModules",
        JSON.stringify([...state.collapsedModules]),
      );
    });
  });
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
  if (!state.asOf && !state.performanceRefreshStarted) {
    state.performanceRefreshLoading = true;
    state.performanceRefreshMessage = "正在自动补齐盈亏曲线所需的历史收盘价…";
  }
  elements.dataStatus.textContent = "正在读取本地账本";
  try {
    state.payload = await api(`/api/portfolio${query}`);
    renderAll();
    elements.footerStatusDot.classList.add("is-ready");
    if (!state.asOf) {
      await refreshRealtime();
      void refreshPerformanceHistoryOnOpen();
    }
    if (announce) showToast(state.asOf ? `已切换到 ${state.asOf}` : "已恢复最新持仓");
  } catch (error) {
    state.performanceRefreshLoading = false;
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
  elements.marketValue.textContent = money(summary.total_assets).replace("¥", "");
  elements.remainingCost.textContent = money(summary.remaining_cost);
  elements.cashBalance.textContent = money(summary.cash_balance);
  elements.unrealizedPnl.textContent = money(summary.unrealized_pnl, true);
  elements.unrealizedReturn.textContent = percent(summary.unrealized_return_pct, true);
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
  elements.assetMix.textContent = `${summary.equity_count} 只股票 · ${summary.etf_count} 只 ETF · 现金 ${percent(summary.cash_weight_pct)}`;
  setTone(elements.unrealizedPnl, summary.unrealized_pnl);
  setTone(elements.unrealizedReturn, summary.unrealized_return_pct);
  renderPerformance();

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

async function refreshPerformanceHistoryOnOpen() {
  if (state.asOf || state.performanceRefreshStarted) return;
  state.performanceRefreshStarted = true;
  state.performanceRefreshLoading = true;
  state.performanceRefreshMessage = "正在自动补齐盈亏曲线所需的历史收盘价…";
  renderPerformance();
  try {
    const result = await api("/api/refresh-performance", {
      method: "POST",
      headers: { "X-Portfolio-Action": "refresh-performance" },
      body: JSON.stringify({}),
    });
    const errorCount = (result.errors || []).length;
    if (result.requested_range_count === 0) {
      state.performanceRefreshMessage = "曲线行情已是最新。";
    } else if (errorCount) {
      state.performanceRefreshMessage = `自动更新完成：新增 ${result.new_observations} 个收盘价，${errorCount} 个区间待重试。`;
    } else {
      state.performanceRefreshMessage = `自动更新完成：新增 ${result.new_observations} 个收盘价。`;
    }
    // 无条件重读一次本地曲线。盘中刷新在页面隐藏或已有请求进行时会跳过，
    // 不能依赖它把刚补齐的历史曲线写回当前页面状态。
    if (!state.asOf) {
      state.payload = await api("/api/portfolio");
      renderAll();
      await refreshRealtime();
    }
  } catch (error) {
    state.performanceRefreshMessage = `自动更新失败：${error.message}；已保留现有曲线。`;
  } finally {
    state.performanceRefreshLoading = false;
    renderPerformance();
  }
}

function showPerformanceTooltip(point, x, y) {
  elements.performanceTooltip.textContent = `${point.date} · ${money(point.pnl, true)}`;
  elements.performanceTooltip.style.left = `${(x / 480) * 100}%`;
  elements.performanceTooltip.style.top = `${(y / 148) * 100}%`;
  elements.performanceTooltip.hidden = false;
}

function hidePerformanceTooltip() {
  elements.performanceTooltip.hidden = true;
}

function selectedLookbackPeriod(recentRanges) {
  const availableMonths = recentRanges.map((period) => String(period.months));
  if (!availableMonths.includes(state.performanceLookbackMonths)) {
    state.performanceLookbackMonths = availableMonths.includes("3")
      ? "3"
      : (availableMonths[0] || "3");
  }
  elements.performanceLookbackSelect.value = state.performanceLookbackMonths;
  return recentRanges.find(
    (period) => String(period.months) === state.performanceLookbackMonths,
  ) || null;
}

function renderPerformance() {
  const performance = state.payload?.pnl_performance || {};
  const periods = performance.periods || {};
  const recentRanges = performance.recent_ranges || [];
  const lookbackPeriod = selectedLookbackPeriod(recentRanges);
  const refreshLoading = state.performanceRefreshLoading && !state.asOf;
  const refreshMessage = state.asOf ? "" : state.performanceRefreshMessage;
  const valueElements = {
    month: elements.monthPnl,
    year: elements.yearPnl,
    all: elements.allPnl,
  };
  Object.entries(valueElements).forEach(([key, element]) => {
    const value = periods[key]?.pnl;
    element.textContent = refreshLoading ? "更新中" : compactMoney(value, true);
    setTone(element, refreshLoading ? null : value);
  });
  elements.lookbackPnl.textContent = refreshLoading
    ? "更新中"
    : compactMoney(lookbackPeriod?.pnl, true);
  setTone(elements.lookbackPnl, refreshLoading ? null : lookbackPeriod?.pnl);

  const selectablePeriods = {
    ...periods,
    ...(lookbackPeriod ? { lookback: lookbackPeriod } : {}),
  };
  if (!selectablePeriods[state.performanceRange]) {
    state.performanceRange = ["month", "year", "lookback", "all"]
      .find((key) => selectablePeriods[key]) || "month";
  }
  const period = selectablePeriods[state.performanceRange];
  document.querySelectorAll("[data-performance-range]").forEach((button) => {
    const active = button.dataset.performanceRange === state.performanceRange;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  });

  elements.performancePoints.replaceChildren();
  elements.performanceLine.setAttribute("d", "");
  elements.performanceArea.setAttribute("d", "");
  hidePerformanceTooltip();
  if (refreshLoading) {
    elements.performanceRangeDates.textContent = "自动更新中";
    elements.performanceNote.textContent = refreshMessage;
    elements.performanceEmpty.textContent = "正在抓取历史收盘价并重算曲线";
    elements.performanceEmpty.hidden = false;
    elements.performanceChart.setAttribute("aria-label", "盈亏曲线正在自动更新");
    elements.performanceChartShell.classList.remove("gain", "loss");
    elements.performanceChartShell.classList.add("neutral");
    return;
  }
  if (!period) {
    elements.performanceRangeDates.textContent = "暂无可追溯区间";
    elements.performanceNote.textContent = [
      refreshMessage,
      performance.data_note || "暂无可追溯台账。",
    ].filter(Boolean).join(" ");
    elements.performanceEmpty.hidden = false;
    elements.performanceChart.setAttribute("aria-label", "盈亏曲线暂无数据");
    return;
  }

  elements.performanceRangeDates.textContent = `${period.start_date} → ${period.end_date}`;
  elements.performanceNote.textContent = [
    refreshMessage,
    period.coverage_note,
    performance.data_note || "曲线来自本地台账与收盘价。",
  ].filter(Boolean).join(" ");
  elements.performanceChart.setAttribute("aria-label", `${period.label}曲线`);
  elements.performanceChartShell.classList.remove("gain", "loss", "neutral");
  elements.performanceChartShell.classList.add(toneClass(period.pnl));
  elements.performanceEmpty.textContent = period.status === "partial_history"
    ? "区间早于账户基准日，历史不完整"
    : "本地收盘价不足，暂不能绘制曲线";

  const series = (period.series || [])
    .map((point) => ({ date: point.date, pnl: numberValue(point.pnl) }))
    .filter((point) => point.pnl !== null);
  elements.performanceEmpty.hidden = series.length !== 0;
  if (series.length === 0) return;

  const width = 480;
  const height = 148;
  const horizontalPadding = 7;
  const verticalPadding = 13;
  const timestamps = series.map((point) => Date.parse(`${point.date}T00:00:00Z`));
  const firstTimestamp = Math.min(...timestamps);
  const lastTimestamp = Math.max(...timestamps);
  const rawValues = series.map((point) => point.pnl);
  let minimum = Math.min(0, ...rawValues);
  let maximum = Math.max(0, ...rawValues);
  if (minimum === maximum) {
    minimum -= 1;
    maximum += 1;
  } else {
    const padding = (maximum - minimum) * 0.1;
    minimum -= padding;
    maximum += padding;
  }
  const xAt = (timestamp) => firstTimestamp === lastTimestamp
    ? width / 2
    : horizontalPadding + ((timestamp - firstTimestamp) / (lastTimestamp - firstTimestamp)) * (width - horizontalPadding * 2);
  const yAt = (value) => verticalPadding + ((maximum - value) / (maximum - minimum)) * (height - verticalPadding * 2);
  const coordinates = series.map((point, index) => ({
    point,
    x: xAt(timestamps[index]),
    y: yAt(point.pnl),
  }));
  const linePath = coordinates
    .map(({ x, y }, index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(" ");
  const zeroY = yAt(0);
  const first = coordinates[0];
  const last = coordinates.at(-1);
  const areaPath = `${linePath} L${last.x.toFixed(2)},${zeroY.toFixed(2)} L${first.x.toFixed(2)},${zeroY.toFixed(2)} Z`;
  elements.performanceLine.setAttribute("d", linePath);
  elements.performanceArea.setAttribute("d", areaPath);
  elements.performanceZeroLine.setAttribute("y1", zeroY.toFixed(2));
  elements.performanceZeroLine.setAttribute("y2", zeroY.toFixed(2));

  coordinates.forEach(({ point, x, y }, index) => {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", index === coordinates.length - 1 ? "performance-point is-latest" : "performance-point");
    circle.setAttribute("cx", x.toFixed(2));
    circle.setAttribute("cy", y.toFixed(2));
    circle.setAttribute("r", index === coordinates.length - 1 ? "4" : "2.5");
    circle.setAttribute("tabindex", "0");
    circle.setAttribute("aria-label", `${point.date}，${money(point.pnl, true)}`);
    circle.addEventListener("pointerenter", () => showPerformanceTooltip(point, x, y));
    circle.addEventListener("pointerleave", hidePerformanceTooltip);
    circle.addEventListener("focus", () => showPerformanceTooltip(point, x, y));
    circle.addEventListener("blur", hidePerformanceTooltip);
    elements.performancePoints.appendChild(circle);
  });
}

function allocationGroups() {
  const assets = [...state.payload.positions]
    .filter((item) => numberValue(item.market_value) !== null)
    .map((item) => ({
      name: item.name,
      weight_pct: item.weight_pct,
      market_value: item.market_value,
    }));
  const cashBalance = numberValue(state.payload.summary.cash_balance) || 0;
  if (cashBalance > 0) {
    assets.push({
      name: "现金",
      weight_pct: state.payload.summary.cash_weight_pct,
      market_value: cashBalance,
    });
  }
  assets.sort((a, b) => numberValue(b.market_value) - numberValue(a.market_value));
  const head = assets.slice(0, 5).map((item) => ({
    name: item.name,
    weight: numberValue(item.weight_pct) || 0,
  }));
  const restWeight = assets
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
  const positions = selectContributionPositions(state.payload.positions);
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

function industryPieGroups(industries) {
  const weighted = industries
    .map((industry) => ({
      name: industry.industry_name,
      weight: numberValue(industry.weight_pct) || 0,
    }))
    .filter((industry) => industry.weight > 0);
  const groups = weighted.slice(0, 7);
  const otherWeight = weighted
    .slice(7)
    .reduce((total, industry) => total + industry.weight, 0);
  if (otherWeight > 0.001) groups.push({ name: "其他行业", weight: otherWeight });
  return groups;
}

function piePoint(angle, radius = 84) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: 100 + radius * Math.cos(radians),
    y: 100 + radius * Math.sin(radians),
  };
}

function pieSlicePath(startAngle, endAngle) {
  if (endAngle - startAngle >= 359.999) {
    return "M 100 16 A 84 84 0 1 1 100 184 A 84 84 0 1 1 100 16 Z";
  }
  const start = piePoint(startAngle);
  const end = piePoint(endAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return [
    "M 100 100",
    `L ${start.x.toFixed(3)} ${start.y.toFixed(3)}`,
    `A 84 84 0 ${largeArc} 1 ${end.x.toFixed(3)} ${end.y.toFixed(3)}`,
    "Z",
  ].join(" ");
}

function renderIndustryPie(industries) {
  const groups = industryPieGroups(industries);
  const totalWeight = groups.reduce((total, group) => total + group.weight, 0);
  const hasData = totalWeight > 0;
  elements.industryPie.hidden = !hasData;
  elements.industryPieEmpty.hidden = hasData;
  elements.industryPieLegend.hidden = !hasData;
  elements.industryPieSegments.replaceChildren();
  elements.industryPieLegend.replaceChildren();
  if (!hasData) {
    elements.industryPie.setAttribute("aria-label", "行业市值占比饼图暂无数据");
    return;
  }

  const svgNamespace = "http://www.w3.org/2000/svg";
  let angle = 0;
  groups.forEach((group, index) => {
    const sweep = (group.weight / totalWeight) * 360;
    const color = group.name.startsWith("未分类")
      ? "#8d8d86"
      : industryColors[index % industryColors.length];
    const segment = document.createElementNS(svgNamespace, "path");
    segment.setAttribute("class", "industry-pie-segment");
    segment.setAttribute("d", pieSlicePath(angle, angle + sweep));
    segment.setAttribute("fill", color);
    const title = document.createElementNS(svgNamespace, "title");
    title.textContent = `${group.name} ${group.weight.toFixed(2)}%`;
    segment.appendChild(title);
    elements.industryPieSegments.appendChild(segment);
    angle += sweep;

    const legendItem = makeElement("li", "industry-pie-legend-item");
    const swatch = makeElement("span", "industry-pie-swatch");
    swatch.style.backgroundColor = color;
    legendItem.append(
      swatch,
      makeElement("span", "industry-pie-name", group.name),
      makeElement("strong", "industry-pie-weight sensitive", percent(group.weight)),
    );
    elements.industryPieLegend.appendChild(legendItem);
  });
  elements.industryPie.setAttribute(
    "aria-label",
    `行业市值占比：${groups.map((group) => `${group.name} ${percent(group.weight)}`).join("，")}`,
  );
}

function renderIndustries() {
  const industries = state.payload.industries || [];
  const positionsByCode = new Map(
    (state.payload.positions || []).map((position) => [position.ts_code, position]),
  );
  const summary = state.payload.industry_summary || {};
  const metadata = state.payload.metadata || {};
  renderIndustryPie(industries);
  const maxWeight = Math.max(
    ...industries.map((item) => numberValue(item.weight_pct) || 0),
    1,
  );
  elements.industryList.replaceChildren();

  industries.forEach((industry, index) => {
    const weight = numberValue(industry.weight_pct);
    const pnl = numberValue(industry.unrealized_pnl);
    const group = makeElement("div", "industry-group");
    const row = makeElement("button", "industry-row");
    row.type = "button";
    const detailsId = `industryPositions${index}`;
    const expanded = state.expandedIndustries.has(industry.industry_name);
    row.setAttribute("aria-expanded", String(expanded));
    row.setAttribute("aria-controls", detailsId);
    row.setAttribute(
      "aria-label",
      `${expanded ? "收起" : "展开"}${industry.industry_name}，${industry.position_count} 支持仓，权重 ${percent(weight)}`,
    );
    const nameWrap = makeElement("div", "industry-name-wrap");
    const memberText = industry.etf_count
      ? `${industry.position_count} 只 · ${industry.etf_count} 只 ETF`
      : `${industry.position_count} 只`;
    nameWrap.append(
      makeElement("span", "industry-name", industry.industry_name),
      makeElement("span", "industry-members", memberText),
    );
    nameWrap.appendChild(makeElement("span", "industry-expand-indicator", expanded ? "收起持仓" : "查看持仓"));
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
    const memberList = makeElement("div", "industry-position-list");
    memberList.id = detailsId;
    memberList.hidden = !expanded;
    const memberHeader = makeElement("div", "industry-position-header");
    ["持仓股票", "类型", "市值", "浮动盈亏", "组合权重"].forEach((label) => {
      memberHeader.appendChild(makeElement("span", "", label));
    });
    memberList.appendChild(memberHeader);
    (industry.members || []).forEach((member) => {
      const position = positionsByCode.get(member.ts_code);
      const item = position || member;
      const memberRow = makeElement("button", "industry-position-row");
      memberRow.type = "button";
      memberRow.disabled = !position;
      memberRow.setAttribute("aria-label", `查看 ${item.name} 持仓详情`);
      const security = makeElement("span", "industry-position-security");
      security.append(
        makeElement("strong", "", item.name),
        makeElement("small", "", item.ts_code),
      );
      if (item.asset_type === "etf" && item.industry_source) {
        const sourceDate = item.industry_source.match(/reviewed_at=(\d{4}-\d{2}-\d{2})/);
        const coverage = item.industry_source.match(/coverage=([^|]+)/);
        const confidence = item.industry_source.match(/confidence=([^|]+)/);
        const evidence = [
          sourceDate ? `复核 ${sourceDate[1]}` : "复核映射",
          coverage ? `覆盖 ${coverage[1]}` : null,
          confidence ? `置信 ${confidence[1]}` : null,
        ].filter(Boolean).join(" · ");
        security.appendChild(makeElement("small", "industry-position-evidence", evidence));
      }
      memberRow.append(
        security,
        makeElement("span", "industry-position-type", item.asset_type === "etf" ? "ETF" : "股票"),
        makeElement("span", "industry-position-value sensitive", money(position?.market_value).replace("¥", "")),
        makeElement(
          "span",
          `industry-position-pnl sensitive ${toneClass(position?.unrealized_pnl)}`,
          money(position?.unrealized_pnl, true).replace("¥", ""),
        ),
        makeElement("span", "industry-position-weight sensitive", percent(position?.weight_pct)),
      );
      if (position) memberRow.addEventListener("click", () => openDrawer(position));
      memberList.appendChild(memberRow);
    });
    row.append(nameWrap, track, weightValue, marketValue, pnlValue);
    row.addEventListener("click", () => {
      const nextExpanded = row.getAttribute("aria-expanded") !== "true";
      row.setAttribute("aria-expanded", String(nextExpanded));
      row.setAttribute(
        "aria-label",
        `${nextExpanded ? "收起" : "展开"}${industry.industry_name}，${industry.position_count} 支持仓，权重 ${percent(weight)}`,
      );
      memberList.hidden = !nextExpanded;
      nameWrap.querySelector(".industry-expand-indicator").textContent = nextExpanded ? "收起持仓" : "查看持仓";
      if (nextExpanded) state.expandedIndustries.add(industry.industry_name);
      else state.expandedIndustries.delete(industry.industry_name);
    });
    group.append(row, memberList);
    elements.industryList.appendChild(group);
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

function sortedClearanceGroups() {
  const providedGroups = state.payload?.closed_position_groups || [];
  const groups = providedGroups.length > 0
    ? [...providedGroups]
    : (state.payload?.closed_positions || []).map((cycle) => ({
      ...cycle,
      group_id: `security:${cycle.ts_code}`,
      cycle_count: 1,
      cycles: [cycle],
    }));
  return groups.sort((leftGroup, rightGroup) => {
    const key = state.clearanceSortKey;
    const leftRaw = leftGroup[key];
    const rightRaw = rightGroup[key];
    const leftMissing = leftRaw === null || leftRaw === undefined || leftRaw === "";
    const rightMissing = rightRaw === null || rightRaw === undefined || rightRaw === "";
    if (leftMissing && !rightMissing) return 1;
    if (!leftMissing && rightMissing) return -1;

    let order = 0;
    if (!leftMissing && key === "name") {
      order = String(leftRaw).localeCompare(String(rightRaw), "zh-CN");
    } else if (!leftMissing && key === "closed_on") {
      order = String(leftRaw).localeCompare(String(rightRaw));
    } else if (!leftMissing) {
      order = numberValue(leftRaw) - numberValue(rightRaw);
    }
    if (order === 0) {
      order = String(leftGroup.ts_code).localeCompare(String(rightGroup.ts_code));
    }
    return state.clearanceSortDirection === "asc" ? order : -order;
  });
}

function makeClearanceCycleRow(cycle) {
  const row = document.createElement("tr");
  row.className = "clearance-cycle-row";
  row.tabIndex = 0;
  row.id = `clearance-cycle-${cycle.cycle_id.replaceAll(/[^a-zA-Z0-9_-]/g, "-")}`;
  row.setAttribute("aria-label", `查看 ${cycle.name} 第 ${cycle.cycle_number} 次清仓操作复盘`);
  const cycleCell = makeElement("td");
  const cycleLabel = makeElement("div", "clearance-cycle-label");
  cycleLabel.append(
    makeElement("span", "clearance-cycle-branch", "↳"),
    makeElement("span", "security-name", `第 ${cycle.cycle_number} 次清仓`),
    makeElement("span", "security-code", cycle.ts_code),
  );
  cycleCell.appendChild(cycleLabel);

  const intervalCell = makeElement("td");
  const interval = makeElement("div", "clearance-interval");
  interval.append(
    makeElement("span", "clearance-dates", `${cycle.opened_on} → ${cycle.closed_on}`),
    makeElement("small", "", `${cycle.holding_days} 天 · ${cycle.sell_count} 笔卖出`),
  );
  intervalCell.appendChild(interval);
  row.append(
    cycleCell,
    intervalCell,
    dataCell(quantity(cycle.sold_quantity), "numeric sensitive"),
    dataCell(money(cycle.cost_basis).replace("¥", ""), "numeric sensitive"),
    dataCell(money(cycle.net_sale_proceeds).replace("¥", ""), "numeric sensitive"),
    dataCell(
      money(cycle.realized_pnl, true).replace("¥", ""),
      `numeric sensitive ${toneClass(cycle.realized_pnl)}`,
    ),
    dataCell(percent(cycle.return_pct, true), `numeric ${toneClass(cycle.return_pct)}`),
  );
  row.addEventListener("click", () => openDrawer(cycle, "closed"));
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openDrawer(cycle, "closed");
    }
  });
  return row;
}

function renderClearance() {
  const groups = sortedClearanceGroups();
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
  elements.clearanceTableWrap.hidden = groups.length === 0;
  elements.clearanceEmpty.hidden = groups.length !== 0;
  groups.forEach((group) => {
    const row = document.createElement("tr");
    row.className = "clearance-group-row";
    row.tabIndex = 0;
    const expanded = state.expandedClearanceGroups.has(group.ts_code);
    row.setAttribute("aria-expanded", String(expanded));
    row.setAttribute("aria-label", `${expanded ? "收起" : "展开"}${group.name}的 ${group.cycle_count} 次清仓记录`);
    const securityCell = makeElement("td");
    const security = makeElement("div", "security-cell");
    security.append(
      makeElement("span", "security-name", group.name),
      makeElement("span", "security-code", `${group.ts_code} · ${group.cycle_count} 次清仓`),
      makeElement("span", "clearance-group-toggle", expanded ? "收起明细" : "展开明细"),
    );
    securityCell.appendChild(security);

    const intervalCell = makeElement("td");
    const interval = makeElement("div", "clearance-interval");
    interval.append(
      makeElement("span", "clearance-dates", `${group.opened_on} → ${group.closed_on}`),
      makeElement("small", "", `${group.cycle_count} 个完整周期 · ${group.sell_count} 笔卖出`),
    );
    intervalCell.appendChild(interval);

    row.append(
      securityCell,
      intervalCell,
      dataCell(quantity(group.sold_quantity), "numeric sensitive"),
      dataCell(money(group.cost_basis).replace("¥", ""), "numeric sensitive"),
      dataCell(money(group.net_sale_proceeds).replace("¥", ""), "numeric sensitive"),
      dataCell(
        money(group.realized_pnl, true).replace("¥", ""),
        `numeric sensitive ${toneClass(group.realized_pnl)}`,
      ),
      dataCell(percent(group.return_pct, true), `numeric ${toneClass(group.return_pct)}`),
    );
    const cycleRows = (group.cycles || []).map(makeClearanceCycleRow);
    cycleRows.forEach((cycleRow) => {
      cycleRow.hidden = !expanded;
    });
    row.setAttribute("aria-controls", cycleRows.map((cycleRow) => cycleRow.id).join(" "));
    const toggleGroup = () => {
      const nextExpanded = row.getAttribute("aria-expanded") !== "true";
      row.setAttribute("aria-expanded", String(nextExpanded));
      row.setAttribute("aria-label", `${nextExpanded ? "收起" : "展开"}${group.name}的 ${group.cycle_count} 次清仓记录`);
      row.querySelector(".clearance-group-toggle").textContent = nextExpanded ? "收起明细" : "展开明细";
      cycleRows.forEach((cycleRow) => {
        cycleRow.hidden = !nextExpanded;
      });
      if (nextExpanded) state.expandedClearanceGroups.add(group.ts_code);
      else state.expandedClearanceGroups.delete(group.ts_code);
      scheduleStickyTableHeadersSync();
    };
    row.addEventListener("click", toggleGroup);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleGroup();
      }
    });
    elements.clearanceBody.append(row, ...cycleRows);
  });

  const outside = numberValue(summary.realized_pnl_outside_closed_cycles) || 0;
  const outsideNote = outside === 0
    ? ""
    : ` 另有 ${money(outside, true)} 已实现盈亏来自未完成清仓周期或周期外现金项目，未计入本区。`;
  elements.clearanceNote.textContent = `${summary.calculation_note || "仅统计完整清仓周期。"}${outsideNote}`;
  updateClearanceSortIndicators();
  scheduleStickyTableHeadersSync();
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
  scheduleStickyTableHeadersSync();
}

const stickyTableHeaderControllers = [];
let stickyTableHeaderFrame = null;

function scheduleStickyTableHeadersSync() {
  if (stickyTableHeaderFrame !== null) return;
  stickyTableHeaderFrame = window.requestAnimationFrame(() => {
    stickyTableHeaderFrame = null;
    stickyTableHeaderControllers.forEach(syncStickyTableHeader);
  });
}

function syncStickyTableHeader(controller) {
  const {
    sourceTable,
    scrollContainer,
    stickyHeader,
    stickyViewport,
    stickyTable,
  } = controller;
  if (!stickyTable || scrollContainer.hidden) {
    stickyHeader.classList.remove("is-visible");
    stickyHeader.setAttribute("aria-hidden", "true");
    stickyHeader.inert = true;
    return;
  }

  const topbarPosition = window.getComputedStyle(elements.topbar).position;
  const stickyTop = topbarPosition === "sticky"
    ? elements.topbar.getBoundingClientRect().height
    : 0;
  const scrollContainerRect = scrollContainer.getBoundingClientRect();
  const sourceTableRect = sourceTable.getBoundingClientRect();
  const sourceHeadRect = sourceTable.tHead.getBoundingClientRect();
  stickyHeader.style.setProperty("--sticky-table-top", `${stickyTop}px`);
  stickyHeader.style.setProperty("--sticky-table-left", `${scrollContainerRect.left}px`);
  stickyHeader.style.setProperty("--sticky-table-width", `${scrollContainerRect.width}px`);
  stickyHeader.style.setProperty("--sticky-table-height", `${sourceHeadRect.height}px`);
  stickyTable.style.width = `${sourceTableRect.width}px`;
  stickyTable.style.transform = `translateX(${-scrollContainer.scrollLeft}px)`;

  const sourceHeaders = [...sourceTable.tHead.rows[0].cells];
  const stickyHeaders = [...stickyTable.tHead.rows[0].cells];
  sourceHeaders.forEach((header, index) => {
    const width = header.getBoundingClientRect().width;
    if (stickyHeaders[index]) stickyHeaders[index].style.width = `${width}px`;
  });

  const shouldShow = sourceHeadRect.bottom <= stickyTop
    && sourceTableRect.bottom > stickyTop + sourceHeadRect.height;
  stickyHeader.classList.toggle("is-visible", shouldShow);
  stickyHeader.setAttribute("aria-hidden", String(!shouldShow));
  stickyHeader.inert = !shouldShow;
}

function registerStickyTableHeader({ sourceTable, scrollContainer, stickyHeader, stickyViewport }) {
  const stickyTable = sourceTable.cloneNode(false);
  const stickyHead = sourceTable.tHead.cloneNode(true);
  stickyTable.classList.add("sticky-table-copy");
  stickyTable.appendChild(stickyHead);
  stickyViewport.appendChild(stickyTable);
  stickyTableHeaderControllers.push({
    sourceTable,
    scrollContainer,
    stickyHeader,
    stickyViewport,
    stickyTable,
  });
  scrollContainer.addEventListener("scroll", scheduleStickyTableHeadersSync, { passive: true });
}

function initializeStickyTableHeaders() {
  registerStickyTableHeader({
    sourceTable: elements.clearanceTable,
    scrollContainer: elements.clearanceTableWrap,
    stickyHeader: elements.clearanceStickyHeader,
    stickyViewport: elements.clearanceStickyViewport,
  });
  registerStickyTableHeader({
    sourceTable: elements.holdingsTable,
    scrollContainer: elements.holdingsContent,
    stickyHeader: elements.holdingsStickyHeader,
    stickyViewport: elements.holdingsStickyViewport,
  });
  window.addEventListener("scroll", scheduleStickyTableHeadersSync, { passive: true });
  window.addEventListener("resize", scheduleStickyTableHeadersSync);
  const stickyHeaderResizeObserver = new ResizeObserver(scheduleStickyTableHeadersSync);
  stickyHeaderResizeObserver.observe(elements.topbar);
  stickyHeaderResizeObserver.observe(elements.clearanceTableWrap);
  stickyHeaderResizeObserver.observe(elements.holdingsContent);
  stickyTableHeaderControllers.forEach(syncStickyTableHeader);
}

function drawerRow(label, value, extraClass = "") {
  const row = makeElement("div", "drawer-row");
  row.append(makeElement("dt", "", label), makeElement("dd", extraClass, value));
  return row;
}

function activeChartPayload() {
  return state.chartView === "intraday" ? state.intradayPayload : state.klinePayload;
}

function activeIndicatorSelection() {
  return state.chartView === "intraday" ? state.intradayIndicators : state.klineIndicators;
}

function setActiveIndicatorSelection(selection) {
  if (state.chartView === "intraday") state.intradayIndicators = selection;
  else state.klineIndicators = selection;
}

function activeIndicatorStorageKey() {
  return state.chartView === "intraday"
    ? INTRADAY_INDICATOR_STORAGE_KEY
    : DAILY_INDICATOR_STORAGE_KEY;
}

function availableKlineIndicatorNames(payload = activeChartPayload()) {
  const advertised = payload?.technical_indicators?.available;
  return normalizeTechnicalIndicatorSelection(
    TECHNICAL_INDICATOR_NAMES,
    Array.isArray(advertised) ? advertised : TECHNICAL_INDICATOR_NAMES,
  );
}

function selectedKlineIndicatorNames(payload = activeChartPayload()) {
  return normalizeTechnicalIndicatorSelection(
    activeIndicatorSelection(),
    availableKlineIndicatorNames(payload),
  );
}

function klineIndicatorSelectionText(names) {
  if (!names.length) return "未显示副图";
  const labels = names.map((name) => TECHNICAL_INDICATOR_LABELS.get(name) || name);
  if (labels.length <= 3) return labels.join(" / ");
  return `${labels.slice(0, 3).join(" / ")} 等 ${labels.length} 项`;
}

function persistKlineIndicatorSelection() {
  localStorage.setItem(
    activeIndicatorStorageKey(),
    JSON.stringify(normalizeTechnicalIndicatorSelection(activeIndicatorSelection())),
  );
}

function renderKlineIndicatorControls(payload = activeChartPayload()) {
  const available = new Set(availableKlineIndicatorNames(payload));
  const selected = selectedKlineIndicatorNames(payload);
  const selectedSet = new Set(selected);
  const hasAdvertisedCatalog = Array.isArray(payload?.technical_indicators?.available);
  document.querySelectorAll("[data-kline-indicator]").forEach((button) => {
    const name = button.dataset.klineIndicator;
    const supported = available.has(name);
    const active = supported && selectedSet.has(name);
    button.disabled = hasAdvertisedCatalog && !supported;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const summary = document.getElementById("klineIndicatorSelection");
  if (summary) summary.textContent = klineIndicatorSelectionText(selected);
  const hint = document.getElementById("klineIndicatorHint");
  if (hint) {
    const calculation = payload?.technical_indicators?.calculation;
    const engine = calculation
      ? `${calculation.engine} ${calculation.engine_version}`
      : "KLineChart v10";
    hint.textContent = state.chartView === "intraday"
      ? `由所选日期原始分钟行情在浏览器内计算 · ${engine} 默认参数 · 日内均价固定显示 · 不落库，不构成交易信号。`
      : `由同批前复权日 K 在浏览器内计算 · ${engine} 默认参数 · 不落库；窗口不足时起始值留空，不构成交易信号。`;
  }
}

function setKlineChartHeight(payload = activeChartPayload()) {
  const container = document.getElementById("klineChart");
  if (!container) return;
  const compact = window.matchMedia("(max-width: 840px)").matches;
  const height = technicalIndicatorChartHeight(
    selectedKlineIndicatorNames(payload).length,
    compact,
  );
  const cssHeight = `${height}px`;
  if (container.style.height !== cssHeight) container.style.height = cssHeight;
}

function renderKlineStatus(payload = activeChartPayload()) {
  const status = document.getElementById("klineStatus");
  if (!status || !payload) return;
  const indicatorCount = selectedKlineIndicatorNames(payload).length;
  const indicatorText = indicatorCount ? `${indicatorCount} 个副图` : "无副图";
  status.className = `kline-status is-${payload.status}`;
  if (state.chartView === "intraday") {
    const frequency = payload.period?.label || "分钟精度待刷新";
    status.textContent = {
      ready: `${payload.trade_date} · ${payload.coverage.bar_count} 根 ${frequency}行情 · 日内均价 · ${indicatorText}`,
      missing: `${payload.trade_date} 本地尚无分钟行情缓存`,
      unsupported: `暂不支持 ${payload.instrument.asset_type} 资产的分钟行情`,
    }[payload.status] || payload.status;
    return;
  }
  status.textContent = {
    ready: `${rangeLabel(payload.range.key)} · ${payload.coverage.bar_count} 根日 K · 前复权 · ${indicatorText}`,
    incomplete: `数据不完整 · ${payload.coverage.gaps.length} 个覆盖缺口 · ${indicatorText}`,
    missing: "本地区间尚无 K 线缓存",
  }[payload.status] || payload.status;
}

function toggleKlineIndicator(name) {
  if (!availableKlineIndicatorNames().includes(name)) {
    showToast(`${name} 当前不可用`, true);
    return;
  }
  const indicators = activeIndicatorSelection();
  const enable = !indicators.has(name);
  if (state.chart) {
    const changed = setTechnicalIndicatorVisibility(state.chart, name, enable);
    if (enable && !changed) {
      showToast(`${name} 副图创建失败`, true);
      return;
    }
  }
  if (enable) indicators.add(name);
  else indicators.delete(name);
  setActiveIndicatorSelection(
    new Set(normalizeTechnicalIndicatorSelection(indicators)),
  );
  persistKlineIndicatorSelection();
  renderKlineIndicatorControls();
  renderKlineStatus();
  setKlineChartHeight();
  state.chart?.resize();
}

function replaceKlineIndicatorSelection(names) {
  setActiveIndicatorSelection(new Set(
    normalizeTechnicalIndicatorSelection(names, availableKlineIndicatorNames()),
  ));
  persistKlineIndicatorSelection();
  renderKlineIndicatorControls();
  renderKlineStatus();
  const payload = activeChartPayload();
  if (state.chart && payload?.bars?.length) {
    if (state.chartView === "intraday") renderIntradayChart(payload);
    else renderKlineChart(payload);
  } else {
    setKlineChartHeight();
  }
}

function disposeKlineChart() {
  state.chartResizeObserver?.disconnect();
  state.chartResizeObserver = null;
  const container = document.getElementById("klineChart");
  if (state.chart && container) dispose(container);
  state.chart = null;
}

function focusOperation(groupId) {
  document.querySelectorAll(".operation-group.is-focused").forEach((item) => {
    item.classList.remove("is-focused");
  });
  const target = document.getElementById(operationDomId(groupId));
  if (!target) return;
  target.classList.add("is-focused");
  target.scrollIntoView({ block: "nearest", behavior: "smooth" });
  target.focus({ preventScroll: true });
  window.setTimeout(() => target.classList.remove("is-focused"), 1800);
}

function showMarkerTooltip(groupId, payload) {
  const tooltip = document.getElementById("klineMarkerTooltip");
  if (!tooltip) return;
  const group = payload.operation_groups?.find((item) => item.group_id === groupId);
  if (!group) return;
  tooltip.textContent = payload.view === "intraday"
    ? `${group.label} ${group.event_date} ${group.mapped_bar_time?.slice(11, 19) || ""} · 实际成交均价 ${price(group.actual_price, payload.instrument.asset_type)} · 数量 ${quantity(group.quantity)} · 费用 ${money(group.fees)}`
    : `${group.label} ${group.event_date} · 原始价 ${price(group.actual_price, payload.instrument.asset_type)} · 前复权定位 ${price(group.adjusted_price, "etf")} · 数量 ${quantity(group.quantity)} · 费用 ${money(group.fees)}`;
  tooltip.classList.add("has-value");
}

function clearMarkerTooltip() {
  const tooltip = document.getElementById("klineMarkerTooltip");
  if (!tooltip) return;
  tooltip.textContent = state.chartView === "intraday"
    ? "悬浮成交标注可查看实际成交均价与分钟定位。"
    : "点击任意日 K 可自动更新并查看当日分时；悬浮操作标注可查看原始成交价与前复权定位价。";
  tooltip.classList.remove("has-value");
}

function renderKlineChart(payload) {
  disposeKlineChart();
  const container = document.getElementById("klineChart");
  if (!container || !payload.bars?.length) return;
  container.classList.add("is-daily");
  container.classList.remove("is-intraday");
  container.setAttribute(
    "aria-label",
    "前复权日 K 线与成交操作点；点击日 K 自动更新并查看当日分时",
  );
  setKlineChartHeight(payload);
  const chart = init(container, {
    locale: "zh-CN",
    timezone: "Asia/Shanghai",
    styles: {
      grid: {
        horizontal: { color: "#2b3038" },
        vertical: { color: "#22272e" },
      },
      candle: {
        type: "candle_solid",
        bar: {
          upColor: "#e5484d",
          downColor: "#30a46c",
          noChangeColor: "#8d8d86",
          upBorderColor: "#e5484d",
          downBorderColor: "#30a46c",
          noChangeBorderColor: "#8d8d86",
          upWickColor: "#e5484d",
          downWickColor: "#30a46c",
          noChangeWickColor: "#8d8d86",
        },
      },
      xAxis: { axisLine: { color: "#3a4048" }, tickText: { color: "#a9b0ba" } },
      yAxis: { axisLine: { color: "#3a4048" }, tickText: { color: "#a9b0ba" } },
    },
  });
  if (!chart) return;
  state.chart = chart;
  chart.setSymbol({
    ticker: payload.instrument.ts_code,
    pricePrecision: payload.instrument.price_precision || 4,
    volumePrecision: payload.instrument.volume_precision || 0,
  });
  chart.setPeriod({ span: 1, type: "day" });
  let overlaysCreated = false;
  chart.setDataLoader({
    getBars: ({ callback }) => {
      callback(normalizeBars(payload.bars), { forward: false, backward: false });
      if (overlaysCreated) return;
      overlaysCreated = true;
      window.requestAnimationFrame(() => {
        if (state.chart !== chart) return;
        buildOperationMarkers(payload.operation_groups).forEach((marker) => {
          chart.createOverlay({
            name: "portfolioOperation",
            lock: true,
            zLevel: 20,
            points: [{ timestamp: marker.timestamp, value: marker.value }],
            extendData: marker,
            onClick: () => focusOperation(marker.groupId),
            onMouseEnter: () => showMarkerTooltip(marker.groupId, payload),
            onMouseLeave: clearMarkerTooltip,
          });
        });
        chart.scrollToRealTime();
      });
    },
  });
  chart.subscribeAction("onCandleBarClick", (actionData) => {
    if (state.chart !== chart || state.chartView !== "daily") return;
    const tradeDate = candleClickTradeDate(actionData, payload.bars);
    if (!tradeDate) return;
    if (!tradeDateOnOrBeforeAsOf(tradeDate, payload.range?.as_of || state.asOf)) {
      showToast(`${tradeDate} 晚于当前回看日，无法查看分时`, true);
      return;
    }
    openIntradayForTradeDate(tradeDate);
  });
  selectedKlineIndicatorNames(payload).forEach((name) => {
    setTechnicalIndicatorVisibility(chart, name, true);
  });
  state.chartResizeObserver = new ResizeObserver(() => {
    setKlineChartHeight(payload);
    chart.resize();
  });
  state.chartResizeObserver.observe(container);
}

function renderIntradayChart(payload) {
  disposeKlineChart();
  const container = document.getElementById("klineChart");
  if (!container || !payload.bars?.length) return;
  container.classList.remove("is-daily");
  container.classList.add("is-intraday");
  container.setAttribute(
    "aria-label",
    `${payload.trade_date} 分时价格、日内均价与成交点`,
  );
  setKlineChartHeight(payload);
  const zoomLimits = intradayBarSpaceLimit(payload.period?.span);
  const chart = init(container, {
    locale: "zh-CN",
    timezone: "Asia/Shanghai",
    layout: { barSpaceLimit: zoomLimits },
    styles: {
      grid: {
        horizontal: { color: "#2b3038" },
        vertical: { color: "#22272e" },
      },
      candle: {
        type: "area",
        area: {
          lineSize: 2,
          lineColor: "#5b8def",
          value: "close",
          smooth: false,
          backgroundColor: [
            { offset: 0, color: "rgba(91, 141, 239, 0.30)" },
            { offset: 1, color: "rgba(91, 141, 239, 0.02)" },
          ],
          point: {
            show: false,
            color: "#5b8def",
            radius: 3,
            rippleColor: "rgba(91, 141, 239, 0.35)",
            rippleRadius: 8,
            animation: false,
            animationDuration: 0,
          },
        },
      },
      xAxis: { axisLine: { color: "#3a4048" }, tickText: { color: "#a9b0ba" } },
      yAxis: { axisLine: { color: "#3a4048" }, tickText: { color: "#a9b0ba" } },
    },
  });
  if (!chart) return;
  state.chart = chart;
  chart.setSymbol({
    ticker: payload.instrument.ts_code,
    pricePrecision: payload.instrument.price_precision || 4,
    volumePrecision: payload.instrument.volume_precision || 0,
  });
  chart.setPeriod({ span: Number(payload.period?.span || 1), type: "minute" });
  let overlaysCreated = false;
  chart.setDataLoader({
    getBars: ({ callback }) => {
      callback(normalizeBars(payload.bars), { forward: false, backward: false });
      if (overlaysCreated) return;
      overlaysCreated = true;
      window.requestAnimationFrame(() => {
        if (state.chart !== chart) return;
        chart.setBarSpace(
          intradayFitBarSpace(container.clientWidth, payload.bars.length, zoomLimits),
        );
        buildIntradayMarkers(payload.operation_groups).forEach((marker) => {
          chart.createOverlay({
            name: "portfolioOperation",
            lock: true,
            zLevel: 20,
            points: [{ timestamp: marker.timestamp, value: marker.value }],
            extendData: marker,
            onClick: () => focusOperation(marker.groupId),
            onMouseEnter: () => showMarkerTooltip(marker.groupId, payload),
            onMouseLeave: clearMarkerTooltip,
          });
        });
        chart.scrollToRealTime();
      });
    },
  });
  chart.createIndicator({ name: "INTRADAY_AVG", paneId: "candle_pane" });
  selectedKlineIndicatorNames(payload).forEach((name) => {
    setTechnicalIndicatorVisibility(chart, name, true);
  });
  state.chartResizeObserver = new ResizeObserver(() => {
    setKlineChartHeight(payload);
    chart.resize();
  });
  state.chartResizeObserver.observe(container);
}

function fitIntradayChartToDay() {
  if (state.chartView !== "intraday" || !state.chart || !state.intradayPayload?.bars?.length) {
    showToast("当前没有可适应的分时行情", true);
    return;
  }
  const container = document.getElementById("klineChart");
  if (!container) return;
  const zoomLimits = intradayBarSpaceLimit(state.intradayPayload.period?.span);
  state.chart.setBarSpace(
    intradayFitBarSpace(container.clientWidth, state.intradayPayload.bars.length, zoomLimits),
  );
  state.chart.scrollToRealTime();
}

function operationMappingText(group) {
  if (group.in_range === false) return "当前区间外";
  return {
    exact: "当日 K 线",
    mapped_previous_bar: "映射至此前交易日",
    missing_bar: "缺少对应 K 线",
    missing_factor: "缺少复权因子",
    mapped_1m_bucket: "映射至 1 分钟桶",
    mapped_5m_bucket: "映射至 5 分钟桶",
  }[group.mapping_status] || group.mapping_status;
}

function renderOperationList(payload) {
  const list = document.getElementById("operationList");
  const count = document.getElementById("operationCount");
  if (!list || !count) return;
  const groups = payload.operation_groups || [];
  const unlocatedCount = payload.unlocated_operations?.length || 0;
  count.textContent = `${groups.length} 个已定位组${unlocatedCount ? ` · ${unlocatedCount} 笔未定位` : ""}`;
  list.replaceChildren();
  if (!groups.length) {
    list.appendChild(makeElement("p", "operation-empty", payload.view === "intraday"
      ? "所选日期没有已定位的买卖流水。"
      : "本轮没有可标注的期初、买入或卖出记录。"));
  }

  groups.forEach((group) => {
    const item = makeElement(
      "article",
      `operation-group operation-${group.event_type.toLowerCase()}${group.in_range === false ? " is-outside" : ""}`,
    );
    item.id = operationDomId(group.group_id);
    item.tabIndex = -1;
    const heading = makeElement("div", "operation-heading");
    const titleWrap = makeElement("div");
    titleWrap.append(
      makeElement("span", "operation-label", group.label),
      makeElement("strong", "", group.event_date),
    );
    heading.append(
      titleWrap,
      makeElement("span", "operation-mapping", operationMappingText(group)),
    );

    const metrics = makeElement("dl", "operation-metrics");
    const actualLabel = group.event_type === "OPENING" ? "期初成本参考" : "原始成交均价";
    metrics.append(drawerRow(actualLabel, price(group.actual_price, payload.instrument.asset_type), "sensitive"));
    if (payload.view !== "intraday") {
      metrics.append(drawerRow("前复权定位价", price(group.adjusted_price, "etf"), "sensitive"));
    }
    metrics.append(
      drawerRow("合计数量", quantity(group.quantity), "sensitive"),
      drawerRow("合计费用", money(group.fees), "sensitive"),
    );

    const details = makeElement("details", "operation-entries");
    const summary = makeElement("summary", "", `${group.entry_count} 笔原始流水`);
    const entryList = makeElement("ol");
    (group.entries || []).forEach((entry) => {
      const entryItem = makeElement("li");
      const eventTime = entry.event_time || "未记录时间";
      const priceText = group.event_type === "OPENING"
        ? `总成本 ${money(entry.total_cost)}`
        : `成交价 ${price(entry.price, payload.instrument.asset_type)} · 成交额 ${money(entry.gross_amount)}`;
      entryItem.append(
        makeElement("span", "", `${eventTime} · 数量 ${quantity(entry.quantity)}`),
        makeElement("span", "sensitive", `${priceText} · 费用 ${money(entry.fees)}`),
      );
      entryList.appendChild(entryItem);
    });
    details.append(summary, entryList);
    item.append(heading, metrics, details);
    list.appendChild(item);
  });

  const unlocatedList = document.getElementById("unlocatedOperationList");
  if (!unlocatedList) return;
  unlocatedList.replaceChildren();
  const unlocatedSection = document.getElementById("unlocatedOperationSection");
  if (unlocatedSection) {
    unlocatedSection.hidden = !(payload.unlocated_operations || []).length;
  }
  const reasonLabels = {
    missing_event_time: "交割单未记录成交时间",
    invalid_event_time: "成交时间格式无效",
    outside_session: "成交时间在交易时段外",
    missing_bar: "对应交易时段缺少分钟条",
  };
  (payload.unlocated_operations || []).forEach((entry) => {
    const row = makeElement("article", "unlocated-operation");
    row.append(
      makeElement("strong", "", reasonLabels[entry.reason] || entry.reason),
      makeElement("span", "", `${entry.event_date} ${entry.event_time || "时间未知"} · ${entry.event_type}`),
      makeElement("span", "sensitive", `数量 ${quantity(entry.quantity)} · 成交价 ${price(entry.price, payload.instrument.asset_type)} · 来源行 ${entry.source_row ?? "—"}`),
    );
    unlocatedList.appendChild(row);
  });
}

function renderKlinePayload(payload) {
  state.klinePayload = payload;
  renderKlineIndicatorControls(payload);
  const coverage = document.getElementById("klineCoverage");
  const chartContainer = document.getElementById("klineChart");
  const empty = document.getElementById("klineEmpty");
  document.querySelectorAll("[data-kline-range]").forEach((button) => {
    const active = button.dataset.klineRange === payload.range.key;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  renderKlineStatus(payload);
  if (coverage) {
    const source = [...(payload.sources.bars || []), ...(payload.sources.factors || [])].join(" + ") || "MISSING";
    const outside = payload.coverage.out_of_range_operation_group_count
      ? ` · ${payload.coverage.out_of_range_operation_group_count} 个操作在当前区间外`
      : "";
    coverage.textContent = `行情 ${payload.coverage.first_trade_date || "—"} → ${payload.coverage.last_trade_date || "—"} · 锚定 ${payload.adjustment.anchor_date || "—"} · ${source}${outside} · 更新 ${formatFetchTime(payload.fetched_at)}`;
  }
  renderOperationList(payload);
  if (payload.bars?.length) {
    chartContainer.hidden = false;
    empty.hidden = true;
    renderKlineChart(payload);
  } else {
    disposeKlineChart();
    chartContainer.hidden = true;
    empty.hidden = false;
    empty.textContent = payload.coverage.bar_count
      ? "复权因子或操作定位数据不完整；为避免误导，未绘制未复权 K 线。"
      : "点击“更新 K 线”后才会访问 Tushare；打开详情本身不会联网。";
  }
  clearMarkerTooltip();
}

function renderIntradayDateControls(payload) {
  const input = document.getElementById("intradayDateInput");
  const select = document.getElementById("intradayTradeDateSelect");
  if (input) input.value = payload.trade_date || "";
  if (!select) return;
  select.replaceChildren();
  const placeholder = makeElement("option", "", "本轮成交日");
  placeholder.value = "";
  select.appendChild(placeholder);
  (payload.available_trade_dates || []).forEach((item) => {
    const option = makeElement(
      "option",
      "",
      `${item.trade_date} · ${item.trade_count} 笔${item.with_time_count < item.trade_count ? " · 含未知时间" : ""}`,
    );
    option.value = item.trade_date;
    select.appendChild(option);
  });
  select.value = (payload.available_trade_dates || []).some(
    (item) => item.trade_date === payload.trade_date,
  ) ? payload.trade_date : "";
}

function renderIntradayPayload(payload) {
  state.intradayPayload = payload;
  renderIntradayDateControls(payload);
  renderKlineIndicatorControls(payload);
  renderKlineStatus(payload);
  const coverage = document.getElementById("klineCoverage");
  const chartContainer = document.getElementById("klineChart");
  const empty = document.getElementById("klineEmpty");
  if (coverage) {
    const source = payload.source?.provider || "MISSING";
    const dateScopeLabels = {
      pre_open_context: "建仓前上下文",
      post_close_context: "清仓后上下文",
      cycle: "本轮周期",
    };
    const dateScope = dateScopeLabels[payload.date_scope] || "日期范围待确认";
    const precision = payload.source?.frequency_minutes
      ? `${payload.source.frequency_minutes} 分钟`
      : "精度待刷新";
    const fallbackLabels = {
      missing_credentials: "缺少 Tushare 凭据",
      permission_denied: "Tushare 权限不足",
      empty_response: "Tushare 返回为空",
      invalid_response: "Tushare 数据校验失败",
      dependency_missing: "上游依赖缺失",
      network_error: "上游网络失败",
      upstream_error: "上游调用失败",
    };
    const fallback = payload.source?.fallback_reason
      ? ` · 回退原因 ${fallbackLabels[payload.source.fallback_reason] || payload.source.fallback_reason}`
      : "";
    coverage.textContent = `${payload.trade_date} · ${dateScope} · ${source} · ${precision}${fallback} · 已定位 ${payload.operation_mapping?.mapped_count || 0} 笔 / 未定位 ${payload.operation_mapping?.unlocated_count || 0} 笔 · 更新 ${formatFetchTime(payload.source?.fetched_at)}`;
  }
  renderOperationList(payload);
  if (payload.bars?.length) {
    chartContainer.hidden = false;
    empty.hidden = true;
    renderIntradayChart(payload);
  } else {
    disposeKlineChart();
    chartContainer.hidden = true;
    empty.hidden = false;
    empty.textContent = payload.status === "unsupported"
      ? `暂不支持 ${payload.instrument.asset_type} 资产的分钟行情；不会猜测数据接口。`
      : "交割单成交日会自动更新；非成交日默认读取 SQLite 缓存，也可手动点击“更新分时”。";
  }
  clearMarkerTooltip();
}

function intradayRequestParams(tradeDate = null) {
  const context = state.drawerContext;
  if (!context) return null;
  return {
    ts_code: context.item.ts_code,
    trade_date: tradeDate || context.intradayDate || null,
    cycle_id: context.item.cycle_id || null,
    as_of: state.asOf,
  };
}

async function loadIntraday(tradeDate = null, options = {}) {
  if (!state.drawerContext) return;
  const autoRefreshTradeDate = Boolean(options?.autoRefreshTradeDate);
  if (tradeDate) state.drawerContext.intradayDate = tradeDate;
  const params = intradayRequestParams(tradeDate);
  const query = new URLSearchParams({ ts_code: params.ts_code });
  if (params.trade_date) query.set("trade_date", params.trade_date);
  if (params.cycle_id) query.set("cycle_id", params.cycle_id);
  if (params.as_of) query.set("as_of", params.as_of);
  const requestId = ++state.drawerRequestId;
  const status = document.getElementById("klineStatus");
  if (status) {
    status.className = "kline-status is-loading";
    status.textContent = "正在读取本地分钟行情缓存";
  }
  try {
    const payload = await api(`/api/intraday?${query.toString()}`);
    if (requestId !== state.drawerRequestId || state.chartView !== "intraday") return;
    state.drawerContext.intradayDate = payload.trade_date;
    if (
      autoRefreshTradeDate
      && (payload.available_trade_dates || []).some(
        (item) => item.trade_date === payload.trade_date,
      )
    ) {
      state.intradayPayload = payload;
      renderIntradayDateControls(payload);
      if (status) {
        status.className = "kline-status is-loading";
        status.textContent = `正在自动更新 ${payload.trade_date} 成交日分时`;
      }
      await refreshIntraday({ tradeDate: payload.trade_date, automatic: true });
      return;
    }
    renderIntradayPayload(payload);
  } catch (error) {
    if (requestId !== state.drawerRequestId) return;
    if (status) {
      status.className = "kline-status is-error";
      status.textContent = `分时读取失败：${error.message}`;
    }
  }
}

async function refreshIntraday(options = {}) {
  const requestedTradeDate = options?.tradeDate || null;
  const automatic = Boolean(options?.automatic);
  const dateInput = document.getElementById("intradayDateInput");
  const params = intradayRequestParams(requestedTradeDate || dateInput?.value || null);
  const button = document.getElementById("intradayRefreshButton");
  if (!params || !params.trade_date || !button) {
    showToast("请先选择分时日期", true);
    return;
  }
  button.disabled = true;
  button.textContent = automatic ? "自动更新中" : "更新中";
  const requestId = ++state.drawerRequestId;
  try {
    const payload = await api("/api/refresh-intraday", {
      method: "POST",
      headers: { "X-Portfolio-Action": "refresh-intraday" },
      body: JSON.stringify(params),
    });
    if (requestId !== state.drawerRequestId || state.chartView !== "intraday") return;
    state.drawerContext.intradayDate = payload.trade_date;
    renderIntradayPayload(payload);
    showToast(`${automatic ? "已自动更新" : "已更新"} ${payload.refresh?.fetched_bars || 0} 根分钟行情`);
  } catch (error) {
    if (requestId === state.drawerRequestId) {
      showToast(`分时更新失败：${error.message}`, true);
      if (automatic && state.chartView === "intraday") {
        await loadIntraday(params.trade_date);
      } else {
        const status = document.getElementById("klineStatus");
        if (status) {
          status.className = "kline-status is-error";
          status.textContent = `更新失败，保留原缓存：${error.message}`;
        }
      }
    }
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.textContent = "更新分时";
    }
  }
}

function openIntradayForTradeDate(tradeDate) {
  if (!state.drawerContext) return;
  state.drawerContext.intradayDate = tradeDate;
  state.intradayPayload = null;
  switchChartView("intraday", { skipLoad: true });
  const dateInput = document.getElementById("intradayDateInput");
  if (dateInput) dateInput.value = tradeDate;
  const status = document.getElementById("klineStatus");
  if (status) {
    status.className = "kline-status is-loading";
    status.textContent = `正在自动更新 ${tradeDate} 分时`;
  }
  const coverage = document.getElementById("klineCoverage");
  if (coverage) coverage.textContent = `${tradeDate} · 正在请求分钟行情`;
  void refreshIntraday({ tradeDate, automatic: true });
}

function isLedgerTradeDate(tradeDate) {
  const normalizedDate = String(tradeDate || "");
  if (
    (state.intradayPayload?.available_trade_dates || []).some(
      (item) => item.trade_date === normalizedDate,
    )
  ) {
    return true;
  }
  return (state.klinePayload?.operation_groups || []).some(
    (item) => (
      ["BUY", "SELL"].includes(String(item?.event_type || "").toUpperCase())
      && item.event_date === normalizedDate
    ),
  );
}

function openIntradayForLatestTradeDate() {
  const tradeDate = latestLedgerTradeDate(
    state.klinePayload?.operation_groups || [],
    state.asOf,
  );
  if (tradeDate) {
    openIntradayForTradeDate(tradeDate);
    return;
  }
  switchChartView("intraday", { skipLoad: true });
  void loadIntraday(null, { autoRefreshTradeDate: true });
}

function switchChartView(view, options = {}) {
  if (!state.drawerContext || !["daily", "intraday"].includes(view)) return;
  const skipLoad = Boolean(options?.skipLoad);
  state.chartView = view;
  state.drawerRequestId += 1;
  disposeKlineChart();
  document.querySelectorAll("[data-chart-view]").forEach((button) => {
    const active = button.dataset.chartView === view;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const dailyControls = document.getElementById("dailyKlineControls");
  const intradayControls = document.getElementById("intradayControls");
  if (dailyControls) dailyControls.hidden = view !== "daily";
  if (intradayControls) intradayControls.hidden = view !== "intraday";
  const tooltip = document.getElementById("klineMarkerTooltip");
  if (tooltip) tooltip.textContent = view === "daily"
    ? "点击任意日 K 可自动更新并查看当日分时；悬浮操作标注可查看原始成交价与前复权定位价。"
    : "悬浮成交标注可查看实际成交均价与分钟定位。";
  if (view === "daily") {
    if (state.klinePayload) renderKlinePayload(state.klinePayload);
    else loadKline(state.drawerContext.range || "3m");
  } else if (skipLoad) {
    renderKlineIndicatorControls(null);
    const chartContainer = document.getElementById("klineChart");
    const empty = document.getElementById("klineEmpty");
    if (chartContainer) chartContainer.hidden = true;
    if (empty) {
      empty.hidden = false;
      empty.textContent = "正在自动更新所选日期的分时行情";
    }
  } else if (state.intradayPayload) {
    renderIntradayPayload(state.intradayPayload);
  } else {
    loadIntraday();
  }
}

function klineRequestParams() {
  const context = state.drawerContext;
  if (!context) return null;
  return {
    ts_code: context.item.ts_code,
    range: context.range,
    cycle_id: context.item.cycle_id || null,
    as_of: state.asOf,
  };
}

async function loadKline(rangeKey) {
  if (!state.drawerContext) return;
  state.drawerContext.range = rangeKey;
  const params = klineRequestParams();
  const query = new URLSearchParams({ ts_code: params.ts_code, range: params.range });
  if (params.cycle_id) query.set("cycle_id", params.cycle_id);
  if (params.as_of) query.set("as_of", params.as_of);
  const requestId = ++state.drawerRequestId;
  const status = document.getElementById("klineStatus");
  if (status) {
    status.className = "kline-status is-loading";
    status.textContent = `正在读取${rangeLabel(rangeKey)}本地缓存`;
  }
  try {
    const payload = await api(`/api/kline?${query.toString()}`);
    if (requestId !== state.drawerRequestId || !state.drawerContext) return;
    renderKlinePayload(payload);
  } catch (error) {
    if (requestId !== state.drawerRequestId) return;
    if (status) {
      status.className = "kline-status is-error";
      status.textContent = `K 线读取失败：${error.message}`;
    }
  }
}

async function refreshKline() {
  const params = klineRequestParams();
  const button = document.getElementById("klineRefreshButton");
  if (!params || !button) return;
  button.disabled = true;
  button.textContent = "更新中";
  const requestId = ++state.drawerRequestId;
  try {
    const payload = await api("/api/refresh-kline", {
      method: "POST",
      headers: { "X-Portfolio-Action": "refresh-kline" },
      body: JSON.stringify(params),
    });
    if (requestId !== state.drawerRequestId || !state.drawerContext) return;
    renderKlinePayload(payload);
    showToast(`已更新 ${payload.refresh?.fetched_bars || 0} 根 K 线`);
  } catch (error) {
    if (requestId === state.drawerRequestId) {
      const status = document.getElementById("klineStatus");
      if (status) {
        status.className = "kline-status is-error";
        status.textContent = `更新失败，保留原缓存：${error.message}`;
      }
      showToast(`K 线更新失败：${error.message}`, true);
    }
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.textContent = "更新 K 线";
    }
  }
}

function createKlinePanel() {
  const panel = makeElement("section", "kline-panel");
  const heading = makeElement("header", "kline-heading");
  const headingText = makeElement("div");
  headingText.append(
    makeElement("p", "section-kicker", "OPERATION REVIEW"),
    makeElement("h3", "", "行情与操作点"),
  );
  const controls = makeElement("div", "kline-controls");
  controls.id = "dailyKlineControls";
  [
    ["3m", "3 个月"],
    ["1y", "1 年"],
    ["cycle", "本轮"],
  ].forEach(([key, label]) => {
    const button = makeElement("button", `kline-range-button${key === "3m" ? " is-active" : ""}`, label);
    button.type = "button";
    button.dataset.klineRange = key;
    button.setAttribute("aria-pressed", String(key === "3m"));
    button.addEventListener("click", () => loadKline(key));
    controls.appendChild(button);
  });
  const refresh = makeElement("button", "kline-refresh-button", "更新 K 线");
  refresh.id = "klineRefreshButton";
  refresh.type = "button";
  refresh.addEventListener("click", refreshKline);
  controls.appendChild(refresh);
  heading.append(headingText, controls);

  const viewTabs = makeElement("div", "chart-view-tabs");
  [["daily", "日 K"], ["intraday", "分时"]].forEach(([view, label]) => {
    const button = makeElement(
      "button",
      `chart-view-tab${view === "daily" ? " is-active" : ""}`,
      label,
    );
    button.type = "button";
    button.dataset.chartView = view;
    button.setAttribute("aria-pressed", String(view === "daily"));
    button.addEventListener("click", () => {
      if (view === "intraday") openIntradayForLatestTradeDate();
      else switchChartView(view);
    });
    viewTabs.appendChild(button);
  });

  const intradayControls = makeElement("div", "intraday-controls");
  intradayControls.id = "intradayControls";
  intradayControls.hidden = true;
  const dateInput = makeElement("input", "intraday-date-input");
  dateInput.id = "intradayDateInput";
  dateInput.type = "date";
  dateInput.setAttribute("aria-label", "分时交易日");
  dateInput.addEventListener("change", () => {
    if (!dateInput.value) return;
    if (isLedgerTradeDate(dateInput.value)) openIntradayForTradeDate(dateInput.value);
    else loadIntraday(dateInput.value);
  });
  const tradeDateSelect = makeElement("select", "intraday-date-select");
  tradeDateSelect.id = "intradayTradeDateSelect";
  tradeDateSelect.setAttribute("aria-label", "本轮成交日快捷选择");
  tradeDateSelect.addEventListener("change", () => {
    if (tradeDateSelect.value) openIntradayForTradeDate(tradeDateSelect.value);
  });
  const intradayRefresh = makeElement("button", "kline-refresh-button", "更新分时");
  intradayRefresh.id = "intradayRefreshButton";
  intradayRefresh.type = "button";
  intradayRefresh.addEventListener("click", refreshIntraday);
  const intradayFit = makeElement("button", "kline-refresh-button", "适应全日");
  intradayFit.id = "intradayFitButton";
  intradayFit.type = "button";
  intradayFit.addEventListener("click", fitIntradayChartToDay);
  intradayControls.append(dateInput, tradeDateSelect, intradayRefresh, intradayFit);

  const status = makeElement("p", "kline-status is-loading", "正在读取本地缓存");
  status.id = "klineStatus";
  const indicatorPicker = makeElement("details", "kline-indicator-picker");
  const indicatorSummary = makeElement("summary", "kline-indicator-summary");
  indicatorSummary.append(
    makeElement("span", "", "副图指标"),
    makeElement("strong", "", "成交量"),
  );
  indicatorSummary.lastChild.id = "klineIndicatorSelection";
  const indicatorBody = makeElement("div", "kline-indicator-body");
  const indicatorActions = makeElement("div", "kline-indicator-actions");
  const restoreIndicators = makeElement("button", "kline-indicator-action", "恢复默认");
  restoreIndicators.type = "button";
  restoreIndicators.addEventListener("click", () => {
    replaceKlineIndicatorSelection(
      activeChartPayload()?.technical_indicators?.default_selected
        || DEFAULT_TECHNICAL_INDICATORS,
    );
  });
  const clearIndicators = makeElement("button", "kline-indicator-action", "隐藏全部");
  clearIndicators.type = "button";
  clearIndicators.addEventListener("click", () => replaceKlineIndicatorSelection([]));
  indicatorActions.append(restoreIndicators, clearIndicators);
  const indicatorGroups = makeElement("div", "kline-indicator-groups");
  TECHNICAL_INDICATOR_GROUPS.forEach((group) => {
    const groupElement = makeElement("section", "kline-indicator-group");
    groupElement.appendChild(makeElement("h4", "", group.label));
    const optionList = makeElement("div", "kline-indicator-options");
    group.items.forEach((item) => {
      const label = item.label === item.name ? item.name : `${item.label} · ${item.name}`;
      const button = makeElement("button", "kline-indicator-option", label);
      button.type = "button";
      button.dataset.klineIndicator = item.name;
      button.title = item.description;
      button.setAttribute("aria-label", `${label}：${item.description}`);
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => toggleKlineIndicator(item.name));
      optionList.appendChild(button);
    });
    groupElement.appendChild(optionList);
    indicatorGroups.appendChild(groupElement);
  });
  const indicatorHint = makeElement(
    "p",
    "kline-indicator-hint",
    "由同批前复权日 K 在浏览器内计算；窗口不足时起始值留空，不构成交易信号。",
  );
  indicatorHint.id = "klineIndicatorHint";
  indicatorBody.append(indicatorActions, indicatorGroups, indicatorHint);
  indicatorPicker.append(indicatorSummary, indicatorBody);
  const chart = makeElement("div", "kline-chart");
  chart.id = "klineChart";
  chart.setAttribute("aria-label", "前复权日 K 线与成交操作点");
  const empty = makeElement("div", "kline-empty", "正在读取本地 K 线缓存");
  empty.id = "klineEmpty";
  empty.hidden = true;
  const markerTooltip = makeElement(
    "p",
    "kline-marker-tooltip sensitive",
    "点击任意日 K 可自动更新并查看当日分时；悬浮操作标注可查看原始成交价与前复权定位价。",
  );
  markerTooltip.id = "klineMarkerTooltip";
  const coverage = makeElement("p", "kline-coverage", "行情覆盖待读取");
  coverage.id = "klineCoverage";
  const operationHeading = makeElement("div", "operation-list-heading");
  operationHeading.append(
    makeElement("h4", "", "本轮操作流水"),
    makeElement("span", "", "—"),
  );
  operationHeading.lastChild.id = "operationCount";
  const operationList = makeElement("div", "operation-list");
  operationList.id = "operationList";
  const unlocatedSection = makeElement("section", "unlocated-operation-section");
  unlocatedSection.id = "unlocatedOperationSection";
  unlocatedSection.hidden = true;
  unlocatedSection.appendChild(makeElement("h4", "", "时间未知 / 未定位成交"));
  const unlocatedList = makeElement("div", "unlocated-operation-list");
  unlocatedList.id = "unlocatedOperationList";
  unlocatedSection.appendChild(unlocatedList);
  panel.append(
    heading,
    viewTabs,
    intradayControls,
    status,
    indicatorPicker,
    chart,
    empty,
    markerTooltip,
    coverage,
    operationHeading,
    operationList,
    unlocatedSection,
  );
  return panel;
}

function openDrawer(item, kind = "position") {
  disposeKlineChart();
  state.drawerRequestId += 1;
  state.klinePayload = null;
  state.intradayPayload = null;
  state.chartView = "daily";
  state.drawerContext = { item, kind, range: "3m", intradayDate: null };
  elements.drawerContent.replaceChildren();
  const closed = kind === "closed";
  const kicker = makeElement("p", "section-kicker", closed ? "CLOSED CYCLE" : "POSITION DETAIL");
  const title = makeElement("h2", "", item.name);
  title.id = "drawerTitle";
  const cycleLabel = item.cycle_number ? ` · 第 ${item.cycle_number} 轮` : "";
  const code = makeElement("p", "drawer-code", `${item.ts_code} · ${item.asset_type.toUpperCase()}${cycleLabel}`);
  const pnl = makeElement(
    "p",
    `drawer-pnl sensitive ${toneClass(closed ? item.realized_pnl : item.unrealized_pnl)}`,
    money(closed ? item.realized_pnl : item.unrealized_pnl, true),
  );
  const returnValue = makeElement(
    "p",
    `drawer-return ${toneClass(item.return_pct)}`,
    `${percent(item.return_pct, true)} ${closed ? "清仓收益率" : "浮动收益率"}`,
  );
  const grid = makeElement("dl", "drawer-grid");
  if (closed) {
    grid.append(
      drawerRow("行业分类", item.industry_name || "未分类"),
      drawerRow("持有区间", `${item.opened_on} → ${item.closed_on}`),
      drawerRow("清仓数量", quantity(item.sold_quantity), "sensitive"),
      drawerRow("结转成本", money(item.cost_basis), "sensitive"),
      drawerRow("净卖出额", money(item.net_sale_proceeds), "sensitive"),
      drawerRow("交易盈亏", money(item.trading_pnl, true), "sensitive"),
      drawerRow("现金收入", money(item.cash_income), "sensitive"),
      drawerRow("现金税费", money(item.cash_fees), "sensitive"),
    );
  } else {
    grid.append(
      drawerRow("行业分类", item.industry_name || "未分类"),
      drawerRow("本轮开始", item.opened_on || "MISSING"),
      drawerRow("持仓数量", quantity(item.quantity), "sensitive"),
      drawerRow("平均成本", price(item.average_cost, item.asset_type), "sensitive"),
      drawerRow("剩余成本", money(item.remaining_cost), "sensitive"),
      drawerRow(
        item.is_live ? "盘中最新价" : "最新收盘价",
        price(item.close, item.asset_type),
      ),
      drawerRow("最新市值", money(item.market_value), "sensitive"),
      drawerRow("组合权重", percent(item.weight_pct), "sensitive"),
      drawerRow("当日涨跌", percent(item.pct_chg, true), toneClass(item.pct_chg)),
      drawerRow("已实现盈亏", money(item.realized_pnl, true), "sensitive"),
    );
  }
  const source = makeElement(
    "p",
    "drawer-source",
    closed
      ? `核算来源 ${item.calculation_source || "MISSING"}\n行业来源 ${item.industry_source || "MISSING"}\n操作点仅来自该轮 ledger_entries`
      : `行情日期 ${item.price_date || "MISSING"}\n行情时间 ${item.quote_time || "正式收盘"}\n行情来源 ${item.price_source || "MISSING"}\n成本口径 ${item.cost_basis_method || "ledger_entries.diluted_cost"}\n成本状态 ${item.cost_basis_status || "ledger_only"}\n成本锚点 ${item.cost_basis_source_path || "MISSING"}\n行业来源 ${item.industry_source || "MISSING"}`,
  );
  source.style.whiteSpace = "pre-line";
  elements.drawerContent.append(
    kicker,
    title,
    code,
    pnl,
    returnValue,
    grid,
    source,
    createKlinePanel(),
  );
  renderKlineIndicatorControls();
  elements.drawerBackdrop.hidden = false;
  elements.detailDrawer.classList.add("is-open");
  elements.detailDrawer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  elements.drawerClose.focus();
  loadKline("3m");
}

function closeDrawer() {
  state.drawerRequestId += 1;
  state.drawerContext = null;
  state.klinePayload = null;
  state.intradayPayload = null;
  state.chartView = "daily";
  disposeKlineChart();
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

function updateClearanceSortIndicators() {
  document.querySelectorAll("[data-clearance-sort]").forEach((button) => {
    const active = button.dataset.clearanceSort === state.clearanceSortKey;
    button.classList.toggle("is-sorted", active);
    button.dataset.direction = active
      ? (state.clearanceSortDirection === "asc" ? "↑" : "↓")
      : "";
    button.closest("th").setAttribute(
      "aria-sort",
      active ? (state.clearanceSortDirection === "asc" ? "ascending" : "descending") : "none",
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
  document.querySelectorAll("[data-performance-range]").forEach((button) => {
    button.addEventListener("click", () => {
      state.performanceRange = button.dataset.performanceRange;
      renderPerformance();
    });
    button.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const buttons = [...document.querySelectorAll("[data-performance-range]")];
      const offset = event.key === 'ArrowRight' ? 1 : -1;
      const nextIndex = (buttons.indexOf(button) + offset + buttons.length) % buttons.length;
      buttons[nextIndex].click();
      buttons[nextIndex].focus();
    });
  });
  elements.performanceLookbackSelect.addEventListener("change", (event) => {
    state.performanceLookbackMonths = event.target.value;
    state.performanceRange = "lookback";
    localStorage.setItem(
      "portfolioPerformanceLookbackMonths",
      state.performanceLookbackMonths,
    );
    renderPerformance();
  });

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

  document.querySelectorAll(".holdings-table thead").forEach((header) => header.addEventListener("click", (event) => {
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
  }));

  document.querySelectorAll(".clearance-table thead").forEach((header) => header.addEventListener("click", (event) => {
    const button = event.target.closest("[data-clearance-sort]");
    if (!button) return;
    const nextKey = button.dataset.clearanceSort;
    if (state.clearanceSortKey === nextKey) {
      state.clearanceSortDirection = state.clearanceSortDirection === "asc" ? "desc" : "asc";
    } else {
      state.clearanceSortKey = nextKey;
      state.clearanceSortDirection = nextKey === "name" ? "asc" : "desc";
    }
    renderClearance();
  }));

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
initializeCollapsibleModules();
initializeStickyTableHeaders();
bindEvents();
startRealtimeTimer();
loadPortfolio();
