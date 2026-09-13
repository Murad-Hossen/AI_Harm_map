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
const state = {category: null, country: '', query: '', start: minMonth, end: maxMonth, undated: false, mode: 'period', cluster: null, resolution: 'year', selected: null, limit: 30};
const colours = Object.fromEntries(Object.entries(sample.ramps).map(([k, v]) => [k, v[4]]));
let map, landLayer, markerLayer, animation = null, currentByCountry = new Map();
const worldBounds = [[-55, -170], [78, 180]];
const anchors = window.MAP_GEOGRAPHY.anchors;

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
function matchesSearch(r) {
  return !state.query || [r.t, r.s, r.k, ...r.h].join(' ').toLowerCase().includes(state.query);
}
function matchesTime(r) {
  if (!r.date) return state.undated;
  const start = state.mode === 'cumulative' ? minMonth : state.start;
  return r.date.end >= start && r.date.start <= state.end;
}
function countryMatch(r) { return !state.country || r.k === state.country; }
function results() { return records.filter(r => matchesSearch(r) && matchesTime(r) && matchesCategory(r) && countryMatch(r)); }
function pause() {
  clearInterval(animation); animation = null;
  $('play').textContent = '▶ Play'; $('play').setAttribute('aria-pressed', 'false');
}

function worldView() { map?.stop(); map?.fitBounds(worldBounds, {animate: false}); }
function setupMap() {
  if (!window.L) { $('map-error').hidden = false; return; }
  map = L.map('map', {zoomControl: false, minZoom: 0, maxZoom: 7, zoomSnap: .25, preferCanvas: true});
  L.control.zoom({position: 'topright'}).addTo(map);
  worldView();
  landLayer = L.geoJSON(window.MAP_GEOGRAPHY.land, {
    interactive: false,
    style: {stroke: false, weight: 0, fillColor: '#303030', fillOpacity: 1}
  }).addTo(map);
  markerLayer = L.layerGroup().addTo(map);
  map.on('zoomend moveend resize', renderMarkers);
  new ResizeObserver(() => {
    map.invalidateSize();
    if (!state.country && !state.cluster) worldView();
  }).observe($('map'));
}
function dominant(rs) {
  const counts = new Map();
  rs.forEach(r => r.b.forEach(b => counts.set(b, (counts.get(b) || 0) + 1)));
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0];
}
function revealReports() {
  $('reports-panel').scrollTop = 0;
  $('reports-heading').tabIndex = -1;
  $('reports-heading').focus({preventScroll: true});
  if (window.innerWidth <= 900) document.querySelector('.inspector').scrollIntoView({block: 'start'});
}
function selectCountry(country, zoom = false, reveal = false) {
  pause(); state.country = country; state.cluster = null; state.selected = null; state.limit = 30;
  $('country').value = country; render();
  $('reports-panel').scrollTop = 0;
  if (zoom && country && map) map.setView(anchors[country], Math.max(map.getZoom(), 4), {animate: false});
  if (reveal) revealReports();
}
function toggleCountrySelection(country, selectedCountry) {
  return selectedCountry === country ? '' : country;
}
// Groups are based on screen overlap, not model similarity or geographic spread.
// Stable country anchors never move; only the aggregate display marker changes on zoom.
function markerGroups() {
  if (!map) return [];
  const points = [...currentByCountry.keys()].sort().map(country => ({country, point: map.latLngToContainerPoint(anchors[country])}));
  const groups = [];
  const remaining = new Set(points);
  while (remaining.size) {
    const members = [remaining.values().next().value]; remaining.delete(members[0]);
    for (const point of remaining) {
      // Every member must be close: a chain of neighbours must not combine
      // distant countries into a single continent-spanning display group.
      if (members.every(member => member.point.distanceTo(point.point) < 20)) {
        members.push(point); remaining.delete(point);
      }
    }
    const center = members.reduce((sum, member) => sum.add(member.point), L.point(0, 0)).divideBy(members.length);
    groups.push({countries: members.map(member => member.country), latlng: map.containerPointToLatLng(center)});
  }
  return groups;
}
function renderMarkers() {
  if (!markerLayer) return;
  const focused = document.activeElement?.dataset?.countryGroup;
  markerLayer.clearLayers();
  markerGroups().forEach(group => {
    const rs = group.countries.flatMap(country => currentByCountry.get(country));
    const multiple = group.countries.length > 1;
    const category = state.category === null ? dominant(rs) : sample.filters[state.category].b;
    const colour = colours[category];
    const label = multiple ? `${group.countries.length} countries` : group.countries[0];
    const description = `${label} · ${rs.length} reports · ${multiple ? 'grouped for display' : 'country-level location'}`;
    // Keep the visible dot small, with a larger transparent click target.
    const size = 24;
    const icon = element('div', `report-dot${state.country && group.countries.includes(state.country) ? ' selected' : ''}`);
    icon.style.setProperty('--marker-colour', colour);
    const marker = L.marker(group.latlng, {
      icon: L.divIcon({className: 'report-marker', html: icon, iconSize: [size, size], iconAnchor: [size / 2, size / 2]}),
      keyboard: true, title: description, alt: description,
      opacity: state.country && !group.countries.includes(state.country) ? .4 : 1,
      zIndexOffset: multiple ? 100 : 0
    });
    marker.bindTooltip(() => {
      const tooltip = element('div');
      tooltip.append(element('strong', '', label), element('div', '', `${rs.length.toLocaleString()} reports`), element('div', 'marker-note', multiple ? 'Grouped for display · click to choose a country' : 'Country-level location · not an incident coordinate'));
      tooltip.append(element('div', 'marker-note', `Colour: ${category}`));
      return tooltip;
    }, {direction: 'top', offset: [0, -12]});
    marker.on('click', () => {
      if (!multiple) {
        const country = toggleCountrySelection(group.countries[0], state.country);
        selectCountry(country, false, true);
        return;
      }
      pause(); state.cluster = group.countries; state.selected = null; state.country = ''; $('country').value = '';
      render(); $('reports-panel').scrollTop = 0;
      map.fitBounds(L.latLngBounds(group.countries.map(country => anchors[country])), {padding: [65, 65], maxZoom: Math.min(7, map.getZoom() + 2), animate: false});
      revealReports();
    });
    marker.addTo(markerLayer);
    const node = marker.getElement(); node.dataset.countryGroup = group.countries.join('|'); node.setAttribute('aria-label', description);
    node.setAttribute('role', 'button'); node.tabIndex = 0;
    if (node.dataset.countryGroup === focused) node.focus({preventScroll: true});
  });
}
function renderLegend() {
  const legend = $('map-legend'); legend.replaceChildren();
  const scale = element('div', 'legend-scale');
  const entries = Object.entries(colours).filter(([k]) => k !== '__neutral__');
  entries.forEach(([label, colour]) => {
    const item = element('span', 'legend-item'); const swatch = element('i'); swatch.style.background = colour;
    item.append(swatch, document.createTextNode(label)); scale.append(item);
  });
  legend.append(scale);
}
function showCountryGroup(countries) {
  const container = $('report-content'); container.replaceChildren();
  const back = element('button', 'back-button', '← All matching reports');
  back.addEventListener('click', () => { state.cluster = null; render(); });
  const available = countries.filter(country => currentByCountry.has(country));
  container.append(back, element('div', 'eyebrow', 'NEARBY COUNTRY GROUPS'), element('h2', '', `${available.length} countries`), element('p', 'group-explainer', 'Choose a country to read its reports. Nearby dots are grouped together to keep the map readable.'));
  if (!available.length) container.append(element('div', 'pending-box', 'No reports in this group match the current filters.'));
  available.forEach(country => {
    const button = element('button', 'report-card');
    button.append(element('span', 'report-title', country), element('div', 'report-meta', `${currentByCountry.get(country).length} reports · country-level location`));
    button.addEventListener('click', () => selectCountry(country, true)); container.append(button);
  });
}
function renderCategories() {
  const context = records.filter(r => matchesSearch(r) && matchesTime(r) && countryMatch(r));
  const container = $('categories');
  if (!container.children.length) {
    [null, ...sample.filters.keys()].forEach(index => {
      const f = index === null ? null : sample.filters[index];
      const button = element('button', `category-button${f?.k === 's' ? ' child' : ''}`);
      if (f?.k === 'b') { const swatch = element('i', 'swatch'); swatch.style.background = colours[f.b]; button.append(swatch); }
      button.append(element('span', '', f ? f.v : 'All harm categories'), element('span', 'cat-count'));
      button.addEventListener('click', () => { pause(); state.category = state.category === index ? null : index; state.selected = null; state.limit = 30; render(); });
      container.append(button);
    });
  }
  [...container.children].forEach((button, i) => {
    const index = i === 0 ? null : i - 1;
    button.classList.toggle('active', state.category === index);
    button.setAttribute('aria-pressed', String(state.category === index));
    button.querySelector('.cat-count').textContent = context.filter(r => matchesCategory(r, index)).length;
  });
}

function renderHistogram() {
  const context = records.filter(r => matchesSearch(r) && matchesCategory(r) && countryMatch(r) && (!r.date || r.date.end >= minMonth && r.date.start <= maxMonth));
  const monthly = state.resolution === 'month';
  const bins = [];
  const first = monthly ? minMonth : Math.floor(minMonth / 12) * 12;
  for (let start = first; start <= maxMonth; start += monthly ? 1 : 12) {
    const end = monthly ? start : start + 11;
    // Monthly bars exclude year-only/range dates to avoid invented monthly counts.
    const count = context.filter(r => r.date && (!monthly || ['day', 'month'].includes(r.date.precision)) && r.date.start <= end && r.date.end >= start).length;
    bins.push({start, end, count});
  }
  const max = Math.max(1, ...bins.map(b => b.count));
  const histogram = $('histogram'); const scroll = histogram.scrollLeft; histogram.replaceChildren();
  const selectedStart = state.mode === 'cumulative' ? minMonth : state.start;
  bins.forEach(b => {
    const label = monthly ? monthLabel(b.start) : String(Math.floor(b.start / 12));
    const button = element('button', `hist-bin${monthly ? ' month' : ''}${b.end >= selectedStart && b.start <= state.end ? ' selected' : ''}`);
    const description = `${label}: ${b.count} reports${monthly ? '' : ' overlapping this year'}. Select this period.`;
    button.title = description; button.setAttribute('aria-label', description);
    const bar = element('span', 'hist-bar'); bar.style.height = `${b.count ? Math.max(2, b.count / max * 60) : 0}px`;
    const showYear = monthly ? b.start % 12 === 0 : bins.length <= 12 || Math.floor(b.start / 12) % 5 === 0 || b === bins.at(-1);
    button.append(bar, element('span', 'hist-year', showYear ? String(Math.floor(b.start / 12)) : ''));
    button.addEventListener('click', () => { pause(); state.start = Math.max(minMonth, b.start); state.end = Math.min(maxMonth, b.end); state.selected = null; syncTimeControls(); render(); });
    histogram.append(button);
  }); histogram.scrollLeft = scroll;
  $('undated-count').textContent = `(${context.filter(r => !r.date).length})`;
  const broad = context.filter(r => r.date && ['year', 'range'].includes(r.date.precision)).length;
  $('date-note').textContent = monthly
    ? `Monthly bars omit ${broad} reports with year-only or year-range dates. Map filtering includes overlapping date ranges; undated reports follow the checkbox.`
    : 'Bars count reports overlapping each year. Reports with date ranges may appear in more than one bar. Undated reports are not charted.';
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
function reportList(list) {
  const container = $('report-content'); container.replaceChildren();
  const heading = element('div', 'list-heading');
  heading.append(element('span', 'eyebrow', 'FOLLOW THE EVIDENCE'), element('h2', '', state.country || 'All countries'), element('p', '', `${list.length.toLocaleString()} matching reports · select a report to inspect its evidence.`));
  container.append(heading);
  if (!list.length) { container.append(element('div', 'pending-box', 'No reports match these filters. Widen the date range, include undated reports, or reset the filters.')); return; }
  list.slice(0, state.limit).forEach(r => {
    const button = element('button', 'report-card');
    button.append(element('div', 'report-meta', `${r.k} · ${r.d || 'Date not supplied'}`), element('span', 'report-title', r.t));
    r.b.forEach(b => button.append(element('span', 'report-tag', b)));
    button.addEventListener('click', () => {
      state.selected = r.displayId; showReport(r);
      revealReports();
    });
    container.append(button);
  });
  if (list.length > state.limit) {
    const more = element('button', 'load-more', `Show more (${list.length - state.limit} remaining)`);
    more.addEventListener('click', () => { state.limit += 30; reportList(list); }); container.append(more);
  }
}
function detailSection(container, heading) {
  const section = element('section', 'detail-section'); section.append(element('h3', '', heading)); container.append(section); return section;
}
function showReport(r) {
  const container = $('report-content'); container.replaceChildren();
  const back = element('button', 'back-button', '← Back to matching reports');
  back.addEventListener('click', () => { state.selected = null; reportList(results()); revealReports(); });
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
  const mapRecords = records.filter(r => matchesSearch(r) && matchesTime(r) && matchesCategory(r));
  currentByCountry = new Map();
  mapRecords.forEach(r => { if (!currentByCountry.has(r.k)) currentByCountry.set(r.k, []); currentByCountry.get(r.k).push(r); });
  renderMarkers();
  const list = mapRecords.filter(countryMatch);
  $('visible-count').textContent = list.length.toLocaleString();
  $('country-count').textContent = new Set(list.map(r => r.k)).size;
  $('map-title').textContent = state.country || 'A world of documented harms';
  $('open-filters').textContent = state.category === null ? `Filter by category (${sample.filters.length})` : 'Filter by category · 1 selected';
  $('apply-filters').textContent = `Show ${list.length.toLocaleString()} reports`;
  renderLegend(); renderCategories(); syncTimeControls(); renderHistogram();
  const selected = list.find(r => r.displayId === state.selected);
  if (selected) showReport(selected); else if (state.cluster) showCountryGroup(state.cluster); else { state.selected = null; reportList(list); }
}

[...new Set(records.map(r => r.k))].sort().forEach(country => $('country').add(new Option(country, country)));
['start', 'end'].forEach(id => {
  $(id).min = minMonth; $(id).max = maxMonth;
  $(id).addEventListener('input', () => {
    pause();
    const start = state.mode === 'cumulative' ? minMonth : state.start;
    Object.assign(state, moveRangeHandle(id, +$(id).value, start, state.end));
    state.limit = 30; render();
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
  state.selected = null; state.limit = 30; render();
}));
$('search').addEventListener('input', () => { state.query = $('search').value.toLowerCase().trim(); state.limit = 30; render(); });
$('country').addEventListener('change', () => selectCountry($('country').value, true));
$('world-view').addEventListener('click', worldView);
$('resolution').addEventListener('change', () => { pause(); state.resolution = $('resolution').value; render(); });
$('undated').addEventListener('change', () => { state.undated = $('undated').checked; render(); });
$('time-mode').addEventListener('change', () => { pause(); state.mode = $('time-mode').value; render(); });
document.querySelector('.timeline-settings').addEventListener('toggle', event => { if (!event.currentTarget.open) pause(); });
$('reset').addEventListener('click', () => {
  pause(); Object.assign(state, {category: null, country: '', query: '', start: minMonth, end: maxMonth, undated: false, selected: null, limit: 30, mode: 'period', cluster: null, resolution: 'year'});
  $('search').value = ''; $('country').value = ''; $('undated').checked = false; $('time-mode').value = 'period'; $('resolution').value = 'year';
  worldView(); render();
});
$('play').addEventListener('click', () => {
  if (animation) { pause(); return; }
  const span = state.resolution === 'year' ? 12 : 1;
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
