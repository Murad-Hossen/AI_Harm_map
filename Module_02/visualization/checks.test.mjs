import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const read = name => readFileSync(new URL(name, import.meta.url), 'utf8');
const source = read('app.js');
const html = read('index.html');
const context = vm.createContext({window: {MAP_GEOGRAPHY: {anchors: {}}}});
vm.runInContext(read('data.js'), context);
// Exercise the actual date/filter functions without pretending to render a browser.
vm.runInContext(source.slice(0, source.indexOf('function syncMapFilterControls()')), context);
const evaluate = code => vm.runInContext(code, context);

test('month values preserve the supported precision and date bounds', () => {
  assert.equal(evaluate('readMonth("2021-01")'), 2021 * 12);
  assert.equal(evaluate('readMonth("2026-13")'), null);
  assert.equal(evaluate('readMonth("")'), null);
  assert.equal(evaluate('isValidRange(readMonth("2021-01"), readMonth("2026-07"))'), true);
  for (const [start, end] of [['2020-12', '2026-07'], ['2021-01', '2027-01'], ['2026-08', '2021-01'], ['', '2022-01']]) {
    assert.equal(evaluate(`isValidRange(readMonth(${JSON.stringify(start)}), readMonth(${JSON.stringify(end)}))`), false);
  }
});

test('slider handles stay ordered and inside 2021–2026', () => {
  assert.equal(evaluate('moveRangeHandle("start", maxMonth, minMonth, minMonth + 12).start === minMonth + 12'), true);
  assert.equal(evaluate('moveRangeHandle("end", minMonth, minMonth + 12, maxMonth).end === minMonth + 12'), true);
  assert.equal(evaluate('moveRangeHandle("start", minMonth - 50, minMonth, maxMonth).start === minMonth'), true);
  assert.equal(evaluate('moveRangeHandle("end", maxMonth + 50, minMonth, maxMonth).end === maxMonth'), true);
  assert.equal(evaluate('moveRangeHandle("start", minMonth + 5, minMonth, maxMonth).end === maxMonth'), true);
});

test('clicking a selected event dot clears the selection', () => {
  assert.equal(evaluate('toggleEventSelection(42, null)'), 42);
  assert.equal(evaluate('toggleEventSelection(42, 42)'), null);
  assert.equal(evaluate('toggleEventSelection(42, 17)'), 42);
  assert.doesNotMatch(source, /dimmed|fillOpacity: dimmed|opacity: dimmed/);
  assert.match(source, /fillOpacity: 0\.88,[\s\S]*?opacity: 1/);
});

test('event hover summaries stay between 50 and 70 characters', () => {
  assert.equal(evaluate('records.every(record => compactEventSummary(record).length >= 50 && compactEventSummary(record).length <= 70)'), true);
  assert.equal(evaluate('records.every(record => !compactEventSummary(record).includes("…") && !compactEventSummary(record).includes("—") && !compactEventSummary(record).includes("\\n"))'), true);
  assert.equal(evaluate(`compactEventSummary({t: 'Sarah silverman paul tremblay openai chatgpt copyright lawsuit', b: [], k: ''})`), 'Sarah silverman paul tremblay openai chatgpt copyright lawsuit');
});

test('every event receives a stable position inside its display-placement country', () => {
  assert.equal(evaluate('eventPositions.size'), evaluate('records.length'));
  assert.equal(evaluate(`records.every(record => {
    const position = eventPositions.get(record.displayId);
    if (record.c) return position[0] === record.c[0] && position[1] === record.c[1];
    const point = [position[1], position[0]];
    return pointInPolygon(point, primaryPolygon(countryFeatures.get(record.p || record.k)));
  })`), true);
  assert.equal(evaluate(`(() => {
    const alaska = records.find(record => record.i === 'R847');
    return alaska.l === 'Alaska, United States'
      && alaska.c[0] === 67.5 && alaska.c[1] === -156
      && eventPositions.get(alaska.displayId).join(',') === '67.5,-156';
  })()`), true);
  assert.equal(evaluate(`(() => {
    const positions = records.filter(record => record.k === 'United States' && !record.c).map(record => eventPositions.get(record.displayId));
    return new Set(positions.map(point => point.join(','))).size === positions.length
      && positions.every(([lat, lon]) => lat >= 25 && lat <= 50 && lon >= -125 && lon <= -66);
  })()`), true);
});

test('quick ranges anchor to the end month and clamp to 2021', () => {
  for (const [years, start] of [['1', '2025-08'], ['3', '2023-08'], ['5', '2021-08'], ['all', '2021-01']]) {
    assert.equal(evaluate(`presetRange('${years}', maxMonth).start === readMonth('${start}')`), true);
    assert.equal(evaluate(`presetRange('${years}', maxMonth).end === maxMonth`), true);
  }
  assert.equal(evaluate('presetRange("5", readMonth("2022-06")).start === minMonth'), true);
  assert.equal(evaluate('presetRange("all", readMonth("2022-06")).end === maxMonth'), true);
});

test('default view keeps all 2,845 notebook-placed reports across 81 countries', () => {
  assert.equal(evaluate('records.length'), 2845);
  assert.equal(evaluate('new Set(records.map(record => record.i)).size'), 2845);
  assert.equal(evaluate('results().length'), 2845);
  assert.equal(evaluate('results().every(r => r.date && r.date.end >= minMonth && r.date.start <= maxMonth)'), true);
  assert.equal(evaluate('new Set(records.map(record => record.k)).size'), 81);
  assert.doesNotMatch(source, /state\.limit|list\.slice\(/);
});

test('date ranges overlap the window and undated records remain opt-in', () => {
  assert.equal(evaluate('matchesTime({date: parseDate("2018-2022")})'), true);
  assert.equal(evaluate('matchesTime({date: parseDate("2018")})'), false);
  assert.equal(evaluate('matchesTime({date: parseDate("2028")})'), false);
  assert.equal(evaluate('matchesTime({date: null})'), false);
  evaluate('state.undated = true');
  assert.equal(evaluate('matchesTime({date: null})'), true);
  evaluate('state.undated = false; state.mode = "cumulative"; state.end = readMonth("2022-12")');
  assert.equal(evaluate('results().every(r => r.date.end >= minMonth && r.date.start <= readMonth("2022-12"))'), true);
  evaluate('state.mode = "period"; state.end = maxMonth');
});

test('controls have unique targets and correctly associated labels', () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const [, id] of source.matchAll(/\$\('([^']+)'\)/g)) assert.ok(ids.includes(id), `Missing #${id}`);
  for (const [, id] of html.matchAll(/\bfor="([^"]+)"/g)) assert.ok(ids.includes(id), `Missing label target ${id}`);
  assert.match(html, /<dialog id="filter-sheet" aria-labelledby="filter-sheet-title"/);
  assert.match(html, /<input type="range" id="start"/);
  assert.match(html, /<input type="range" id="end"/);
  assert.match(html, /id="date-range" role="group"/);
  assert.doesNotMatch(html, /type="month"|patterns-tab|map-category-filter/);
  assert.match(html, /<details class="timeline-settings">/);
  assert.match(html, /<aside class="inspector"[^>]*hidden>/);
  assert.match(html, /id="expanded-categories" class="expanded-categories"[^>]*tabindex="0"/);
  assert.match(html, /id="expanded-map-legend" class="expanded-map-legend"/);
  assert.match(html, /id="map-theme-toggle" class="map-theme-toggle"/);
  assert.match(html, /<body class="map-expanded">/);
  assert.match(html, /class="map-wrap map-expanded" id="map-wrap"/);
  assert.match(html, /styles\.css\?v=20260922-10/);
  assert.match(html, /data-bootstrap\.js\?v=20260922-12/);
  assert.match(html, /data-finalize\.js\?v=20260922-12/);
  assert.match(html, /app\.js\?v=20260922-12/);
  assert.match(html, /phtkg_patterns\.js\?v=20260920-4/);
  assert.doesNotMatch(html, /id="expand-map"|class="map-expand"/);
  assert.match(source, /mapTheme: 'dark'/);
  assert.match(source, /landLayer\?\.setStyle\(\{fillColor: light/);
  assert.match(html, /id="expanded-report" class="expanded-report"[^>]*hidden/);
  assert.match(source, /Summary generated with LLM assistance\. Verify details against the original source\./);
  assert.match(source, /link\.href = url\.href; link\.target = '_blank'; link\.rel = 'noopener noreferrer'/);
  assert.doesNotMatch(source, /more reports in this country/);
  assert.match(source, /Related structural pattern/);
  assert.doesNotMatch(source, /Structured event context|Documented action:|Reported consequence:/);
  assert.match(source, /expanded-report-harm/);
  assert.match(source, /label\.style\.color = colours\[branch\]/);
  assert.equal(evaluate("records.filter(record => record.x?.action && record.x?.consequence).length"), 2845);
  assert.equal(evaluate("records.find(record => record.i === 'R1517').s.length"), 621);
  assert.equal(evaluate("records.find(record => record.i === 'R873').d"), '2023-08');
  assert.equal(evaluate("records.find(record => record.i === 'R873').x.dateBasis"), 'reported month in source');
  assert.match(html, /class="expanded-map-title"[^>]*>[^<]*<span>◉<\/span> AI HARM MAP<\/div>/);
  assert.match(source, /\$\('expanded-coverage-period'\)\.textContent = periodText/);
  assert.match(html, /class="expanded-map-stats"[\s\S]*?id="expanded-coverage-period"/);
  assert.match(source, /\[\$\('categories'\), \$\('expanded-categories'\)\]/);
  assert.match(read('styles.css'), /\.map-wrap:fullscreen #map, \.map-wrap\.map-expanded #map \{ right: 298px; width: auto; \}/);
  assert.match(read('styles.css'), /\.expanded-taxonomy \{[^}]*height: calc\(66\.667dvh - 133\.333px\)/);
  assert.match(read('styles.css'), /\.expanded-report \{[^}]*right: 378px/);
  assert.match(read('styles.css'), /\.map-filter-tray \{[^}]*width: min\(350px/);
  assert.match(read('styles.css'), /\.expanded-categories \.all-categories \{[^}]*position: sticky/);
  assert.match(source, /workspace\.classList\.add\('report-open'\)/);
  assert.match(source, /radius: selected \? 2\.5 : 1\.75/);
  assert.match(source, /map\.setZoom\(map\.getZoom\(\) \+ \.31/);
  assert.match(source, /zoomSnap: \.01/);
});

function luminance(hex) {
  const values = hex.match(/[a-f\d]{2}/gi).map(v => parseInt(v, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return values[0] * .2126 + values[1] * .7152 + values[2] * .0722;
}
function contrast(a, b) {
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + .05) / (values[1] + .05);
}
test('specified text pairs exceed 4.5:1, and graph/focus colours exceed 3:1', () => {
  const css = read('styles.css');
  for (const [text, background] of [['#1e293b', '#ffffff'], ['#1e293b', '#f8f9fa'], ['#475569', '#ffffff'], ['#475569', '#f8f9fa'], ['#881337', '#fff0ee'], ['#ffffff', '#881337'], ['#64748b', '#ffffff']]) {
    assert.ok(css.toLowerCase().includes(text.toLowerCase()));
    assert.ok(contrast(text, background) >= 4.5, `${text} on ${background}`);
  }
  for (const colour of ['#2563eb', '#c85b50', '#64748b']) assert.ok(contrast(colour, '#ffffff') >= 3);
  const reds = JSON.parse(evaluate('JSON.stringify(Object.values(colours).filter(colour => colour !== colours.__neutral__))'));
  assert.equal(new Set(reds).size, 5);
  for (const colour of reds) assert.ok(contrast(colour, '#1a1a1a') >= 3, `${colour} is unclear against the map`);
});
