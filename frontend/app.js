const fmtNum = (v, dp = 2) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp });
};
const fmtInt = (v) => (v === null || v === undefined ? '—' : Number(v).toLocaleString());
const fmtPct = (v) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`);
const colorClass = (v) => (v > 0 ? 'up' : v < 0 ? 'dn' : '');

let chart = null;
let oiChart = null;
let shapeChart = null;
let cotChart = null;
let candleSeries = null;
let volSeries = null;
let oiSeries = null;
let shapeSeries = null;
let cotMmSeries = null;
let cotCommSeries = null;
let activeSymbol = null;
let activeLabel = null;
let lastUpdateAt = null;

let fxRate = null;
let displayCcy = 'GBP';
let chartTimeframe = 'D';
let chartSeries = 'continuous';
let lastCurveRows = null;
let lastHistoryData = null;

const MONTHS = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };

function contractMonthToEpoch(label) {
  const m = /^([A-Za-z]{3})\s+(\d{4})$/.exec((label || '').trim());
  if (!m || !(m[1] in MONTHS)) return null;
  return Math.floor(Date.UTC(parseInt(m[2], 10), MONTHS[m[1]], 15) / 1000);
}

function convertPrice(v) {
  if (v == null || Number.isNaN(v)) return v;
  return displayCcy === 'USD' && fxRate ? v * fxRate : v;
}

function initCharts() {
  const chartEl = document.getElementById('chart');
  const common = {
    layout: { background: { color: '#161c24' }, textColor: '#8a95a3' },
    grid: { vertLines: { color: '#1a2129' }, horzLines: { color: '#1a2129' } },
    rightPriceScale: { borderColor: '#1f2832' },
    timeScale: { borderColor: '#1f2832', timeVisible: false },
  };
  chart = LightweightCharts.createChart(chartEl, { ...common, height: 280, autoSize: true });
  candleSeries = chart.addCandlestickSeries({ upColor: '#2ecc71', downColor: '#e74c3c', borderVisible: false, wickUpColor: '#2ecc71', wickDownColor: '#e74c3c' });
  volSeries = chart.addHistogramSeries({
    color: '#3b4654',
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
  });
  chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });

  const oiEl = document.getElementById('oi-chart');
  if (oiEl) {
    oiChart = LightweightCharts.createChart(oiEl, {
      ...common,
      height: 110,
      autoSize: true,
      timeScale: { ...common.timeScale, timeVisible: false, secondsVisible: false },
    });
    oiSeries = oiChart.addLineSeries({ color: '#f5a623', lineWidth: 2, priceLineVisible: false });
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range && oiChart) oiChart.timeScale().setVisibleLogicalRange(range);
    });
  }

  const shapeEl = document.getElementById('curve-shape');
  shapeChart = LightweightCharts.createChart(shapeEl, {
    ...common,
    height: 140,
    autoSize: true,
    timeScale: { ...common.timeScale, timeVisible: false, secondsVisible: false },
  });
  shapeSeries = shapeChart.addLineSeries({ color: '#f5a623', lineWidth: 2, priceLineVisible: false });

  const cotEl = document.getElementById('cot-chart');
  if (cotEl) {
    cotChart = LightweightCharts.createChart(cotEl, {
      ...common,
      height: 200,
      autoSize: true,
      timeScale: { ...common.timeScale, timeVisible: false, secondsVisible: false },
    });
    cotMmSeries = cotChart.addLineSeries({ color: '#f5a623', lineWidth: 2, priceLineVisible: false });
    cotCommSeries = cotChart.addLineSeries({ color: '#3b8a8a', lineWidth: 2, priceLineVisible: false });
  }
}

function isoDateToEpoch(iso) {
  const d = new Date(iso + 'T00:00:00Z');
  const t = d.getTime();
  return Number.isFinite(t) ? Math.floor(t / 1000) : null;
}

function renderCotChart(rows) {
  if (!cotMmSeries || !cotCommSeries) return;
  const ordered = [...rows].sort((a, b) => (a.report_date < b.report_date ? -1 : 1));
  const mmPts = ordered
    .map((r) => {
      const t = isoDateToEpoch(r.report_date);
      if (t == null || r.mm_long == null || r.mm_short == null) return null;
      return { time: t, value: r.mm_long - r.mm_short };
    })
    .filter(Boolean);
  const commPts = ordered
    .map((r) => {
      const t = isoDateToEpoch(r.report_date);
      if (t == null || r.commercial_long == null || r.commercial_short == null) return null;
      return { time: t, value: r.commercial_long - r.commercial_short };
    })
    .filter(Boolean);
  cotMmSeries.setData(mmPts);
  cotCommSeries.setData(commPts);
  cotChart.timeScale().fitContent();
}

function renderCurveTable(rows) {
  const tbody = document.querySelector('#curve-table tbody');
  tbody.innerHTML = '';
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty">No contracts yet — scrapers running. Try POST /api/admin/run/ice or /api/admin/run/intraday.</td></tr>';
    return;
  }
  for (const r of rows) {
    const tr = document.createElement('tr');
    tr.dataset.symbol = r.symbol;
    const chgCls = colorClass(r.change ?? 0);
    const last = convertPrice(r.last);
    const settle = convertPrice(r.settle);
    const change = convertPrice(r.change);
    tr.innerHTML = `
      <td class="sym">${r.contract_month}</td>
      <td class="num">${fmtNum(last)}</td>
      <td class="num">${fmtNum(settle)}</td>
      <td class="num ${chgCls}">${change == null ? '—' : (change > 0 ? '+' : '') + fmtNum(change)}</td>
      <td class="num ${chgCls}">${fmtPct(r.change_pct)}</td>
      <td class="num">${fmtInt(r.volume)}</td>
      <td class="num">${fmtInt(r.open_interest)}</td>
      <td class="ts">${r.updated_at ? new Date(r.updated_at).toLocaleString() : '—'}</td>
    `;
    tr.addEventListener('click', () => selectContract(r.symbol, r.contract_month));
    tbody.appendChild(tr);
  }
  if (rows.every((r) => r.change == null)) {
    const hint = document.createElement('tr');
    hint.className = 'hint';
    hint.innerHTML = '<td colspan="8">Change vs prior settle populates after the next EOD scrape (~19:30 London).</td>';
    tbody.appendChild(hint);
  }
  if (activeSymbol) highlightRow(activeSymbol);
}

function renderCurveShape(rows) {
  if (!shapeSeries) return;
  const points = rows
    .map((r) => {
      const t = contractMonthToEpoch(r.contract_month);
      const raw = r.settle ?? r.last;
      const v = convertPrice(raw);
      return t != null && v != null ? { time: t, value: Number(v) } : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.time - b.time);
  shapeSeries.setData(points);
  shapeChart.timeScale().fitContent();
}

function renderHistoryChart(data) {
  const rows = (data && data.ohlc) || [];
  const ohlc = rows.filter((r) => r.close != null).map((r) => ({
    time: r.date,
    open: convertPrice(r.open ?? r.close),
    high: convertPrice(r.high ?? r.close),
    low: convertPrice(r.low ?? r.close),
    close: convertPrice(r.close),
  }));
  const vol = rows.filter((r) => r.volume != null).map((r) => ({ time: r.date, value: r.volume, color: '#3b4654' }));
  const oi = rows.filter((r) => r.open_interest != null).map((r) => ({ time: r.date, value: r.open_interest }));
  candleSeries.setData(ohlc);
  volSeries.setData(vol);
  if (oiSeries) oiSeries.setData(oi);
  chart.timeScale().fitContent();
  if (oiChart) oiChart.timeScale().fitContent();

  const empty = document.getElementById('chart-empty');
  if (empty) empty.classList.toggle('hidden', ohlc.length > 1);

  const noteEl = document.getElementById('chart-note');
  if (noteEl) {
    const parts = [];
    if (data && data.series_label) parts.push(`Source: ${data.series_label}`);
    if (oi.length === 0 && ohlc.length > 0) parts.push('OI: no source yet (yfinance feed has no OI; ICE extraction pending)');
    if (data && data.note) parts.push(data.note);
    noteEl.textContent = parts.join(' · ');
  }
}

function updateCurveSubtitle() {
  const sub = document.getElementById('curve-sub');
  if (sub) sub.textContent = `${displayCcy}/t · ICE Liffe C`;
}

function rerenderForCcy() {
  updateCurveSubtitle();
  if (lastCurveRows) {
    renderCurveTable(lastCurveRows);
    renderCurveShape(lastCurveRows);
  }
  if (lastHistoryData) renderHistoryChart(lastHistoryData);
}

async function fetchJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function loadFxRate() {
  try {
    const r = await fetch('https://api.frankfurter.dev/v1/latest?from=GBP&to=USD');
    if (!r.ok) return;
    const data = await r.json();
    const v = data && data.rates && data.rates.USD;
    if (typeof v === 'number' && v > 0) {
      fxRate = v;
      const input = document.getElementById('fx-rate');
      if (input) input.value = v.toFixed(4);
      rerenderForCcy();
    }
  } catch (e) {
    console.warn('FX fetch failed', e);
  }
}

function initFxControls() {
  const input = document.getElementById('fx-rate');
  const refresh = document.getElementById('fx-refresh');
  const gbpBtn = document.getElementById('ccy-gbp');
  const usdBtn = document.getElementById('ccy-usd');
  if (input) {
    input.addEventListener('input', () => {
      const v = parseFloat(input.value);
      fxRate = Number.isFinite(v) && v > 0 ? v : null;
      rerenderForCcy();
    });
  }
  if (refresh) refresh.addEventListener('click', loadFxRate);
  if (gbpBtn) gbpBtn.addEventListener('click', () => setDisplayCcy('GBP'));
  if (usdBtn) usdBtn.addEventListener('click', () => setDisplayCcy('USD'));
}

async function downloadCotCsv() {
  const btn = document.getElementById('cot-download');
  if (btn) btn.disabled = true;
  try {
    const r = await fetch('/api/positioning.csv', { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'cocoa-cftc.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) {
    console.error('CSV download failed', e);
    alert(`Download failed: ${e.message}. Restart uvicorn if /api/positioning.csv was just added.`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function setDisplayCcy(ccy) {
  if (ccy !== 'GBP' && ccy !== 'USD') return;
  displayCcy = ccy;
  document.getElementById('ccy-gbp').classList.toggle('active', ccy === 'GBP');
  document.getElementById('ccy-usd').classList.toggle('active', ccy === 'USD');
  rerenderForCcy();
}

async function loadCurve() {
  const data = await fetchJSON('/api/curve');
  lastUpdateAt = data.as_of;
  lastCurveRows = data.rows;
  renderCurveTable(data.rows);
  renderCurveShape(data.rows);
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

async function loadHistory() {
  if (!activeSymbol) return;
  const empty = document.getElementById('chart-empty');
  const params = new URLSearchParams({ series: chartSeries, tf: chartTimeframe });
  try {
    const data = await fetchJSON(`/api/contract/${encodeURIComponent(activeSymbol)}/history?${params.toString()}`);
    lastHistoryData = data;
    renderHistoryChart(data);
  } catch (e) {
    console.warn('history load failed', e);
    if (empty) empty.classList.remove('hidden');
  }
}

async function selectContract(symbol, label) {
  activeSymbol = symbol;
  activeLabel = label;
  highlightRow(symbol);
  document.getElementById('chart-title').textContent = label || symbol;
  document.getElementById('chart-sub').textContent = symbol;
  await loadHistory();
}

function setChartTimeframe(tf) {
  if (!['D', 'W', 'M'].includes(tf)) return;
  chartTimeframe = tf;
  document.querySelectorAll('.tf-toggle button').forEach((b) => {
    b.classList.toggle('active', b.dataset.tf === tf);
  });
  loadHistory();
}

function setChartSeries(series) {
  if (!['this', 'continuous'].includes(series)) return;
  chartSeries = series;
  const cont = document.getElementById('series-continuous');
  const ths = document.getElementById('series-this');
  if (cont) cont.classList.toggle('active', series === 'continuous');
  if (ths) ths.classList.toggle('active', series === 'this');
  loadHistory();
}

function initChartControls() {
  document.querySelectorAll('.tf-toggle button').forEach((b) => {
    b.addEventListener('click', () => setChartTimeframe(b.dataset.tf));
  });
  const cont = document.getElementById('series-continuous');
  const ths = document.getElementById('series-this');
  if (cont) cont.addEventListener('click', () => setChartSeries('continuous'));
  if (ths) ths.addEventListener('click', () => setChartSeries('this'));
}

async function loadCot() {
  const data = await fetchJSON('/api/positioning');
  renderCotChart(data.rows);
}

async function fetchHealthWithRetry(attempts = 3, backoffMs = 2000) {
  let lastErr = null;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fetchJSON('/api/health');
    } catch (e) {
      lastErr = e;
      if (i < attempts - 1) await new Promise((res) => setTimeout(res, backoffMs));
    }
  }
  throw lastErr;
}

async function loadHealth() {
  const statusEl = document.getElementById('status');
  if (statusEl) {
    const cur = statusEl.textContent.trim();
    if (cur === '' || cur === 'checking…' || cur.includes('unavailable')) {
      statusEl.textContent = 'checking…';
    }
  }
  try {
    const health = await fetchHealthWithRetry();
    const parts = Object.entries(health.sources).map(
      ([src, s]) => `${src}: ${s.status}${s.rows_written ? ` (${s.rows_written})` : ''}`
    );
    if (statusEl) statusEl.textContent = parts.length ? parts.join(' · ') : 'no scrapes yet';
  } catch (e) {
    if (statusEl) statusEl.textContent = 'health endpoint unavailable';
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
  initFxControls();
  initChartControls();
  updateCurveSubtitle();
  const dlBtn = document.getElementById('cot-download');
  if (dlBtn) dlBtn.addEventListener('click', downloadCotCsv);
  loadFxRate();
  refreshAll();
  setInterval(refreshAll, 60_000);
});
