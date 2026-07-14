const EVENT_PRIORITY = { OPENING: 0, BUY: 1, SELL: 2 };

export const TECHNICAL_INDICATOR_GROUPS = Object.freeze([
  {
    label: "成交与量价",
    items: [
      { name: "VOL", label: "成交量", description: "成交量柱状副图" },
      { name: "OBV", label: "能量潮", description: "按涨跌方向累计成交量" },
      { name: "VR", label: "成交量比率", description: "比较上涨、下跌与平盘成交量" },
      { name: "EMV", label: "简易波动", description: "结合价格区间、成交量与成交额" },
      { name: "PVT", label: "量价趋势", description: "累计价格变动与成交量的关系" },
      { name: "AVP", label: "平均成交价", description: "基于成交额与成交量的平均价格" },
    ],
  },
  {
    label: "趋势",
    items: [
      { name: "MACD", label: "MACD", description: "指数平滑异同移动平均" },
      { name: "DMI", label: "趋向指标", description: "衡量方向性变化与趋势强度" },
      { name: "DMA", label: "平行线差", description: "不同周期均线差及其均线" },
      { name: "TRIX", label: "三重平滑", description: "三重指数平滑变化率" },
      { name: "SAR", label: "抛物线", description: "抛物线转向指标" },
      { name: "BBI", label: "多空指标", description: "多周期移动平均的综合值" },
    ],
  },
  {
    label: "动量与摆动",
    items: [
      { name: "KDJ", label: "KDJ", description: "随机指标" },
      { name: "RSI", label: "相对强弱", description: "比较一段窗口内的涨跌幅度" },
      { name: "WR", label: "威廉指标", description: "收盘价在近期价格区间的位置" },
      { name: "BIAS", label: "乖离率", description: "价格相对移动平均的偏离程度" },
      { name: "CCI", label: "顺势指标", description: "典型价格相对均值的偏离程度" },
      { name: "MTM", label: "动量", description: "比较当前价格与历史价格" },
      { name: "ROC", label: "变动率", description: "价格相对历史窗口的变化率" },
      { name: "PSY", label: "心理线", description: "统计窗口内上涨交易日占比" },
      { name: "AO", label: "动量振荡", description: "不同周期中间价均值之差" },
    ],
  },
  {
    label: "均线与价格结构",
    items: [
      { name: "MA", label: "移动平均", description: "简单移动平均线" },
      { name: "EMA", label: "指数均线", description: "指数加权移动平均线" },
      { name: "SMA", label: "平滑均线", description: "平滑移动平均线" },
      { name: "BOLL", label: "布林带", description: "均线及标准差价格通道" },
      { name: "CR", label: "CR", description: "比较价格动量的多周期结构" },
      { name: "BRAR", label: "人气意愿", description: "比较开盘价与价格区间的强弱" },
    ],
  },
]);

export const TECHNICAL_INDICATOR_NAMES = Object.freeze(
  TECHNICAL_INDICATOR_GROUPS.flatMap((group) => group.items.map((item) => item.name)),
);

export const DEFAULT_TECHNICAL_INDICATORS = Object.freeze(["VOL"]);

export function normalizeTechnicalIndicatorSelection(
  selection,
  availableNames = TECHNICAL_INDICATOR_NAMES,
) {
  const values = selection instanceof Set ? [...selection] : Array.isArray(selection) ? selection : [];
  const selected = new Set(values.map((item) => String(item).trim().toUpperCase()));
  const known = new Set(TECHNICAL_INDICATOR_NAMES);
  const available = new Set(
    (Array.isArray(availableNames) ? availableNames : TECHNICAL_INDICATOR_NAMES)
      .map((item) => String(item).trim().toUpperCase())
      .filter((item) => known.has(item)),
  );
  return TECHNICAL_INDICATOR_NAMES.filter(
    (name) => selected.has(name) && available.has(name),
  );
}

export function technicalIndicatorPaneId(name) {
  const normalized = normalizeTechnicalIndicatorSelection([name])[0];
  if (!normalized) throw new RangeError(`不支持的技术指标: ${name}`);
  return `technical_indicator_${normalized.toLowerCase()}`;
}

export function technicalIndicatorChartHeight(indicatorCount, compact = false) {
  const numericCount = Number(indicatorCount);
  const paneCount = Number.isFinite(numericCount)
    ? Math.max(0, Math.trunc(numericCount))
    : 0;
  return (compact ? 250 : 360) + paneCount * (compact ? 110 : 120);
}

export function setTechnicalIndicatorVisibility(chart, name, visible) {
  const normalized = normalizeTechnicalIndicatorSelection([name])[0];
  if (!chart || !normalized) return false;
  const paneId = technicalIndicatorPaneId(normalized);
  if (!visible) return Boolean(chart.removeIndicator({ paneId }));
  const indicatorId = chart.createIndicator({ name: normalized, paneId });
  if (!indicatorId) return false;
  chart.setPaneOptions({ id: paneId, height: 120, minHeight: 88 });
  return true;
}

const EVENT_STYLE = {
  OPENING: { color: "#8d8d86", shortLabel: "期", baseOffset: -46 },
  BUY: { color: "#3e63dd", shortLabel: "买", baseOffset: 28 },
  SELL: { color: "#f5a623", shortLabel: "卖", baseOffset: -28 },
};

export function normalizeBars(bars = []) {
  const normalized = bars
    .map((item) => ({
      timestamp: Number(item.timestamp),
      open: Number(item.open),
      high: Number(item.high),
      low: Number(item.low),
      close: Number(item.close),
      volume: Number(item.volume),
      turnover: Number(item.turnover),
    }))
    .filter((item) =>
      [
        item.timestamp,
        item.open,
        item.high,
        item.low,
        item.close,
        item.volume,
        item.turnover,
      ].every(Number.isFinite),
    )
    .sort((left, right) => left.timestamp - right.timestamp);
  return normalized.filter(
    (item, index) => index === 0 || item.timestamp !== normalized[index - 1].timestamp,
  );
}

export function rangeLabel(rangeKey) {
  return { "3m": "最近 3 个月", "1y": "最近 1 年", cycle: "本轮持仓" }[rangeKey] || rangeKey;
}

export function candleClickTradeDate(actionData, bars = []) {
  const timestamp = Number(actionData?.data?.current?.timestamp);
  if (!Number.isFinite(timestamp)) return null;
  const bar = bars.find((item) => Number(item.timestamp) === timestamp);
  const tradeDate = String(bar?.trade_date || "");
  return /^\d{4}-\d{2}-\d{2}$/.test(tradeDate) ? tradeDate : null;
}

export function tradeDateOnOrBeforeAsOf(tradeDate, asOf) {
  const normalizedDate = String(tradeDate || "");
  const cutoff = String(asOf || "");
  const datePattern = /^\d{4}-\d{2}-\d{2}$/;
  if (![normalizedDate, cutoff].every((item) => datePattern.test(item))) {
    return false;
  }
  return normalizedDate <= cutoff;
}

export function latestLedgerTradeDate(operationGroups = [], asOf = null) {
  const cutoff = /^\d{4}-\d{2}-\d{2}$/.test(String(asOf || "")) ? String(asOf) : null;
  const dates = operationGroups
    .filter((item) => ["BUY", "SELL"].includes(String(item?.event_type || "").toUpperCase()))
    .map((item) => String(item?.event_date || ""))
    .filter((item) => /^\d{4}-\d{2}-\d{2}$/.test(item) && (!cutoff || item <= cutoff));
  return dates.sort().at(-1) || null;
}

export function intradayBarSpaceLimit(periodSpan = 1) {
  return {
    min: 2,
    max: Number(periodSpan) >= 5 ? 24 : 14,
  };
}

export function intradayFitBarSpace(containerWidth, barCount, limits) {
  const width = Number(containerWidth);
  const count = Number(barCount);
  const min = Number(limits?.min);
  const max = Number(limits?.max);
  if (![width, count, min, max].every(Number.isFinite) || width <= 0 || count <= 0) {
    return Number.isFinite(min) && min > 0 ? min : 2;
  }
  const usableWidth = Math.max(width - 80, min);
  return Math.max(min, Math.min(max, usableWidth / (count + 4)));
}

export function operationDomId(groupId) {
  return `operation-${String(groupId).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

export function buildOperationMarkers(groups = []) {
  const plottable = groups
    .filter(
      (item) =>
        item.in_range &&
        item.timestamp !== null &&
        item.timestamp !== undefined &&
        item.adjusted_price !== null &&
        item.adjusted_price !== undefined &&
        Number.isFinite(Number(item.timestamp)) &&
        Number.isFinite(Number(item.adjusted_price)),
    )
    .sort(
      (left, right) =>
        Number(left.timestamp) - Number(right.timestamp) ||
        (EVENT_PRIORITY[left.event_type] ?? 9) - (EVENT_PRIORITY[right.event_type] ?? 9),
    );
  const buckets = new Map();
  plottable.forEach((item) => {
    const key = Number(item.timestamp);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(item);
  });

  const markers = [];
  buckets.forEach((items) => {
    const midpoint = (items.length - 1) / 2;
    items.forEach((item, index) => {
      const style = EVENT_STYLE[item.event_type] || EVENT_STYLE.OPENING;
      markers.push({
        groupId: item.group_id,
        targetId: operationDomId(item.group_id),
        timestamp: Number(item.timestamp),
        value: Number(item.adjusted_price),
        text: `${style.shortLabel}${Number(item.entry_count) > 1 ? item.entry_count : ""}`,
        color: style.color,
        verticalOffset: style.baseOffset + Math.round((index - midpoint) * 18),
      });
    });
  });
  return markers;
}

export function intradayAverageSeries(bars = []) {
  let cumulativeTurnover = 0;
  let cumulativeVolume = 0;
  let previousAverage = null;
  return bars.map((item) => {
    const volume = Number(item.volume);
    const turnover = Number(item.turnover);
    if (Number.isFinite(volume) && Number.isFinite(turnover) && volume > 0) {
      cumulativeVolume += volume;
      cumulativeTurnover += turnover;
      previousAverage = cumulativeTurnover / cumulativeVolume;
    }
    return { average: previousAverage };
  });
}

export function buildIntradayMarkers(groups = []) {
  const plottable = groups
    .filter(
      (item) =>
        ["BUY", "SELL"].includes(item.event_type) &&
        item.timestamp !== null &&
        item.timestamp !== undefined &&
        item.marker_price !== null &&
        item.marker_price !== undefined &&
        Number.isFinite(Number(item.timestamp)) &&
        Number.isFinite(Number(item.marker_price)),
    )
    .sort(
      (left, right) =>
        Number(left.timestamp) - Number(right.timestamp) ||
        (EVENT_PRIORITY[left.event_type] ?? 9) - (EVENT_PRIORITY[right.event_type] ?? 9),
    );
  const buckets = new Map();
  plottable.forEach((item) => {
    const key = Number(item.timestamp);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(item);
  });
  const markers = [];
  buckets.forEach((items) => {
    const midpoint = (items.length - 1) / 2;
    items.forEach((item, index) => {
      const style = EVENT_STYLE[item.event_type];
      markers.push({
        groupId: item.group_id,
        targetId: operationDomId(item.group_id),
        timestamp: Number(item.timestamp),
        value: Number(item.marker_price),
        text: `${style.shortLabel}${Number(item.entry_count) > 1 ? item.entry_count : ""}`,
        color: style.color,
        verticalOffset: style.baseOffset + Math.round((index - midpoint) * 18),
      });
    });
  });
  return markers;
}

export function sensitiveText(value, privacy) {
  return privacy ? "••••••" : String(value ?? "—");
}
