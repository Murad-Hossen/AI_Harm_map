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
vm.runInContext(source.slice(0, source.indexOf('[...new Set(records.map')), context);
const evaluate = code => vm.runInContext(code, context);

test('month values preserve the supported precision and date bounds', () => {
  assert.equal(evaluate('readMonth("2021-01")'), 2021 * 12);
  assert.equal(evaluate('readMonth("2026-13")'), null);
  assert.equal(evaluate('readMonth("")'), null);
  assert.equal(evaluate('isValidRange(readMonth("2021-01"), readMonth("2026-12"))'), true);
  for (const [start, end] of [['2020-12', '2026-12'], ['2021-01', '2027-01'], ['2026-12', '2021-01'], ['', '2022-01']]) {
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

test('clicking a selected country dot clears the selection', () => {
  assert.equal(evaluate('toggleCountrySelection("Norway", "")'), 'Norway');
  assert.equal(evaluate('toggleCountrySelection("Norway", "Norway")'), '');
  assert.equal(evaluate('toggleCountrySelection("Norway", "Sweden")'), 'Norway');
});

test('quick ranges anchor to the end month and clamp to 2021', () => {
  for (const [years, start] of [['1', '2026-01'], ['3', '2024-01'], ['5', '2022-01'], ['all', '2021-01']]) {
    assert.equal(evaluate(`presetRange('${years}', maxMonth).start === readMonth('${start}')`), true);
    assert.equal(evaluate(`presetRange('${years}', maxMonth).end === maxMonth`), true);
  }
  assert.equal(evaluate('presetRange("5", readMonth("2022-06")).start === minMonth'), true);
  assert.equal(evaluate('presetRange("all", readMonth("2022-06")).end === maxMonth'), true);
});

test('default view keeps 956 reports overlapping 2021–2026', () => {
  assert.equal(evaluate('records.length'), 988);
  assert.equal(evaluate('results().length'), 956);
  assert.equal(evaluate('results().every(r => r.date && r.date.end >= minMonth && r.date.start <= maxMonth)'), true);
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
  assert.doesNotMatch(html, /type="month"|PHTKG|patterns-tab/);
  assert.match(html, /<details class="timeline-settings">/);
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
});
