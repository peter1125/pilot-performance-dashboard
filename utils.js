export function round2(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function formatCurrency(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(value) {
  const rounded = round2(value);
  const sign = rounded > 0 ? '+' : '';
  return `${sign}${rounded.toFixed(2)}%`;
}

export function buildPilotSummaries(pilotHistory) {
  return Object.entries(pilotHistory).map(([pilot, rows]) => {
    const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
    const first = sorted[0];
    const latest = sorted.at(-1);
    const currentNav = latest.end;
    const dayPnl = latest.end - latest.start;
    const dayReturnPct = latest.start ? (dayPnl / latest.start) * 100 : 0;
    const totalReturnPct = first.start ? ((latest.end - first.start) / first.start) * 100 : 0;
    return {
      pilot,
      strategy: latest.strategy,
      currentNav,
      startingCapital: first.start,
      dayPnl,
      dayReturnPct,
      totalReturnPct,
      cash: latest.cash ?? 0,
      latestDate: latest.date,
      latestLog: latest.log,
      latestTransaction: latest.transactions,
      latestResearch: latest.research,
      latestAllocation: extractAllocation(latest.transactions),
    };
  });
}

export function computeLeaderboard(summaries) {
  return [...summaries]
    .sort((a, b) => b.currentNav - a.currentNav)
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

export function buildEquitySeries(pilotHistory) {
  const dates = [...new Set(Object.values(pilotHistory).flat().map((row) => row.date))].sort();
  const latestByPilot = Object.fromEntries(Object.keys(pilotHistory).map((pilot) => [pilot, null]));

  return dates.map((date) => {
    const entry = { date };
    for (const [pilot, rows] of Object.entries(pilotHistory)) {
      const exact = rows.find((row) => row.date === date);
      if (exact) latestByPilot[pilot] = exact.end;
      entry[pilot] = latestByPilot[pilot];
    }
    return entry;
  });
}

export function filterTransactions(rows, filters) {
  const query = (filters.query || '').trim().toLowerCase();
  return rows
    .filter((row) => (filters.pilot === 'All' ? true : row.pilot === filters.pilot))
    .filter((row) => (filters.cashOnly ? (row.cash ?? 0) > 0 : true))
    .filter((row) => {
      if (!query) return true;
      return [row.transactions, row.research, row.strategy, row.log, row.date, row.pilot]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(query));
    })
    .sort((a, b) => b.date.localeCompare(a.date));
}

export function flattenTransactions(pilotHistory) {
  return Object.values(pilotHistory)
    .flat()
    .sort((a, b) => b.date.localeCompare(a.date));
}

export function normalizeTransactionFilters(state) {
  return {
    pilot: state.pilotFilter ?? state.pilot ?? 'All',
    query: state.query ?? '',
    cashOnly: Boolean(state.cashOnly),
  };
}

export function extractAllocation(transactionText) {
  if (!transactionText) return 'No transaction note';
  const normalized = transactionText
    .replace(/^\d{4}-\d{2}-\d{2}[^:]*:\s*/u, '')
    .replace(/^Rebalanced (?:at [^:]+: )?/u, '')
    .replace(/^to\s+/u, '')
    .replace(/\s+based on.*$/iu, '')
    .replace(/\s+Following strongest.*$/iu, '')
    .replace(/\s+Momentum leadership.*$/iu, '')
    .replace(/\s+Top 24h breakouts.*$/iu, '')
    .replace(/\s+Some role buckets.*$/iu, '')
    .replace(/\s+Allocated to strongest.*$/iu, '')
    .replace(/\s+All four sentiment.*$/iu, '')
    .trim();

  return normalized || transactionText;
}
