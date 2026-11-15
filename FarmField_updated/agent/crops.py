"""Crop names and coefficients.

The list of valid crops ALWAYS comes from the teammates' list_crops() (see team_bridge).
This file only adds (a) words farmers may use for those crops and (b) FAO-56 coefficients.
"""
from __future__ import annotations

import re
import unicodedata

# FAO-56 (Allen et al. 1998), Table 12, single crop coefficient Kc mid, as published at
# https://www.fao.org/4/x0490e/x0490e0b.htm (checked 2026-11-14).
# NEEDS EXPERT REVIEW: Table 12 values are for a sub-humid climate (RHmin ~45%, wind ~2 m/s) and
# FAO Penman-Monteith ET0. Here ET0 is Hargreaves and the climate is arid, so no climatic adjustment
# (FAO-56 eq. 62) is applied. Treat results as rough estimates.
KC_MID_FAO56 = {
    "wheat": dict(kc=1.15, row="Spring Wheat 1.15 (winter wheat also 1.15)"),
    "barley": dict(kc=1.15, row="Barley 1.15"),
    "sorghum": dict(kc=1.05, row="Sorghum, grain 1.00-1.10 (midpoint 1.05 used)"),
    "pearl_millet": dict(kc=1.00, row="Millet 1.00 (not specific to pearl millet)"),
    "cowpea": dict(kc=1.05, row="Green Gram and Cowpeas 1.05"),
    "chickpea": dict(kc=1.00, row="Chick pea 1.00"),
    "tomato": dict(kc=1.15, row="Tomato 1.15 (staked tomatoes may need ~1.20)"),
    "onion": dict(kc=1.05, row="Onions, dry 1.05"),
    "sesame": dict(kc=1.10, row="Sesame 1.10"),
    # okra: NOT in FAO-56 Table 12 -> crop-neutral estimate (Kc = 1.0) is used and the answer says so.
}
NEUTRAL_KC = 1.0
KC_REVIEW_NOTE = "needs expert review"

# Words farmers may use. English/Arabic written by the developer; bn/ur/hi NEED NATIVE REVIEW.
# Ambiguous words are deliberately NOT mapped: Arabic "ذرة" (maize OR sorghum), Gulf "بر" (wheat OR land),
# Urdu "جو" (barley, but Arabic "weather"), Urdu "تل" (sesame, but Arabic "hill"), English "millet" (many species).
ALIASES = {
    "wheat": ["wheat", "قمح", "حنطة", "গম", "گندم", "गेहूं", "गेहूँ"],
    "barley": ["barley", "شعير", "যব", "বার্লি", "जौ"],
    "sorghum": ["sorghum", "ذرة رفيعة", "ذرة بيضاء", "سورغم", "জোয়ার", "جوار", "ज्वार"],
    "pearl_millet": ["pearl millet", "pearl_millet", "دخن", "الدخن", "বাজরা", "باجرا", "बाजरा"],
    "cowpea": ["cowpea", "cowpeas", "لوبيا", "لوبياء", "বরবটি", "লোবিয়া", "لوبیا", "लोबिया"],
    "chickpea": ["chickpea", "chickpeas", "chick pea", "حمص", "ছোলা", "چنا", "چنے", "चना"],
    "tomato": ["tomato", "tomatoes", "طماطم", "طماط", "بندورة", "টমেটো", "ٹماٹر", "टमाटर"],
    "onion": ["onion", "onions", "بصل", "پیاز", "পেঁয়াজ", "পিঁয়াজ", "प्याज"],
    "sesame": ["sesame", "سمسم", "তিল", "तिल"],
    "okra": ["okra", "lady finger", "bhindi", "بامية", "باميا", "ঢেঁড়স", "ঢেড়স", "ভেন্ডি", "بھنڈی", "भिंडी"],
}

_AR_DIACRITICS = re.compile(r"[ً-ْـ]")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).strip().lower()
    text = _AR_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[\s_\-]+", " ", text)


def resolve_crop(word: str, valid: list[str]) -> str | None:
    """Map one farmer word to a valid crop name, or None. Only names in `valid` (list_crops()) are returned."""
    w = _norm(word)
    w_noal = w[2:] if w.startswith("ال") and len(w) > 3 else w      # Arabic article
    for crop in valid:
        cands = {_norm(crop)} | {_norm(a) for a in ALIASES.get(crop, [])}
        if w in cands or w_noal in cands:
            return crop
    return None


def resolve_crops(words: list, valid: list[str]) -> tuple[list[str], list[str]]:
    ok, bad = [], []
    for word in words or []:
        c = resolve_crop(word, valid)
        (ok if c else bad).append(c or str(word))
    return ok, bad


def find_crops_in_text(text: str, valid: list[str]) -> list[str]:
    t = " " + _norm(text) + " "
    hits = []
    for crop in valid:
        for a in sorted({crop, *ALIASES.get(crop, [])}, key=len, reverse=True):
            a = _norm(a)
            # Arabic "و"/"ال" prefixes and plain word boundaries
            m = re.search(r"(?:^|[\s,،.؟?!/()]|و|ال|وال|بال|لل)" + re.escape(a)
                          + r"(?=$|[\s,،.؟?!/()।]|ات|s|es|ের|র|কে|এ|ও|ে)", t)
            if m and len(a) >= 2:
                hits.append((m.start(), crop))
                break
    return [c for _, c in sorted(hits)]


def kc_for(crop: str | None) -> dict:
    if crop and crop in KC_MID_FAO56:
        k = KC_MID_FAO56[crop]
        return dict(kc=k["kc"], kc_source="FAO-56 Table 12 Kc mid: " + k["row"], kc_status=KC_REVIEW_NOTE)
    return dict(kc=NEUTRAL_KC, kc_source="crop-neutral estimate (Kc = 1.0, plain ET0); no verified FAO-56 value",
                kc_status=KC_REVIEW_NOTE)
