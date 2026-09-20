/* Display adapter for the supplied HTML sample. No PHTKG outputs are inferred. */
'use strict';
const sample = window.MAP_SAMPLE;
const $ = id => document.getElementById(id);
const monthIndex = (y, m = 1) => y * 12 + m - 1;
const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const monthLabel = n => `${monthNames[n % 12]} ${Math.floor(n / 12)}`;
const monthValue = n => `${Math.floor(n / 12)}-${String(n % 12 + 1).padStart(2, '0')}`;
function readMonth(value) {
  const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(value);
  return match ? monthIndex(+match[1], +match[2]) : null;
}

// Preserve broad intervals rather than inventing a day for a year-only date.
function parseDate(value) {
  const s = String(value || '').trim();
  let match;
  if ((match = s.match(/^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?$/))) {
    const year = +match[1], month = +match[2], day = +(match[3] || 1);
    const maxDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
    if (month < 1 || month > 12 || day < 1 || day > maxDay) return null;
    const n = monthIndex(year, month);
    return {start: n, end: n, precision: match[3] ? 'day' : 'month'};
  }
  if ((match = s.match(/^(\d{4})$/))) return {start: monthIndex(+match[1]), end: monthIndex(+match[1], 12), precision: 'year'};
  if ((match = s.match(/^(\d{4})\s*[-–]\s*(\d{4})$/))) {
    if (+match[2] < +match[1]) return null;
    return {start: monthIndex(+match[1]), end: monthIndex(+match[2], 12), precision: 'range'};
  }
  const named = s.match(/^(?:(?:early|mid|late)[ -]+)?([a-z]+)\s+(\d{4})$/i);
  if (named) {
    const month = monthNames.findIndex(m => m.toLowerCase() === named[1].slice(0, 3).toLowerCase());
    if (month >= 0) return {start: monthIndex(+named[2], month + 1), end: monthIndex(+named[2], month + 1), precision: 'month'};
  }
  return null;
}

const records = sample.records.map((r, index) => ({...r, displayId: index, date: parseDate(r.d)}));
const minMonth = monthIndex(2021, 1);
const maxMonth = monthIndex(2026, 12);
function isValidRange(start, end) {
  return start !== null && end !== null && start >= minMonth && end <= maxMonth && start <= end;
}
function presetRange(years, end) {
  return years === 'all' ? {start: minMonth, end: maxMonth} : {start: Math.max(minMonth, end - Number(years) * 12 + 1), end};
}
function moveRangeHandle(handle, value, start, end) {
  const month = Math.max(minMonth, Math.min(maxMonth, Math.round(value)));
  return handle === 'start' ? {start: Math.min(month, end), end} : {start, end: Math.max(month, start)};
}
const state = {category: null, start: minMonth, end: maxMonth, undated: false, mode: 'period', selected: null, mapTheme: 'dark'};
const colours = {
  'Compute / Model Behavior': '#C92A3E',
  'Data': '#DC3A2F',
  'Deployment Context / Weapons': '#E85D5D',
  'Labor': '#F37A6B',
  'Energy / Land': '#FFB3A7',
  '__neutral__': '#A65A62'
};
let map, landLayer, markerLayer, animation = null, currentMapRecords = [];
const worldBounds = [[-55, -170], [78, 180]];
const anchors = window.MAP_GEOGRAPHY.anchors;
const countryFeatures = new Map(sample.countries.features.map(feature => [feature.properties.Country, feature]));

function halton(index, base) {
  let result = 0, fraction = 1 / base;
  while (index > 0) {
    result += fraction * (index % base);
    index = Math.floor(index / base);
    fraction /= base;
  }
  return result;
}
function ringArea(ring) {
  let area = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) area += ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
  return Math.abs(area / 2);
}
function pointInRing(point, ring) {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    const crosses = (yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi;
    if (crosses) inside = !inside;
  }
  return inside;
}
function pointInPolygon(point, polygon) {
  return pointInRing(point, polygon[0]) && !polygon.slice(1).some(hole => pointInRing(point, hole));
}
function polygonsFor(feature) {
  const geometry = feature?.geometry;
  if (!geometry) return [];
  return geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
}
function primaryPolygon(feature) {
  return polygonsFor(feature).reduce((largest, polygon) => !largest || ringArea(polygon[0]) > ringArea(largest[0]) ? polygon : largest, null);
}
function pointHasClearance(point, polygon, xMargin, yMargin) {
  return [
    point,
    [point[0] - xMargin, point[1]], [point[0] + xMargin, point[1]],
    [point[0], point[1] - yMargin], [point[0], point[1] + yMargin],
    [point[0] - xMargin, point[1] - yMargin], [point[0] + xMargin, point[1] - yMargin],
    [point[0] - xMargin, point[1] + yMargin], [point[0] + xMargin, point[1] + yMargin]
  ].every(candidate => pointInPolygon(candidate, polygon));
}
function approximateEventPosition(country, ordinal) {
  const polygon = primaryPolygon(countryFeatures.get(country));
  if (!polygon) return anchors[country];
  const xs = polygon[0].map(point => point[0]);
  const ys = polygon[0].map(point => point[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const xMargin = Math.min((maxX - minX) * 0.012, 0.35);
  const yMargin = Math.min((maxY - minY) * 0.012, 0.25);
  for (let attempt = 1; attempt <= 4096; attempt++) {
    const sequence = ordinal * 4099 + attempt;
    const point = [minX + halton(sequence, 2) * (maxX - minX), minY + halton(sequence, 3) * (maxY - minY)];
    if (pointHasClearance(point, polygon, xMargin, yMargin)) return [point[1], point[0]];
  }
  return anchors[country];
}
const eventPositions = new Map();
const countryOrdinals = new Map();
records.forEach(record => {
  const placementCountry = record.p || record.k;
  const ordinal = countryOrdinals.get(placementCountry) || 0;
  countryOrdinals.set(placementCountry, ordinal + 1);
  eventPositions.set(record.displayId, approximateEventPosition(placementCountry, ordinal));
});

function element(tag, className, content) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (content !== undefined) el.textContent = content;
  return el;
}
function matchesCategory(r, category = state.category) {
  if (category === null) return true;
  const f = sample.filters[category];
  return (f.k === 'b' ? r.b : r.h).includes(f.v);
}
function matchesTime(r) {
  if (!r.date) return state.undated;
  const start = state.mode === 'cumulative' ? minMonth : state.start;
  return r.date.end >= start && r.date.start <= state.end;
}
function results() { return records.filter(r => matchesTime(r) && matchesCategory(r)); }
function pause() {
  clearInterval(animation); animation = null;
  $('play').textContent = '▶ Play'; $('play').setAttribute('aria-pressed', 'false');
}

function worldView() {
  if (!map) return;
  map.stop();
  map.fitBounds(worldBounds, {animate: false});
  map.setZoom(map.getZoom() + .31, {animate: false});
}
function applyMapTheme() {
  const light = state.mapTheme === 'light';
  $('map-wrap').classList.toggle('map-light', light);
  $('map-theme-toggle').textContent = light ? '☾ Dark' : '☀ Light';
  $('map-theme-toggle').setAttribute('aria-label', light ? 'Use dark map theme' : 'Use light map theme');
  $('map-theme-toggle').setAttribute('aria-pressed', String(light));
  landLayer?.setStyle({fillColor: light ? '#d5d9dc' : '#303030'});
}
function setupMap() {
  if (!window.L) { $('map-error').hidden = false; return; }
  map = L.map('map', {zoomControl: false, minZoom: 0, maxZoom: 7, zoomSnap: .01, preferCanvas: true});
  L.control.zoom({position: 'topright'}).addTo(map);
  worldView();
  landLayer = L.geoJSON(window.MAP_GEOGRAPHY.land, {
    interactive: false,
    style: {stroke: false, weight: 0, fillColor: '#303030', fillOpacity: 1}
  }).addTo(map);
  applyMapTheme();
  markerLayer = L.layerGroup().addTo(map);
  map.on('zoomend moveend resize', renderMarkers);
  new ResizeObserver(() => {
    map.invalidateSize();
    worldView();
  }).observe($('map'));
}
function revealReports() {
  $('reports-panel').scrollTop = 0;
  $('reports-heading').tabIndex = -1;
  $('reports-heading').focus({preventScroll: true});
  if (window.innerWidth <= 900) document.querySelector('.inspector').scrollIntoView({block: 'start'});
}
function toggleEventSelection(eventId, selectedEvent) {
  return selectedEvent === eventId ? null : eventId;
}
function isMapExpanded() {
  const wrap = $('map-wrap');
  return document.fullscreenElement === wrap || wrap.classList.contains('map-expanded');
}
function compactEventSummary(record, minimum = 50, maximum = 70) {
  const clean = value => String(value || '').replace(/\s+/g, ' ').trim();
  const title = clean(record.t);
  if (title.length >= minimum && title.length <= maximum) return title;

  if (title.length > maximum) {
    const filler = new Set(['a', 'an', 'and', 'as', 'at', 'by', 'for', 'from', 'in', 'of', 'on', 'or', 'the', 'to', 'with']);
    const reduced = title.split(' ').filter(word => !filler.has(word.toLowerCase())).join(' ');
    if (reduced.length >= minimum && reduced.length <= maximum) return reduced;
    const words = (reduced.length >= minimum ? reduced : title).split(' ');
    let headline = '';
    for (const word of words) {
      const candidate = headline ? `${headline} ${word}` : word;
      if (candidate.length > maximum) break;
      headline = candidate;
    }
    return headline;
  }

  const categoryNames = {
    'Compute / Model Behavior': 'compute and model harms',
    'Data': 'data harms',
    'Deployment Context / Weapons': 'deployment and weapons harms',
    'Labor': 'labor harms',
    'Energy / Land': 'energy and land harms'
  };
  const additions = [clean(record.k), categoryNames[record.b?.[0]], 'documented AI harm event', clean(record.d)].filter(Boolean);
  let headline = title;
  for (const addition of additions) {
    const candidate = `${headline}: ${addition}`;
    if (candidate.length <= maximum) headline = candidate;
    if (headline.length >= minimum) break;
  }
  if (headline.length < minimum) {
    const fallback = `${headline}: documented report`;
    if (fallback.length <= maximum) headline = fallback;
  }
  return headline;
}
function renderMarkers() {
  if (!markerLayer) return;
  markerLayer.clearLayers();
  currentMapRecords.forEach(record => {
    const selected = state.selected === record.displayId;
    const dimmed = state.selected !== null && !selected;
    const category = state.category === null ? record.b[0] : sample.filters[state.category].b;
    const colour = colours[category] || colours.__neutral__ || '#64748b';
    const description = `${record.t} · ${record.k} · ${record.d || 'Date not supplied'}`;
    const marker = L.circleMarker(eventPositions.get(record.displayId), {
      radius: selected ? 2.5 : 1.75,
      color: selected ? '#ffffff' : colour,
      weight: selected ? 2 : 1,
      fillColor: colour,
      fillOpacity: dimmed ? 0.16 : 0.88,
      opacity: dimmed ? 0.24 : 1,
      bubblingMouseEvents: false
    });
    marker.bindTooltip(() => element('div', 'event-tooltip-summary', compactEventSummary(record)), {direction: 'top', offset: [0, -8]});
    marker.on('click', () => {
      pause();
      state.selected = toggleEventSelection(record.displayId, state.selected);
      render();
      if (state.selected !== null && !isMapExpanded()) revealReports();
    });
    marker.addTo(markerLayer);
  });
}
function renderLegend() {
  const entries = Object.entries(colours).filter(([k]) => k !== '__neutral__');
  [$('map-legend'), $('expanded-map-legend')].forEach(legend => {
    legend.replaceChildren();
    const scale = element('div', 'legend-scale');
    entries.forEach(([label, colour]) => {
      const item = element('span', 'legend-item'); const swatch = element('i'); swatch.style.background = colour;
      item.append(swatch, document.createTextNode(label)); scale.append(item);
    });
    legend.append(scale);
  });
}
function renderCategories() {
  const context = records.filter(r => matchesTime(r));
  [$('categories'), $('expanded-categories')].forEach(container => {
    if (!container.children.length) {
      [null, ...sample.filters.keys()].forEach(index => {
        const f = index === null ? null : sample.filters[index];
        const button = element('button', `category-button${f?.k === 's' ? ' child' : ''}`);
        if (f?.k === 'b') { const swatch = element('i', 'swatch'); swatch.style.background = colours[f.b]; button.append(swatch); }
        button.append(element('span', '', f ? f.v : 'All harm categories'), element('span', 'cat-count'));
        button.addEventListener('click', () => { pause(); state.category = state.category === index ? null : index; state.selected = null; render(); });
        container.append(button);
      });
    }
    [...container.children].forEach((button, i) => {
      const index = i === 0 ? null : i - 1;
      button.classList.toggle('active', state.category === index);
      button.setAttribute('aria-pressed', String(state.category === index));
      button.querySelector('.cat-count').textContent = context.filter(r => matchesCategory(r, index)).length;
    });
  });
}

function renderExpandedReport(selected, list) {
  const panel = $('expanded-report');
  const wrap = $('map-wrap');
  wrap.classList.toggle('has-expanded-report', Boolean(selected));
  panel.hidden = !selected;
  if (!selected) { $('expanded-report-content').replaceChildren(); return; }

  const container = $('expanded-report-content');
  container.replaceChildren();
  const heading = element('div', 'expanded-report-heading');
  const harm = selected.h?.[0] || selected.b?.[0] || 'Category not supplied';
  heading.append(element('h3', 'expanded-report-title', `${selected.t} | Harm: ${harm}`));
  const close = element('button', 'expanded-report-close', 'Close');
  close.type = 'button';
  close.addEventListener('click', () => { state.selected = null; render(); });
  heading.append(close);
  container.append(heading, element('p', 'expanded-report-summary', selected.s || 'No summary supplied.'));

  const meta = element('p', 'expanded-report-meta');
  meta.append(document.createTextNode(`${selected.k} · ${selected.d || 'Date not supplied'} · ${selected.e || 'Duration not supplied'} · Source: `));
  try {
    const url = new URL(selected.u);
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Unsupported source protocol');
    const link = element('a', '', url.hostname);
    link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
    meta.append(link);
  } catch { meta.append(document.createTextNode('Source not supplied')); }
  container.append(meta);
  container.append(element('small', 'expanded-report-disclaimer', 'Summary generated with LLM assistance. Verify details against the original source.'));

  const related = list.filter(record => record.k === selected.k && record.displayId !== selected.displayId);
  if (related.length) {
    const details = element('details', 'expanded-related');
    details.append(element('summary', '', `${related.length.toLocaleString()} more reports in this country`));
    const relatedList = element('div', 'expanded-related-list');
    related.slice(0, 8).forEach(record => {
      const button = element('button', '', record.t);
      button.type = 'button';
      button.addEventListener('click', () => { state.selected = record.displayId; render(); });
      relatedList.append(button);
    });
    details.append(relatedList); container.append(details);
  }
}

function renderTimeSummary() {
  const context = records.filter(r => matchesCategory(r));
  $('undated-count').textContent = `(${context.filter(r => !r.date).length})`;
  $('period-label').textContent = state.mode === 'cumulative' ? `Up to ${monthLabel(state.end)}` : `${monthLabel(state.start)} — ${monthLabel(state.end)}`;
}
function syncTimeControls() {
  const start = state.mode === 'cumulative' ? minMonth : state.start;
  $('start').value = start;
  $('end').value = state.end;
  $('start').disabled = state.mode === 'cumulative';
  $('start-label').textContent = monthLabel(start);
  $('end-label').textContent = monthLabel(state.end);
  $('start').setAttribute('aria-valuetext', monthLabel(start));
  $('end').setAttribute('aria-valuetext', monthLabel(state.end));
  $('start').setAttribute('aria-valuemax', state.end);
  $('end').setAttribute('aria-valuemin', start);
  $('date-range').style.setProperty('--range-start', `${(start - minMonth) / (maxMonth - minMonth) * 100}%`);
  $('date-range').style.setProperty('--range-end', `${(state.end - minMonth) / (maxMonth - minMonth) * 100}%`);
  $('date-range').classList.toggle('same-month', start === state.end);
  document.querySelectorAll('[data-years]').forEach(button => {
    const value = button.dataset.years;
    const selected = state.mode === 'period' && (value === 'all'
      ? state.start === minMonth && state.end === maxMonth
      : state.end - state.start + 1 === +value * 12);
    button.setAttribute('aria-pressed', String(selected));
  });
}
function detailSection(container, heading) {
  const section = element('section', 'detail-section'); section.append(element('h3', '', heading)); container.append(section); return section;
}
function showReport(r) {
  const container = $('report-content'); container.replaceChildren();
  const back = element('button', 'back-button', '✕ Close report');
  back.addEventListener('click', () => { state.selected = null; render(); });
  container.append(back, element('div', 'eyebrow', r.k), element('h2', 'detail-title', r.t), element('div', 'report-meta', `${r.d || 'Date not supplied'} · ${r.e || 'Duration not supplied'}`));
  r.h.forEach(h => container.append(element('span', 'report-tag', h)));
  const summary = detailSection(container, 'What happened'); summary.append(element('p', 'detail-summary', r.s || 'No description supplied.'));
  const evidence = detailSection(container, 'Source & evidence');
  try {
    const url = new URL(r.u);
    if (['http:', 'https:'].includes(url.protocol)) {
      const link = element('a', 'source-link', `Read source at ${url.hostname} ↗`);
      link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; evidence.append(link);
    }
  } catch { /* Missing or invalid source URLs remain plain text. */ }
  evidence.append(element('p', 'fine-print', 'Read the original source for context and supporting evidence.'));
}
function render() {
  const mapRecords = records.filter(r => matchesTime(r) && matchesCategory(r));
  currentMapRecords = mapRecords;
  renderMarkers();
  const list = mapRecords;
  const visibleCount = list.length.toLocaleString();
  const countryCount = new Set(list.map(r => r.k)).size;
  $('visible-count').textContent = visibleCount;
  $('country-count').textContent = countryCount;
  $('expanded-visible-count').textContent = visibleCount;
  $('expanded-country-count').textContent = countryCount;
  $('map-title').textContent = 'A world of documented harms';
  $('open-filters').textContent = state.category === null ? `Filter by category (${sample.filters.length})` : 'Filter by category · 1 selected';
  $('apply-filters').textContent = `Show ${list.length.toLocaleString()} reports`;
  renderLegend(); renderCategories(); syncTimeControls(); renderTimeSummary(); syncMapFilterControls();
  const selected = list.find(r => r.displayId === state.selected);
  renderExpandedReport(selected, list);
  const inspector = document.querySelector('.inspector');
  const workspace = $('main-content');
  if (selected) {
    inspector.hidden = false;
    workspace.classList.add('report-open');
    showReport(selected);
  } else {
    state.selected = null;
    inspector.hidden = true;
    workspace.classList.remove('report-open');
  }
}

function syncMapFilterControls() {
  const start = state.mode === 'cumulative' ? minMonth : state.start;
  $('map-start').value = start;
  $('map-end').value = state.end;
  $('map-start').disabled = state.mode === 'cumulative';
  $('map-start').setAttribute('aria-valuetext', monthLabel(start));
  $('map-end').setAttribute('aria-valuetext', monthLabel(state.end));
  $('map-start').setAttribute('aria-valuemax', state.end);
  $('map-end').setAttribute('aria-valuemin', start);
  const periodText = state.mode === 'cumulative' ? `Up to ${monthLabel(state.end)}` : `${monthLabel(start)} — ${monthLabel(state.end)}`;
  $('map-period-label').textContent = periodText;
  $('expanded-coverage-period').textContent = periodText;
  $('map-date-range').style.setProperty('--range-start', `${(start - minMonth) / (maxMonth - minMonth) * 100}%`);
  $('map-date-range').style.setProperty('--range-end', `${(state.end - minMonth) / (maxMonth - minMonth) * 100}%`);
}
['start', 'end'].forEach(id => {
  $(id).min = minMonth; $(id).max = maxMonth;
  $(id).addEventListener('input', () => {
    pause();
    const start = state.mode === 'cumulative' ? minMonth : state.start;
    Object.assign(state, moveRangeHandle(id, +$(id).value, start, state.end));
    render();
  });
});
$('date-range').addEventListener('pointerdown', event => {
  if (event.target.tagName === 'INPUT' || event.button !== 0) return;
  const rect = $('date-range').getBoundingClientRect();
  const fraction = Math.max(0, Math.min(1, (event.clientX - rect.left - 14) / Math.max(1, rect.width - 28)));
  const month = minMonth + Math.round(fraction * (maxMonth - minMonth));
  const id = $('start').disabled || Math.abs(month - state.end) < Math.abs(month - state.start) ? 'end' : 'start';
  $(id).value = month; $(id).dispatchEvent(new Event('input', {bubbles: true})); $(id).focus({preventScroll: true});
});
document.querySelectorAll('[data-years]').forEach(button => button.addEventListener('click', () => {
  pause(); state.mode = 'period'; $('time-mode').value = 'period';
  Object.assign(state, presetRange(button.dataset.years, state.end));
  state.selected = null; render();
}));
['map-start', 'map-end'].forEach(id => {
  $(id).addEventListener('input', () => {
    pause();
    const handle = id === 'map-start' ? 'start' : 'end';
    const start = state.mode === 'cumulative' ? minMonth : state.start;
    Object.assign(state, moveRangeHandle(handle, +$(id).value, start, state.end));
    state.selected = null; render();
  });
});
$('map-theme-toggle').addEventListener('click', () => {
  state.mapTheme = state.mapTheme === 'dark' ? 'light' : 'dark';
  applyMapTheme();
});
$('clear-map-filters').addEventListener('click', () => {
  pause(); Object.assign(state, {category: null, start: minMonth, end: maxMonth, undated: false, mode: 'period', selected: null});
  $('undated').checked = false; $('time-mode').value = 'period'; worldView(); render();
});
$('world-view').addEventListener('click', worldView);
$('undated').addEventListener('change', () => { state.undated = $('undated').checked; render(); });
$('time-mode').addEventListener('change', () => { pause(); state.mode = $('time-mode').value; render(); });
document.querySelector('.timeline-settings').addEventListener('toggle', event => { if (!event.currentTarget.open) pause(); });
$('reset').addEventListener('click', () => {
  pause(); Object.assign(state, {category: null, start: minMonth, end: maxMonth, undated: false, selected: null, mode: 'period'});
  $('undated').checked = false; $('time-mode').value = 'period';
  worldView(); render();
});
$('play').addEventListener('click', () => {
  if (animation) { pause(); return; }
  const span = 12;
  if (state.end >= maxMonth || state.end - state.start >= span) {
    state.start = minMonth; state.end = Math.min(maxMonth, minMonth + span - 1);
  }
  $('play').textContent = 'Ⅱ Pause'; $('play').setAttribute('aria-pressed', 'true'); render();
  animation = setInterval(() => {
    if (state.end >= maxMonth) { pause(); return; }
    if (state.mode === 'period') state.start = Math.min(maxMonth, state.end + 1);
    state.end = Math.min(maxMonth, state.end + span); render();
  }, 1100);
});
document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
const mobileLayout = window.matchMedia('(max-width: 900px)');
function placeTaxonomy() {
  if (!mobileLayout.matches && $('filter-sheet').open) $('filter-sheet').close();
  (mobileLayout.matches ? $('sheet-content') : $('taxonomy-home')).append($('taxonomy-panel'));
}
$('open-filters').addEventListener('click', () => {
  pause(); $('filter-sheet').showModal(); document.body.classList.add('sheet-open');
  $('close-filters').focus();
});
['close-filters', 'apply-filters'].forEach(id => $(id).addEventListener('click', () => $('filter-sheet').close()));
$('filter-sheet').addEventListener('close', () => {
  document.body.classList.remove('sheet-open');
  if (mobileLayout.matches) $('open-filters').focus({preventScroll: true});
});
mobileLayout.addEventListener('change', placeTaxonomy);
placeTaxonomy();
setupMap(); render();
