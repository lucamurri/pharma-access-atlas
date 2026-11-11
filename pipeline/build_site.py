"""Build the static website into _site/ (the folder GitHub Pages publishes), in four languages.

    python3 pipeline/build_site.py
    python3 -m http.server 8000 --directory _site     # then open http://localhost:8000

What it does
  1. Wraps each page template with the shared layout (header, nav, language switcher, footer).
     English pages come from site/pages/, translations from site/pages/i18n/<lang>/.
  2. Fills {{placeholders}} with numbers from pipeline/analysis.py, formatted the local way.
  3. Generates one brief page per drug and language.
  4. Copies assets and writes the data files the JavaScript reads (one per language, same data).

English lives at the site root (unchanged addresses); Italian, German and French under /it/, /de/, /fr/.
All other text (navigation, briefs, chart labels, generated bullets) comes from site/i18n/<lang>.json.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from datetime import date

import analysis
import check_text
import i18n
import so_what as so_what_rules
from common import PROCESSED, ROOT, write_json

SITE = ROOT / "site"
OUT = ROOT / "_site"
REPO_URL = "https://github.com/lucamurri/pharma-access-atlas"
SITE_URL = "https://lucamurri.github.io/pharma-access-atlas/"
LANG_NAMES = {"en": "English", "it": "Italiano", "de": "Deutsch", "fr": "Français"}

NAV = [("index.html", "nav.overview"), ("explorer.html", "nav.explorer"), ("companies.html", "nav.companies"),
       ("compare.html", "nav.compare"), ("italy.html", "nav.countries"), ("insights.html", "nav.insights"),
       ("methodology.html", "nav.methodology"), ("about.html", "nav.about")]
PAGES = ["index.html", "explorer.html", "compare.html", "companies.html", "insights.html", "methodology.html",
         "about.html"]
SCRIPTS = {"index.html": ["vendor/chart.umd.min.js", "js/common.js", "js/overview.js"],
           "explorer.html": ["js/common.js", "js/explorer.js"],
           "companies.html": ["js/common.js", "js/companies.js"],
           "compare.html": ["vendor/chart.umd.min.js", "js/common.js", "js/compare.js"],
           "insights.html": ["vendor/chart.umd.min.js", "js/common.js", "js/insights.js"]}
US_SLUG = "united-states.html"
COUNTRIES = [{"key": "it", "slug": "italy.html"}, {"key": "de", "slug": "germany.html"},
             {"key": "fr", "slug": "france.html"}, {"key": "en", "slug": "england.html"}]

esc = html.escape


def lang_prefix(lang: str) -> str:
    return "" if lang == "en" else f"{lang}/"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout(t: i18n.Strings, title: str, description: str, body: str, active: str, path: str,
           scripts=(), data_as_of: str = "", extra_body_attr: str = "") -> str:
    """path: the page's address inside a language, e.g. 'explorer.html' or 'drugs/kisunla.html'."""
    depth = path.count("/")
    pages = "../" * depth                                  # back to this language's top folder
    assets = pages + ("../" if t.lang != "en" else "")     # back to the site root (assets, data)
    current = ' aria-current="page"'
    nav = "\n".join(f'<li><a href="{pages}{href}"{current if href == active else ""}>{esc(t(key))}</a></li>'
                    for href, key in NAV)
    langs = "".join(
        f'<a href="{assets}{lang_prefix(l)}{path}" hreflang="{l}" lang="{l}"'
        f'{current if l == t.lang else ""}>{l.upper()}<span class="visually-hidden"> {LANG_NAMES[l]}</span></a>'
        for l in i18n.available())
    alternates = "\n".join(f'<link rel="alternate" hreflang="{l}" href="{SITE_URL}{lang_prefix(l)}{path}">'
                           for l in i18n.available())
    page_url = f"{SITE_URL}{lang_prefix(t.lang)}{'' if path == 'index.html' else path}"
    script_tags = "\n".join(f'<script src="{assets}assets/{s}" defer></script>' for s in scripts)
    return f"""<!doctype html>
<html lang="{t.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{page_url}">
{alternates}
<link rel="alternate" hreflang="x-default" href="{SITE_URL}{path}">
<link rel="icon" href="{assets}assets/img/favicon.svg" type="image/svg+xml">
<!-- Link previews (LinkedIn, Slack, iMessage, X): one site-wide image, per-page title and summary. -->
<meta property="og:type" content="website">
<meta property="og:site_name" content="Pharma Access Atlas">
<meta property="og:locale" content="{t.loc['locale'].replace('-', '_')}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}assets/img/social.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(t('layout.og_alt'))}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{assets}assets/css/style.css">
{script_tags}
</head>
<body data-root="{assets}" data-pages="{pages}" data-lang="{t.lang}"{extra_body_attr}>
<a class="skip-link" href="#main">{esc(t('layout.skip'))}</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{pages}index.html">Pharma Access Atlas</a>
    <nav class="lang-switch" aria-label="{esc(t('layout.lang_aria'))}">{langs}</nav>
    <nav aria-label="{esc(t('layout.nav_aria'))}">
      <ul class="nav">{nav}</ul>
    </nav>
  </div>
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site-footer">
  <div class="wrap footer-inner">
    <p>{esc(t('layout.footer_asof', date=t.date(data_as_of)))}</p>
    <p><a href="{pages}methodology.html">{esc(t('layout.footer_method'))}</a> ·
       <a href="{assets}data/drugs.json">{esc(t('layout.footer_data'))}</a> ·
       <a href="{REPO_URL}">{esc(t('layout.footer_code'))}</a></p>
  </div>
</footer>
</body>
</html>
"""


def fill(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    if "{{" in text:
        start = text.index("{{")
        raise SystemExit(f"Unfilled placeholder: {text[start:start + 40]}")
    return text


def template(name: str, lang: str) -> str:
    """The page template in this language; English if no translation exists yet."""
    path = SITE / "pages" / ("" if lang == "en" else f"i18n/{lang}") / name
    if not path.exists():
        print(f"  warn no {lang} translation of {name}; using English")
        path = SITE / "pages" / name
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Study-window check (Methodology): FDA's 2024-2025 novel drugs and the EU
# ---------------------------------------------------------------------------
def window_numbers(ctx_rows: list[dict], n) -> dict:
    """How many of FDA's 2024-2025 novel drugs the window leaves out, from pipeline/crosscheck_fda.py."""
    import re
    import statistics
    path = analysis.PROCESSED.parent / "raw" / "universe" / "fda_crosscheck.json"
    years = json.loads(path.read_text())["years"]
    drugs = [d for y in ("2024", "2025") for d in years[y]["drugs"]]
    late = [d for d in drugs if d.get("reason", "").startswith("EU first authorisation after the window")]
    late_lags = [(date.fromisoformat(re.search(r"\d{4}-\d{2}-\d{2}", d["reason"]).group(0))
                  - date.fromisoformat(d["fda_date"])).days for d in late]
    lags = [r["lag"] for r in analysis.core(ctx_rows) if r["lag"] is not None]
    return {
        "win_n": n(len(drugs)), "win_in": n(sum(1 for d in drugs if d["status"] == "in atlas")),
        "win_late": n(len(late)), "win_none": n(len(drugs) - len(late) - sum(1 for d in drugs if d["status"] == "in atlas")),
        "win_med": n(analysis.days(statistics.median(lags + late_lags))),
    }


# ---------------------------------------------------------------------------
# Chart titles: each states what the chart shows, built from the data
# ---------------------------------------------------------------------------
def titles(s: dict, t: i18n.Strings) -> dict:
    a = s["access"]
    steps = {k: a[k]["median"] for k in ("de", "fr", "en", "it") if a[k]["median"] is not None}
    out = {
        "lag": t("title.lag", us_first=t.num(s["lag_us_first"]), n=t.num(s["n"]), lag=t.num(analysis.days(s["lag_median"]))),
        "italy": t("title.italy", n=t.num(s["it_n_reimbursed"]), med=t.num(analysis.days(s["it_lag_median"]))),
        "hta": t("title.hta", de=s["gba_pct_no_added_benefit"], de_n=t.num(s["gba_n_assessed"]),
                 fr_v=s["fr_pct_v"], fr_smr=s["fr_pct_smr_insufficient"], fr_n=t.num(s["fr_n"])),
    }
    # Fixed country order, no ranking: the four milestones are different events (see Methodology).
    if len(steps) == 4:
        out["countries"] = t("title.countries", **{k: t.num(v) for k, v in steps.items()})
    else:
        out["countries"] = t("title.countries_none")
    big = [c for c in s["companies"] if c["n"] >= analysis.SCORECARD_MIN]
    timed = [c for c in big if c["it_median"] is not None]
    if timed:
        f = min(timed, key=lambda c: (c["it_median"], c["company"]))
        w = max(timed, key=lambda c: (c["it_median"], c["company"]))
        out["companies"] = t("title.companies", k=len(big), min=analysis.SCORECARD_MIN, fast=f["company"],
                             fast_days=t.num(f["it_median"]), slow=w["company"], slow_days=t.num(w["it_median"]))
    else:
        out["companies"] = t("title.companies_none", k=len(big), min=analysis.SCORECARD_MIN)
    return out


# ---------------------------------------------------------------------------
# Drug brief pages
# ---------------------------------------------------------------------------
def timeline_svg(events: list[dict], as_of: str | None, t: i18n.Strings) -> str:
    """A simple horizontal timeline drawn as inline SVG (no JavaScript needed)."""
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
        parts.append(f'<text x="{cx:.1f}" y="{ty + 17}" text-anchor="{anchor}" class="tl-date">{esc(t.date(e["date"]))}</text>')
    summary = "; ".join(f'{e["label"]} {t.date(e["date"])}' for e in sorted(dated, key=lambda e: e["date"]))
    return (f'<svg class="timeline" viewBox="0 0 {width} 160" role="img" '
            f'aria-label="{esc(t("tl.aria", summary=summary))}">{"".join(parts)}</svg>')


def source_link(obj: dict, text: str) -> str:
    url = obj.get("source_url")
    return f'<a href="{esc(url)}" rel="noopener">{text}</a>' if url else ""


def brief_page(drug: dict, row: dict, prev_next: tuple, defs: dict, t: i18n.Strings) -> str:
    f = drug["fields"]
    name = row["brand_us"] if row["brand_us"] == row["brand_eu"] else f'{row["brand_us"]} / {row["brand_eu"]}'
    days = lambda n: t("brief.days", n=t.num(n))
    src_word = t("brief.src_word")

    badges = []
    if row["us_orphan"] == "yes":
        badges.append(t("badge.us_orphan"))
    if row["eu_orphan"] == "yes":
        badges.append(t("badge.eu_orphan"))
    if row["eu_conditional"] == "yes":
        badges.append(t("badge.conditional"))
    if row["atmp"] == "yes":
        badges.append(t("badge.atmp"))
    if row["cms_selected"] == "yes":
        badges.append(t("badge.cms", year=row["cms_ipay"]))
    if row["cohort"] == "reference":
        badges.append(t("badge.reference"))
    if row["eu_status"] and row["eu_status"] != "Authorised":
        badges.append(t("badge.eu_status", status=t.label(row["eu_status"])))
    badge_html = "".join(f'<li class="badge">{esc(b)}</li>' for b in badges)

    # --- timeline ---------------------------------------------------------
    events = [
        {"label": t("tl.fda"), "date": row["fda_date"], "kind": "us"},
        {"label": t("tl.ec"), "date": row["ec_date"], "kind": "eu"},
        {"label": t("tl.it"), "date": row["it_date"], "kind": "it"},
        {"label": t("tl.de"), "date": row["gba_date"], "kind": "de"},
        {"label": t("tl.fr"), "date": row["fr_date"], "kind": "fr"},
        {"label": t("tl.en"), "date": row["en_date"], "kind": "en"},
    ]
    as_of = None
    if row["it_status"] == "not reimbursed":
        events.append({"label": t("tl.it_waiting"), "date": row["it_checked"], "kind": "pending"})
        as_of = row["it_checked"]
    svg = timeline_svg(events, as_of, t)
    # The same events as a plain list, shown instead of the drawing on narrow screens.
    tl_list = '<ol class="timeline-list">' + "".join(
        f'<li><span>{esc(e["label"])}</span><span class="tl-when">{esc(t.date(e["date"]))}</span></li>'
        for e in sorted((e for e in events if e["date"]), key=lambda e: e["date"])) + "</ol>"

    # --- key numbers ------------------------------------------------------
    lag = row["lag"]
    lag_text = days(lag) if lag is not None else t("na")
    lag_note = t("brief.lag_us") if lag and lag > 0 else t("brief.lag_eu") if lag and lag < 0 else t("brief.lag_same")
    if row["it_lag"] is not None:
        it_text, it_note = days(row["it_lag"]), t("brief.it_note")
    elif row["it_status"] == "not reimbursed":
        it_text = t("brief.it_not")
        it_note = t("brief.it_waiting_note", days=t.num(row["it_waiting"]), date=t.date(row["it_checked"]))
    else:
        it_text, it_note = t("brief.unknown"), t("brief.not_verified")
    rating = row["gba_rating"]
    if rating in analysis.G_BA_ORDER:
        de_text = t("brief.gba." + rating)
    else:
        de_text = (t("brief.gba.not_assessed") if rating == "not assessed"
                   else t("brief.gba.pending") if row["gba_pending"] else t("brief.unknown"))
    de_note = t("brief.de_note", date=t.date(row["gba_date"])) if row["gba_date"] else t("brief.de_none")

    if row["fr_asmr"]:
        fr_text = t("brief.asmr." + row["fr_asmr"])
    else:
        fr_text = (t("brief.fr_insufficient") if row["fr_smr"] == "insufficient"
                   else t("brief.fr_pending") if row["fr_pending"] else t("brief.unknown"))
    fr_note = t("brief.fr_note", date=t.date(row["fr_date"])) if row["fr_date"] else t("brief.not_available")
    en_text = (t("brief.nice." + row["en_decision"]) if row["en_decision"]
               else t("brief.nice.pending") if row["en_pending"] else t("brief.unknown"))

    innov_text = (t("brief.innov." + row["it_innov"]) if row["it_innov"]
                  else t("brief.innov.none_yet") if row["it_status"] == "not reimbursed" else t("brief.unknown"))

    # --- access outcomes table ---------------------------------------------
    def cell(field, text):
        return f'{esc(str(text))} <span class="src">{source_link(f.get(field) or {}, src_word)}</span>'

    if row["it_status"] == "reimbursed":
        it_outcome = t("brief.it_out_reimbursed", cls=row["it_class"])
    elif row["it_status"] == "not reimbursed":
        it_outcome = t("brief.it_out_not", date=t.date(row["it_checked"]), cls=row["it_class"])
    else:
        it_outcome = t("brief.unknown")
    gba_extra = []
    if row["gba_any_nab"] == "yes" and rating != "no added benefit":
        gba_extra.append(t("brief.gba_extra_nab"))
    if row["gba_orphan"] == "yes":
        gba_extra.append(t("brief.gba_extra_orphan"))
    de_outcome = de_text + (f' ({"; ".join(gba_extra)})' if gba_extra else "")
    if row["cms_selected"] == "yes":
        us_outcome = t("brief.us_out_cms", mfp=t.num(row["cms_mfp"]), year=row["cms_ipay"],
                       list=t.num(row["cms_list"]), pct=t.num(row["cms_discount"]))
    else:
        us_outcome = t("brief.us_out_none")
    # The SMR is added after the ASMR; with no ASMR the label already says "SMR insufficient".
    smr = f' · {t("brief.smr", level=t("brief.smr." + row["fr_smr"]))}' if row["fr_smr"] and row["fr_asmr"] else ""
    it_date = t.date(row["it_date"]) if row["it_date"] else (t("brief.none_yet") if row["it_status"] == "not reimbursed" else t("na"))
    de_date = t.date(row["gba_date"]) if row["gba_date"] else (t("brief.none") if rating == "not assessed" else t("na"))

    table = f"""
<table class="data-table">
  <caption class="visually-hidden">{esc(t("brief.table_caption"))}</caption>
  <thead><tr><th scope="col">{esc(t("brief.th_market"))}</th><th scope="col">{esc(t("brief.th_milestone"))}</th><th scope="col">{esc(t("brief.th_date"))}</th><th scope="col">{esc(t("brief.th_outcome"))}</th></tr></thead>
  <tbody>
    <tr><th scope="row">{esc(t("brief.m_us"))}</th><td>{esc(t("brief.ms_fda"))}</td><td>{cell("fda_approval_date", t.date(row["fda_date"]))}</td>
        <td>{cell("cms_selected", us_outcome)}</td></tr>
    <tr><th scope="row">{esc(t("brief.m_eu"))}</th><td>{esc(t("brief.ms_ec"))}</td><td>{cell("ec_approval_date", t.date(row["ec_date"]))}</td>
        <td>{esc(t("brief.eu_conditional") if row["eu_conditional"] == "yes" else t("brief.eu_standard"))} <span class="src">{source_link(f["eu_conditional"], src_word)}</span></td></tr>
    <tr><th scope="row">{esc(t("brief.m_it"))}</th><td>{esc(t("brief.ms_it"))}</td>
        <td>{cell("it_gu_date", it_date)}</td>
        <td>{cell("it_reimbursement_class", it_outcome)}</td></tr>
    <tr><th scope="row">{esc(t("brief.m_it"))}</th><td>{esc(t("brief.ms_it_price"))}</td>
        <td>{cell("it_price_opinion_date", t.date(row["it_price_date"]) if row["it_price_date"] else t("na"))}</td>
        <td>{cell("it_innovative", innov_text)}</td></tr>
    <tr><th scope="row">{esc(t("brief.m_de"))}</th><td>{esc(t("brief.ms_de"))}</td>
        <td>{cell("de_gba_decision_date", de_date)}</td>
        <td>{cell("de_gba_rating_best", de_outcome)}</td></tr>
    <tr><th scope="row">{esc(t("brief.m_fr"))}</th><td>{esc(t("brief.ms_fr"))}</td>
        <td>{cell("fr_has_date", t.date(row["fr_date"]) if row["fr_date"] else t("na"))}</td>
        <td>{cell("fr_has_asmr_best", fr_text + smr)}</td></tr>
    <tr><th scope="row">{esc(t("brief.m_en"))}</th><td>{esc(t("brief.ms_en"))}{f' ({esc(row["en_ta"])})' if row["en_ta"] else ""}</td>
        <td>{cell("en_nice_date", t.date(row["en_date"]) if row["en_date"] else t("na"))}</td>
        <td>{cell("en_nice_decision", en_text)}</td></tr>
  </tbody>
</table>"""

    # --- every field with its source (values and source notes stay as recorded) ---
    source_rows = []
    for key, obj in f.items():
        label = t("field." + key) if t.has("field." + key) else defs[key]["label"]
        if obj.get("status") == "calculated":
            src = t("brief.src_calc", fields=", ".join(t("field." + k) for k in obj["derived_from"]))
        elif obj.get("source_url"):
            src = f'{source_link(obj, t("brief.src_link"))} · {esc(t("brief.src_retrieved", date=t.date(obj.get("retrieved_date"))))}'
        else:
            src = esc(t("brief.src_none"))
        value = obj.get("value")
        shown = t("na") if value is None else value
        status = obj.get("status", "")
        status_txt = "" if status in ("verified", "calculated") else \
            f' <span class=status>({esc(t("status." + status) if t.has("status." + status) else status)})</span>'
        note = f'<br><span class="muted small">{esc(obj["notes"])}</span>' if obj.get("notes") else ""
        source_rows.append(f'<tr><th scope="row">{esc(label)}</th><td>{esc(str(shown))}{status_txt}{note}</td><td>{src}</td></tr>')

    prev_row, next_row = prev_next
    pager = f'<nav class="pager" aria-label="{esc(t("brief.pager_aria"))}">'
    if prev_row:
        pager += f'<a href="{prev_row["id"]}.html">← {esc(prev_row["brand_us"])}</a>'
    pager += f'<a href="../explorer.html">{esc(t("brief.pager_all"))}</a>'
    if next_row:
        pager += f'<a href="{next_row["id"]}.html">{esc(next_row["brand_us"])} →</a>'
    pager += "</nav>"

    return f"""
<article class="brief">
  <p class="eyebrow">{esc(t("brief.eyebrow", area=t.label(row["area"])))}</p>
  <h1>{esc(name)}</h1>
  <p class="lede">{esc(row["inn"])} · {esc(row["company"])}</p>
  <ul class="badges" aria-label="{esc(t("brief.badges_aria"))}">{badge_html}</ul>
  <p class="small"><a href="../compare.html?ids={row["id"]}">{esc(t("brief.compare_link", name=name))}</a></p>

  <section aria-labelledby="tl-h">
    <h2 id="tl-h">{esc(t("brief.h_timeline"))}</h2>
    <div class="timeline-wrap">{svg}{tl_list}</div>
  </section>

  <section class="kpis" aria-label="{esc(t("brief.kpis_aria"))}">
    <div class="kpi"><p class="kpi-label">{esc(t("brief.kpi_lag"))}</p><p class="kpi-value">{esc(lag_text)}</p><p class="kpi-note">{esc(lag_note)}</p></div>
    <div class="kpi"><p class="kpi-label">{esc(t("brief.kpi_it"))}</p><p class="kpi-value">{esc(it_text)}</p><p class="kpi-note">{esc(it_note)}</p></div>
    <div class="kpi"><p class="kpi-label">{esc(t("brief.kpi_de"))}</p><p class="kpi-value kpi-value-sm">{esc(de_text)}</p><p class="kpi-note">{esc(de_note)}</p></div>
    <div class="kpi"><p class="kpi-label">{esc(t("brief.kpi_fr"))}</p><p class="kpi-value kpi-value-sm">{esc(fr_text)}</p><p class="kpi-note">{esc(fr_note)} · {esc(t("brief.nice_inline", text=en_text))}</p></div>
  </section>

  <section aria-labelledby="out-h">
    <h2 id="out-h">{esc(t("brief.h_outcomes"))}</h2>
    <div class="table-scroll">{table}</div>
  </section>

  <section aria-labelledby="sw-h" class="so-what">
    <h2 id="sw-h">{esc(t("brief.h_sowhat"))}</h2>
    {{{{so_what}}}}
  </section>

  <details class="sources">
    <summary>{esc(t("brief.sources_summary", brand=row["brand_us"]))}</summary>
    <div class="table-scroll">
    <table class="data-table small">
      <thead><tr><th scope="col">{esc(t("brief.th_field"))}</th><th scope="col">{esc(t("brief.th_value"))}</th><th scope="col">{esc(t("brief.th_source"))}</th></tr></thead>
      <tbody>{"".join(source_rows)}</tbody>
    </table>
    </div>
  </details>
  {pager}
</article>"""


# ---------------------------------------------------------------------------
def build_language(t: i18n.Strings, ctx: dict) -> int:
    data, rows, s, findings, as_of = ctx["data"], ctx["rows"], ctx["s"], ctx["findings"], ctx["as_of"]
    out = OUT / lang_prefix(t.lang)
    out.mkdir(parents=True, exist_ok=True)
    tt = titles(s, t)
    bullets = so_what_rules.generate_all(rows, s, t.lang)
    pages_written = 0

    # Data for the page scripts: the same data in every language, plus that language's strings.
    write_json(OUT / "data" / f"atlas.{t.lang}.json",
               {"data_as_of": as_of, "lang": t.lang, "locale": t.loc["locale"], "summary": s, "titles": tt,
                "rows": rows, "t": t.js()})

    n = t.num
    values = {
        "data_as_of": t.date(as_of), "n": n(s["n"]), "lag_median": n(analysis.days(s["lag_median"])),
        "lag_us_first": n(s["lag_us_first"]), "lag_eu_first": n(s["lag_eu_first"]),
        "it_lag_median": n(s["access"]["it"]["median"]), "it_n_reimbursed": n(s["it_n_reimbursed"]),
        "it_n_waiting": n(s["it_n_waiting"]), "it_n_unknown": n(s["it_n_unknown"]),
        "it_waiting_names": ", ".join(w["brand"] for w in s["it_waiting"]) or t("brief.none"),
        "gba_pct_nab": s["gba_pct_no_added_benefit"], "gba_n_nab": n(s["gba_n_no_added_benefit"]),
        "gba_n_assessed": n(s["gba_n_assessed"]), "cms_n_selected": s["cms_n_selected"],
        "title_lag": esc(tt["lag"]), "title_italy": esc(tt["italy"]), "title_countries": esc(tt["countries"]),
        "title_hta": esc(tt["hta"]), "title_companies": esc(tt["companies"]),
        "scorecard_min": analysis.SCORECARD_MIN, "n_companies": len(s["companies"]), "n_reference": s["n_reference"],
        "fr_pct_negative": s["fr_pct_negative"], "fr_n": n(s["fr_n"]),
        "en_pct_positive": s["en_pct_positive"] if s["en_pct_positive"] is not None else t("na"), "en_n": n(s["en_n"]),
        "repo_url": REPO_URL,
        "n_all": n(s["n_all"]),
        "it_innov_n": n(sum(s["it_innov"].values())), "it_innov_full": n(s["it_innov"]["full"]),
        "it_innov_cond": n(s["it_innov"]["conditional"]), "it_innov_no": n(s["it_innov"]["not recognised"]),
        "it_admin_med": n(analysis.days(s["it_admin"]["median"])) if s["it_admin"]["median"] is not None else t("na"),
        "it_admin_p25": n(analysis.days(s["it_admin"]["p25"])) if s["it_admin"]["p25"] is not None else t("na"),
        "it_admin_p75": n(analysis.days(s["it_admin"]["p75"])) if s["it_admin"]["p75"] is not None else t("na"),
        "it_admin_n": n(s["it_admin"]["n"]),
        **{f"inn_{key}_{g}_{m}": n(val) for key, gs in s["it_innov_by_verdict"].items() for g, ms in gs.items()
           for m, val in (("n", sum(ms.values())), ("yes", ms["full"] + ms["conditional"]))},
        "it_price_med": n(s["access"]["it_price"]["median"]) if s["access"]["it_price"]["median"] is not None else t("na"),
        "it_price_n": n(s["access"]["it_price"]["n"]),
        "gba_none_n": n(sum(s["gba_none"].values())), "gba_none_na": n(s["gba_none"]["not_assessed"]),
        "gba_none_ongoing": n(s["gba_none"]["not_reimbursed_as_of"]), "gba_none_unk": n(s["gba_none"]["unknown"]),
        "gba_n_nq": n(s["gba_ratings"]["non-quantifiable"]), "gba_n_nq_orphan": n(s["gba_n_nq_orphan"]),
        "fr_none": n(s["fr_none"]), "fr_n_v": n(s["fr_n_v"]), "fr_n_smr": n(s["fr_n_smr_insufficient"]),
        "fr_pct_v": s["fr_pct_v"], "fr_pct_smr": s["fr_pct_smr_insufficient"],
        "en_none_n": n(sum(s["en_none"].values())), "en_none_prog": n(s["en_none"]["in_progress"]),
        "en_none_na": n(s["en_none"]["not_appraised"]), "en_none_unk": n(s["en_none"]["unknown"]),
        "en_n_term": n(s["en_n_terminated"]),
        "en_med_all": n(s["access"]["en"]["median"]), "en_2y_all": analysis.days(s["access"]["en"]["pct_2y"]),
        "en_med_cens": n(s["en_terminated_censored"]["median"]),
        "en_2y_cens": analysis.days(s["en_terminated_censored"]["pct_2y"]),
        **window_numbers(ctx_rows=ctx["rows"], n=n),
    }
    # Robustness table on the Methodology page: early vs recent EC approvals
    dec = lambda x: f"{x:.2f}".replace(".", t.loc["decimal"])
    for k, c in s["access_by_cohort"].items():
        for g in ("early", "late"):
            values[f"coh_{k}_{g}_n"] = n(c[g]["n"])
            values[f"coh_{k}_{g}_med"] = n(c[g]["median"]) if c[g]["median"] is not None else t("na")
            values[f"coh_{k}_{g}_2y"] = analysis.days(c[g]["pct_2y"])
        values[f"coh_{k}_p"] = dec(c["p"]) if c["p"] is not None else t("na")
    # Numbers for the Insights page (years stay as they are; other whole numbers are formatted locally).
    for key, value in (findings or {}).items():
        is_year = key in ("cms_ipay", "cms_list_year")
        if key in ("drv_lc_p", "drv_alpha"):
            value = value.replace(".", t.loc["decimal"])
        values[key] = value if is_year or not isinstance(value, int) else n(value)

    def write(path: str, title: str, desc: str, body: str, active: str, scripts=(), attr=""):
        nonlocal pages_written
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        page_assets = "../" * path.count("/") + ("../" if t.lang != "en" else "")
        if page_assets:  # templates link the data file relative to the site root
            body = body.replace('href="data/', f'href="{page_assets}data/')
        target.write_text(layout(t, title, desc, body, active, path, scripts, as_of, attr), encoding="utf-8")
        pages_written += 1

    for page in PAGES:
        key = page.removesuffix(".html")
        tpl = template(page, t.lang)
        if page == "insights.html" and findings is None:
            tpl = f'<h1>{esc(t("nav.insights"))}</h1><p class="callout">{esc(t("page.insights.draft"))}</p>'
        write(page, t(f"page.{key}.title"), t(f"page.{key}.desc"), fill(tpl, values), page, SCRIPTS.get(page, ()))

    # Country pages. The US page has its own template: FDA approval is market entry, so it
    # measures how long after US approval each European milestone came.
    current = ' aria-current="page"'

    def switch(active_slug):
        links = [(US_SLUG, t("country.us.name"))] + [(c["slug"], t(f'country.{c["key"]}.name')) for c in COUNTRIES]
        return "".join(f'<a href="{slug}"{current if slug == active_slug else ""}>{esc(label)}</a>' for slug, label in links)

    u, ua = s["us"], s["access"]
    us_values = {**values, "country_switch": switch(US_SLUG),
                 "us_pct_first": u["pct_us_first"], "us_first": n(u["us_first"]), "us_n": n(u["n"]),
                 "us_pct_priority": u["pct_priority"], "us_priority": n(u["priority"]), "us_reviewed": n(u["reviewed"]),
                 "us_pct_orphan": u["pct_orphan"], "us_orphan": n(u["orphan"]), "us_orphan_known": n(u["orphan_known"]),
                 "us_curve_title": esc(t("country.us.curve_title", ec=n(ua["ec_from_fda"]["median"]),
                                         it=n(ua["it_from_fda"]["median"])))}
    write(US_SLUG, t("country.us.page_title"), t("country.us.desc", pct=u["pct_us_first"]),
          fill(template("us.html", t.lang), us_values), "italy.html",
          ["vendor/chart.umd.min.js", "js/common.js", "js/us.js"])

    tpl = template("country.html", t.lang)
    for c in COUNTRIES:
        k, a = c["key"], s["access"][c["key"]]
        median = n(a["median"]) if a["median"] is not None else t("country.not_reached")
        cvalues = {**values, "country_switch": switch(c["slug"]),
                   "c_name": esc(t(f"country.{k}.name")), "c_milestone_title": esc(t(f"country.{k}.title")),
                   "c_lede": esc(t(f"country.{k}.lede")), "c_median": median,
                   "c_1y": analysis.days(a["pct_1y"]), "c_2y": analysis.days(a["pct_2y"]),
                   "c_n": n(a["n"]), "c_waiting": n(a["waiting"]), "c_waiting_note": esc(t("country.waiting_note")),
                   "c_curve_title": esc(t("country.curve_title", short=t(f"country.{k}.short"), median=median,
                                          pct=analysis.days(a["pct_2y"]))),
                   "c_mix_title": esc(t(f"country.{k}.mix_title")), "c_mix_sub": esc(t(f"country.{k}.mix_sub")),
                   "c_note": esc(t(f"country.{k}.note"))}
        write(c["slug"], t("country.page_title", name=t(f"country.{k}.name"), title=t(f"country.{k}.title")),
              t("country.desc", short=t(f"country.{k}.short"), median=median), fill(tpl, cvalues), "italy.html",
              ["vendor/chart.umd.min.js", "js/common.js", "js/country.js"], f' data-country="{k}"')

    # One brief per drug, ordered as in the drug list.
    defs = data["field_definitions"]
    by_id = {d["drug_id"]: d for d in data["drugs"]}
    for i, row in enumerate(rows):
        prev_next = (rows[i - 1] if i > 0 else None, rows[i + 1] if i < len(rows) - 1 else None)
        body = brief_page(by_id[row["id"]], row, prev_next, defs, t)
        body = body.replace("{{so_what}}", "<ul>" + "".join(f"<li>{esc(b)}</li>" for b in bullets[row["id"]]) + "</ul>")
        # The preview text is the drug's own first two "so what" bullets (already checked against the data).
        desc = t("brief.desc", brand=row["brand_us"], inn=row["inn"], text=" ".join(bullets[row["id"]][:2]))
        if len(desc) > 200:
            desc = desc[:197].rsplit(" ", 1)[0] + "…"
        write(f'drugs/{row["id"]}.html', t("brief.title", brand=row["brand_us"]), desc, body, "explorer.html")
    return pages_written


def main() -> None:
    problems = i18n.check()
    if problems:
        print("Translation problems:\n  " + "\n  ".join(problems[:40]))
        raise SystemExit("Fix site/i18n/*.json before publishing.")
    data = analysis.load()
    rows = analysis.flat_rows(data)
    s = analysis.summary(rows)
    draft = "--draft" in sys.argv
    try:
        findings = analysis.findings(rows, s)  # stops the build if a written claim no longer holds
    except (SystemExit, KeyError, TypeError):
        if not draft:
            raise
        findings = None  # draft preview: the Insights page shows a placeholder
    # Numbers in the English bullets are checked against the data; other languages use the same rules.
    if check_text.main(so_what_rules.generate_all(rows, s, "en"), findings) != 0:
        raise SystemExit("A generated 'so what' bullet contains a number not found in the data.")

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE / "assets", OUT / "assets")
    (OUT / ".nojekyll").write_text("")  # tell GitHub Pages to serve files as-is
    (OUT / "data").mkdir()
    shutil.copy(PROCESSED / "drugs.json", OUT / "data" / "drugs.json")

    ctx = {"data": data, "rows": rows, "s": s, "findings": findings, "as_of": data["data_as_of"]}
    counts = {lang: build_language(i18n.Strings(lang), ctx) for lang in i18n.available()}

    # Sitemap: every page in every language, with its translations (submit in Google Search Console).
    paths = (PAGES + [US_SLUG] + [c["slug"] for c in COUNTRIES] + [f'drugs/{r["id"]}.html' for r in rows])
    entries = []
    for p in paths:
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITE_URL}{lang_prefix(l)}{p}"/>' for l in i18n.available())
        for l in i18n.available():
            loc = f"{SITE_URL}{lang_prefix(l)}{'' if p == 'index.html' else p}"
            entries.append(f"  <url><loc>{loc}</loc><lastmod>{data['data_as_of']}</lastmod>{alts}</url>\n")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "".join(entries) + "</urlset>\n", encoding="utf-8")
    print(f"  ok   built {sum(counts.values())} pages in {len(counts)} languages "
          f"({', '.join(f'{k}: {v}' for k, v in counts.items())}) into _site/")


if __name__ == "__main__":
    print("Building site ...")
    main()
