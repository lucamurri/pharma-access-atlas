# Design and accessibility audit

Audit of the Pharma Access Atlas (all four languages) against the standard checks for public data tools,
16 November 2026. Each finding was fixed and re-tested; the "after" column is the re-test result.

## Standards and tools used

| Area | Reference | Tool or method |
|---|---|---|
| Accessibility | WCAG 2.2 level AA | axe-core 4.10 (WCAG 2.0/2.1/2.2 AA and best-practice rules) on 12 page types × 4 languages × 320 px and 1280 px, light and dark; manual checks for focus, contrast, reflow, text spacing, sticky elements |
| Performance, best practice, search | Google Lighthouse 12, Core Web Vitals (LCP ≤ 2.5 s, CLS ≤ 0.1) | Lighthouse on 6 pages, phone and desktop |
| Usability | Nielsen's 10 usability heuristics | Page-by-page review |
| Charts | Data-visualisation practice (FT, Our World in Data) and the charting guide's anti-pattern catalogue | Review of every chart type; colour validator for colour-blind separation and contrast |
| Data publication | Conventions for open data tools: downloadable data, citation, metadata, versioning | Review; schema.org Dataset markup |
| Search engines | Unique titles and descriptions, hreflang, canonical, sitemap, 404 | Script over all 896 pages |

## Results before and after

### Accessibility (WCAG 2.2 AA)

| Check | Before | Fix | After |
|---|---|---|---|
| Automated axe rules, 72 page/language/width combinations | 1 rule failed (methodology page) | See next rows | **0 violations** |
| 1.4.11 Focus indicator contrast | Yellow ring at 2.2:1 on white | Petrol ring, 6.8:1 (light) and 8.4:1 (dark) | Pass |
| 1.4.3 Placeholder text contrast | Browser grey, 4.2:1 (light) and 3.4:1 (dark) | Placeholder uses the muted ink, 5.0:1 and 6.0:1 | Pass |
| 1.4.11 Form field boundaries | 1.35:1 | Field edges 3.4–3.8:1 in both modes | Pass |
| 1.4.11 Chart lines and markers | Germany yellow 2.2:1, England pink 2.7:1, grey 2.4:1 | Darker steps (#c08600, #c85c88, #848d98), all ≥ 3:1; re-validated as a set for colour-blind separation | Pass (worst colour-blind pair 6.6, allowed because every line carries a direct name label and every chart has a table) |
| 2.4.11 Focus not obscured (new in 2.2) | Sticky section bar and sticky table header could cover a focused link | Scroll padding on the page and inside the table frame | Pass |
| 4.1.2 / landmarks: scrolling tables | Methodology tables named with a raw key ("js.table_scrolls"); two sharing one name; country tables repeating their section's name | Name from the table caption or nearest heading, made distinct and numbered if repeated | Pass |
| 1.4.10 Reflow at 320 px | French explorer cards overflowed (status tags could not wrap) | Tags wrap on phones | Pass on every page and language |
| 1.4.12 Text spacing | — | Tested with WCAG spacing overrides | Pass, nothing clipped |
| 2.5.8 Target size (24 px) | — | axe rule plus review | Pass |
| 1.4.3 Text contrast (all colour tokens) | All ≥ 5.0:1 | — | Pass, light and dark |
| 3.1.2 Language of parts | Foreign official terms (Gazzetta Ufficiale, Zusatznutzen) are not marked up | None needed: proper names and technical terms are exempt | Pass |

### Performance and search (Lighthouse)

| Check | Before | Fix | After |
|---|---|---|---|
| Accessibility, best practices, SEO scores | 100 / 100 / 100 on every page | — | 100 / 100 / 100 |
| Largest contentful paint (live site) | 0.3–1.8 s | — | Unchanged |
| Layout shift (CLS), explorer | **0.33 (poor)** on desktop | Filter menus get fixed widths (they grew when filled and re-wrapped the row); result line and table frame reserve their height before data loads | **0.01** |
| Layout shift, compare page | 0.14–0.17 (needs improvement) | Chart and table space reserved; content shown from the first paint | 0–0.04 |
| Page descriptions | 863 longer than 160 characters; 16 shorter than 70 | Trimmed at a word to ~155; four thin descriptions rewritten in all languages | All within range |
| Titles and descriptions unique | Yes | — | Yes |
| Heading structure | One h1 per page, no skipped levels | — | Same |
| 404 page | GitHub's generic page | Site-branded page with search, main pages and the four languages; not indexed | Added |

### Charts

| Anti-pattern or practice | Before | After |
|---|---|---|
| Dual axes, rainbow scales, recolouring on filter | None | None |
| Legend for ≥ 2 series, direct labels on curves | Yes | Yes |
| Every chart has a table view | Yes | Yes |
| Source line under each figure (FT/OWID practice) | Missing | Sources and data date under every figure, with a CSV download |
| Tabular figures on big standalone numbers | Used (looks loose at display sizes) | Proportional figures on key numbers; tabular only in tables and axes |
| Values on every bar | Only on short ranked bar charts (≤ 8 bars) | Kept: accepted practice for few ranked bars |
| Dashed line | The 50% reference line only | Kept: it marks a threshold, not a grid |

### Usability (Nielsen's heuristics)

| Heuristic | Finding | Fix |
|---|---|---|
| Consistency and standards | "Countries" in the menu opened Italy, not an overview of countries | New Countries page listing all five with their key figure |
| Consistency | English dates written two ways: "15 Sept 2022" (explorer) and "15 Sep 2022" (briefs) | The page scripts now use the build's month names in every language |
| Visibility of system status | Explorer said "All 209 drugs" but "Showing 211 of 211" (reference drugs unexplained) | The count names the reference drugs: "Showing 211 of 211 drugs, including 2 reference drugs" |
| Match with the real world | Agency jargon (ASMR, SMR, G-BA, CDF, ATMP) not explained in one place | Glossary of 12 terms on the methodology page, four languages |
| Flexibility and efficiency | No way to take the data out except one JSON file | CSV of the whole dataset, and a button that downloads exactly the filtered explorer rows |
| Help and documentation | No guidance on citing the atlas | "How to cite" with the data date, plus licence terms |

### Data publication

| Convention | Before | After |
|---|---|---|
| Machine-readable dataset metadata | None | schema.org Dataset (name, creator, coverage, date modified, downloads) on the overview in each language, for Google Dataset Search |
| Open download formats | JSON | CSV and JSON |
| Citation and version | Data date in the footer only | Citation block with data date; date on every figure |
| Licence | In the README only | Summarised on the methodology page |

## Not changed, by decision

- **Phone load time measured locally** looked slow (5–6 s) only because the local preview server does not compress
  files; on GitHub Pages the same pages load in 1.3–1.8 s.
- **Chart colours in dark mode** already met 3:1 and were not changed.
- **Native-speaker review** of the German and French remains recommended; it is outside an automated audit.

## How to repeat this audit

Run Lighthouse (`npx lighthouse <url> --preset=desktop`) on the overview, explorer, compare and a brief, and
axe-core with the `wcag22aa` and `best-practice` rule sets at 320 px and 1280 px in each language. Re-run the
colour validator whenever a chart colour changes.
