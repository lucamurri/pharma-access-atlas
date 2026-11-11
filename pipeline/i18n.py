"""Languages of the site: English (default), Italian, German, French.

Every piece of text that is not in a page template lives in site/i18n/<lang>.json, keyed by a short id:

    t = i18n.Strings("it")
    t("brief.kpi.lag")                          -> "Ritardo di approvazione USA-UE"
    t("so.lag_longer", lag=t.num(449), med=212) -> fills {lag} and {med}

English is the reference: every key must exist in en.json, and a translation that lacks a key, or drops or
adds a {placeholder}, fails the build (see check()). Numbers and dates are formatted the local way.
"""
from __future__ import annotations

import json
import re
from datetime import date

from common import ROOT

LANGS = ["en", "it", "de", "fr"]
STRINGS = ROOT / "site" / "i18n"

# Local number and date conventions.
LOCALE = {
    "en": {"locale": "en-GB", "thousands": ",", "decimal": ".",
           "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
           "date": "{d} {m} {y}"},
    "it": {"locale": "it-IT", "thousands": ".", "decimal": ",",
           "months": ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"],
           "date": "{d} {m} {y}"},
    "de": {"locale": "de-DE", "thousands": ".", "decimal": ",",
           "months": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."],
           "date": "{d}. {m} {y}"},
    "fr": {"locale": "fr-FR", "thousands": " ", "decimal": ",",
           "months": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
           "date": "{d} {m} {y}"},
}
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def available() -> list[str]:
    """Languages that have a strings file (English always)."""
    return [l for l in LANGS if l == "en" or (STRINGS / f"{l}.json").exists()]


def _load(lang: str) -> dict:
    return json.loads((STRINGS / f"{lang}.json").read_text(encoding="utf-8"))


class Strings:
    def __init__(self, lang: str):
        self.lang = lang
        self.en = _load("en")
        self.table = self.en if lang == "en" else {**self.en, **_load(lang)}
        self.loc = LOCALE[lang]

    def __call__(self, key: str, **kw) -> str:
        text = self.table[key]
        return text.format(**kw) if kw else text

    def has(self, key: str) -> bool:
        return key in self.table

    def num(self, n) -> str:
        """1234 -> '1,234' (en), '1.234' (it, de), '1 234' (fr)."""
        if n is None:
            return self("na")
        if isinstance(n, float) and not n.is_integer():
            whole, frac = f"{n:.1f}".split(".")
            return self.num(int(whole)) + self.loc["decimal"] + frac
        return f"{int(n):,}".replace(",", self.loc["thousands"])

    def date(self, iso: str | None) -> str:
        if not iso:
            return self("na")
        d = date.fromisoformat(iso)
        return self.loc["date"].format(d=d.day, m=self.loc["months"][d.month - 1], y=d.year)

    def ordinal(self, n: int) -> str:
        """3 -> '3rd' (en), '3ª' (it), '3.' (de), '3e' (fr; 1 -> '1re')."""
        if self.lang == "en":
            return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
        if self.lang == "it":
            return f"{n}ª"
        if self.lang == "de":
            return f"{n}."
        return "1re" if n == 1 else f"{n}e"

    def label(self, text: str) -> str:
        """Translate a data label (therapy area, chart label) if a translation exists."""
        return self.table.get("label." + text, text)

    def js(self) -> dict:
        """The strings the page scripts need (keys starting with js., label., or the shared verdict names)."""
        prefixes = ("js.", "label.", "gba.", "asmr.", "nice.", "innov.", "na")
        return {k: v for k, v in self.table.items() if k.startswith(prefixes)}


def check() -> list[str]:
    """Problems in the translations: missing keys, extra keys, or placeholders that differ from English."""
    en = _load("en")
    problems = []
    for lang in available()[1:]:
        tr = _load(lang)
        for key, text in en.items():
            if key.startswith("_"):
                continue
            if key not in tr:
                problems.append(f"{lang}: missing {key}")
            elif sorted(PLACEHOLDER.findall(text)) != sorted(PLACEHOLDER.findall(tr[key])):
                problems.append(f"{lang}: {key} placeholders {sorted(PLACEHOLDER.findall(tr[key]))} "
                                f"!= {sorted(PLACEHOLDER.findall(text))}")
        problems += [f"{lang}: unknown key {k}" for k in tr if k not in en and not k.startswith("_")]
    return problems
