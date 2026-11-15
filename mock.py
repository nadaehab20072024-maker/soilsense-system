"""Mock mode (USE_MOCK=true): NO LLM call. A tiny rule-based router picks a tool, runs the REAL tool,
and fills a template in the user's language. Good enough to test the UI and the whole pipeline."""
from __future__ import annotations

import re

from . import guards
from .crops import find_crops_in_text
from .i18n import crop_name, crops_text, t

_ROT = r"(rotation|after|next|grow|plant|sow|دورة|بعد|أزرع|ازرع|نزرع|أزرعه|الموسم الجاي|পরে|চক্র|চাষ করব|লাগাব)"
_WATER = r"(irrigat|water need|how much water|سقي|\bري\b|\bالري\b|\bماي\b|\bماء\b|সেচ|পানি)"
_HEAT = (r"(hot|heat|temperature|rain|weather|climate|risk|dry|driest|\bحر\b|حار|حرارة|مطر|\bالجو\b|\bجو\b|طقس|مناخ|خطر|جاف|أجف|"
        r"গরম|বৃষ্টি|আবহাওয়া|ঝুঁকি|শুকনো)")
_WHATIF = r"(what if|\bلو\b|ماذا لو|যদি)"

TEMPLATES = {
    "rotation": {
        "ar": "أنصحك تجرب الدورة: {best}. درجتها {b} من 100، ودورتك الحالية {e}.",
        "en": "Try this rotation: {best}. It scores {b} out of 100; your current one scores {e}.",
        "bn": "এই চক্রটি চেষ্টা করুন: {best}। এর স্কোর ১০০-এর মধ্যে {b}; আপনার বর্তমান চক্রের {e}।"},
    "rotation_why": {
        "ar": "الأسباب من أداة الدورة: {reasons}.", "en": "Reasons from the rotation tool: {reasons}.",
        "bn": "ফসল-চক্র টুলের কারণ: {reasons}।"},
    "water": {
        "ar": "أكثر شهور تحتاج فيها سقي: {m}. الاحتياج السنوي التقريبي {y} ملم.",
        "en": "The months that need the most irrigation are {m}. The yearly need is about {y} mm.",
        "bn": "সবচেয়ে বেশি সেচ লাগে {m} মাসে। বছরে আনুমানিক {y} মিমি লাগে।"},
    "risk": {
        "ar": "مستوى الخطر المناخي لسنة {year}: {level}.",
        "en": "The climate risk level for {year} is {level}.",
        "bn": "{year} সালের জলবায়ু ঝুঁকি: {level}।"},
    "mock_why": {"ar": "(وضع Mock: الرد من قالب، الأرقام من الأدوات.)", "en": "(Mock mode: template answer, numbers from tools.)",
                 "bn": "(Mock মোড: ছাঁচের উত্তর, সংখ্যা টুল থেকে।)"},
}
LEVELS = {"low": {"ar": "منخفض", "en": "low", "bn": "কম"}, "moderate": {"ar": "متوسط", "en": "moderate", "bn": "মাঝারি"},
          "high": {"ar": "عالي", "en": "high", "bn": "বেশি"}, "very_high": {"ar": "عالي جداً", "en": "very high", "bn": "খুব বেশি"}}


def _tt(key, lang, **kw):
    row = TEMPLATES[key]
    return (row.get(lang) or row["en"]).format(**kw)


def plan(question: str, ctx: dict, profile: dict, valid_crops: list[str]):
    """-> ("refuse", code) | ("ask", key) | ("tools", [(name, args), ...])"""
    q = (question or "").lower()
    if guards.asks_chemical_dose(q):
        return "refuse", "refuse_chemical"
    crops = find_crops_in_text(question, valid_crops)
    rot_intent = bool(re.search(_ROT, q))
    if crops and (rot_intent or len(crops) >= 2):
        if re.search(_WHATIF, q):
            return "tools", [("rotation_what_if", {"existing_rotation": crops, "rain_change_pct": -30})]
        return "tools", [("recommend", {"existing_rotation": crops})]
    if rot_intent and re.search(r"(rotation|دورة|চক্র|after|بعد|পরে)", q):
        if profile.get("existing_rotation"):
            return "tools", [("recommend", {"existing_rotation": profile["existing_rotation"]})]
        return "ask", "ask_rotation"
    if re.search(_WATER, q):
        return "tools", [("get_water_guidance", {"crop": crops[0] if crops else ctx.get("crop")})]
    if re.search(_HEAT, q) or guards.looks_farming(q):
        return "tools", [("get_climate_risk", {})]
    return "refuse", "refuse_offtopic"


def write(lang: str, log: list[dict]) -> dict:
    """Template answer from the first tool result."""
    if not log:
        return dict(answer="", why="", confidence="low", suggestions=[])
    name, res = log[0]["name"], log[0]["result"]
    why = t("mock_badge", lang)
    if "error" in res:
        return dict(answer="", why=why, confidence="low", suggestions=[])
    if name == "recommend":
        best = res["alternatives"][0]
        reasons = "; ".join(best["reasons"])
        return dict(answer=_tt("rotation", lang, best=" → ".join(crop_name(c, lang) for c in best["rotation"]),
                               b=best["total_score"], e=res["existing"]["total_score"]),
                    why=_tt("rotation_why", lang, reasons=reasons) + " " + _tt("mock_why", lang),
                    confidence="medium", suggestions=[])
    if name == "rotation_what_if":
        a, b = res["before"], res["after"]
        return dict(answer=t("wi_story", lang, a=a["existing"]["total_score"], b=b["existing"]["total_score"],
                             c=a["best"]["total_score"], d=b["best"]["total_score"]),
                    why=_tt("mock_why", lang), confidence="medium", suggestions=[])
    if name == "get_water_guidance":
        m = ", ".join(str(x) for x in res["peak_months"])
        return dict(answer=_tt("water", lang, m=m, y=res["yearly_irrigation_need_mm"]),
                    why=f"Kc {res['kc_used']} ({res['kc_source']}). " + _tt("mock_why", lang),
                    confidence="medium", suggestions=[])
    if name == "get_climate_risk":
        lvl = LEVELS.get(res.get("overall_level"), {}).get(lang, res.get("overall_level"))
        return dict(answer=_tt("risk", lang, year=res["year"], level=lvl), why=_tt("mock_why", lang),
                    confidence="medium", suggestions=[])
    return dict(answer="", why=why, confidence="low", suggestions=[])


__all__ = ["plan", "write", "crops_text"]
