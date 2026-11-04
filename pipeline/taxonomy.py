"""Rule-based grouping of drugs into therapy areas and companies.

With ~200 drugs, labels are assigned by transparent rules instead of by hand:
  - Therapy area comes from the drug's ATC code (WHO Anatomical Therapeutic
    Chemical classification, as published by the EMA). Where the EMA has not
    yet assigned an ATC code, keywords in the EMA therapeutic area are used.
  - Company is the EU marketing authorisation holder, with legal-form and
    country words removed ("Eli Lilly Nederland B.V." -> "Eli Lilly").

Orphan / rare-disease status is NOT a therapy area here; it is a separate
filter (US orphan designation, EU orphan status).
"""
from __future__ import annotations

import re

# First matching prefix wins, so more specific codes come first.
ATC_AREAS = [
    ("V10X", "Oncology"),                    # therapeutic radiopharmaceuticals (e.g. Pluvicto)
    ("L01", "Oncology"), ("L02", "Oncology"),
    ("L03", "Immunology & inflammation"), ("L04", "Immunology & inflammation"),
    ("D11AH", "Immunology & inflammation"),  # e.g. atopic dermatitis biologics
    ("R03DX", "Immunology & inflammation"),  # e.g. severe asthma biologics
    ("A10", "Cardiometabolic"), ("A08", "Cardiometabolic"), ("C", "Cardiometabolic"),
    ("N", "Neurology & psychiatry"), ("M09AX", "Neurology & psychiatry"),
    ("J", "Infectious disease"),
    ("B", "Haematology"),
    ("A16", "Metabolic & genetic disorders"), ("A05", "Metabolic & genetic disorders"),
    ("R", "Respiratory"),
    ("S01", "Ophthalmology"),
    ("D", "Dermatology"),
    ("H", "Endocrinology"),
    ("M", "Musculoskeletal"),
    ("G", "Women's health & urology"),
]

# Fallback when no ATC code has been assigned yet (keyword in EMA therapeutic area).
MESH_KEYWORDS = [
    (r"neoplasm|carcinoma|lymphoma|leukemia|leukaemia|myeloma|tumou?r|cancer|myelofibrosis|sarcoma|melanoma", "Oncology"),
    (r"hemophilia|haemophilia|anemia|anaemia|thalass|sickle", "Haematology"),
    (r"diabetes|obesity|hypercholesterol|heart|cardio", "Cardiometabolic"),
    (r"alzheimer|migraine|epilep|sclerosis|parkinson|muscular atrophy|schizophren|depress", "Neurology & psychiatry"),
    (r"infection|virus|viral|bacteria|hiv|covid", "Infectious disease"),
]

LEGAL_WORDS = r"""\b(b\.?v\.?|n\.?v\.?|gmbh|ag|a/s|s\.?a\.?s?|s\.?p\.?a\.?|s\.?r\.?l\.?|ltd\.?|limited|plc|inc\.?|llc|uc|
    eeig|kg|co\.?|& co\.? kg|ab|oy|se|ireland|nederland|netherlands|europe|european|europharm|deutschland|
    international|registration|pharma(ceuticals)?|pharmaceutical|danmark|belgium|france|italia|espa[nñ]a|
    holdings?|group|the)\b"""


# Cosmetic clean-ups so one company appears under one name.
ALIASES = {
    "Bristol-Myers Squibb": "Bristol Myers Squibb", "Gilead Sciences Unlimited Company": "Gilead Sciences",
    "Janssen Cilag": "Janssen (J&J)", "Janssen-Cilag": "Janssen (J&J)", "Beone Medicines": "BeOne Medicines",
    "Swedish Orphan Biovitrum": "Sobi", "Swedish Orphan Biovitrum publ": "Sobi", "Takeda Branch": "Takeda",
    "Pfizer MA": "Pfizer", "Kite EU": "Kite (Gilead)", "Merck": "Merck KGaA", "Merck Sharp & Dohme": "MSD",
    "Regeneron Designated Activity Company DAC": "Regeneron", "Ultragenyx Germany": "Ultragenyx",
    "Accord Healthcare S.L.U": "Accord Healthcare", "Neuraxpharm S.L": "Neuraxpharm", "Estetra SPRL": "Estetra",
    "medac Gesellschaft für klinische Spezialpräparate mbH": "medac", "Incyte Biosciences Distribution": "Incyte",
    "Madrigal EU": "Madrigal", "Integral Solutions EU": "Integral Pharma Solutions", "Marinus Emerald": "Marinus",
    "Curium Pet": "Curium", "GlaxoSmithKline Trading Services": "GSK", "Sanofi Winthrop Industrie": "Sanofi",
    "Vifor Fresenius Medical Care Renal": "Vifor", "Medice Arzneimittel Pütter": "Medice",
    "Ascendis Bone Diseases": "Ascendis", "Ascendis Endocrinology Division": "Ascendis", "LEO": "LEO Pharma",
    "Pierre Fabre Medicament": "Pierre Fabre", "Les Laboratoires Servier": "Servier",
    "Viatris Healthcare": "Viatris", "Recordati Rare Diseases": "Recordati", "Argenx": "argenx",
}


def therapy_area(atc: str, mesh: str) -> str:
    atc = (atc or "").upper().replace(" ", "")
    if atc:
        for prefix, area in ATC_AREAS:
            if atc.startswith(prefix):
                return area
    for pattern, area in MESH_KEYWORDS:
        if re.search(pattern, mesh or "", re.I):
            return area
    return "Other"


def company(holder: str) -> str:
    """'Eli Lilly Nederland B.V.' -> 'Eli Lilly'; 'Bristol-Myers Squibb Pharma EEIG' -> 'Bristol-Myers Squibb'."""
    name = (holder or "").replace("\xa0", " ").strip()
    cleaned = re.sub(LEGAL_WORDS, " ", name, flags=re.I | re.X)
    cleaned = re.sub(r"[,()]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-&")
    cleaned = cleaned or name
    return ALIASES.get(cleaned, cleaned)
