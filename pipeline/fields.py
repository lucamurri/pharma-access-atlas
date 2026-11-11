"""The data dictionary: every field the Atlas publishes, in one place.

group  - which source the field comes from (used for the coverage table)
kind   - date | text | number | yes_no | enum
mode   - auto (refreshed by the pipeline) | manual (data/manual/*.csv) | calculated
"""

G_BA_RATINGS = ["major", "considerable", "minor", "non-quantifiable", "no added benefit", "lesser"]
IT_CLASSES = ["A", "H", "C", "Cnn"]
FR_SMR = ["important", "moderate", "low", "insufficient"]
FR_ASMR = ["I", "II", "III", "IV", "V"]
# NICE technology appraisal outcomes, as worded by NICE.
IT_INNOVATIVE = ["full", "conditional", "not recognised"]
NICE_DECISIONS = ["recommended", "optimised", "managed access", "not recommended", "terminated", "not appraised"]

FIELDS = {
    # --- Identity (curated in data/manual/drugs.csv) -----------------------
    "brand_us":          {"group": "Identity", "kind": "text", "mode": "manual", "label": "US brand"},
    "brand_eu":          {"group": "Identity", "kind": "text", "mode": "manual", "label": "EU brand"},
    "inn":               {"group": "Identity", "kind": "text", "mode": "manual", "label": "Active ingredient"},
    "company":           {"group": "Identity", "kind": "text", "mode": "auto", "label": "Company (EU authorisation holder)"},
    "therapy_area":      {"group": "Identity", "kind": "text", "mode": "auto", "label": "Therapy area (from ATC code)"},
    "cohort":            {"group": "Identity", "kind": "enum", "mode": "manual", "label": "Cohort", "allowed": ["core", "reference"]},

    # --- United States: FDA -----------------------------------------------
    "fda_approval_date":   {"group": "FDA", "kind": "date", "mode": "auto", "label": "FDA approval date"},
    "fda_application":     {"group": "FDA", "kind": "text", "mode": "auto", "label": "FDA application number"},
    "fda_sponsor":         {"group": "FDA", "kind": "text", "mode": "auto", "label": "FDA applicant (as recorded)"},
    "fda_review_priority": {"group": "FDA", "kind": "text", "mode": "auto", "label": "FDA review priority"},
    "us_orphan_designated": {"group": "FDA", "kind": "yes_no", "mode": "manual", "label": "US orphan designation"},

    # --- European Union: EMA / European Commission -------------------------
    "ema_opinion_date":    {"group": "EMA", "kind": "date", "mode": "auto", "label": "CHMP positive opinion date"},
    "ec_approval_date":    {"group": "EMA", "kind": "date", "mode": "auto", "label": "EC marketing authorisation date"},
    "ema_holder":          {"group": "EMA", "kind": "text", "mode": "auto", "label": "EU marketing authorisation holder"},
    "ema_therapeutic_area": {"group": "EMA", "kind": "text", "mode": "auto", "label": "EMA therapeutic area (MeSH)"},
    "atc_code":            {"group": "EMA", "kind": "text", "mode": "auto", "label": "ATC code"},
    "eu_status":           {"group": "EMA", "kind": "text", "mode": "auto", "label": "EU authorisation status"},
    "eu_orphan":           {"group": "EMA", "kind": "yes_no", "mode": "auto", "label": "EU orphan medicine (current status)"},
    "eu_conditional":      {"group": "EMA", "kind": "yes_no", "mode": "auto", "label": "EU conditional approval"},
    "eu_accelerated":      {"group": "EMA", "kind": "yes_no", "mode": "auto", "label": "EU accelerated assessment"},
    "eu_prime":            {"group": "EMA", "kind": "yes_no", "mode": "auto", "label": "EU PRIME scheme"},
    "eu_atmp":             {"group": "EMA", "kind": "yes_no", "mode": "auto", "label": "Advanced therapy (ATMP)"},

    # --- Italy: AIFA / Gazzetta Ufficiale ----------------------------------
    "it_gu_date":             {"group": "Italy", "kind": "date", "mode": "manual", "label": "Italy reimbursement (GU publication) date"},
    "it_reimbursement_class": {"group": "Italy", "kind": "enum", "mode": "manual", "label": "Italy reimbursement class", "allowed": IT_CLASSES},
    # From the reimbursement determination itself (recitals and operative part)
    "it_innovative":          {"group": "Italy", "kind": "enum", "mode": "manual", "label": "AIFA innovativeness in the reimbursement determination", "allowed": IT_INNOVATIVE},
    "it_dossier_date":        {"group": "Italy", "kind": "date", "mode": "manual", "label": "Reimbursement application date (per determination)"},
    "it_cts_date":            {"group": "Italy", "kind": "date", "mode": "manual", "label": "AIFA scientific opinion date (CTS, or CSE from 2024)"},
    "it_price_opinion_date":  {"group": "Italy", "kind": "date", "mode": "manual", "label": "AIFA price opinion date (CPR, or CSE from 2024)"},
    "it_board_date":          {"group": "Italy", "kind": "date", "mode": "manual", "label": "AIFA Board (CdA) resolution date"},

    # --- Germany: G-BA (AMNOG) ---------------------------------------------
    "de_gba_decision_date":        {"group": "Germany", "kind": "date", "mode": "manual", "label": "G-BA decision date (first)"},
    "de_gba_rating_best":          {"group": "Germany", "kind": "enum", "mode": "manual", "label": "G-BA added benefit (best patient group)", "allowed": G_BA_RATINGS},
    "de_gba_any_no_added_benefit": {"group": "Germany", "kind": "yes_no", "mode": "manual", "label": "Any patient group with no added benefit"},
    "de_gba_orphan_route":         {"group": "Germany", "kind": "yes_no", "mode": "manual", "label": "Assessed under orphan rules"},

    # --- France: HAS Transparency Committee (via BDPM) ----------------------
    "fr_has_date":             {"group": "France", "kind": "date", "mode": "auto", "label": "HAS first inclusion opinion date"},
    "fr_has_smr_best":         {"group": "France", "kind": "enum", "mode": "auto", "label": "HAS SMR (best indication)", "allowed": FR_SMR},
    "fr_has_asmr_best":        {"group": "France", "kind": "enum", "mode": "auto", "label": "HAS ASMR (best indication; I = major, V = none)", "allowed": FR_ASMR},
    "fr_has_any_insufficient": {"group": "France", "kind": "yes_no", "mode": "auto", "label": "Any indication with insufficient SMR"},

    # --- England: NICE --------------------------------------------------------
    "en_nice_decision": {"group": "England", "kind": "enum", "mode": "manual", "label": "NICE first appraisal outcome", "allowed": NICE_DECISIONS},
    "en_nice_date":     {"group": "England", "kind": "date", "mode": "manual", "label": "NICE first guidance publication date"},
    "en_nice_ta":       {"group": "England", "kind": "text", "mode": "manual", "label": "NICE guidance number"},

    # --- US Medicare negotiation: CMS --------------------------------------
    "cms_selected":         {"group": "CMS", "kind": "yes_no", "mode": "auto", "label": "Selected for Medicare negotiation"},
    "cms_ipay":             {"group": "CMS", "kind": "number", "mode": "auto", "label": "Price applicability year"},
    "cms_mfp_30day":        {"group": "CMS", "kind": "number", "mode": "auto", "label": "Maximum Fair Price, 30-day supply (USD)"},
    "cms_list_price_30day": {"group": "CMS", "kind": "number", "mode": "manual", "label": "List price, 30-day supply (USD), per CMS"},
    "cms_list_price_year":  {"group": "CMS", "kind": "number", "mode": "manual", "label": "Year of CMS list price"},

    # --- Calculated by the pipeline ----------------------------------------
    "us_eu_lag_days":        {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "US-to-EU approval lag (days; negative = EU first)"},
    "first_region":          {"group": "Calculated", "kind": "text", "mode": "calculated", "label": "Approved first in"},
    "it_access_lag_days":    {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "EC approval to Italian reimbursement (days)"},
    "it_price_opinion_lag_days": {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "EC approval to AIFA price opinion (days)"},
    "it_admin_days":         {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "AIFA price opinion to GU publication (days)"},
    "it_days_waiting":       {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "Days since EC approval without Italian reimbursement (as of check)"},
    "de_gba_lag_days":       {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "EC approval to G-BA decision (days)"},
    "fr_has_lag_days":       {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "EC approval to HAS opinion (days)"},
    "en_nice_lag_days":      {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "EC approval to NICE guidance (days)"},
    "cms_discount_pct":      {"group": "Calculated", "kind": "number", "mode": "calculated", "label": "MFP discount vs CMS list price (%)"},
}

# Which manual CSV holds which fields (validation checks fields land in the right file).
MANUAL_FILES = {
    "italy_aifa.csv": ["it_gu_date", "it_reimbursement_class", "it_innovative", "it_dossier_date", "it_cts_date",
                       "it_price_opinion_date", "it_board_date"],
    "germany_gba.csv": ["de_gba_decision_date", "de_gba_rating_best", "de_gba_any_no_added_benefit", "de_gba_orphan_route"],
    "us_fda.csv": ["us_orphan_designated", "fda_approval_date", "fda_application", "fda_brand"],
    "cms_list_prices.csv": ["cms_list_price_30day", "cms_list_price_year"],
    "england_nice.csv": ["en_nice_decision", "en_nice_date", "en_nice_ta"],
    "france_has.csv": ["fr_has_date", "fr_has_smr_best", "fr_has_asmr_best", "fr_has_any_insufficient"],
}
