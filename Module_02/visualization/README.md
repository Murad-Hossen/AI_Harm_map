# Map interface prototype

Open `index.html` in a browser. No build step or Python environment is needed.
Leaflet loads from a CDN; an internet connection is needed for the geographic
map. The optional web font falls back to the system font. Reports and country
geometry are local in `data.js`. Run `python3 build_data.py` to regenerate the
browser data from the frozen release corpus.

The prototype preserves all 3,041 unique release reports. Enriched action and
consequence fields are used for the annotated 1,162-report partition; the
remaining release records use browser-safe summaries derived from structured
metadata. The browser does not run PHTKG.

Implemented interactions:

- Borderless dark-grey land silhouette on charcoal water, with one small dot for
  every event in the active filters. Each event receives a stable, deterministic
  position safely inside its reported country’s primary land polygon and uses a distinct shade of red for its broad harm
  category. These positions prevent same-country events from covering each other;
  they are approximate display locations, not reported incident coordinates.
  Clicking a dot opens its report, dims other dots, and clicking it again clears
  the selection.
- One shared date slider with separate start/end handles and 1Y/3Y/5Y/All
  presets. Handles step by month, cannot cross, and have keyboard support and
  spoken month labels. When both select the same month, their visual positions
  separate vertically so either can be dragged. Presets end at the selected
  end month; All restores January 2021–December 2026.
- Period/cumulative modes, annual playback, and undated inclusion
  sit inside a collapsed "More time options" disclosure. Undated reports are
  excluded by default; playback stays within January 2021–December 2026.
- A contextual report-and-source panel with description, country, date, harm
  categories, and safe source links. It stays hidden until an event dot is
  selected and closes when the dot is selected again or Close report is used.
  The user-facing interface contains no PHTKG tab, model controls, research
  badges, or unconnected technical placeholders.
- A two-column desktop layout with the map on the left and taxonomy filters on the right. Reports & sources is added as the outer-right column only while an event is selected. The taxonomy list and report panel scroll
  independently; the report heading stays above its scrolling content. At widths
  of 900px and below, metrics, map, and reports stack vertically. A
  persistent category button opens a native modal bottom sheet; only the sheet
  scrolls while open, with background scroll locked and focus restored on close.
  The stacked report panel retains its own scroll area on mobile.
- The map supports dragging, zooming, event selection, and full-screen expansion immediately, with a subtle synchronized matching-report metrics at the top and a category/time filter tray at the bottom-right of the expanded view and
  keyboard access and no activation overlay. Category filters and the report
  list remain available without map use.
- Neutral surfaces, 14px taxonomy labels/counts, 44px primary control heights,
  and visible blue keyboard focus rings. Small dots use a graduated red category palette
  with matching coloured borders. Interface text uses dark slate and deep crimson.
- Event dots toggle their selection: the first click opens that event and dims
  the other dots; clicking the selected dot again restores every dot to full
  opacity.

Date policy: exact dates and month-only dates map to their supplied month;
year-only dates and year ranges retain their full interval. Named months with
years are supported. Unrecognized or invalid dates are treated as undated and
the original text remains visible. A report matches a date window when its
interval overlaps it. No supplied dates are relabelled as verified incident
dates. Source records outside 2021–2026 remain intact in `data.js`
but do not appear in the dated map view. Ranges overlapping 2021–2026 remain
eligible. Reset and cumulative playback both respect these fixed bounds.

Dot tooltips show a complete, single-line 50–70 character headline derived from the report
title and its country/category context. Event positions are generated deterministically inside the primary land polygon for each country embedded in `data.js`, with
an interior margin to avoid coastlines and remote-island placements. The layout stays stable when filters
change, but the coordinates must not be interpreted as incident locations.
Taxonomy and time filters remove non-matching event dots and
reports. Counts measure reports, not deduplicated incidents or harm severity.
World view resets the camera without clearing filters; Reset clears filters and
resets the camera.

`geography.js` contains a dissolved land silhouette with shared political
boundaries removed, and the 47 display anchors. To regenerate it from the
original geometry in `data.js`, run `python3 build_geography.py` with Shapely
installed. This is only a preparation step; the browser does not need Python.

Files: `index.html` defines the layout; `styles.css` provides responsive
styling; `app.js` handles interactions; `build_data.py` adapts the frozen releases; and
`data.js` contains the generated browser dataset. `displayId` is only an
in-memory row index for UI selection; each record also preserves its stable
source `report_id`. Learned-representation and verification fields can be added
when the final enriched artifact is released.

Run `node --test checks.test.mjs` for date-policy, dataset-filter, markup wiring,
and palette contrast checks. These checks do not replace visual browser or
assistive-technology testing.
