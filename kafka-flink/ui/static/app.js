'use strict';

const RANGES = [
  { minutes: 5, label: '5 min' },
  { minutes: 15, label: '15 min' },
  { minutes: 60, label: '1 hour' },
  { minutes: 360, label: '6 hours' },
];
const TILE_MINUTES = 5; // 5 minutes are served as raw 10-second windows
const SPARK_POINTS = 30;
const REFRESH_MS = 5000;
const CHART_HEIGHT = 260;
const SVG_NS = 'http://www.w3.org/2000/svg';
const HINTS = {
  druid: 'Druid needs a minute or two after startup before the datasource can be queried.',
  clickhouse: 'Check the ClickHouse container with `docker compose logs clickhouse`.',
};

const state = {
  info: null,
  minutes: readSetting('minutes', 15, (value) => RANGES.some((range) => range.minutes === value)),
  symbol: readSetting('symbol', null, (value) => typeof value === 'string'),
  symbols: [],
  tiles: null,
  series: null,
  error: null,
  updatedAt: null,
  request: 0,
  timer: null,
};

// ---------- helpers ----------

const $ = (id) => document.getElementById(id);

function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}

function s(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (parent) parent.appendChild(node);
  return node;
}

function syncChildren(container, wanted) {
  // Re-appending existing nodes would drop keyboard focus on every refresh, so only touch a changed list.
  const current = [...container.children];
  if (current.length !== wanted.length || current.some((node, index) => node !== wanted[index])) {
    container.replaceChildren(...wanted);
  }
}

function readSetting(key, fallback, valid) {
  try {
    const value = JSON.parse(localStorage.getItem(`exchange-ui.${key}`));
    return value !== null && valid(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

function writeSetting(key, value) {
  try {
    localStorage.setItem(`exchange-ui.${key}`, JSON.stringify(value));
  } catch {
    // Storage can be unavailable (private windows); the setting just won't persist.
  }
}

async function getJSON(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return body;
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const qty = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat('en-US');

function clock(ms, seconds = true) {
  return new Date(ms).toLocaleTimeString('en-GB', seconds
    ? { hour: '2-digit', minute: '2-digit', second: '2-digit' }
    : { hour: '2-digit', minute: '2-digit' });
}

function durationLabel(seconds) {
  if (seconds % 3600 === 0) return `${seconds / 3600} h`;
  if (seconds % 60 === 0) return `${seconds / 60} min`;
  return `${seconds} s`;
}

function rangeLabel(minutes) {
  return RANGES.find((range) => range.minutes === minutes)?.label ?? `${minutes} min`;
}

function groupBySymbol(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.symbol)) groups.set(row.symbol, []);
    groups.get(row.symbol).push(row);
  }
  return groups;
}

// ---------- scales & axes ----------

function scale(d0, d1, r0, r1) {
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  return (value) => r0 + (value - d0) * k;
}

function niceTicks(min, max, target) {
  if (!(max > min)) {
    const pad = Math.abs(max) * 0.001 || 1;
    min -= pad;
    max += pad;
  }
  const raw = (max - min) / target;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= raw);
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks = [];
  for (let value = lo; value <= hi + step / 2; value += step) ticks.push(Number(value.toPrecision(12)));
  return { lo, hi, step, ticks };
}

function decimalsOf(step) {
  const text = String(Number(step.toPrecision(6)));
  return text.includes('.') ? Math.min(6, text.split('.')[1].length) : 0;
}

const TIME_STEPS = [10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200].map((seconds) => seconds * 1000);

function timeTicks(t0, t1, width) {
  const maxTicks = Math.max(2, Math.floor(width / 80));
  const step = TIME_STEPS.find((candidate) => (t1 - t0) / candidate <= maxTicks) ?? TIME_STEPS.at(-1);
  const offset = new Date(t0).getTimezoneOffset() * 60000; // align ticks to local clock time
  const ticks = [];
  for (let t = Math.ceil((t0 - offset) / step) * step + offset; t <= t1; t += step) ticks.push(t);
  return { ticks, seconds: step < 60000 };
}

const measureContext = document.createElement('canvas').getContext('2d');
function textWidth(text, size = 11, weight = 400) {
  measureContext.font = `${weight} ${size}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  return measureContext.measureText(text).width;
}

function drawGrid(svg, frame, yTicks, yLabel, xTicks) {
  const { x, y, left, right, bottom, width } = frame;
  const grid = s('g', { class: 'grid' }, svg);
  for (const value of yTicks) {
    const py = Math.round(y(value)) + 0.5;
    s('line', { x1: left, x2: right, y1: py, y2: py }, grid);
    s('text', { x: left - 8, y: py, class: 'tick', 'text-anchor': 'end', 'dominant-baseline': 'middle' }, grid)
      .textContent = yLabel(value);
  }
  for (const t of xTicks.ticks) {
    const label = clock(t, xTicks.seconds);
    const px = x(t);
    const half = textWidth(label) / 2;
    if (px - half < 0 || px + half > width) continue;
    s('text', { x: px, y: bottom + 18, class: 'tick', 'text-anchor': 'middle' }, grid).textContent = label;
  }
}

// Rounded corners on the data end, square on the baseline; works for bars growing up or down.
function barPath(cx, width, base, end, radius) {
  const left = cx - width / 2;
  const right = cx + width / 2;
  const length = Math.abs(base - end);
  const r = Math.min(radius, width / 2, length);
  const dir = end < base ? 1 : -1;
  return `M${left},${base}L${left},${end + dir * r}Q${left},${end} ${left + r},${end}`
    + `L${right - r},${end}Q${right},${end} ${right},${end + dir * r}L${right},${base}Z`;
}

function splitOnGaps(points, bucketMs) {
  const segments = [];
  for (const point of points) {
    const segment = segments.at(-1);
    if (segment && point.t - segment.at(-1).t <= bucketMs * 1.5) segment.push(point);
    else segments.push([point]);
  }
  return segments;
}

// ---------- tooltip & hover ----------

const tooltip = $('tooltip');

function showTooltip(owner, content, anchorX, anchorY) {
  tooltip.replaceChildren(content);
  tooltip.hidden = false;
  tooltip.owner = owner;
  const { width, height } = tooltip.getBoundingClientRect();
  let left = anchorX + 14;
  if (left + width > window.innerWidth - 8) left = anchorX - width - 14;
  const top = Math.min(Math.max(8, anchorY - height / 2), window.innerHeight - height - 8);
  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${top}px`;
}

function hideTooltip(owner) {
  if (tooltip.owner === owner) tooltip.hidden = true;
}

function tooltipContent(point, bucketMs, rows) {
  const box = h('div', {}, h('div', { class: 'tt-time', text: `${state.symbol} · ${clock(point.t)}–${clock(point.t + bucketMs)}` }));
  for (const row of rows) {
    box.append(h('div', { class: 'tt-row' },
      h('span', { class: `tt-key ${row.key ?? ''}` }),
      h('strong', { text: row.value }),
      h('span', { class: 'tt-label', text: row.label })));
  }
  return box;
}

function setHover(container, index) {
  const chart = container._chart;
  container._hoverIndex = chart ? index : null;
  container._hoverT = chart && index !== null ? chart.points[index].t : null;
  if (!chart) return hideTooltip(container);
  chart.highlight(index);
  if (index === null) return hideTooltip(container);
  const rect = container.getBoundingClientRect();
  showTooltip(container, chart.tooltip(index), rect.left + chart.xs[index], rect.top + chart.anchorY(index));
}

function restoreHover(container) {
  const index = container._hoverT == null ? -1 : container._chart.points.findIndex((p) => p.t === container._hoverT);
  setHover(container, index >= 0 ? index : null);
}

function setupHover(container) {
  container.addEventListener('pointermove', (event) => {
    const chart = container._chart;
    if (!chart) return;
    const px = event.clientX - container.getBoundingClientRect().left;
    if (px < chart.left - 8 || px > chart.right + 8) return setHover(container, null);
    let nearest = 0;
    chart.xs.forEach((x, index) => {
      if (Math.abs(x - px) < Math.abs(chart.xs[nearest] - px)) nearest = index;
    });
    if (nearest !== container._hoverIndex) setHover(container, nearest);
  });
  container.addEventListener('pointerleave', () => setHover(container, null));
  container.addEventListener('blur', () => setHover(container, null));
  container.addEventListener('keydown', (event) => {
    const chart = container._chart;
    if (!chart) return;
    const last = chart.points.length - 1;
    const current = container._hoverIndex;
    const next = {
      ArrowLeft: current === null ? last : Math.max(0, current - 1),
      ArrowRight: current === null ? last : Math.min(last, current + 1),
      Home: 0,
      End: last,
      Escape: null,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    setHover(container, next);
  });
}

function renderEmpty(container, message) {
  container._chart = null;
  setHover(container, null);
  container.replaceChildren(h('div', { class: 'chart-empty', text: message }));
}

// ---------- charts ----------

function chartModel() {
  const series = state.series;
  if (!series || !state.symbol) return { series, points: [], bucketMs: 10000 };
  const bucketMs = series.bucket_seconds * 1000;
  const rows = series.rows.filter((row) => row.symbol === state.symbol);
  // The server clock bounds the window, so a drifting browser clock can't push data off the chart.
  const t1 = Math.max(series.now, rows.length ? rows.at(-1).t + bucketMs : 0);
  const t0 = t1 - series.minutes * 60000;
  return { series, bucketMs, t0, t1, points: rows.filter((p) => p.t + bucketMs / 2 >= t0) };
}

function emptyMessage() {
  if (!state.series) return state.error ? 'No data loaded yet.' : 'Loading…';
  return state.symbol ? `No windows for ${state.symbol} in the last ${rangeLabel(state.series.minutes)}.` : 'No windows yet.';
}

function renderPriceChart({ series, points, bucketMs, t0, t1 }) {
  const container = $('price-chart');
  $('price-title').textContent = state.symbol ? `Average price · ${state.symbol}` : 'Average price';
  $('price-sub').textContent = series ? `${durationLabel(series.bucket_seconds)} buckets, weighted by trade count` : '';
  if (!points.length) return renderEmpty(container, emptyMessage());

  const width = container.clientWidth;
  const height = CHART_HEIGHT;
  const yTicks = niceTicks(Math.min(...points.map((p) => p.low_price)), Math.max(...points.map((p) => p.high_price)), 4);
  const decimals = decimalsOf(yTicks.step);
  const yLabel = (value) => value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  const last = points.at(-1);
  const endLabel = usd.format(last.average_price);

  const left = Math.ceil(Math.max(...yTicks.ticks.map((value) => textWidth(yLabel(value))))) + 14;
  const right = width - Math.ceil(textWidth(endLabel, 12, 600)) - 16;
  const top = 10;
  const bottom = height - 28;
  const x = scale(t0, t1, left, right);
  const y = scale(yTicks.lo, yTicks.hi, bottom, top);
  const mid = (p) => x(p.t + bucketMs / 2);

  const svg = s('svg', { width, height, 'aria-hidden': 'true' });
  drawGrid(svg, { x, y, left, right, bottom, width }, yTicks.ticks, yLabel, timeTicks(t0, t1, right - left));
  s('line', { x1: left, x2: right, y1: bottom + 0.5, y2: bottom + 0.5, class: 'axis' }, svg);

  const plot = s('g', {}, svg);
  for (const segment of splitOnGaps(points, bucketMs)) {
    if (segment.length === 1) {
      s('circle', { cx: mid(segment[0]), cy: y(segment[0].average_price), r: 3, class: 'line-dot' }, plot);
      continue;
    }
    const upper = segment.map((p) => `${mid(p)},${y(p.high_price)}`);
    const lower = segment.map((p) => `${mid(p)},${y(p.low_price)}`).reverse();
    s('path', { d: `M${upper.join('L')}L${lower.join('L')}Z`, class: 'band' }, plot);
    s('path', { d: `M${segment.map((p) => `${mid(p)},${y(p.average_price)}`).join('L')}`, class: 'line' }, plot);
  }
  s('circle', { cx: mid(last), cy: y(last.average_price), r: 4, class: 'end-dot' }, plot);
  s('text', { x: mid(last) + 10, y: y(last.average_price), class: 'end-label', 'dominant-baseline': 'middle' }, plot)
    .textContent = endLabel;

  const hover = s('g', { visibility: 'hidden' }, svg);
  const crosshair = s('line', { y1: top, y2: bottom, class: 'crosshair' }, hover);
  const dot = s('circle', { r: 4, class: 'end-dot' }, hover);

  container.replaceChildren(svg);
  container._chart = {
    points,
    left,
    right,
    xs: points.map(mid),
    anchorY: (index) => y(points[index].average_price),
    highlight(index) {
      if (index === null) return hover.setAttribute('visibility', 'hidden');
      const px = Math.round(mid(points[index])) + 0.5;
      crosshair.setAttribute('x1', px);
      crosshair.setAttribute('x2', px);
      dot.setAttribute('cx', mid(points[index]));
      dot.setAttribute('cy', y(points[index].average_price));
      hover.setAttribute('visibility', 'visible');
    },
    tooltip(index) {
      const p = points[index];
      return tooltipContent(p, bucketMs, [
        { key: 'line', value: usd.format(p.average_price), label: 'Average' },
        { key: 'band', value: usd.format(p.high_price), label: 'High' },
        { key: 'band', value: usd.format(p.low_price), label: 'Low' },
        { value: integer.format(p.trade_count), label: 'Trades' },
      ]);
    },
  };
  restoreHover(container);
}

function renderFlowChart({ series, points, bucketMs, t0, t1 }) {
  const container = $('flow-chart');
  $('flow-title').textContent = state.symbol ? `Buy and sell quantity · ${state.symbol}` : 'Buy and sell quantity';
  $('flow-sub').textContent = series ? `${durationLabel(series.bucket_seconds)} buckets` : '';
  if (!points.length) return renderEmpty(container, emptyMessage());

  const width = container.clientWidth;
  const height = CHART_HEIGHT;
  const half = niceTicks(0, Math.max(...points.flatMap((p) => [p.buy_quantity, p.sell_quantity])), 2);
  const ticks = [...half.ticks.slice(1).map((value) => -value).reverse(), ...half.ticks];
  const decimals = decimalsOf(half.step);
  const yLabel = (value) => Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

  const left = Math.ceil(Math.max(...ticks.map((value) => textWidth(yLabel(value))))) + 14;
  const right = width - 12;
  const top = 10;
  const bottom = height - 28;
  const x = scale(t0, t1, left, right);
  const y = scale(-half.hi, half.hi, bottom, top);
  const zero = Math.round(y(0)) + 0.5;
  const slot = x(t0 + bucketMs) - x(t0);
  const barWidth = Math.max(1, Math.min(24, slot - 2));
  const mid = (p) => x(p.t + bucketMs / 2);

  const svg = s('svg', { width, height, 'aria-hidden': 'true' });
  drawGrid(svg, { x, y, left, right, bottom, width }, ticks, yLabel, timeTicks(t0, t1, right - left));
  const wash = s('rect', { y: top, height: bottom - top, class: 'slot-wash', visibility: 'hidden' }, svg);

  // A 2px surface gap separates the buy and sell bars at the zero line.
  const bars = s('g', {}, svg);
  for (const p of points) {
    if (p.buy_quantity > 0) {
      s('path', { d: barPath(mid(p), barWidth, zero - 1, Math.min(y(p.buy_quantity), zero - 2), 4), class: 'bar buy' }, bars);
    }
    if (p.sell_quantity > 0) {
      s('path', { d: barPath(mid(p), barWidth, zero + 1, Math.max(y(-p.sell_quantity), zero + 2), 4), class: 'bar sell' }, bars);
    }
  }
  s('line', { x1: left, x2: right, y1: zero, y2: zero, class: 'axis' }, svg);

  container.replaceChildren(svg);
  container._chart = {
    points,
    left,
    right,
    xs: points.map(mid),
    anchorY: (index) => y(points[index].buy_quantity),
    highlight(index) {
      if (index === null) return wash.setAttribute('visibility', 'hidden');
      wash.setAttribute('x', mid(points[index]) - Math.max(slot, barWidth + 4) / 2);
      wash.setAttribute('width', Math.max(slot, barWidth + 4));
      wash.setAttribute('visibility', 'visible');
    },
    tooltip(index) {
      const p = points[index];
      const net = p.buy_quantity - p.sell_quantity;
      return tooltipContent(p, bucketMs, [
        { key: 'buy', value: qty.format(p.buy_quantity), label: 'Buy' },
        { key: 'sell', value: qty.format(p.sell_quantity), label: 'Sell' },
        { value: `${net >= 0 ? '+' : '−'}${qty.format(Math.abs(net))}`, label: 'Net' },
      ]);
    },
  };
  restoreHover(container);
}

function renderWindowTable({ series, points }) {
  const raw = series?.bucket_seconds === 10;
  $('table-title').textContent = state.symbol ? `Windows · ${state.symbol}` : 'Windows';
  $('windows-time-heading').textContent = raw ? 'Window start' : 'Bucket start';
  $('table-sub').textContent = series
    ? `${integer.format(points.length)} ${raw ? 'windows' : `${durationLabel(series.bucket_seconds)} buckets`} in the last ${rangeLabel(series.minutes)}, newest first`
    : '';

  const body = $('windows-table').tBodies[0];
  if (!points.length) {
    body.replaceChildren(h('tr', {}, h('td', { class: 'empty', colspan: 7, text: emptyMessage() })));
    return;
  }
  const cell = (text) => h('td', { class: 'num', text });
  body.replaceChildren(...points.slice().reverse().map((p) => h('tr', {},
    h('td', { text: clock(p.t) }),
    cell(integer.format(p.trade_count)),
    cell(usd.format(p.low_price)),
    cell(usd.format(p.average_price)),
    cell(usd.format(p.high_price)),
    cell(qty.format(p.buy_quantity)),
    cell(qty.format(p.sell_quantity)))));
}

// ---------- tiles, filters, status ----------

const tileNodes = new Map();

function createTile(symbol) {
  const tile = {
    root: h('button', { type: 'button', class: 'tile' }),
    value: h('span', { class: 'tile-value' }),
    delta: h('span', { class: 'tile-delta' }),
    spark: h('div', { class: 'tile-spark', 'aria-hidden': 'true' }),
    meta: h('span', { class: 'tile-meta' }),
  };
  tile.root.append(h('span', { class: 'tile-label', text: symbol }), tile.value, tile.delta, tile.spark, tile.meta);
  tile.root.addEventListener('click', () => selectSymbol(symbol));
  return tile;
}

function drawSparkline(container, points) {
  const width = container.clientWidth || 180;
  const height = 32;
  const svg = s('svg', { width, height });
  if (points.length >= 2) {
    const values = points.map((p) => p.average_price);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const x = scale(0, values.length - 1, 2, width - 6);
    const y = hi === lo ? () => height / 2 : scale(lo, hi, height - 5, 5);
    s('path', { d: `M${values.map((value, index) => `${x(index)},${y(value)}`).join('L')}`, class: 'spark' }, svg);
    s('circle', { cx: x(values.length - 1), cy: y(values.at(-1)), r: 3, class: 'spark-dot' }, svg);
  }
  container.replaceChildren(svg);
}

function renderTiles() {
  const groups = groupBySymbol(state.tiles?.rows ?? []);
  const wanted = state.symbols.map((symbol) => {
    if (!tileNodes.has(symbol)) tileNodes.set(symbol, createTile(symbol));
    const tile = tileNodes.get(symbol);
    const points = groups.get(symbol) ?? [];
    const latest = points.at(-1);
    const previous = points.at(-2);
    tile.root.setAttribute('aria-pressed', String(symbol === state.symbol));
    if (!latest) {
      tile.value.textContent = '—';
      tile.delta.textContent = `No windows in the last ${TILE_MINUTES} min`;
      tile.meta.textContent = '';
    } else {
      tile.value.textContent = usd.format(latest.average_price);
      if (previous) {
        const change = ((latest.average_price - previous.average_price) / previous.average_price) * 100;
        tile.delta.textContent = `${change >= 0 ? '▲' : '▼'} ${Math.abs(change).toFixed(2)}% vs previous window`;
      } else {
        tile.delta.textContent = 'First window';
      }
      tile.meta.textContent = `${integer.format(latest.trade_count)} trades · ${clock(latest.t)}`;
    }
    return tile;
  });
  syncChildren($('tiles'), wanted.map((tile) => tile.root));
  // Sparklines size to the tile, so draw them once the tiles are in the layout.
  wanted.forEach((tile, index) => drawSparkline(tile.spark, (groups.get(state.symbols[index]) ?? []).slice(-SPARK_POINTS)));
}

const symbolButtons = new Map();

function renderSymbolFilter() {
  const wanted = state.symbols.map((symbol) => {
    if (!symbolButtons.has(symbol)) {
      const button = h('button', { type: 'button', text: symbol });
      button.addEventListener('click', () => selectSymbol(symbol));
      symbolButtons.set(symbol, button);
    }
    const button = symbolButtons.get(symbol);
    button.setAttribute('aria-pressed', String(symbol === state.symbol));
    return button;
  });
  syncChildren($('symbols'), wanted);
  $('symbols').hidden = !wanted.length;
}

function renderStatus() {
  const name = state.info?.name ?? 'the OLAP store';
  let tone = 'good';
  let label = 'Live';
  let title = '';
  let detail = '';
  if (state.error) {
    tone = 'critical';
    label = 'Unavailable';
    title = `Can't query ${name}.`;
    detail = `${state.error.replace(/[.\s]*$/, '.')} ${HINTS[state.info?.backend] ?? ''}`;
  } else if (!state.tiles) {
    tone = 'pending';
    label = 'Connecting';
  } else if (!state.tiles.rows.length) {
    tone = 'warning';
    label = 'Waiting for data';
    title = `No windows in ${name} from the last ${TILE_MINUTES} minutes.`;
    detail = 'Flink emits one row per symbol every 10 seconds once trades arrive; the first rows can take a minute after startup.';
  }
  $('status').dataset.state = tone;
  $('status-label').textContent = label;
  $('banner').hidden = !title;
  $('banner').dataset.tone = tone;
  $('banner-title').textContent = title;
  $('banner-detail').textContent = detail;
  $('updated').textContent = state.updatedAt ? `Updated ${clock(state.updatedAt)}` : '';
}

function renderCharts() {
  const model = chartModel();
  renderPriceChart(model);
  renderFlowChart(model);
  renderWindowTable(model);
}

function render() {
  const seen = new Set(state.symbols);
  for (const row of [...(state.tiles?.rows ?? []), ...(state.series?.rows ?? [])]) seen.add(row.symbol);
  state.symbols = [...seen].sort();
  if (!state.symbols.includes(state.symbol)) state.symbol = state.symbols[0] ?? null;

  renderStatus();
  renderSymbolFilter();
  renderTiles();
  renderCharts();
}

function selectSymbol(symbol) {
  state.symbol = symbol;
  writeSetting('symbol', symbol);
  render();
}

function selectRange(minutes) {
  state.minutes = minutes;
  writeSetting('minutes', minutes);
  for (const button of $('ranges').children) {
    button.setAttribute('aria-pressed', String(Number(button.dataset.minutes) === minutes));
  }
  tick();
}

// ---------- data loading ----------

async function refresh() {
  const request = ++state.request;
  const minutes = state.minutes;
  // Keep the previous render on screen; dim it only when a reload is noticeably slow.
  const slow = setTimeout(() => document.body.classList.add('loading'), 400);
  try {
    const [tiles, series] = await Promise.all([
      getJSON(`/api/series?minutes=${TILE_MINUTES}`),
      minutes === TILE_MINUTES ? null : getJSON(`/api/series?minutes=${minutes}`),
    ]);
    if (request !== state.request) return;
    state.tiles = tiles;
    state.series = series ?? tiles;
    state.error = null;
    state.updatedAt = Date.now();
  } catch (error) {
    if (request !== state.request) return;
    state.error = error.message;
  } finally {
    clearTimeout(slow);
    if (request === state.request) document.body.classList.remove('loading');
  }
  render();
}

async function tick() {
  clearTimeout(state.timer);
  if (!document.hidden) await refresh();
  clearTimeout(state.timer);
  if ($('auto-refresh').checked) state.timer = setTimeout(tick, REFRESH_MS);
}

// ---------- SQL console ----------

function renderResult(columns, rows) {
  const numeric = columns.map((_, index) => rows.length > 0 && rows.every((row) =>
    row[index] === null || typeof row[index] === 'number' || /^-?\d+(\.\d+)?$/.test(row[index])));
  const head = h('thead', {}, h('tr', {}, ...columns.map((column, index) =>
    h('th', { class: numeric[index] ? 'num' : '', text: column }))));
  const body = h('tbody');
  if (!rows.length) {
    body.append(h('tr', {}, h('td', { class: 'empty', colspan: Math.max(1, columns.length), text: 'No rows' })));
  }
  for (const row of rows) {
    body.append(h('tr', {}, ...row.map((value, index) => {
      if (value === null) return h('td', { class: 'null', text: 'NULL' });
      const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
      return h('td', { class: numeric[index] ? 'num' : '', text });
    })));
  }
  $('sql-result').replaceChildren(head, body);
  $('sql-result-wrap').hidden = false;
}

async function runSql() {
  const button = $('run-sql');
  button.disabled = true;
  $('sql-meta').textContent = 'Running…';
  $('sql-error').hidden = true;
  try {
    const result = await getJSON('/api/sql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: $('sql').value }),
    });
    renderResult(result.columns, result.rows);
    const rows = `${integer.format(result.rows.length)} ${result.rows.length === 1 ? 'row' : 'rows'}`;
    const truncated = result.truncated ? ` · only the first ${integer.format(result.max_rows)} rows are shown` : '';
    $('sql-meta').textContent = `${rows} · ${result.elapsed_ms} ms${truncated}`;
  } catch (error) {
    $('sql-meta').textContent = '';
    $('sql-error').textContent = error.message;
    $('sql-error').hidden = false;
  } finally {
    button.disabled = false;
  }
}

// ---------- startup ----------

async function init() {
  for (const range of RANGES) {
    const button = h('button', {
      type: 'button',
      text: range.label,
      'data-minutes': range.minutes,
      'aria-pressed': String(range.minutes === state.minutes),
    });
    button.addEventListener('click', () => selectRange(range.minutes));
    $('ranges').append(button);
  }

  $('auto-refresh').addEventListener('change', () => ($('auto-refresh').checked ? tick() : clearTimeout(state.timer)));
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && $('auto-refresh').checked) tick();
  });

  setupHover($('price-chart'));
  setupHover($('flow-chart'));
  let resizeFrame = 0;
  let lastWidth = 0;
  new ResizeObserver(([entry]) => {
    // Only width changes need a redraw; height changes come from our own renders.
    if (entry.contentRect.width === lastWidth) return;
    lastWidth = entry.contentRect.width;
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      renderTiles();
      renderCharts();
    });
  }).observe(document.querySelector('main'));

  $('run-sql').addEventListener('click', runSql);
  $('reset-sql').addEventListener('click', () => {
    $('sql').value = state.info?.example_query ?? '';
  });
  $('sql').addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      runSql();
    }
  });

  try {
    state.info = await getJSON('/api/info');
    $('backend-name').textContent = state.info.name;
    $('sql').value = state.info.example_query;
    document.title = `Exchange Statistics · ${state.info.name}`;
  } catch (error) {
    state.error = error.message;
  }
  tick();
}

init();
