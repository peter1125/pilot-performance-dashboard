import { pilotHistory, pilotMeta as fallbackPilotMeta } from './data.js';
import {
  buildEquitySeries,
  buildPilotSummaries,
  computeLeaderboard,
  extractAllocation,
  filterTransactions,
  flattenTransactions,
  formatCurrency,
  formatPercent,
  normalizeTransactionFilters,
} from './utils.js';

const state = {
  chartMode: 'nav',
  pilotFilter: 'All',
  query: '',
  cashOnly: false,
  summaries: [],
  leaderboard: [],
  equitySeries: [],
  transactions: [],
  pilotMeta: fallbackPilotMeta,
  latestDate: null,
  refreshedAt: null,
  source: 'fallback',
};

const summaryGrid = document.querySelector('#summaryGrid');
const leaderboardRoot = document.querySelector('#leaderboard');
const notesRoot = document.querySelector('#strategyNotes');
const pilotFiltersRoot = document.querySelector('#pilotFilters');
const transactionsBody = document.querySelector('#transactionsBody');
const chartLegend = document.querySelector('#chartLegend');
const chartSvg = document.querySelector('#equityChart');
const searchInput = document.querySelector('#searchInput');
const cashOnlyToggle = document.querySelector('#cashOnlyToggle');
const dataStatus = document.querySelector('#dataStatus');
const refreshMeta = document.querySelector('#refreshMeta');
const refreshButton = document.querySelector('#refreshButton');

function fallbackPayload() {
  const summaries = buildPilotSummaries(pilotHistory);
  const leaderboard = computeLeaderboard(summaries);
  return {
    pilotMeta: fallbackPilotMeta,
    summaries: leaderboard,
    leaderboard,
    equitySeries: buildEquitySeries(pilotHistory),
    transactions: flattenTransactions(pilotHistory),
    latestDate: leaderboard[0]?.latestDate ?? null,
    refreshedAt: new Date().toISOString(),
    source: 'embedded-fallback',
  };
}

function applyPayload(payload) {
  state.pilotMeta = payload.pilotMeta || fallbackPilotMeta;
  state.summaries = payload.summaries || [];
  state.leaderboard = payload.leaderboard || state.summaries;
  state.equitySeries = payload.equitySeries || [];
  state.transactions = payload.transactions || [];
  state.latestDate = payload.latestDate || null;
  state.refreshedAt = payload.refreshedAt || null;
  state.source = payload.source || 'unknown';
}

function setStatus(kind, text, meta = '') {
  dataStatus.textContent = text;
  dataStatus.className = `status-pill ${kind}`;
  refreshMeta.textContent = meta;
}

async function loadDashboardData(force = false) {
  setStatus('status-loading', 'Loading live data…', '');
  refreshButton.disabled = true;
  try {
    const response = await fetch(`./dashboard-data.json${force ? `?t=${Date.now()}` : ''}`, {
      cache: 'no-store',
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    applyPayload(payload);
    const refreshed = state.refreshedAt ? new Date(state.refreshedAt).toLocaleString() : '';
    const sourceLabel = state.source === 'github-pages-notion-sync' ? 'Live data synced from Notion' : 'Live dashboard data';
    setStatus('status-live', sourceLabel, refreshed ? `Refreshed ${refreshed}` : '');
  } catch (error) {
    applyPayload(fallbackPayload());
    setStatus('status-fallback', 'Showing embedded fallback data', 'Latest sync unavailable');
    console.error(error);
  } finally {
    refreshButton.disabled = false;
    renderAll();
  }
}

function renderSummaryCards() {
  summaryGrid.innerHTML = state.leaderboard
    .map((item) => {
      const meta = state.pilotMeta[item.pilot] || { color: '#64748b', accent: 'rgba(100,116,139,.18)' };
      const pnlClass = item.dayPnl >= 0 ? 'positive' : 'negative';
      return `
        <article class="summary-card" style="--pilot-color:${meta.color}; --pilot-accent:${meta.accent}">
          <div class="summary-head">
            <div>
              <p class="eyebrow">${item.strategy}</p>
              <h2>${item.pilot}</h2>
            </div>
            <div class="rank-pill">#${item.rank}</div>
          </div>
          <div class="metric-grid">
            <div class="metric">
              <span class="metric-label">Current NAV</span>
              <strong>${formatCurrency(item.currentNav)}</strong>
              <small>Updated ${item.latestDate ?? '—'}</small>
            </div>
            <div class="metric">
              <span class="metric-label">Day return</span>
              <strong class="${pnlClass}">${formatPercent(item.dayReturnPct)}</strong>
              <small>${item.dayPnl >= 0 ? '+' : '-'}${formatCurrency(Math.abs(item.dayPnl))} on the latest mark</small>
            </div>
            <div class="metric">
              <span class="metric-label">Total return</span>
              <strong class="${item.totalReturnPct >= 0 ? 'positive' : 'negative'}">${formatPercent(item.totalReturnPct)}</strong>
              <small>From KRW 10,000,000 starting capital</small>
            </div>
            <div class="metric">
              <span class="metric-label">Current allocation</span>
              <strong>${extractAllocation(item.latestTransaction)}</strong>
              <small>Cash reserve: ${formatCurrency(item.cash ?? 0)}</small>
            </div>
          </div>
        </article>
      `;
    })
    .join('');
}

function renderLeaderboard() {
  leaderboardRoot.innerHTML = `<div class="leaderboard-stack">${state.leaderboard
    .map((item) => {
      const meta = state.pilotMeta[item.pilot] || { color: '#64748b' };
      return `
        <article class="leaderboard-item" style="--pilot-color:${meta.color}">
          <div class="leaderboard-top">
            <div class="pilot-line">
              <span class="dot"></span>
              <strong>#${item.rank} ${item.pilot}</strong>
            </div>
            <strong>${formatCurrency(item.currentNav)}</strong>
          </div>
          <div class="value-row">
            <span>${item.strategy}</span>
            <span class="${item.totalReturnPct >= 0 ? 'positive' : 'negative'}">${formatPercent(item.totalReturnPct)} total</span>
            <span class="${item.dayReturnPct >= 0 ? 'positive' : 'negative'}">${formatPercent(item.dayReturnPct)} latest day</span>
          </div>
        </article>
      `;
    })
    .join('')}</div>`;
}

function renderStrategyNotes() {
  notesRoot.innerHTML = state.leaderboard
    .map((item) => {
      const meta = state.pilotMeta[item.pilot] || { color: '#64748b' };
      return `
        <article class="note-card" style="--pilot-color:${meta.color}">
          <div class="pilot-line">
            <span class="dot"></span>
            <strong>${item.pilot}</strong>
          </div>
          <div class="note-meta">
            <span>${item.latestDate ?? '—'}</span>
            <span>${item.latestLog ?? ''}</span>
          </div>
          <div>${item.latestResearch || 'No research note available.'}</div>
        </article>
      `;
    })
    .join('');
}

function buildChartSeries() {
  if (state.chartMode === 'nav') {
    return state.leaderboard.map((summary) => ({
      pilot: summary.pilot,
      color: state.pilotMeta[summary.pilot]?.color || '#64748b',
      values: state.equitySeries.map((row) => ({ date: row.date, value: row[summary.pilot] })),
    }));
  }

  return state.leaderboard.map((summary) => {
    const firstValue = state.equitySeries.find((row) => row[summary.pilot] != null)?.[summary.pilot] ?? 0;
    return {
      pilot: summary.pilot,
      color: state.pilotMeta[summary.pilot]?.color || '#64748b',
      values: state.equitySeries.map((row) => ({
        date: row.date,
        value: row[summary.pilot] == null || firstValue === 0 ? null : ((row[summary.pilot] - firstValue) / firstValue) * 100,
      })),
    };
  });
}

function renderChartLegend(series) {
  chartLegend.innerHTML = series
    .map(
      (line) => `
        <span class="legend-item">
          <span class="legend-swatch" style="background:${line.color}"></span>
          ${line.pilot}
        </span>
      `,
    )
    .join('');
}

function renderChart() {
  if (!state.equitySeries.length || !state.leaderboard.length) {
    chartSvg.innerHTML = '';
    return;
  }

  const width = 960;
  const height = 380;
  const margin = { top: 24, right: 24, bottom: 42, left: 74 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const series = buildChartSeries();
  renderChartLegend(series);

  const points = series.flatMap((line) => line.values.map((point) => point.value).filter((value) => value != null));
  const minValue = Math.min(...points);
  const maxValue = Math.max(...points);
  const range = maxValue - minValue || 1;
  const stepX = state.equitySeries.length > 1 ? plotWidth / (state.equitySeries.length - 1) : plotWidth;
  const yTicks = 4;

  const yFor = (value) => margin.top + plotHeight - ((value - minValue) / range) * plotHeight;
  const xFor = (index) => margin.left + index * stepX;
  const formatAxisValue = (value) => (state.chartMode === 'nav' ? formatCurrency(value) : formatPercent(value));

  const gridLines = Array.from({ length: yTicks + 1 }, (_, index) => {
    const value = minValue + (range / yTicks) * index;
    const y = yFor(value);
    return `
      <g>
        <line class="chart-grid" x1="${margin.left}" x2="${width - margin.right}" y1="${y}" y2="${y}" />
        <text class="chart-grid-label" x="${margin.left - 12}" y="${y + 4}" text-anchor="end">${formatAxisValue(value)}</text>
      </g>
    `;
  }).join('');

  const xLabels = state.equitySeries
    .map((row, index) => `<text class="chart-label" x="${xFor(index)}" y="${height - 12}" text-anchor="middle">${row.date.slice(5)}</text>`)
    .join('');

  const lines = series
    .map((line) => {
      const validPoints = line.values.filter((point) => point.value != null);
      const path = validPoints
        .map((point, index) => {
          const sourceIndex = line.values.findIndex((entry) => entry.date === point.date);
          return `${index === 0 ? 'M' : 'L'} ${xFor(sourceIndex)} ${yFor(point.value)}`;
        })
        .join(' ');

      const markers = validPoints
        .map((point) => {
          const sourceIndex = line.values.findIndex((entry) => entry.date === point.date);
          const x = xFor(sourceIndex);
          const y = yFor(point.value);
          return `
            <circle class="chart-point" cx="${x}" cy="${y}" r="4" fill="${line.color}">
              <title>${line.pilot} • ${point.date} • ${formatAxisValue(point.value)}</title>
            </circle>
          `;
        })
        .join('');

      return `<g>
        <path class="chart-path" d="${path}" stroke="${line.color}"></path>
        ${markers}
      </g>`;
    })
    .join('');

  chartSvg.innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="rgba(15, 23, 42, 0.3)"></rect>
    ${gridLines}
    ${lines}
    ${xLabels}
  `;
}

function renderFilters() {
  const filterOptions = ['All', ...state.leaderboard.map((item) => item.pilot)];
  pilotFiltersRoot.innerHTML = filterOptions
    .map((pilot) => `<button class="${state.pilotFilter === pilot ? 'active' : ''}" data-pilot-filter="${pilot}">${pilot}</button>`)
    .join('');

  pilotFiltersRoot.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => {
      state.pilotFilter = button.dataset.pilotFilter;
      renderFilters();
      renderTransactions();
    });
  });
}

function renderTransactions() {
  const filtered = filterTransactions(state.transactions, normalizeTransactionFilters(state));
  if (!filtered.length) {
    transactionsBody.innerHTML = `<tr><td colspan="8" class="empty">No transactions match the current filters.</td></tr>`;
    return;
  }

  transactionsBody.innerHTML = filtered
    .map((row) => {
      const pnl = row.end - row.start;
      const returnPct = row.start ? ((row.end - row.start) / row.start) * 100 : 0;
      const meta = state.pilotMeta[row.pilot] || { color: '#64748b' };
      return `
        <tr>
          <td>${row.date}</td>
          <td>
            <span class="table-chip">
              <span class="dot" style="background:${meta.color}"></span>
              ${row.pilot}
            </span>
          </td>
          <td>${row.strategy}</td>
          <td>${formatCurrency(row.start)}</td>
          <td>${formatCurrency(row.end)}</td>
          <td>${formatCurrency(row.cash ?? 0)}</td>
          <td>
            <div class="${pnl >= 0 ? 'positive' : 'negative'}">${pnl >= 0 ? '+' : '-'}${formatCurrency(Math.abs(pnl))}</div>
            <div class="mini-label ${returnPct >= 0 ? 'positive' : 'negative'}">${formatPercent(returnPct)}</div>
          </td>
          <td class="transaction-copy">${row.transactions}</td>
        </tr>
      `;
    })
    .join('');
}

function renderAll() {
  renderSummaryCards();
  renderLeaderboard();
  renderStrategyNotes();
  renderFilters();
  renderTransactions();
  renderChart();
}

function bindControls() {
  document.querySelectorAll('[data-chart-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      state.chartMode = button.dataset.chartMode;
      document.querySelectorAll('[data-chart-mode]').forEach((item) => item.classList.toggle('active', item === button));
      renderChart();
    });
  });

  searchInput.addEventListener('input', (event) => {
    state.query = event.target.value;
    renderTransactions();
  });

  cashOnlyToggle.addEventListener('change', (event) => {
    state.cashOnly = event.target.checked;
    renderTransactions();
  });

  refreshButton.addEventListener('click', () => {
    loadDashboardData(true);
  });
}

bindControls();
loadDashboardData();
setInterval(() => loadDashboardData(true), 60_000);
