# Expansion work in progress (branch `expansion-wip`)

Goal agreed with Luca: cover **all qualifying drugs (~200)** and add **France** and **England (NICE)**.
The live site on `main` still shows the 30-drug version.

## Done (stage 1, universe and automated data)
- `pipeline/universe.py` selects drugs by rule: an FDA new active substance (NME NDA or original BLA) plus the
  first EC authorisation of the same substance, both in 2019–2025. Diagnostics (ATC V04/V09) are excluded.
  Cell and gene therapies come from the EMA advanced-therapy list, with FDA dates hand-verified in `us_fda.csv`.
  Result: **207 drugs** (190 CDER + 15 cell/gene + 2 reference: Rybelsus, Wegovy).
  It was cross-checked against FDA's official novel-approval lists for 2021–2025: 4 explainable mismatches.
- FDA dates were verified for 12 new cell/gene therapies, plus Blenrep's original 2020 approval (manual override).
  Ebvallo and Zemcelpro were excluded (not FDA-approved).
- `pipeline/taxonomy.py`: therapy area from the ATC code, company from the EU holder name (cleaned).
- `pipeline/fetch_france.py`: HAS SMR/ASMR first opinion from the BDPM open data (Licence ouverte).
  Found for 143 of 207 drugs; the rest are not listed in the BDPM.
- `build.py` and `fields.py` were extended with France and England fields, a cohort flag, ATC code, EU status and a
  manual FDA-date override.

## Next steps
1. Fix the one validation error: **artesunate (Amivas)**. The EMA opinion date (2023) is after the EC date (2021),
   which is likely an EMA data quirk (the opinion field shows a later procedure). Treat the opinion date as
   unreliable when it is later than the EC date (set it to null with a note) rather than failing.
2. Research the manual fields for the ~177 new drugs, in batches of 15–20 with research agents and the same strict
   rules as before:
   - Italy: GU date and class
   - Germany: G-BA first decision
   - England: NICE decision, date and TA number (new file `data/manual/england_nice.csv`)
   - US orphan designation
3. Stage 3, site:
   - Redesign the charts for ~200 drugs (distributions or strip plots instead of one bar per drug).
   - Add France and England to the KPIs, briefs and explorer.
   - Exclude the reference cohort from the medians.
4. Stage 4, analysis:
   - Rewrite `analysis.findings()` and the guards, plus the Insights text.
   - Generate the "so what" bullets from rules for the new drugs and keep the 30 hand-written ones.
   - Update the README numbers, methodology (selection rule, taxonomy, France and England sources), and the
     unit tests (`test_real_data_passes`).
5. Merge into `main` only once validation and the build pass. That triggers the deploy.
