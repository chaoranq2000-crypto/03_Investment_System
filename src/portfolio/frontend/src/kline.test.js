import { describe, expect, it, vi } from "vitest";

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
  sensitiveText,
  technicalIndicatorChartHeight,
  technicalIndicatorPaneId,
  tradeDateOnOrBeforeAsOf,
} from "./kline.js";

describe("K 线前端映射", () => {
  it("把后端字段转换为按时间升序的数值 KLineData", () => {
    expect(
      normalizeBars([
        { timestamp: "2", open: "2", high: "3", low: "1", close: "2.5", volume: "8", turnover: "9" },
        { timestamp: "1", open: "1", high: "2", low: "0.5", close: "1.5", volume: "6", turnover: "7" },
      ]),
    ).toEqual([
      { timestamp: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 6, turnover: 7 },
      { timestamp: 2, open: 2, high: 3, low: 1, close: 2.5, volume: 8, turnover: 9 },
    ]);
  });

  it("同日不同方向保留独立标注并设置垂直偏移", () => {
    const markers = buildOperationMarkers([
      { group_id: "code:1:2026-07-10:BUY", event_type: "BUY", entry_count: 2, in_range: true, timestamp: 10, adjusted_price: 12.3 },
      { group_id: "code:1:2026-07-10:SELL", event_type: "SELL", entry_count: 1, in_range: true, timestamp: 10, adjusted_price: 12.8 },
    ]);
    expect(markers).toHaveLength(2);
    expect(markers.map((item) => item.text)).toEqual(["买2", "卖"]);
    expect(markers[0].verticalOffset).not.toBe(markers[1].verticalOffset);
    expect(markers[0].targetId).toBe(operationDomId("code:1:2026-07-10:BUY"));
  });

  it("过滤区间外或缺少复权定位价的操作", () => {
    expect(
      buildOperationMarkers([
        { group_id: "outside", event_type: "BUY", in_range: false, timestamp: 1, adjusted_price: 1 },
        { group_id: "missing", event_type: "SELL", in_range: true, timestamp: null, adjusted_price: null },
      ]),
    ).toEqual([]);
  });

  it("提供固定区间文案和隐私格式", () => {
    expect(rangeLabel("3m")).toBe("最近 3 个月");
    expect(rangeLabel("1y")).toBe("最近 1 年");
    expect(rangeLabel("cycle")).toBe("本轮持仓");
    expect(sensitiveText("12.34", true)).toBe("••••••");
    expect(sensitiveText("12.34", false)).toBe("12.34");
  });

  it("把被点击的日 K 精确映射为交易日，并允许回看日前的上下文日期", () => {
    const action = { data: { current: { timestamp: 1000 } } };
    const bars = [
      { timestamp: 1000, trade_date: "2026-07-14" },
      { timestamp: 2000, trade_date: "2026-07-15" },
    ];
    expect(candleClickTradeDate(action, bars)).toBe("2026-07-14");
    expect(candleClickTradeDate({ data: {} }, bars)).toBeNull();
    expect(tradeDateOnOrBeforeAsOf("2026-07-14", "2026-07-20")).toBe(true);
    expect(tradeDateOnOrBeforeAsOf("2026-05-29", "2026-07-20")).toBe(true);
    expect(tradeDateOnOrBeforeAsOf("2026-07-21", "2026-07-20")).toBe(false);
    expect(tradeDateOnOrBeforeAsOf("not-a-date", "2026-07-20")).toBe(false);
  });

  it("默认选择 as_of 之前最近一笔交割单买卖日期", () => {
    const operations = [
      { event_type: "OPENING", event_date: "2026-07-09" },
      { event_type: "BUY", event_date: "2026-07-10" },
      { event_type: "SELL", event_date: "2026-07-14" },
      { event_type: "BUY", event_date: "2026-07-15" },
    ];
    expect(latestLedgerTradeDate(operations, "2026-07-14")).toBe("2026-07-14");
    expect(latestLedgerTradeDate(operations, "2026-07-13")).toBe("2026-07-10");
    expect(latestLedgerTradeDate([{ event_type: "OPENING", event_date: "2026-07-09" }])).toBeNull();
  });

  it("限制分时过度放大，并计算适应全日的初始柱宽", () => {
    expect(intradayBarSpaceLimit(1)).toEqual({ min: 2, max: 14 });
    expect(intradayBarSpaceLimit(5)).toEqual({ min: 2, max: 24 });
    expect(intradayFitBarSpace(900, 241, { min: 2, max: 14 })).toBeCloseTo(3.3469, 3);
    expect(intradayFitBarSpace(900, 48, { min: 2, max: 24 })).toBeCloseTo(15.7692, 3);
    expect(intradayFitBarSpace(0, 0, { min: 2, max: 14 })).toBe(2);
  });

  it("提供完整且不重复的 KLineChart v10 技术指标目录", () => {
    expect(TECHNICAL_INDICATOR_GROUPS).toHaveLength(4);
    expect(TECHNICAL_INDICATOR_NAMES).toHaveLength(27);
    expect(new Set(TECHNICAL_INDICATOR_NAMES).size).toBe(27);
    expect(TECHNICAL_INDICATOR_NAMES).toEqual(
      expect.arrayContaining(["VOL", "MACD", "KDJ", "RSI", "BOLL", "EMV", "AVP"]),
    );
    expect(DEFAULT_TECHNICAL_INDICATORS).toEqual(["VOL"]);
  });

  it("清洗已保存的指标选择，并按目录顺序和接口可用范围返回", () => {
    expect(
      normalizeTechnicalIndicatorSelection(
        new Set(["rsi", "UNKNOWN", "macd", "VOL"]),
        ["VOL", "MACD", "RSI"],
      ),
    ).toEqual(["VOL", "MACD", "RSI"]);
    expect(normalizeTechnicalIndicatorSelection(null)).toEqual([]);
  });

  it("用显式 paneId 创建和移除副图，而不误把 indicatorId 当成 paneId", () => {
    const chart = {
      createIndicator: vi.fn(() => "generated-indicator-id"),
      removeIndicator: vi.fn(() => true),
      setPaneOptions: vi.fn(),
    };

    expect(setTechnicalIndicatorVisibility(chart, "MACD", true)).toBe(true);
    expect(chart.createIndicator).toHaveBeenCalledWith({
      name: "MACD",
      paneId: "technical_indicator_macd",
    });
    expect(chart.setPaneOptions).toHaveBeenCalledWith({
      id: "technical_indicator_macd",
      height: 120,
      minHeight: 88,
    });
    expect(setTechnicalIndicatorVisibility(chart, "MACD", false)).toBe(true);
    expect(chart.removeIndicator).toHaveBeenCalledWith({ paneId: "technical_indicator_macd" });
    expect(technicalIndicatorPaneId("rsi")).toBe("technical_indicator_rsi");
  });

  it("根据已显示副图数量扩展图表高度", () => {
    expect(technicalIndicatorChartHeight(0)).toBe(360);
    expect(technicalIndicatorChartHeight(1)).toBe(480);
    expect(technicalIndicatorChartHeight(3)).toBe(720);
    expect(technicalIndicatorChartHeight(1, true)).toBe(360);
  });

  it("按分钟累计成交额和成交量计算日内均价，零成交量沿用上一有效值", () => {
    expect(
      intradayAverageSeries([
        { volume: 0, turnover: 0 },
        { volume: 100, turnover: 1000 },
        { volume: 0, turnover: 0 },
        { volume: 100, turnover: 1200 },
      ]),
    ).toEqual([
      { average: null },
      { average: 10 },
      { average: 10 },
      { average: 11 },
    ]);
  });

  it("分时成交点使用实际成交价，并保持同桶买卖分离", () => {
    const markers = buildIntradayMarkers([
      { group_id: "buy", event_type: "BUY", entry_count: 2, timestamp: 10, marker_price: 12.1 },
      { group_id: "sell", event_type: "SELL", entry_count: 1, timestamp: 10, marker_price: 12.2 },
      { group_id: "opening", event_type: "OPENING", entry_count: 1, timestamp: 10, marker_price: 11 },
    ]);
    expect(markers.map((item) => item.text)).toEqual(["买2", "卖"]);
    expect(markers.map((item) => item.value)).toEqual([12.1, 12.2]);
    expect(markers[0].verticalOffset).not.toBe(markers[1].verticalOffset);
  });
});
