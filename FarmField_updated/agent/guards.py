
from __future__ import annotations

import re

from .grounding import normalize_digits

_CHEM = r"(pesticide|insecticide|herbicide|fungicide|glyphosate|chemical|spray|poison|مبيد|مبيدات|كيماوي|كيميائي|\bرش\b|\bسم\b|" \
        r"কীটনাশক|আগাছানাশক|রাসায়নিক|বিষ|স্প্রে)"
_DOSE = r"(dose|dosage|how much|how many|mix|ml|litre|liter|gram|per|جرعة|كم|كمية|نسبة|خلط|مل|لتر|جرام|غرام|" \
        r"মাত্রা|কতটুকু|কত|মিশাব|মিলি|লিটার|গ্রাম)"
_DOSE_OUT = re.compile(r"\d+(?:\.\d+)?\s*(?:ml|mL|g|gm|grams?|l|L|litres?|liters?|cc|مل|ملل|جرام|غرام|لتر|মিলি|গ্রাম|লিটার)"
                       r"\s*(?:/|per|لكل|في|প্রতি)", re.I)


def asks_chemical_dose(question: str) -> bool:
    q = (question or "").lower()
    return bool(re.search(_CHEM, q)) and bool(re.search(_DOSE, q))


def answer_has_dose(text: str) -> bool:
    return bool(_DOSE_OUT.search(normalize_digits(text or "")))


_FARM = r"(farm|crop|grow|plant|soil|water|irrigat|rain|heat|hot|weather|climate|harvest|seed|rotation|season|" \
        r"wheat|tomato|onion|barley|sorghum|millet|cowpea|chickpea|sesame|okra|palm|fertili|drought|" \
        r"مزرع|زرع|محصول|محاصيل|تربة|\bماء\b|\bماي\b|سقي|\bري\b|مطر|\bحر\b|حار|حرارة|\bجو\b|\bالجو\b|طقس|مناخ|حصاد|بذور|دورة|موسم|نخل|سماد|جفاف|" \
        r"قمح|طماطم|بصل|شعير|لوبيا|حمص|سمسم|بامية|دخن|فلج|" \
        r"খামার|ফসল|চাষ|মাটি|পানি|সেচ|বৃষ্টি|গরম|আবহাওয়া|জলবায়ু|বীজ|মৌসুম|গম|টমেটো|পেঁয়াজ|সার|খরা)"


def looks_farming(question: str) -> bool:

    return bool(re.search(_FARM, (question or "").lower()))
