# Pharma Access Atlas

**How quickly, and on what terms, do new drugs reach patients in the US, Italy and Germany? A fully sourced market-access dashboard covering 30 innovative medicines.**

**Live site → [lucamurri.github.io/pharma-access-atlas](https://lucamurri.github.io/pharma-access-atlas/)**

[![Overview page of the Pharma Access Atlas](docs/screenshot.png)](https://lucamurri.github.io/pharma-access-atlas/)

---

## The problem

A drug's approval date is the date that makes headlines, but it is not when patients get the drug. In Europe, an
EU-wide approval is followed by separate national decisions on price, reimbursement and added value. These can take
years and vary by country. The public data needed to see this is scattered across four agencies, three
languages and formats ranging from APIs to official gazettes.

The atlas puts those pieces side by side for 30 drugs approved by both the FDA and the European Commission in
2019–2025. The drugs span oncology, rare disease, immunology, cardiometabolic (including GLP-1s) and neurology. It
tracks each drug from FDA approval, through EU approval, to reimbursement in **Italy** and benefit assessment in
**Germany**, plus Medicare price negotiation in the **US** where it applies. **Every value links to its public source**,
and anything that could not be verified is left blank and flagged.

## Three key findings

*(Data as of 3 November 2026; full analysis on the [Insights](https://lucamurri.github.io/pharma-access-atlas/insights.html) page.)*

1. **Approval is the short part of the wait.** EU approval came a median **227 days** after the FDA's. Italian
   reimbursement then took a median **519 days** more, so reimbursed access in Italy arrived a median
   **795 days** (over two years) after US approval. Three drugs are still waiting.
2. **Without orphan protection, most drugs showed no added benefit in Germany.** Of the 23 drugs assessed against an existing
   therapy, **57% showed no added benefit** for any patient group in their first G-BA decision. All 6 drugs assessed
   under the orphan rules received a benefit rating.
3. **Evidence travels.** Drugs that Germany rated as offering major or considerable benefit were reimbursed in
   Italy a median **174 days sooner** than drugs with no added benefit. This is an association across independent
   systems, not cause and effect.

## Methodology in brief

- **Drugs:** 30 new active substances with both first FDA approval and first EC authorisation between 2019 and 2025,
  curated for a mix of therapy areas and cases where Europe approved first.
- **Measures:** US-to-EU approval lag; Italian access delay (EC approval to reimbursement published in the
  *Gazzetta Ufficiale*); German AMNOG rating and date (first G-BA decision); orphan status; and Medicare negotiated
  price where CMS publishes one.
- **Rules:** no estimates. Each value carries a `source_url` and a `retrieved_date`. A validation step blocks
  publication if a value lacks a source, if dates are illogical (for example, reimbursement before approval) or if a
  drug is duplicated. A text check confirms that every number in the written analysis matches the data.
- **Coverage:** prices are limited to what CMS publishes. US list prices and European net prices are not public.
  Full definitions and limitations are on the [Methodology](https://lucamurri.github.io/pharma-access-atlas/methodology.html) page.

| Source | Fields | Collection |
|---|---|---|
| openFDA (Drugs@FDA) | FDA approval date, applicant | API, refreshed monthly |
| EMA medicine data | CHMP opinion, EC approval, EU orphan, conditional approval | Download, refreshed monthly |
| CMS Drug Price Negotiation | Selection, Maximum Fair Price | Data file, refreshed monthly |
| Gazzetta Ufficiale / AIFA | Italian reimbursement date and class | Manual, sourced CSV |
| G-BA | AMNOG decision date and rating | Manual, sourced CSV |
| FDA OOPD, CBER, CMS fact sheets | US orphan designation, cell and gene therapy dates, list price | Manual, sourced CSV |

## Tech stack

- **Data pipeline:** Python, standard library only (nothing to install). The code fetches, merges, validates and
  reports coverage. See [`pipeline/`](pipeline/).
- **Site:** static HTML, CSS and JavaScript, with [Chart.js](https://www.chartjs.org/) stored in the repo (no CDN,
  no framework, no tracking). Drug briefs are generated as static pages.
- **Hosting and automation:** GitHub Pages and GitHub Actions on the free tier. Every push is validated and
  deployed, and a monthly job refreshes the automatable sources, committing only if something changed.
- **Accessibility:** passes an automated axe-core WCAG 2.1 AA audit in light and dark mode. It supports keyboard
  navigation, and every chart has a data-table alternative.

```
pipeline/           fetch_*.py → build.py → validate.py → coverage.py; build_site.py
data/raw/           trimmed extracts of the downloaded sources
data/manual/        hand-maintained CSVs (one sourced fact per row; see its README)
data/processed/     drugs.json: every field with value, status, source and date
site/               page templates, CSS, JS, written analysis
.github/workflows/  deploy.yml (on push) and refresh.yml (monthly)
```

### Run it locally

Requires Python 3.9 or later.

```bash
git clone https://github.com/lucamurri/pharma-access-atlas.git
cd pharma-access-atlas
python3 pipeline/run_all.py            # fetch sources, build, validate, show coverage
python3 pipeline/build_site.py         # build the site into _site/
python3 -m http.server 8000 --directory _site   # open http://localhost:8000
```

Use `python3 pipeline/run_all.py --offline` to rebuild from the committed data without downloading, and
`python3 -m unittest discover pipeline` to run the validator tests. To update a hand-maintained value, edit
the CSVs in `data/manual/` as described in [`data/manual/README.md`](data/manual/README.md).

## Built with AI

The project was built with [Claude Code](https://claude.com/claude-code) as an AI-augmented workflow. I defined the
question, the scope, the data rules and the analysis. The AI helped write the code and gather sources under those
rules, and I reviewed the results. Researched values carry a source link and notes so that anyone can re-check them.

## Licence

- **Code:** [MIT](LICENSE).
- **Data:** each source keeps its own terms.
  - US federal data (FDA, CMS) is in the public domain.
  - EMA content may be reused with acknowledgement.
  - AIFA open data is CC BY 4.0, and Italian official acts are not subject to copyright.
  - G-BA decisions may be reused provided they are not distorted.
- **Chart.js:** MIT, © Chart.js contributors.

*Not medical, legal or investment advice. Independent project, not affiliated with any agency or company named.*

---

**Luca Murri** · Master in Management, University of Chicago Booth School of Business (2027) ·
[LinkedIn](https://www.linkedin.com/in/lucamurri)
