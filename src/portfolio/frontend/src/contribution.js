export function selectContributionPositions(positions, limitPerSide = 5) {
  const ranked = (positions || [])
    .map((position) => ({
      position,
      pnl: Number(position.unrealized_pnl),
    }))
    .filter(({ pnl }) => Number.isFinite(pnl) && pnl !== 0);

  const gains = ranked
    .filter(({ pnl }) => pnl > 0)
    .sort((left, right) => right.pnl - left.pnl)
    .slice(0, limitPerSide);
  const losses = ranked
    .filter(({ pnl }) => pnl < 0)
    .sort((left, right) => left.pnl - right.pnl)
    .slice(0, limitPerSide);

  return [...gains, ...losses]
    .sort((left, right) => Math.abs(right.pnl) - Math.abs(left.pnl))
    .map(({ position }) => position);
}
