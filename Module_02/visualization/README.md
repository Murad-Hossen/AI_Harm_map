# Map interface prototype

Open `index.html` in a browser. No build step or Python environment is needed.
Leaflet loads from a CDN; an internet connection is needed for the geographic
map. The optional web font falls back to the system font. Reports and country
geometry are local in `data.js`, extracted from the supplied `predicted_map.html`.

The prototype preserves the 988 embedded reports and underlying country data. It
does not connect to enriched inference outputs or run PHTKG.

Implemented interactions:

- Borderless dark-grey land silhouette on charcoal water, with small country-level dots coloured
  by dominant harm category, country selection, taxonomy filters, text search,
  and synchronized report counts. Nearby markers combine on screen to avoid
  overlap; clicking a combined dot zooms in and offers a country picker.
  Report counts appear in tooltips and the report panel, not inside the dots.
- One shared date slider with separate start/end handles and 1Y/3Y/5Y/All
  presets. Handles step by month, cannot cross, and have keyboard support and
  spoken month labels. When both select the same month, their visual positions
  separate vertically so either can be dragged. Presets end at the selected
  end month; All restores January 2021–December 2026.
- Period/cumulative modes, histogram interval, playback, and undated inclusion
  sit inside a collapsed "More time options" disclosure. Undated reports are
  excluded by default; playback stays within January 2021–December 2026.
- Report list and detail panel with description, country, date, harm categories,
  and safe source links. The user-facing interface contains no PHTKG tab,
  model controls, research badges, or unconnected technical placeholders.
- A three-column desktop layout: filters on the left, map in the centre, and
  Reports & sources on the right. The taxonomy list and report panel scroll
  independently; the report heading stays above its scrolling content. At widths
  of 900px and below, search, metrics, map, and reports stack vertically. A
  persistent category button opens a native modal bottom sheet; only the sheet
  scrolls while open, with background scroll locked and focus restored on close.
  The stacked report panel retains its own scroll area on mobile.
- The map supports dragging, zooming, and marker selection immediately, with
  keyboard access and no activation overlay. Category filters and the report
  list remain available without map use.
- Neutral surfaces, 14px taxonomy labels/counts, 44px primary control heights,
  and visible blue keyboard focus rings. Small dots retain category colours
  with matching coloured borders. Interface text uses dark slate and deep crimson.
- Country dots toggle their selection: the first click focuses a country and
  dims the other dots; clicking the selected dot again clears the country
  filter and restores every dot to full opacity.

Date policy: exact dates and month-only dates map to their supplied month;
year-only dates and year ranges retain their full interval. Named months with
years are supported. Unrecognized or invalid dates are treated as undated and
the original text remains visible. A report matches a date window when its
interval overlaps it. Yearly histogram bars count overlap, so a range can
appear in multiple bars. Monthly bars exclude year-only/range dates. The
histogram shows the full temporal context of the other active filters and
highlights the selected window. No supplied dates are relabelled as verified
incident dates. Source records outside 2021–2026 remain intact in `data.js`
but do not appear in the dated map view. Ranges overlapping 2021–2026 remain
eligible. Reset and cumulative playback both respect these fixed bounds.

Dot tooltips summarize reports matching search, taxonomy, and time. Each
country's anchor is a fixed interior point of its largest polygon, not a
reported incident coordinate. Selecting a country highlights its marker and
scopes the list, headline counts, taxonomy counts, and histogram. Nearby
anchors that are all within 20 screen pixels of each other form display groups,
coloured by their most frequent harm category. Dots are a fixed 12 pixels wide,
with transparent 24-pixel click targets. Groups change with zoom and are not PHTKG
clusters. Clicking one opens its country list and zooms toward its anchors.
Ties for dominant category use alphabetical order. Counts measure reports,
not deduplicated incidents or harm severity. World view resets the camera
without clearing filters; Reset clears filters and resets the camera.

`geography.js` contains a dissolved land silhouette with shared political
boundaries removed, and the 47 display anchors. To regenerate it from the
original geometry in `data.js`, run `python3 build_geography.py` with Shapely
installed. This is only a preparation step; the browser does not need Python.

Files: `index.html` defines the layout; `styles.css` provides responsive
styling; `app.js` handles interactions; `data.js` contains the original sample.
`displayId` is only an in-memory row index for UI selection, not a source
`report_id`. A future enriched-data adapter must preserve actual report IDs,
source evidence, verification audits, and `learned_representation` fields.

Run `node --test checks.test.mjs` for date-policy, dataset-filter, markup wiring,
and palette contrast checks. These checks do not replace visual browser or
assistive-technology testing.
