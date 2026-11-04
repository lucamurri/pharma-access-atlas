"""Build the static website into _site/ (the folder GitHub Pages publishes).

    python3 pipeline/build_site.py
    python3 -m http.server 8000 --directory _site     # then open http://localhost:8000

What it does
  1. Wraps each page in site/pages/ with the shared layout (header, nav, footer).
  2. Fills {{placeholders}} in pages with numbers from pipeline/analysis.py.
  3. Generates one brief page per drug in _site/drugs/.
  4. Copies assets and writes the data files the JavaScript reads.
"""
from __future__ import annotations

import html
import json
import shutil
from datetime import date

import analysis
import check_text
import so_what as so_what_rules
import sys
from common import PROCESSED, ROOT, write_json

SITE = ROOT / "site"
OUT = ROOT / "_site"
REPO_URL = "https://github.com/lucamurri/pharma-access-atlas"
SITE_URL = "https://lucamurri.github.io/pharma-access-atlas/"

NAV = [
    ("index.html", "Overview"),
    ("explorer.html", "Drug explorer"),
    ("companies.html", "Companies"),
    ("insights.html", "Insights"),
    ("methodology.html", "Methodology & sources"),
    ("about.html", "About"),
]

PAGES = {
    "index.html": ("Pharma Access Atlas: how fast new drugs reach patients in the US and Europe",
                   "Approval, benefit assessment and reimbursement timelines for every new drug approved by both "
                   "the FDA and the EU in 2019-2025, across the US, Italy, Germany, France and England, with a "
                   "public source for every number."),
    "explorer.html": ("Drug explorer | Pharma Access Atlas", "Sortable, filterable table of every drug in the atlas."),
    "companies.html": ("Company scorecard | Pharma Access Atlas",
                       "How quickly each company's new drugs reached patients in Europe, and how they were rated."),
    "insights.html": ("Insights | Pharma Access Atlas", "Findings on drug access in the US and Europe."),
    "methodology.html": ("Methodology & sources | Pharma Access Atlas", "Definitions, data sources, limitations."),
    "about.html": ("About | Pharma Access Atlas", "About the author of the Pharma Access Atlas."),
}

esc = html.escape


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout(title: str, description: str, body: str, active: str, root: str, data_as_of: str, scripts=(),
           path: str = "") -> str:
    current = ' aria-current="page"'
    nav = "\n".join(
        f'<li><a href="{root}{href}"{current if href == active else ""}>{label}</a></li>'
        for href, label in NAV
    )
    script_tags = "\n".join(f'<script src="{root}assets/{s}" defer></script>' for s in scripts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{SITE_URL}{path}">
<link rel="icon" href="{root}assets/img/favicon.svg" type="image/svg+xml">
<!-- Link previews (LinkedIn, Slack, iMessage, X): one site-wide image, per-page title and summary. -->
<meta property="og:type" content="website">
<meta property="og:site_name" content="Pharma Access Atlas">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{SITE_URL}{path}">
<meta property="og:image" content="{SITE_URL}assets/img/social.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Pharma Access Atlas: how fast do new drugs reach patients in the US and Europe?">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{root}assets/css/style.css">
{script_tags}
</head>
<body data-root="{root}">
<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{root}index.html">Pharma Access Atlas</a>
    <nav aria-label="Main">
      <ul class="nav">{nav}</ul>
    </nav>
  </div>
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site-footer">
  <div class="wrap footer-inner">
    <p>Data as of {esc(fmt_date(data_as_of))}. Every value links to its public source.
       Not medical, legal or investment advice.</p>
    <p><a href="{root}methodology.html">Methodology &amp; sources</a> ·
       <a href="{root}data/drugs.json">Download the data (JSON)</a> ·
       <a href="{REPO_URL}">Code on GitHub</a></p>
  </div>
</footer>
</body>
</html>
"""


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "n/a"
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def fill(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    if "{{" in text:
        start = text.index("{{")
        raise SystemExit(f"Unfilled placeholder: {text[start:start + 40]}")
    return text


# ---------------------------------------------------------------------------
# Drug brief pages
# ---------------------------------------------------------------------------
RATING_LABEL = {
    "major": "Major added benefit", "considerable": "Considerable added benefit",
    "minor": "Minor added benefit", "non-quantifiable": "Non-quantifiable added benefit",
    "no added benefit": "No added benefit proven", "lesser": "Lesser benefit",
}


def timeline_svg(events: list[dict], as_of: str | None) -> str:
    """A simple horizontal timeline drawn as inline SVG (no JavaScript needed).

    events: [{"label", "date", "kind"}], kind = us | eu | it | de | pending
    """
    dated = [e for e in events if e["date"]]
    if not dated:
        return ""
    start = date.fromisoformat(min(e["date"] for e in dated))
    end = date.fromisoformat(max([e["date"] for e in dated] + ([as_of] if as_of else [])))
    span = max((end - start).days, 1)
    width, left, right = 760, 40, 40
    usable = width - left - right

    def x(iso):
        return left + usable * (date.fromisoformat(iso) - start).days / span

    # Alternate labels above/below the axis so close dates don't collide.
    parts = [f'<line x1="{left}" y1="80" x2="{width - right}" y2="80" class="tl-axis"/>']
    for i, e in enumerate(sorted(dated, key=lambda e: e["date"])):
        cx = x(e["date"])
        above = i % 2 == 0
        ty = 26 if above else 126  # label baseline; the date sits 17px below it
        anchor = "start" if cx < width * 0.2 else "end" if cx > width * 0.8 else "middle"
        parts.append(f'<line x1="{cx:.1f}" y1="80" x2="{cx:.1f}" y2="{50 if above else 110}" class="tl-tick"/>')
        cls = "tl-dot tl-pending" if e["kind"] == "pending" else f"tl-dot tl-{e['kind']}"
        parts.append(f'<circle cx="{cx:.1f}" cy="80" r="7" class="{cls}"/>')
        parts.append(f'<text x="{cx:.1f}" y="{ty}" text-anchor="{anchor}" class="tl-label">{esc(e["label"])}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{ty + 17}" text-anchor="{anchor}" class="tl-date">{esc(fmt_date(e["date"]))}</text>')
    summary = "; ".join(f'{e["label"]} {fmt_date(e["date"])}' for e in sorted(dated, key=lambda e: e["date"]))
    return (f'<svg class="timeline" viewBox="0 0 {width} 160" role="img" '
            f'aria-label="Timeline: {esc(summary)}">{"".join(parts)}</svg>')


def source_link(obj: dict, text="source") -> str:
    url = obj.get("source_url")
    return f'<a href="{esc(url)}" rel="noopener">{text}</a>' if url else ""


def brief_page(drug: dict, row: dict, prev_next: tuple, data_as_of: str) -> str:
    f = drug["fields"]
    name = row["brand_us"] if row["brand_us"] == row["brand_eu"] else f'{row["brand_us"]} / {row["brand_eu"]}'

    badges = []
    if row["us_orphan"] == "yes":
        badges.append("US orphan")
    if row["eu_orphan"] == "yes":
        badges.append("EU orphan")
    if row["eu_conditional"] == "yes":
        badges.append("EU conditional approval")
    if row["atmp"] == "yes":
        badges.append("Cell / gene therapy")
    if row["cms_selected"] == "yes":
        badges.append(f"Medicare negotiation ({row['cms_ipay']})")
    if row["cohort"] == "reference":
        badges.append("Reference drug (not in headline statistics)")
    if row["eu_status"] and row["eu_status"] != "Authorised":
        badges.append(f"EU status: {row['eu_status']}")
    badge_html = "".join(f'<li class="badge">{esc(b)}</li>' for b in badges)

    # --- timeline ---------------------------------------------------------
    events = [
        {"label": "FDA approval", "date": row["fda_date"], "kind": "us"},
        {"label": "EC approval", "date": row["ec_date"], "kind": "eu"},
        {"label": "Italy reimbursed", "date": row["it_date"], "kind": "it"},
        {"label": "G-BA decision", "date": row["gba_date"], "kind": "de"},
        {"label": "HAS opinion", "date": row["fr_date"], "kind": "fr"},
        {"label": "NICE guidance", "date": row["en_date"], "kind": "en"},
    ]
    as_of = None
    if row["it_status"] == "not reimbursed":
        events.append({"label": "Italy: still waiting", "date": row["it_checked"], "kind": "pending"})
        as_of = row["it_checked"]
    svg = timeline_svg(events, as_of)
    # The same events as a plain list, shown instead of the drawing on narrow screens.
    tl_list = '<ol class="timeline-list">' + "".join(
        f'<li><span>{esc(e["label"])}</span><span class="tl-when">{esc(fmt_date(e["date"]))}</span></li>'
        for e in sorted((e for e in events if e["date"]), key=lambda e: e["date"])) + "</ol>"

    # --- key numbers ------------------------------------------------------
    lag = row["lag"]
    lag_text = (f"{lag:,} days" if lag is not None else "n/a")
    lag_note = ("US approved first" if lag and lag > 0 else "EU approved first" if lag and lag < 0 else "Same day")
    if row["it_lag"] is not None:
        it_text, it_note = f'{row["it_lag"]:,} days', "EC approval to Italian reimbursement"
    elif row["it_status"] == "not reimbursed":
        it_text, it_note = "Not reimbursed", f'{row["it_waiting"]:,} days since EC approval, as of {fmt_date(row["it_checked"])}'
    else:
        it_text, it_note = "Unknown", "Not yet verified"
    rating = row["gba_rating"]
    de_text = RATING_LABEL.get(rating, "Not assessed" if rating == "not assessed"
                               else "Assessment in progress" if row["gba_pending"] else "Unknown")
    de_note = (f'Best result across patient groups, {fmt_date(row["gba_date"])}' if row["gba_date"]
               else "No § 35a benefit assessment found")

    ASMR_LABEL = {"I": "ASMR I (major)", "II": "ASMR II (important)", "III": "ASMR III (moderate)",
                  "IV": "ASMR IV (minor)", "V": "ASMR V (no improvement)"}
    fr_text = ASMR_LABEL.get(row["fr_asmr"], "SMR insufficient (no ASMR)" if row["fr_smr"] == "insufficient"
                             else "No HAS opinion yet" if row["fr_pending"] else "Unknown")
    fr_note = (f'HAS opinion, {fmt_date(row["fr_date"])}' if row["fr_date"] else
               (f.get("fr_has_asmr_best") or {}).get("notes") or "Not available")
    en_labels = {"recommended": "Recommended", "optimised": "Recommended (restricted)",
                 "managed access": "Managed access (CDF / IMF)", "not recommended": "Not recommended",
                 "terminated": "Terminated appraisal", "not appraised": "Not appraised"}
    en_text = en_labels.get(row["en_decision"], "Appraisal in progress" if row["en_pending"] else "Unknown")

    # --- access outcomes table ---------------------------------------------
    def cell(name, text=None):
        obj = f.get(name) or {}
        shown = text if text is not None else (obj.get("value") if obj.get("value") is not None else "n/a")
        return f'{esc(str(shown))} <span class="src">{source_link(obj)}</span>'

    if row["it_status"] == "reimbursed":
        it_outcome = f'Reimbursed, class {row["it_class"]}'
    elif row["it_status"] == "not reimbursed":
        it_outcome = f'Not reimbursed as of {fmt_date(row["it_checked"])} (class {row["it_class"]})'
    else:
        it_outcome = "Unknown"
    gba_extra = []
    if row["gba_any_nab"] == "yes" and rating != "no added benefit":
        gba_extra.append("at least one patient group: no added benefit")
    if row["gba_orphan"] == "yes":
        gba_extra.append("orphan route (benefit deemed proven by law)")
    de_outcome = de_text + (f' ({"; ".join(gba_extra)})' if gba_extra else "")
    if row["cms_selected"] == "yes":
        us_outcome = (f'Selected for Medicare negotiation; Maximum Fair Price ${row["cms_mfp"]:,} per 30 days '
                      f'from {row["cms_ipay"]}, vs CMS list price ${row["cms_list"]:,} '
                      f'({row["cms_discount"]}% lower)')
    else:
        us_outcome = "Not selected for Medicare negotiation"

    table = f"""
<table class="data-table">
  <caption class="visually-hidden">Access milestones and outcomes by country</caption>
  <thead><tr><th scope="col">Market</th><th scope="col">Milestone</th><th scope="col">Date</th><th scope="col">Outcome</th></tr></thead>
  <tbody>
    <tr><th scope="row">United States</th><td>FDA approval</td><td>{cell("fda_approval_date", fmt_date(row["fda_date"]))}</td>
        <td>{cell("cms_selected", us_outcome)}</td></tr>
    <tr><th scope="row">European Union</th><td>EC marketing authorisation</td><td>{cell("ec_approval_date", fmt_date(row["ec_date"]))}</td>
        <td>{"Conditional approval" if row["eu_conditional"] == "yes" else "Standard approval"} <span class="src">{source_link(f["eu_conditional"])}</span></td></tr>
    <tr><th scope="row">Italy</th><td>Reimbursement published in Gazzetta Ufficiale</td>
        <td>{cell("it_gu_date", fmt_date(row["it_date"]) if row["it_date"] else ("None yet" if row["it_status"] == "not reimbursed" else "n/a"))}</td>
        <td>{cell("it_reimbursement_class", it_outcome)}</td></tr>
    <tr><th scope="row">Germany</th><td>G-BA AMNOG decision</td>
        <td>{cell("de_gba_decision_date", fmt_date(row["gba_date"]) if row["gba_date"] else ("None" if rating == "not assessed" else "n/a"))}</td>
        <td>{cell("de_gba_rating_best", de_outcome)}</td></tr>
    <tr><th scope="row">France</th><td>HAS Transparency Committee opinion</td>
        <td>{cell("fr_has_date", fmt_date(row["fr_date"]) if row["fr_date"] else "n/a")}</td>
        <td>{cell("fr_has_asmr_best", fr_text + (f' · SMR {row["fr_smr"]}' if row["fr_smr"] else ""))}</td></tr>
    <tr><th scope="row">England</th><td>NICE guidance{f' ({esc(row["en_ta"])})' if row["en_ta"] else ""}</td>
        <td>{cell("en_nice_date", fmt_date(row["en_date"]) if row["en_date"] else "n/a")}</td>
        <td>{cell("en_nice_decision", en_text)}</td></tr>
  </tbody>
</table>"""

    # --- every field with its source -------------------------------------
    defs = json.loads((PROCESSED / "drugs.json").read_text())["field_definitions"]
    source_rows = []
    for key, obj in f.items():
        if obj.get("status") == "calculated":
            src = "Calculated from " + ", ".join(defs[k]["label"] for k in obj["derived_from"])
        elif obj.get("source_url"):
            src = f'{source_link(obj, "link")} · retrieved {esc(obj.get("retrieved_date") or "")}'
        else:
            src = "No source: value not available"
        value = obj.get("value")
        shown = "n/a" if value is None else value
        status = obj.get("status", "")
        note = f'<br><span class="muted small">{esc(obj["notes"])}</span>' if obj.get("notes") else ""
        source_rows.append(f'<tr><th scope="row">{esc(defs[key]["label"])}</th><td>{esc(str(shown))}'
                           f'{"" if status in ("verified", "calculated") else f" <span class=status>({esc(status)})</span>"}'
                           f'{note}</td><td>{src}</td></tr>')

    prev_row, next_row = prev_next
    pager = '<nav class="pager" aria-label="Other drugs">'
    if prev_row:
        pager += f'<a href="{prev_row["id"]}.html">← {esc(prev_row["brand_us"])}</a>'
    pager += '<a href="../explorer.html">All drugs</a>'
    if next_row:
        pager += f'<a href="{next_row["id"]}.html">{esc(next_row["brand_us"])} →</a>'
    pager += "</nav>"

    return f"""
<article class="brief">
  <p class="eyebrow">{esc(row["area"])} · Market-access brief</p>
  <h1>{esc(name)}</h1>
  <p class="lede">{esc(row["inn"])} · {esc(row["company"])}</p>
  <ul class="badges" aria-label="Characteristics">{badge_html}</ul>

  <section aria-labelledby="tl-h">
    <h2 id="tl-h">Timeline</h2>
    <div class="timeline-wrap">{svg}{tl_list}</div>
  </section>

  <section class="kpis" aria-label="Key numbers">
    <div class="kpi"><p class="kpi-label">US-to-EU approval lag</p><p class="kpi-value">{esc(lag_text)}</p><p class="kpi-note">{esc(lag_note)}</p></div>
    <div class="kpi"><p class="kpi-label">Italy access delay</p><p class="kpi-value">{esc(it_text)}</p><p class="kpi-note">{esc(it_note)}</p></div>
    <div class="kpi"><p class="kpi-label">Germany G-BA rating</p><p class="kpi-value kpi-value-sm">{esc(de_text)}</p><p class="kpi-note">{esc(de_note)}</p></div>
    <div class="kpi"><p class="kpi-label">France HAS rating</p><p class="kpi-value kpi-value-sm">{esc(fr_text)}</p><p class="kpi-note">{esc(fr_note)} · NICE: {esc(en_text)}</p></div>
  </section>

  <section aria-labelledby="out-h">
    <h2 id="out-h">Access outcomes by market</h2>
    <div class="table-scroll">{table}</div>
  </section>

  <section aria-labelledby="sw-h" class="so-what">
    <h2 id="sw-h">So what</h2>
    {{{{so_what}}}}
  </section>

  <details class="sources">
    <summary>All data points and sources for {esc(row["brand_us"])}</summary>
    <div class="table-scroll">
    <table class="data-table small">
      <thead><tr><th scope="col">Field</th><th scope="col">Value</th><th scope="col">Source</th></tr></thead>
      <tbody>{"".join(source_rows)}</tbody>
    </table>
    </div>
  </details>
  {pager}
</article>"""


# ---------------------------------------------------------------------------
def main() -> None:
    data = analysis.load()
    rows = analysis.flat_rows(data)
    s = analysis.summary(rows)
    titles = analysis.chart_titles(s)
    draft = "--draft" in sys.argv
    try:
        findings = analysis.findings(rows, s)  # stops the build if a written claim no longer holds
    except (SystemExit, KeyError, TypeError):
        if not draft:
            raise
        findings = None  # draft preview: the Insights page shows a placeholder
    bullets = so_what_rules.generate_all(rows, s)
    if check_text.main(bullets, findings) != 0:
        raise SystemExit("A generated 'so what' bullet contains a number not found in the data.")
    as_of = data["data_as_of"]

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE / "assets", OUT / "assets")
    (OUT / ".nojekyll").write_text("")  # tell GitHub Pages to serve files as-is

    # Data for the JavaScript, plus the full sourced dataset for download.
    write_json(OUT / "data" / "atlas.json", {"data_as_of": as_of, "summary": s, "titles": titles, "rows": rows})
    shutil.copy(PROCESSED / "drugs.json", OUT / "data" / "drugs.json")

    waiting_names = ", ".join(w["brand"] for w in s["it_waiting"]) or "none"
    values = {
        "data_as_of": fmt_date(as_of),
        "n": s["n"],
        "lag_median": analysis.days(s["lag_median"]),
        "lag_us_first": s["lag_us_first"],
        "lag_eu_first": s["lag_eu_first"],
        "it_lag_median": s["access"]["it"]["median"],
        "it_n_reimbursed": s["it_n_reimbursed"],
        "it_n_waiting": s["it_n_waiting"],
        "it_waiting_names": waiting_names,
        "gba_pct_nab": s["gba_pct_no_added_benefit"],
        "gba_n_nab": s["gba_n_no_added_benefit"],
        "gba_n_assessed": s["gba_n_assessed"],
        "cms_n_selected": s["cms_n_selected"],
        "title_lag": esc(titles["lag"]),
        "title_italy": esc(titles["italy"]),
        "title_countries": esc(titles["countries"]),
        "title_hta": esc(titles["hta"]),
        "title_companies": esc(analysis.scorecard_title(s)),
        "scorecard_min": analysis.SCORECARD_MIN,
        "n_companies": len(s["companies"]),
        "n_reference": s["n_reference"],
        "fr_pct_negative": s["fr_pct_negative"],
        "fr_n": s["fr_n"],
        "en_pct_positive": s["en_pct_positive"] if s["en_pct_positive"] is not None else "n/a",
        "en_n": s["en_n"],
        "repo_url": REPO_URL,
    }
    # Numbers for the Insights page (years stay unformatted; other numbers get thousands separators).
    for key, value in (findings or {}).items():
        is_year = key in ("cms_ipay", "cms_list_year")
        values[key] = value if is_year or not isinstance(value, int) else f"{value:,}"
    scripts = {"index.html": ["vendor/chart.umd.min.js", "js/common.js", "js/overview.js"],
               "explorer.html": ["js/common.js", "js/explorer.js"],
               "companies.html": ["js/common.js", "js/companies.js"],
               "insights.html": ["vendor/chart.umd.min.js", "js/common.js", "js/insights.js"]}
    for page, (title, description) in PAGES.items():
        template = (SITE / "pages" / page).read_text(encoding="utf-8")
        if page == "insights.html" and findings is None:
            template = '<h1>Insights</h1><p class="callout">Draft build: findings are being rewritten.</p>'
        body = fill(template, values)
        (OUT / page).write_text(layout(title, description, body, page, "", as_of, scripts.get(page, ()),
                                       path="" if page == "index.html" else page), encoding="utf-8")

    # One brief per drug, ordered as in the drug list.
    so_what = {k: "<ul>" + "".join(f"<li>{esc(b)}</li>" for b in v) + "</ul>" for k, v in bullets.items()}
    (OUT / "drugs").mkdir()
    by_id = {d["drug_id"]: d for d in data["drugs"]}
    for i, row in enumerate(rows):
        prev_next = (rows[i - 1] if i > 0 else None, rows[i + 1] if i < len(rows) - 1 else None)
        body = brief_page(by_id[row["id"]], row, prev_next, as_of)
        body = body.replace("{{so_what}}", so_what[row["id"]])
        title = f'{row["brand_us"]} market-access brief | Pharma Access Atlas'
        # The preview text is the drug's own first two "so what" bullets (already checked against the data).
        desc = f'{row["brand_us"]} ({row["inn"]}): ' + " ".join(bullets[row["id"]][:2])
        if len(desc) > 200:
            desc = desc[:197].rsplit(" ", 1)[0] + "…"
        (OUT / "drugs" / f'{row["id"]}.html').write_text(
            layout(title, desc, body, "explorer.html", "../", as_of, path=f'drugs/{row["id"]}.html'), encoding="utf-8")

    # Sitemap so search engines find every page and brief (submit it in Google Search Console).
    urls = [SITE_URL + ("" if p == "index.html" else p) for p in PAGES] + [f'{SITE_URL}drugs/{r["id"]}.html' for r in rows]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{as_of}</lastmod></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    print(f"  ok   built {len(PAGES)} pages + {len(rows)} drug briefs into _site/")


if __name__ == "__main__":
    print("Building site ...")
    main()
