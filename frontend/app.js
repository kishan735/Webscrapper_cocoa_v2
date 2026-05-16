const fmtNum = (v, dp = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp });
};
const fmtInt = (v) => (v === null || v === undefined ? '—' : Number(v).toLocaleString());
const fmtPct = (v) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`);
const colorClass = (v) => (v > 0 ? 'up' : v < 0 ? 'dn' : '');

let chart = null;
let oiChart = null;
let candleSeries = null;
let volSeries = null;
let oiSeries = null;
let activeSymbol = null;
let lastUpdateAt = null;

function initCharts() {
  const chartEl = document.getElementById('chart');
  const oiEl = document.getElementById('oi-chart');
  const common = {
    layout: { background: { color: '#161c24' }, textColor: '#8a95a3' },
    grid: { vertLines: { color: '#1a2129' }, horzLines: { color: '#1a2129' } },
    rightPriceScale: { borderColor: '#1f2832' },
    timeScale: { borderColor: '#1f2832', timeVisible: false },
  };
  chart = LightweightCharts.createChart(chartEl, { ...common, height: 360, autoSize: true });
  candleSeries = chart.addCandlestickSeries({ upColor: '#2ecc71', downColor: '#e74c3c', borderVisible: false, wickUpColor: '#2ecc71', wickDownColor: '#e74c3c' });
  volSeries = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'volume', color: '#3b4654' });
  chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

  oiChart = LightweightCharts.createChart(oiEl, { ...common, height: 120, autoSize: true });
  oiSeries = oiChart.addHistogramSeries({ color: '#f5a623', priceFormat: { type: 'volume' } });

  chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (range) oiChart.timeScale().setVisibleLogicalRange(range);
  });
}

async function fetchJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function loadCurve() {
  const data = await fetchJSON('/api/curve');
  lastUpdateAt = data.as_of;
  const tbody = document.querySelector('#curve-table tbody');
  tbody.innerHTML = '';
  if (!data.rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty">No contracts yet — scrapers running. Try POST /api/admin/run/ice or /api/admin/run/intraday.</td></tr>';
    return;
  }
  for (const r of data.rows) {
    const tr = document.createElement('tr');
    tr.dataset.symbol = r.symbol;
    const chgCls = colorClass(r.change ?? 0);
    tr.innerHTML = `
      <td class="sym">${r.contract_month}</td>
      <td class="num">${fmtNum(r.last)}</td>
      <td class="num">${fmtNum(r.settle)}</td>
      <td class="num ${chgCls}">${r.change == null ? '—' : (r.change > 0 ? '+' : '') + fmtNum(r.change)}</td>
      <td class="num ${chgCls}">${fmtPct(r.change_pct)}</td>
      <td class="num">${fmtInt(r.volume)}</td>
      <td class="num">${fmtInt(r.open_interest)}</td>
      <td class="ts">${r.updated_at ? new Date(r.updated_at).toLocaleString() : '—'}</td>
    `;
    tr.addEventListener('click', () => selectContract(r.symbol, r.contract_month));
    tbody.appendChild(tr);
  }
  if (!activeSymbol && data.rows.length) {
    selectContract(data.rows[0].symbol, data.rows[0].contract_month);
  } else if (activeSymbol) {
    highlightRow(activeSymbol);
  }
}

function highlightRow(symbol) {
  document.querySelectorAll('#curve-table tbody tr').forEach((tr) => {
    tr.classList.toggle('active', tr.dataset.symbol === symbol);
  });
}

async function selectContract(symbol, label) {
  activeSymbol = symbol;
  highlightRow(symbol);
  document.getElementById('chart-title').textContent = label || symbol;
  document.getElementById('chart-sub').textContent = symbol;
  try {
    const data = await fetchJSON(`/api/contract/${encodeURIComponent(symbol)}/history`);
    const ohlc = data.ohlc.filter((r) => r.close != null).map((r) => ({
      time: r.date,
      open: r.open ?? r.close,
      high: r.high ?? r.close,
      low: r.low ?? r.close,
      close: r.close,
    }));
    const vol = data.ohlc.filter((r) => r.volume != null).map((r) => ({ time: r.date, value: r.volume, color: '#3b4654' }));
    const oi = data.ohlc.filter((r) => r.open_interest != null).map((r) => ({ time: r.date, value: r.open_interest }));
    candleSeries.setData(ohlc);
    volSeries.setData(vol);
    oiSeries.setData(oi);
    chart.timeScale().fitContent();
    oiChart.timeScale().fitContent();
  } catch (e) {
    console.warn('history load failed', e);
  }
}

async function loadCot() {
  const data = await fetchJSON('/api/positioning');
  const tbody = document.querySelector('#cot-table tbody');
  tbody.innerHTML = '';
  if (!data.rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">No COT data yet. Triggers Fri 21:00 London, or POST /api/admin/run/cftc.</td></tr>';
    return;
  }
  for (const r of [...data.rows].reverse()) {
    const net = (r.mm_long ?? 0) - (r.mm_short ?? 0);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.report_date}</td>
      <td class="num">${fmtInt(r.mm_long)}</td>
      <td class="num">${fmtInt(r.mm_short)}</td>
      <td class="num ${colorClass(net)}">${net > 0 ? '+' : ''}${fmtInt(net)}</td>
      <td class="num">${fmtInt(r.commercial_long)}</td>
      <td class="num">${fmtInt(r.commercial_short)}</td>
      <td class="num">${fmtInt(r.open_interest_all)}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function loadHealth() {
  try {
    const health = await fetchJSON('/api/health');
    const parts = Object.entries(health.sources).map(
      ([src, s]) => `${src}: ${s.status}${s.rows_written ? ` (${s.rows_written})` : ''}`
    );
    document.getElementById('status').textContent = parts.length ? parts.join(' · ') : 'no scrapes yet';
  } catch (e) {
    document.getElementById('status').textContent = 'health endpoint unavailable';
  }
  document.getElementById('footer-info').textContent =
    `Last refresh: ${lastUpdateAt ? new Date(lastUpdateAt).toLocaleTimeString() : '—'} · Data: ICE Liffe C · ` +
    `Scrapers: intraday 5min · EOD 19:30 London · COT Fri 21:00 London`;
}

async function refreshAll() {
  try {
    await Promise.all([loadCurve(), loadCot(), loadHealth()]);
  } catch (e) {
    console.error(e);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  initCharts();
  refreshAll();
  setInterval(refreshAll, 60_000);
});
