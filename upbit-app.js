import { filterPointsByWindow, nearestPointIndex } from './upbit-chart-utils.mjs';

const STARTING_NAV_KRW = 1_000_000;

const state = {
  payload: null,
  chartMode: 'nav',
  chartWindow: 'all',
  selectedPointIndex: null,
  query: '',
};

const els = {
  status: document.querySelector('#dataStatus'),
  refreshMeta: document.querySelector('#refreshMeta'),
  refreshButton: document.querySelector('#refreshButton'),
  summaryGrid: document.querySelector('#summaryGrid'),
  chart: document.querySelector('#equityChart'),
  chartDetails: document.querySelector('#chartPointDetails'),
  chartWindowControls: document.querySelector('#chartWindowControls'),
  legend: document.querySelector('#chartLegend'),
  allocation: document.querySelector('#allocationPanel'),
  guardrails: document.querySelector('#guardrailsPanel'),
  phaseAssessment: document.querySelector('#phaseAssessmentPanel'),
  leaders: document.querySelector('#leadersPanel'),
  txBody: document.querySelector('#transactionsBody'),
  runsBody: document.querySelector('#runsBody'),
  search: document.querySelector('#searchInput'),
};

function formatCurrency(value) {
  return `KRW ${Math.round(Number(value || 0)).toLocaleString('en-US')}`;
}

function formatPercent(value, digits = 2) {
  const n = Number(value || 0);
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

function formatTime(value) {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Seoul', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatMode(value) {
  if (value === true) return 'Enabled';
  if (value === false) return 'Disabled';
  if (value == null || value === '') return '—';
  return String(value).replace(/[_-]/g, ' ').replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function compactReason(value) {
  if (!value) return '—';
  const text = String(value);
  return text.length > 92 ? `${text.slice(0, 89)}…` : text;
}

function setStatus(kind, text, meta = '') {
  els.status.textContent = text;
  els.status.className = `status-pill ${kind}`;
  els.refreshMeta.textContent = meta;
}

async function loadData(force = false) {
  setStatus('status-loading', 'Loading Upbit data…');
  els.refreshButton.disabled = true;
  try {
    const response = await fetch(`./upbit-data.json${force ? `?t=${Date.now()}` : ''}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.payload = await response.json();
    setStatus('status-live', 'Live Upbit reports', `Refreshed ${formatTime(state.payload.refreshedAt)}`);
  } catch (err) {
    console.error(err);
    setStatus('status-fallback', 'Unable to load Upbit data', 'Run sync_upbit_data.py');
    state.payload = { summary: {}, equitySeries: [], transactions: [], latest: null, guardrails: {} };
  } finally {
    els.refreshButton.disabled = false;
    renderAll();
  }
}

function renderSummary() {
  const s = state.payload.summary || {};
  const latest = state.payload.latest || {};
  const pollClass = (latest.pnlKrw || 0) >= 0 ? 'positive' : 'negative';
  const totalClass = (s.totalPnlKrw || 0) >= 0 ? 'positive' : 'negative';
  const strategyNote = s.liveExtensionEnabled == null ? 'Live extension unknown' : `Live extension ${formatMode(s.liveExtensionEnabled).toLowerCase()}`;
  const freezeReason = s.freezeModeReason || s.riskFreezeReason || s.latestReason;
  const cards = [
    ['Current NAV', formatCurrency(s.currentNav), `Latest ${formatTime(s.latestTime)}`],
    ['Strategy mode', formatMode(s.strategyMode || 'paper-aligned'), strategyNote],
    ['Freeze mode', formatMode(s.freezeMode || 'normal'), compactReason(freezeReason)],
    ['Operating status', String(s.governanceStatus || s.latestStatus || 'unknown').toUpperCase(), `${s.pendingOrderCount || 0} pending · orders ${formatMode(s.latestOrdersSubmitted ?? s.ordersSubmitted).toLowerCase()}`],
    ['Daily P&L', `<span class="${(s.dailyPnlKrw || 0) >= 0 ? 'positive' : 'negative'}">${formatCurrency(s.dailyPnlKrw || 0)}</span>`, formatPercent(s.dailyReturnPct || 0)],
    ['Total return', `<span class="${totalClass}">${formatPercent(s.totalReturnPct)}</span>`, `${formatCurrency(Math.abs(s.totalPnlKrw || 0))} ${s.totalPnlKrw >= 0 ? 'gain' : 'loss'}`],
    ['Latest poll P&L', `<span class="${pollClass}">${formatCurrency(latest.pnlKrw || 0)}</span>`, formatPercent(latest.returnPct || 0)],
    ['Cumulative fees', formatCurrency(s.cumulativeFeesKrw || 0), s.feeNote || 'Recorded/estimated Upbit fees'],
    ['Fee drag today', formatCurrency(s.feeDragTodayKrw || 0), 'Actual + estimated daily fees'],
    ['Phase status', `1 ${s.phase1Status || '—'} · 2 ${s.phase2Status || '—'} · 3 ${s.phase3Status || '—'}`, 'Assessment rollout'],
    ['Warnings', `${s.warningCount || 0} latest`, `${s.rejectionWarningCount || 0} rejection · ${s.eligibilityWarningCount || 0} eligibility`],
    ['Trades / reports', `${s.tradeCount || 0} / ${s.reportCount || 0}`, s.strategy || 'Breakout Rotation'],
  ];
  els.summaryGrid.innerHTML = cards.map(([label, value, note]) => `
    <article class="stat-card">
      <p class="eyebrow">${label}</p>
      <strong>${value}</strong>
      <small>${note}</small>
    </article>
  `).join('');
}

function chartValue(point, idx, firstNav) {
  if (state.chartMode === 'return') return firstNav ? ((point.navAfter - firstNav) / firstNav) * 100 : 0;
  if (state.chartMode === 'pnl') return point.pnlKrw || 0;
  return point.navAfter || 0;
}

function metricLabel(value) {
  if (state.chartMode === 'return') return formatPercent(value);
  return formatCurrency(value);
}

function visibleChartPoints() {
  return filterPointsByWindow(state.payload.equitySeries || [], state.chartWindow);
}

function selectedPoint(points) {
  if (!points.length) return null;
  const idx = state.selectedPointIndex == null ? points.length - 1 : Math.max(0, Math.min(points.length - 1, state.selectedPointIndex));
  return { point: points[idx], index: idx };
}

function renderChartDetails(points, values) {
  const selected = selectedPoint(points);
  if (!selected) {
    els.chartDetails.innerHTML = '<span class="panel-note">Hover or tap the chart to inspect a point.</span>';
    return;
  }
  const { point, index } = selected;
  els.chartDetails.innerHTML = `
    <div class="detail-pill"><span>Selected</span><strong>${formatTime(point.time)}</strong></div>
    <div class="detail-pill"><span>NAV</span><strong>${formatCurrency(point.navAfter)}</strong></div>
    <div class="detail-pill"><span>Poll P&amp;L</span><strong class="${point.pnlKrw >= 0 ? 'positive' : 'negative'}">${formatCurrency(point.pnlKrw)} (${formatPercent(point.returnPct)})</strong></div>
    <div class="detail-pill"><span>Cum. fees</span><strong>${formatCurrency(point.cumulativeFeesKrw || 0)}</strong></div>
    <div class="detail-pill"><span>${state.chartMode === 'return' ? 'Window return' : state.chartMode === 'pnl' ? 'Plotted P&L' : 'Plotted NAV'}</span><strong>${metricLabel(values[index])}</strong></div>
    <div class="detail-pill wide"><span>Allocation</span><strong>${point.allocationText || '—'}</strong></div>
  `;
}

function renderChart() {
  const points = visibleChartPoints();
  els.legend.innerHTML = `<span><span class="dot" style="background:#f97316"></span>Pilot 3 Upbit</span><span>${state.chartWindow === 'all' ? 'All reports' : `Last ${state.chartWindow}`}</span>`;
  if (points.length < 2) {
    els.chart.innerHTML = '<text x="480" y="190" text-anchor="middle" fill="#94a3b8">Need at least two live reports for chart</text>';
    renderChartDetails(points, []);
    return;
  }
  if (state.selectedPointIndex == null || state.selectedPointIndex >= points.length) state.selectedPointIndex = points.length - 1;
  const width = 960, height = 380, pad = 44;
  const firstNav = points[0].navBefore || points[0].navAfter || 0;
  const values = points.map((p, idx) => chartValue(p, idx, firstNav));
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const min = state.chartMode === 'nav' ? Math.min(rawMin, STARTING_NAV_KRW) : rawMin;
  const max = state.chartMode === 'nav' ? Math.max(rawMax, STARTING_NAV_KRW) : rawMax;
  const span = max - min || 1;
  const x = (i) => pad + (i / Math.max(points.length - 1, 1)) * (width - pad * 2);
  const y = (v) => height - pad - ((v - min) / span) * (height - pad * 2);
  const xs = values.map((_, i) => x(i));
  const d = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const area = `${d} L ${x(points.length - 1)} ${height - pad} L ${x(0)} ${height - pad} Z`;
  const selected = selectedPoint(points);
  const selectedX = x(selected.index);
  const selectedY = y(values[selected.index]);
  const baselineY = state.chartMode === 'nav' ? y(STARTING_NAV_KRW) : null;
  const baselineMarkup = baselineY == null ? '' : `
    <line class="chart-baseline" x1="${pad}" x2="${width-pad}" y1="${baselineY}" y2="${baselineY}" />
    <rect x="${pad + 8}" y="${Math.max(8, baselineY - 23)}" width="164" height="22" rx="11" class="chart-baseline-label-bg" />
    <text x="${pad + 18}" y="${Math.max(24, baselineY - 8)}" class="chart-baseline-label">Start ${formatCurrency(STARTING_NAV_KRW)}</text>
  `;
  const label = metricLabel(values.at(-1));
  els.chart.innerHTML = `
    <defs>
      <linearGradient id="upbitLine" x1="0" x2="1"><stop stop-color="#f97316"/><stop offset="1" stop-color="#14b8a6"/></linearGradient>
      <linearGradient id="upbitArea" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#f97316" stop-opacity=".25"/><stop offset="1" stop-color="#14b8a6" stop-opacity="0"/></linearGradient>
    </defs>
    <rect x="0" y="0" width="960" height="380" rx="24" fill="rgba(15,23,42,.35)" />
    ${[0,1,2,3].map(i => `<line x1="${pad}" x2="${width-pad}" y1="${pad + i*(height-pad*2)/3}" y2="${pad + i*(height-pad*2)/3}" stroke="rgba(148,163,184,.16)"/>`).join('')}
    ${baselineMarkup}
    <path d="${area}" fill="url(#upbitArea)" />
    <path d="${d}" fill="none" stroke="url(#upbitLine)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
    ${values.map((v,i) => `<circle class="chart-dot" data-index="${i}" cx="${x(i)}" cy="${y(v)}" r="${i === selected.index ? 6 : 3.5}" fill="${i === selected.index ? '#14b8a6' : '#f8fafc'}"><title>${formatTime(points[i].time)} — ${metricLabel(v)}</title></circle>`).join('')}
    <line class="chart-crosshair" x1="${selectedX}" x2="${selectedX}" y1="${pad}" y2="${height-pad}" />
    <line class="chart-crosshair" x1="${pad}" x2="${width-pad}" y1="${selectedY}" y2="${selectedY}" />
    <circle cx="${selectedX}" cy="${selectedY}" r="9" fill="none" stroke="#14b8a6" stroke-width="2" />
    <g class="chart-tooltip" transform="translate(${Math.min(width - 250, selectedX + 14)} ${Math.max(18, selectedY - 58)})">
      <rect width="232" height="74" rx="12" fill="rgba(15,23,42,.94)" stroke="rgba(20,184,166,.45)" />
      <text x="12" y="24" fill="#e2e8f0" font-size="14" font-weight="800">${formatTime(selected.point.time)}</text>
      <text x="12" y="46" fill="#94a3b8" font-size="12">${state.chartMode.toUpperCase()}: ${metricLabel(values[selected.index])}</text>
      <text x="12" y="64" fill="${selected.point.pnlKrw >= 0 ? '#34d399' : '#fb7185'}" font-size="12">Poll P&L ${formatCurrency(selected.point.pnlKrw)}</text>
    </g>
    <rect id="chartHoverLayer" x="${pad}" y="${pad}" width="${width - pad * 2}" height="${height - pad * 2}" fill="transparent" style="cursor: crosshair" />
    <text x="${width-pad}" y="32" text-anchor="end" fill="#e2e8f0" font-size="18" font-weight="800">${label}</text>
    <text x="${pad}" y="${height-14}" fill="#94a3b8" font-size="12">${formatTime(points[0].time)}</text>
    <text x="${width-pad}" y="${height-14}" text-anchor="end" fill="#94a3b8" font-size="12">${formatTime(points.at(-1).time)}</text>
  `;
  const hoverLayer = els.chart.querySelector('#chartHoverLayer');
  hoverLayer.addEventListener('pointermove', (event) => {
    const rect = els.chart.getBoundingClientRect();
    const viewX = ((event.clientX - rect.left) / rect.width) * width;
    const idx = nearestPointIndex(xs, viewX);
    if (idx !== -1 && idx !== state.selectedPointIndex) {
      state.selectedPointIndex = idx;
      renderChart();
    }
  });
  hoverLayer.addEventListener('pointerleave', () => {
    renderChartDetails(points, values);
  });
  els.chart.querySelectorAll('.chart-dot').forEach((dot) => {
    dot.addEventListener('click', () => {
      state.selectedPointIndex = Number(dot.dataset.index);
      renderChart();
    });
  });
  renderChartDetails(points, values);
}

function renderAllocation() {
  const weights = state.payload.latest?.weightsAfter || {};
  const rows = Object.entries(weights).filter(([, v]) => Number(v) > 0.0001).sort((a,b) => b[1] - a[1]);
  els.allocation.innerHTML = `
    <article class="note-card mode-card">
      <div class="note-meta"><span>Strategy mode</span><span>${formatMode(state.payload.summary?.strategyMode || 'paper-aligned')}</span></div>
      <div class="note-meta"><span>Freeze mode</span><span>${formatMode(state.payload.summary?.freezeMode || 'normal')}</span></div>
      <div class="note-meta"><span>Freeze reason</span><span>${state.payload.summary?.freezeModeReason || state.payload.summary?.riskFreezeReason || '—'}</span></div>
      <div class="note-meta"><span>Latest status</span><span>${state.payload.summary?.latestStatus || '—'}</span></div>
    </article>
    <article class="note-card">
      <div class="note-meta"><span>Target</span><span>${state.payload.summary?.targetAllocation || '—'}</span></div>
      <div class="note-meta"><span>Current</span><span>${state.payload.summary?.currentAllocation || '—'}</span></div>
      <div class="note-meta"><span>Reason</span><span>${state.payload.summary?.latestReason || '—'}</span></div>
    </article>
    ${rows.map(([symbol, weight]) => `
      <div class="allocation-row">
        <div class="allocation-symbol">${symbol}</div>
        <div class="allocation-bar"><div class="allocation-fill" style="width:${Math.max(0, Math.min(100, weight*100))}%"></div></div>
        <div class="allocation-pct">${(weight*100).toFixed(1)}%</div>
      </div>
    `).join('')}
  `;
}

function renderGuardrails() {
  const g = state.payload.guardrails || {};
  els.guardrails.innerHTML = `<article class="note-card"><ul class="guardrail-list">
    <li>${g.universe || 'Core liquid v2 universe: BTC, ETH, SOL, XRP, LINK, DOGE, AVAX'}</li>
    <li>Min ${g.minThirtyMinuteCandles || 337} 30-minute candles</li>
    <li>Min ${formatCurrency(g.min24hQuoteVolumeKrw || 1000000000)} 24h quote volume</li>
    <li>Excluded: ${(g.excluded || []).join(', ')}</li>
    <li>Score: ${g.score || '24h + 0.2 × 7d'}</li>
    <li>${g.capitalPolicy || 'Full available account NAV'}</li>
  </ul></article>`;
}

function renderPhaseAssessment() {
  const phases = state.payload.phaseAssessment || {};
  const rows = ['phase1', 'phase2', 'phase3'].map((key) => phases[key]).filter(Boolean);
  if (!els.phaseAssessment) return;
  els.phaseAssessment.innerHTML = rows.map((phase) => `
    <article class="phase-card phase-${String(phase.status || 'unknown').replace(/[^a-z0-9_-]/gi, '-')}">
      <div class="phase-head">
        <h3>${phase.title || 'Phase'}</h3>
        <span>${phase.status || 'unknown'}</span>
      </div>
      <p>${phase.summary || ''}</p>
      <ul>${(phase.evidence || []).map((item) => `<li>${item}</li>`).join('')}</ul>
    </article>
  `).join('') || '<p class="panel-note">Phase assessment has not been generated yet.</p>';
}

function renderLeaders() {
  const leaders = state.payload.latest?.rankedCandidates || [];
  els.leaders.innerHTML = leaders.slice(0, 8).map((row, i) => `
    <div class="leader-row">
      <div class="leader-rank">${i + 1}</div>
      <div>
        <div class="leader-symbol">${row.symbol}</div>
        <div class="leader-meta">24h ${formatPercent(row.r24Pct)} · 7d ${formatPercent(row.r7Pct)}</div>
      </div>
      <div class="leader-score">${formatPercent(row.scorePct)}</div>
    </div>
  `).join('') || '<p class="panel-note">No ranked candidates in latest report.</p>';
}

function renderTransactions() {
  const q = state.query.trim().toLowerCase();
  const rows = (state.payload.transactions || []).filter((tx) => JSON.stringify(tx).toLowerCase().includes(q)).slice().reverse();
  els.txBody.innerHTML = rows.map((tx) => `
    <tr>
      <td>${formatTime(tx.time)}</td>
      <td><span class="${tx.side === 'BUY' ? 'positive' : 'negative'}">${tx.side}</span></td>
      <td>${tx.symbol || '—'}</td>
      <td>${formatCurrency(tx.notionalKrw)}</td>
      <td>${formatCurrency(tx.feeKrw || 0)}</td>
      <td>${formatCurrency(tx.cumulativeFeesKrw || 0)}</td>
      <td>${tx.state || '—'}</td>
      <td class="uuid-cell">${tx.uuid || '—'}</td>
    </tr>
  `).join('') || '<tr><td colspan="8">No executions match the current search.</td></tr>';
}

function renderRuns() {
  const rows = (state.payload.equitySeries || []).slice().reverse();
  els.runsBody.innerHTML = rows.map((run) => `
    <tr>
      <td>${formatTime(run.time)}</td>
      <td>${formatCurrency(run.navBefore)}</td>
      <td>${formatCurrency(run.navAfter)}</td>
      <td><span class="${run.pnlKrw >= 0 ? 'positive' : 'negative'}">${formatCurrency(run.pnlKrw)} (${formatPercent(run.returnPct)})</span></td>
      <td>${formatCurrency(run.feesKrw || 0)}</td>
      <td>${formatCurrency(run.cumulativeFeesKrw || 0)}</td>
      <td>${run.allocationText}</td>
      <td>${run.targetReason}</td>
    </tr>
  `).join('') || '<tr><td colspan="8">No live reports found.</td></tr>';
}

function renderAll() {
  renderSummary();
  renderChart();
  renderAllocation();
  renderGuardrails();
  renderPhaseAssessment();
  renderLeaders();
  renderTransactions();
  renderRuns();
}

document.querySelectorAll('[data-chart-mode]').forEach((button) => {
  button.addEventListener('click', () => {
    state.chartMode = button.dataset.chartMode;
    state.selectedPointIndex = null;
    document.querySelectorAll('[data-chart-mode]').forEach((b) => b.classList.toggle('active', b === button));
    renderChart();
  });
});

document.querySelectorAll('[data-chart-window]').forEach((button) => {
  button.addEventListener('click', () => {
    state.chartWindow = button.dataset.chartWindow;
    state.selectedPointIndex = null;
    document.querySelectorAll('[data-chart-window]').forEach((b) => b.classList.toggle('active', b === button));
    renderChart();
  });
});

els.refreshButton.addEventListener('click', () => loadData(true));
els.search.addEventListener('input', (event) => {
  state.query = event.target.value;
  renderTransactions();
});

loadData();
