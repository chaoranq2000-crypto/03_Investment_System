import { describe, expect, it } from "vitest";

import { selectContributionPositions } from "./contribution.js";

describe("盈亏贡献筛选", () => {
  it("分别保留浮盈前五和浮亏前五", () => {
    const positions = [
      ...[1, 2, 3].map((value) => ({ ts_code: `gain-${value}`, unrealized_pnl: String(value) })),
      ...[1, 2, 3, 4, 5, 6, 7].map((value) => ({ ts_code: `loss-${value}`, unrealized_pnl: String(-value) })),
    ];

    const selected = selectContributionPositions(positions);

    expect(selected.filter((item) => Number(item.unrealized_pnl) > 0)).toHaveLength(3);
    expect(selected.filter((item) => Number(item.unrealized_pnl) < 0)).toHaveLength(5);
    expect(selected.map((item) => item.ts_code)).toEqual([
      "loss-7",
      "loss-6",
      "loss-5",
      "loss-4",
      "gain-3",
      "loss-3",
      "gain-2",
      "gain-1",
    ]);
  });

  it("忽略零盈亏和缺失值且不修改原数组", () => {
    const positions = [
      { ts_code: "gain", unrealized_pnl: "10" },
      { ts_code: "flat", unrealized_pnl: "0" },
      { ts_code: "missing", unrealized_pnl: null },
      { ts_code: "loss", unrealized_pnl: "-20" },
    ];
    const originalOrder = positions.map((item) => item.ts_code);

    expect(selectContributionPositions(positions).map((item) => item.ts_code)).toEqual([
      "loss",
      "gain",
    ]);
    expect(positions.map((item) => item.ts_code)).toEqual(originalOrder);
  });
});
