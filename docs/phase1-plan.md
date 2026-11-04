# Pharma Access Atlas: Phase 1 plan

*Prepared 3 November 2026. Every access method below was tested live today, not taken from documentation alone.*

---

## 1. Data sources and how we get them

| # | Field(s) | Source | Access method (tested) | Refresh | Licence / terms |
|---|---|---|---|---|---|
| 1 | FDA approval date, sponsor, application number, review priority | **openFDA Drugs@FDA API** (`api.fda.gov/drug/drugsfda.json`) | Free JSON API, no key needed. Limit without a key: 240 requests/min and 1,000/day, far more than we need. | **Automatic** | US government data, public domain |
| 1b | FDA approval date for **cell & gene therapies** (Carvykti, Zolgensma, Hemgenix) | FDA CBER approval pages | **Not in openFDA** (confirmed: the API returns nothing). Enter by hand with the FDA page URL. | Manual | Public domain |
| 2 | EMA positive opinion date, EC approval date, EU orphan flag, conditional approval, holder, therapeutic area | **EMA "Medicines" download** (`medicines-output-medicines_json-report_en.json`) | Free JSON file covering all 2,754 EMA products, updated daily. No key needed. | **Automatic** | Reuse allowed with attribution (EMA legal notice) |
| 3 | US–EU approval lag | Calculated | EC approval date minus FDA approval date. A negative number means Europe approved first. | Automatic | n/a |
| 4 | Italy: date of reimbursement publication in the Gazzetta Ufficiale, reimbursement class (A / H / C / Cnn) | **Gazzetta Ufficiale** (AIFA "determina" on price and reimbursement) + **AIFA Class A/H lists** | GU: no API, so **manual** search on gazzettaufficiale.it. AIFA publishes class A/H lists as CSV (CC-BY 4.0, latest dated 30 June 2026), but they **contain no dates**, so they are useful only to cross-check the class. | Manual (dates); auto cross-check (class) | Official acts are not copyrighted (Italian law 633/1941, art. 5); AIFA data CC-BY 4.0 |
| 5 | Italy approval-to-access lag | Calculated | GU publication date minus EC approval date | Automatic | n/a |
| 6 | Germany: G-BA AMNOG added-benefit rating and decision date | **G-BA** (decision pages + machine-readable "AIS" XML) | The XML (≈26 MB, updated on the 1st and 15th of each month) is free, but the download sits behind an **"I agree to the terms of use" checkbox**. I won't script around that. Plan: **manual CSV** with the G-BA decision URL. Optionally, you download the XML yourself and a helper script cross-checks your entries against it. | Manual (+ optional cross-check) | Free reuse; G-BA terms forbid misleading or manipulated reuse, which our source-per-value rule already covers |
| 7 | Medicare negotiation: selected? Maximum Fair Price (MFP) vs list price | **CMS** fact sheets (PDF) | CMS publishes MFP and list price for a 30-day supply in PDF fact sheets (2026 and 2027 cycles). The 2028 cycle list is out (27 Jan 2026), and its prices are due by **30 Nov 2026**. Few rows and PDF format, so **manual** entry. | Manual | Public domain |
| 8 | US orphan designation | **FDA Orphan Drug Designations database** (OOPD) | Search tool only, no API. **Manual**, with the OOPD result URL. | Manual | Public domain |
| 8b | EU orphan status | EMA file (row 2) | Automatic. Caveat: the field shows the *current* status, so a drug whose orphan status was later removed shows "No". | Automatic | as row 2 |
| 9 | US list price (WAC) outside Medicare negotiation | — | **Not covered.** No free, legal, reusable source exists. The site will say so plainly. | — | — |

**In short, automatic:** FDA dates and sponsor (except cell and gene therapies), all EMA fields, EU orphan flag, and every calculated lag.
**Manual (your CSVs):** Italy GU date and class, Germany G-BA rating and date, US orphan designation, CMS negotiation and prices, FDA dates for the 3 cell and gene therapies.

### Manual CSV design (`data/manual/*.csv`)
One row per drug per field. Every row carries its proof:

```
drug_id, field, value, status, source_url, retrieved_date, notes
enhertu, it_gu_date, 2021-xx-xx, verified, https://www.gazzettaufficiale.it/..., 2026-11-03,
leqembi, it_gu_date, , not_reimbursed_as_of, https://..., 2026-11-03, no GU determina found
```

`status` separates the three cases a blank cell would otherwise mix up:
- `verified`: a value with a source
- `not_reimbursed_as_of`: we checked and access has not happened yet. This is real information, not missing data.
- `unknown`: not yet checked, or not verifiable. Flagged on the site.

Planned files: `italy_aifa.csv`, `germany_gba.csv`, `us_orphan.csv`, `cms_negotiation.csv`, `fda_cber_dates.csv`.

---

## 2. Proposed drug list (30 drugs)

**Inclusion rule:** a new active substance (or new combination) with its **first FDA approval** and its **first EC marketing authorisation** both between 1 Jan 2019 and 31 Dec 2025.

FDA dates come from openFDA (first "ORIG" approval). EC dates come from the EMA file. Both were pulled live today. The lag is EC minus FDA, in days.

| Area | Drug (US / EU brand) | Company | FDA | EC | Lag | Why it's in |
|---|---|---|---|---|---|---|
| Oncology | Enhertu | Daiichi Sankyo / AZ | 2019-12-20 | 2021-01-18 | 395 | Blockbuster ADC; EU conditional approval |
| Oncology | Lumakras / Lumykras | Amgen | 2021-05-28 | 2022-01-06 | 223 | First KRAS inhibitor; tough HTA reviews |
| Oncology | Trodelvy | Gilead | 2020-04-22 | 2021-11-22 | 579 | US accelerated approval, long EU gap |
| Oncology | Pluvicto | Novartis | 2022-03-23 | 2022-12-09 | 261 | Radioligand; complex delivery logistics |
| Oncology | Retevmo / Retsevmo | Eli Lilly | 2020-05-08 | 2021-02-11 | 279 | Precision oncology (RET) |
| Oncology | Carvykti | J&J / Legend | *manual (CBER)* | 2022-05-25 | — | CAR-T; EU orphan |
| Rare | Trikafta / Kaftrio | Vertex | 2019-10-21 | 2020-08-21 | 305 | Landmark CF drug; famous EU pricing debates |
| Rare | Evrysdi | Roche | 2020-08-07 | 2021-03-26 | 231 | Oral SMA therapy |
| Rare | Zolgensma | Novartis | *manual (CBER)* | 2020-05-18 | — | Gene therapy, multi-million-dollar price |
| Rare | Hemgenix | CSL Behring | *manual (CBER)* | 2023-02-20 | — | Hemophilia B gene therapy |
| Rare | Oxlumo | Alnylam | 2020-11-23 | 2020-11-19 | −4 | Same-week approval in US and EU |
| Rare | Skyclarys | Biogen (Reata) | 2023-02-28 | 2024-02-09 | 346 | First therapy for Friedreich ataxia |
| Rare | Voxzogo | BioMarin | 2021-11-19 | 2021-08-26 | −85 | **EU first** |
| Immunology | Rinvoq | AbbVie | 2019-08-16 | 2019-12-16 | 122 | Major JAK inhibitor |
| Immunology | Skyrizi | AbbVie | 2019-04-23 | 2019-04-26 | 3 | Near-simultaneous approval |
| Immunology | Tezspire | AstraZeneca / Amgen | 2021-12-17 | 2022-09-19 | 276 | Severe asthma biologic |
| Immunology | Adbry / Adtralza | LEO Pharma | 2021-12-27 | 2021-06-17 | −193 | **EU first**; European sponsor |
| Immunology | Sotyktu | BMS | 2022-09-09 | 2023-03-24 | 196 | First TYK2 inhibitor |
| Immunology | Bimzelx | UCB | 2023-10-17 | 2021-08-20 | −788 | **EU first, by over 2 years** |
| Cardiometabolic | Rybelsus | Novo Nordisk | 2019-09-20 | 2020-04-03 | 196 | **Medicare-negotiated** (semaglutide, 2027 MFP) |
| Cardiometabolic | Wegovy | Novo Nordisk | 2021-06-04 | 2022-01-06 | 216 | **Medicare-negotiated** (semaglutide, 2027 MFP); obesity coverage differs across countries |
| Cardiometabolic | Mounjaro | Eli Lilly | 2022-05-13 | 2022-09-15 | 125 | GLP-1/GIP; same molecule as Zepbound |
| Cardiometabolic | Leqvio | Novartis | 2021-12-22 | 2020-12-09 | −378 | **EU first**; siRNA for LDL |
| Cardiometabolic | Camzyos | BMS | 2022-04-28 | 2023-06-26 | 424 | First-in-class for obstructive HCM |
| Cardiometabolic | Kerendia | Bayer | 2021-07-09 | 2022-02-16 | 222 | European sponsor; kidney/heart |
| Neurology | Leqembi | Eisai / Biogen | 2023-01-06 | 2025-04-15 | 830 | Alzheimer's; restricted EU label |
| Neurology | Kisunla | Eli Lilly | 2024-07-02 | 2025-09-24 | 449 | Alzheimer's; recent, so access is likely still pending |
| Neurology | Vyepti | Lundbeck | 2020-02-21 | 2022-01-24 | 703 | Migraine (IV anti-CGRP) |
| Neurology | Nurtec ODT / Vydura | Pfizer | 2020-02-27 | 2022-04-25 | 788 | Oral migraine (gepant) |
| Neurology | Vyvgart | argenx | 2021-12-17 | 2022-08-10 | 236 | Myasthenia gravis; European sponsor |

**Mix:** 6 oncology, 7 rare disease, 6 immunology, 6 cardiometabolic, 5 neurology. Of these, 3 are cell or gene therapies, 5 were approved first in the EU, and 2 are Medicare-negotiated.

**Early sanity check (not a finding yet):** across the 27 drugs with both dates automated, the median US-to-EU lag is **231 days**.

**Reserves**, if a drug drops out: Elrexfio, Opdualag, Saphnelo, Nilemdo/Nexletol, Qalsody, Casgevy, Wainua/Wainzua, Ebglyss, Zeposia, Ponvory.

**Deliberately excluded:** Kesimpta. The FDA records it as a supplement to an older ofatumumab application (Arzerra, 2009), so its "first US approval" would be misleading. Zepbound is excluded too, as the same molecule as Mounjaro.

---

## 3. Risks and how I'll handle them

1. **Medicare negotiation barely overlaps the 2019–2025 window. This needs your decision.** By law, a drug becomes eligible only 7 years after approval (11 for biologics). So a drug first approved in 2019 or later can't be selected on its own yet. Across the 40 drugs selected so far (2026, 2027 and 2028 cycles; the 2028 list was confirmed from the CMS fact sheet), only **Rybelsus and Wegovy** fall inside our window. They got in because CMS grouped all semaglutide products with Ozempic (2017). That is a finding in its own right. Options:
   - **A (recommended):** keep the window strict, flag Rybelsus and Wegovy, and explain the 7/11-year rule on the Methodology page.
   - **B:** also add a clearly labelled "Medicare negotiation reference set" of about 5 older drugs (e.g., Kisqali, Verzenio, Erleada, Calquence, Trulicity), shown separately and kept out of the headline numbers.
2. **The same drug can have several FDA applications** (e.g., Rybelsus has two NDAs). openFDA also sometimes labels products under the wrong brand name. Fix: I'll store each drug's original application number in a hand-curated list, so the pipeline never guesses.
3. **"Access" means different things in each country.** In **Germany**, a drug is reimbursed from launch, and the G-BA rating comes about 6 months later, mainly to set the price. So for Germany we report the *rating* and *decision date*, not an "access delay". In **Italy**, reimbursement starts at GU publication, so Italy gets a true access lag. The site will explain this so the numbers aren't compared like-for-like by mistake.
4. **One drug can have many G-BA decisions** (new indications, time-limited re-assessments) and several patient groups with different ratings. Rule: use the **first decision for the first indication**, and record both the best rating across patient groups and whether any group got "no added benefit". Orphan drugs under the revenue threshold get added benefit "deemed proven" by law, so the site must flag them.
5. **Obesity drugs** may be excluded from statutory reimbursement as "lifestyle" products (e.g., Germany §34 SGB V). These get recorded as `not_reimbursed_as_of` with a source, never left blank.
6. **Early or special access in Italy** (Law 648/96, the 5% AIFA fund, Cnn class) isn't the same as full reimbursement. In v1, the GU reimbursement determina defines "access", and early access is listed as a limitation.
7. **The EMA opinion date is sometimes blank** (e.g., Camzyos). That value stays null and gets flagged. The EC date, which is the one that matters, is always present.
8. **GitHub pauses scheduled workflows in public repos after 60 days with no commits.** If the data doesn't change for two months, the monthly refresh could stop. Fix: the workflow writes a small "last checked" log each run, which keeps the repo active, or I'll show you how to re-enable it.
9. **Manual workload.** About 30 drugs × (Italy + Germany + US orphan) ≈ 90 lookups. See decision 2 below.
10. **Prices are thin by design.** Only CMS-published US prices (MFP and list price for semaglutide) will appear. No Italian or German net prices. Those are confidential, and the site will say so.

---

## 4. Technical choices (plain language)

- **Python using only its built-in libraries.** The pipeline needs nothing installed, so there are fewer things that can break. (Exception: Phase 6 may need one small tool for the screenshot.)
- **Plain HTML/CSS/JS** with **Chart.js saved inside the repo**. No framework is needed for 6 page types and about 30 drugs.
- **Drug brief pages** are generated as static HTML files by a Python script, one per drug. They load fast and work without JavaScript.
- **Everything is free:** GitHub Pages and Actions for public repos, plus free public data. No API keys anywhere.

---

## 5. Decisions I need from you

1. **Medicare scope:** Option A (strict window, recommended) or B (add a separate reference set)?
2. **Who fills the manual CSVs:** I can **pre-fill** them in Phase 2 from the Gazzetta Ufficiale, G-BA and FDA OOPD pages, each value with its source URL, and you spot-check. Or I hand you empty templates. Pre-filling is recommended; you'd review about 90 values instead of researching them.
3. **Drug list:** approve as is, or swap any drug for a reserve.
