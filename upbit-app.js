const state = {
  payload: null,
  chartMode: 'nav',
  query: '',
};

const els = {
  status: document.querySelector('#dataStatus'),
  refreshMeta: document.querySelector('#refreshMeta'),
  refreshButton: document.querySelector('#refreshButton'),
  summaryGrid: document.querySelector('#summaryGrid'),
  chart: document.querySelector('#equityChart'),
  legend: document.querySelector('#chartLegend'),
  allocation: document.querySelector('#allocationPanel'),
  guardrails: document.querySelector('#guardrailsPanel'),
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
  const cards = [
    ['Current NAV', formatCurrency(s.currentNav), `Latest ${formatTime(s.latestTime)}`],
    ['Total return', `<span class="${totalClass}">${formatPercent(s.totalReturnPct)}</span>`, `${formatCurrency(Math.abs(s.totalPnlKrw || 0))} ${s.totalPnlKrw >= 0 ? 'gain' : 'loss'}`],
    ['Latest poll P&L', `<span class="${pollClass}">${formatCurrency(latest.pnlKrw || 0)}</span>`, formatPercent(latest.returnPct || 0)],
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

function renderChart() {
  const points = state.payload.equitySeries || [];
  els.legend.innerHTML = '<span><span class="dot" style="background:#f97316"></span>Pilot 3 Upbit</span>';
  if (points.length < 2) {
    els.chart.innerHTML = '<text x="480" y="190" text-anchor="middle" fill="#94a3b8">Need at least two live reports for chart</text>';
    return;
  }
  const width = 960, height = 380, pad = 44;
  const firstNav = points[0].navBefore || points[0].navAfter || 0;
  const values = points.map((p, idx) => chartValue(p, idx, firstNav));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const x = (i) => pad + (i / Math.max(points.length - 1, 1)) * (width - pad * 2);
  const y = (v) => height - pad - ((v - min) / span) * (height - pad * 2);
  const d = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const area = `${d} L ${x(points.length - 1)} ${height - pad} L ${x(0)} ${height - pad} Z`;
  const label = state.chartMode === 'nav' ? formatCurrency(values.at(-1)) : state.chartMode === 'return' ? formatPercent(values.at(-1)) : formatCurrency(values.at(-1));
  els.chart.innerHTML = `
    <defs>
      <linearGradient id="upbitLine" x1="0" x2="1"><stop stop-color="#f97316"/><stop offset="1" stop-color="#14b8a6"/></linearGradient>
      <linearGradient id="upbitArea" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#f97316" stop-opacity=".25"/><stop offset="1" stop-color="#14b8a6" stop-opacity="0"/></linearGradient>
    </defs>
    <rect x="0" y="0" width="960" height="380" rx="24" fill="rgba(15,23,42,.35)" />
    ${[0,1,2,3].map(i => `<line x1="${pad}" x2="${width-pad}" y1="${pad + i*(height-pad*2)/3}" y2="${pad + i*(height-pad*2)/3}" stroke="rgba(148,163,184,.16)"/>`).join('')}
    <path d="${area}" fill="url(#upbitArea)" />
    <path d="${d}" fill="none" stroke="url(#upbitLine)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
    ${values.map((v,i) => `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="#f8fafc"><title>${formatTime(points[i].time)} — ${state.chartMode === 'return' ? formatPercent(v) : formatCurrency(v)}</title></circle>`).join('')}
    <text x="${width-pad}" y="32" text-anchor="end" fill="#e2e8f0" font-size="18" font-weight="800">${label}</text>
    <text x="${pad}" y="${height-14}" fill="#94a3b8" font-size="12">${formatTime(points[0].time)}</text>
    <text x="${width-pad}" y="${height-14}" text-anchor="end" fill="#94a3b8" font-size="12">${formatTime(points.at(-1).time)}</text>
  `;
}

function renderAllocation() {
  const weights = state.payload.latest?.weightsAfter || {};
  const rows = Object.entries(weights).filter(([, v]) => Number(v) > 0.0001).sort((a,b) => b[1] - a[1]);
  els.allocation.innerHTML = `
    <article class="note-card">
      <div class="note-meta"><span>Target</span><span>${state.payload.summary?.targetAllocation || '—'}</span></div>
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
    <li>${g.universe || 'Full Upbit KRW spot universe'}</li>
    <li>Min ${g.minThirtyMinuteCandles || 337} 30-minute candles</li>
    <li>Min ${formatCurrency(g.min24hQuoteVolumeKrw || 1000000000)} 24h quote volume</li>
    <li>Excluded: ${(g.excluded || []).join(', ')}</li>
    <li>Score: ${g.score || '24h + 0.2 × 7d'}</li>
    <li>${g.capitalPolicy || 'Full available account NAV'}</li>
  </ul></article>`;
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
      <td>${tx.state || '—'}</td>
      <td class="uuid-cell">${tx.uuid || '—'}</td>
    </tr>
  `).join('') || '<tr><td colspan="6">No executions match the current search.</td></tr>';
}

function renderRuns() {
  const rows = (state.payload.equitySeries || []).slice().reverse();
  els.runsBody.innerHTML = rows.map((run) => `
    <tr>
      <td>${formatTime(run.time)}</td>
      <td>${formatCurrency(run.navBefore)}</td>
      <td>${formatCurrency(run.navAfter)}</td>
      <td><span class="${run.pnlKrw >= 0 ? 'positive' : 'negative'}">${formatCurrency(run.pnlKrw)} (${formatPercent(run.returnPct)})</span></td>
      <td>${run.allocationText}</td>
      <td>${run.targetReason}</td>
    </tr>
  `).join('') || '<tr><td colspan="6">No live reports found.</td></tr>';
}

function renderAll() {
  renderSummary();
  renderChart();
  renderAllocation();
  renderGuardrails();
  renderLeaders();
  renderTransactions();
  renderRuns();
}

document.querySelectorAll('[data-chart-mode]').forEach((button) => {
  button.addEventListener('click', () => {
    state.chartMode = button.dataset.chartMode;
    document.querySelectorAll('[data-chart-mode]').forEach((b) => b.classList.toggle('active', b === button));
    renderChart();
  });
});

els.refreshButton.addEventListener('click', () => loadData(true));
els.search.addEventListener('input', (event) => {
  state.query = event.target.value;
  renderTransactions();
});

loadData();
