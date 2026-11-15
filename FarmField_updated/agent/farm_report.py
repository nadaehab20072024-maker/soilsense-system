"""Farm report: the farmer updates the farm info and current status; the report summarises the coming
weather, alerts, watering schedule, rotation advice and photo hints, plus a short AI "insights" part.

Every number in the AI insights is checked against the report data (same grounding rule as the chat).
Without an LLM (Mock mode / no key / outage) the insights come from simple rules instead."""
from __future__ import annotations

import datetime as dt
import json
import re

from . import config as C
from . import grounding as G
from . import guards
from .i18n import crop_name
from .i18n_farm import tf
from .llm import AllProvidersFailed, chat

# Typical application efficiency by method. NEEDS EXPERT REVIEW (commonly quoted FAO ranges:
# drip ~90%, sprinkler ~75%, surface/flood ~60%; real values depend on design and upkeep).
METHOD_EFFICIENCY = {"drip": 0.9, "sprinkler": 0.75, "flood": 0.6, "falaj": 0.6, "unknown": 1.0}
STAGES = ("sowing", "growing", "flowering", "harvest")
STATUSES = ("good", "some_problems", "serious_problems")


def new_farm_info(profile: dict | None = None) -> dict:
    p = profile or {}
    return dict(name="", lat=p.get("lat"), lon=p.get("lon"), crops=list(p.get("existing_rotation") or [])[:3],
                crop_now=p.get("crop") or "", stage="growing", area_m2=None, method="unknown",
                last_irrigation=None, status="good", notes="", updated=None)


def build_report_data(info: dict, weather: dict, schedule: dict | None, rotation: dict | None,
                      photo_notes: list[str] | None) -> dict:
    """Compact, number-carrying dict. It is both the report body and the grounding source."""
    coming = [d for d in weather.get("days", []) if d["when"] != "past"] if weather.get("available") else []
    counts = {}
    for d in coming:
        counts[d["level"]] = counts.get(d["level"], 0) + 1
    worst = max(coming, key=lambda d: d["level"]) if coming else None
    data = dict(
        date=dt.date.today().isoformat(),
        farm={k: info.get(k) for k in ("name", "lat", "lon", "crops", "crop_now", "stage", "area_m2", "method",
                                       "last_irrigation", "status", "notes", "updated")},
        weather=dict(available=bool(weather.get("available")), demo=weather.get("demo", False),
                     days=len(coming), level_counts=counts,
                     worst_day=dict(date=worst["date"], level=worst["level"], top=worst["top"],
                                    tmax_c=worst["tmax_c"], rain_mm=worst["rain_mm"], gust_kmh=worst["gust_kmh"])
                     if worst else None,
                     hottest_c=max([d["tmax_c"] for d in coming if d["tmax_c"] is not None], default=None),
                     rain_total_mm=round(sum(d["rain_mm"] for d in coming), 1),
                     alerts=[dict(date=a["date"], level=a["level"], hazards=[h["key"] for h in a["hazards"]])
                             for a in weather.get("alerts", [])][:5]),
    )
    if schedule:
        fut = [r for r in schedule["rows"] if r["when"] != "past"]
        data["watering"] = dict(crop=schedule["crop"], kc=schedule["kc"],
                                coming_total_mm=schedule["coming_total_irrigation_mm"],
                                coming_total_litres=schedule["coming_total_litres"],
                                avg_need_before_rain_mm=schedule["avg_need_before_rain_mm"],
                                avg_need_after_rain_mm=schedule["avg_need_after_rain_mm"],
                                days=[dict(date=r["date"], action=r["action"], mm=r["irrigate_mm"], litres=r["litres"])
                                      for r in fut])
    if rotation and not rotation.get("error"):
        best = rotation["alternatives"][0]
        data["rotation"] = dict(current=rotation["existing"]["rotation"], current_score=rotation["existing"]["total_score"],
                                best=best["rotation"], best_score=best["total_score"],
                                scores_are_local=(rotation.get("location") or {}).get("scores_are_local"))
    if photo_notes:
        data["photos"] = photo_notes[-3:]
    return data


# ------------------------------------------------------------------ insights
# Structure (like an "AI insights" card): headline / why (evidence bullets) / meaning / actions.
def _rule_insights(data: dict, lang: str) -> dict:
    w, wt, farm = data["weather"], data.get("watering"), data["farm"]
    worst = w.get("worst_day")
    lvl = worst["level"] if worst else 0
    why, actions = [], []
    if worst and lvl >= 3:
        headline = tf("ins_danger", lang, date=worst["date"], lvl=tf(f"lvl_{lvl}", lang))
        why.append(tf("why_worst", lang, date=worst["date"], hz=tf("hz_" + worst["top"], lang)))
    elif w.get("available"):
        headline = tf("ins_calm", lang)
    else:
        headline = tf("forecast_unavailable", lang)
    if w.get("available"):
        why.append(tf("why_rain_heat", lang, mm=w["rain_total_mm"], c=w["hottest_c"]))
    for a in w.get("alerts", [])[:1]:
        from .weather import ADVICE, _family
        actions += [tf(ADVICE.get(_family(h), "adv_general"), lang) for h in a["hazards"][:2]]
    if wt and wt["coming_total_mm"] > 0:
        why.append(tf("ins_water", lang, mm=wt["coming_total_mm"]) + (
            " " + tf("ins_litres", lang, l=wt["coming_total_litres"]) if wt.get("coming_total_litres") else ""))
    if wt and wt.get("days"):
        actions.append(tf("act_today", lang, act=tf("act_" + wt["days"][0]["action"], lang)))
    if wt and any(d["action"] in ("skip_rain", "wait_rain") for d in wt["days"]):
        why.append(tf("ins_rain_save", lang))
    if farm.get("status") in ("some_problems", "serious_problems"):
        why.append(tf("why_status", lang, s=tf("status_" + farm["status"], lang)))
        actions.append(tf("ins_status", lang))
    if data.get("rotation"):
        r = data["rotation"]
        why.append(tf("ins_rotation", lang, best=" → ".join(crop_name(c, lang) for c in r["best"]), s=r["best_score"]))
    actions = list(dict.fromkeys(actions))[:4] or [tf("act_none", lang)]
    return dict(headline=headline, why=why[:5], meaning=tf(f"msg_{lvl}", lang), actions=actions)


INSIGHT_PROMPT = """You write the "AI insights" part of a farm report for a farmer in Oman. Language: {lang}.
Use ONLY the data below. Every number you write must appear in the data. Plain, short words for older farmers.
No pesticide or chemical doses. Weather data is a model forecast, not an official warning.
Return ONE JSON object:
{{"headline": "one sentence: the most important thing now",
  "why": ["2 to 5 short evidence bullets from the data"],
  "meaning": "one or two sentences: what this means for the farm",
  "actions": ["1 to 4 short things to do now"]}}
DATA:
{data}"""


def _pack(rep: dict, source: str, **extra) -> dict:
    rep = dict(rep)
    rep.update(insights=rep["why"], priority_action=rep["actions"][0] if rep["actions"] else "", source=source, **extra)
    return rep


def _all_text(rep: dict) -> str:
    return " ".join([rep.get("headline", ""), rep.get("meaning", ""), *rep.get("why", []), *rep.get("actions", [])])


def ai_insights(data: dict, lang: str) -> dict:
    """-> {headline, why[], meaning, actions[], insights(=why), priority_action, source: "ai"|"rules", grounding}"""
    fallback = _pack(_rule_insights(data, lang), "rules", grounding={})
    if C.USE_MOCK:
        return fallback
    blob = json.dumps(data, ensure_ascii=False, default=str)
    from .vision import LANG_NAME
    messages = [{"role": "user", "content": INSIGHT_PROMPT.format(lang=LANG_NAME.get(lang, "English"), data=blob)}]
    allowed = G.allowed_numbers([data])
    try:
        msg, provider = chat(messages, max_tokens=600)
        rep = _parse(msg.get("content"))
        bad = G.ungrounded_numbers(_all_text(rep), allowed)
        retried = False
        if bad:
            retried = True
            messages += [{"role": "assistant", "content": msg.get("content") or ""},
                         {"role": "user", "content": f"CORRECTION: these numbers are not in the data: {bad}. "
                                                     "Rewrite the same JSON using only numbers from the data."}]
            msg, provider = chat(messages, max_tokens=600)
            rep = _parse(msg.get("content"))
            bad = G.ungrounded_numbers(_all_text(rep), allowed)
            if bad:                                  # still wrong: drop bullets / sentences that carry them
                for k in ("why", "actions"):
                    rep[k] = [x for x in rep[k] if not set(G.extract_numbers(x)) & set(bad)]
                for k in ("headline", "meaning"):
                    rep[k] = G.strip_numbers(rep[k], bad) if set(G.extract_numbers(rep[k])) & set(bad) else rep[k]
        for k in ("why", "actions"):
            rep[k] = [x for x in rep[k] if x and not guards.answer_has_dose(x)][:5]
        for k in ("headline", "meaning"):
            if guards.answer_has_dose(rep[k]):
                rep[k] = ""
        if not rep["why"] or not rep["headline"]:
            return fallback
        rep["actions"] = rep["actions"] or fallback["actions"]
        rep["meaning"] = rep["meaning"] or fallback["meaning"]
        return _pack(rep, "ai", provider=provider, grounding=dict(retried=retried, removed=bad))
    except AllProvidersFailed:
        return fallback


def _parse(text):
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", text, re.S)
    out = dict(headline="", why=[], meaning="", actions=[])
    try:
        d = json.loads(m.group(0) if m else text)
    except (json.JSONDecodeError, AttributeError):
        return out
    if isinstance(d, dict):
        out["headline"] = str(d.get("headline") or d.get("priority_action") or "")
        out["meaning"] = str(d.get("meaning") or "")
        out["why"] = [str(x) for x in (d.get("why") or d.get("insights") or []) if isinstance(x, (str, int, float))]
        out["actions"] = [str(x) for x in (d.get("actions") or []) if isinstance(x, (str, int, float))]
    return out


# ------------------------------------------------------------------ markdown
def to_markdown(data: dict, ins: dict, lang: str, crop_label=lambda c: c) -> str:
    f, w = data["farm"], data["weather"]
    L = [f"# {tf('rep_title', lang)}: {f.get('name') or tf('rep_my_farm', lang)}", f"_{data['date']}_", ""]
    L += [f"## {tf('rep_farm', lang)}",
          f"- {tf('f_crops', lang)}: {', '.join(crop_label(c) for c in f.get('crops') or []) or '—'}",
          f"- {tf('f_stage', lang)}: {tf('stage_' + (f.get('stage') or 'growing'), lang)}",
          f"- {tf('f_status', lang)}: {tf('status_' + (f.get('status') or 'good'), lang)}",
          f"- {tf('f_method', lang)}: {tf('method_' + (f.get('method') or 'unknown'), lang)}"]
    if f.get("area_m2"):
        L.append(f"- {tf('f_area', lang)}: {f['area_m2']:g} m²")
    if f.get("last_irrigation"):
        L.append(f"- {tf('f_last_irr', lang)}: {f['last_irrigation']}")
    if f.get("notes"):
        L.append(f"- {tf('f_notes', lang)}: {f['notes']}")
    L += ["", f"## {tf('rep_insights', lang)} ({tf('src_' + ins['source'], lang)})", f"**{ins['headline']}**", "",
          f"**{tf('rp_why', lang)}**"] + [f"- {x}" for x in ins["why"]]
    L += ["", f"**{tf('rp_meaning', lang)}** {ins['meaning']}", "", f"**{tf('rp_actions', lang)}**"]
    L += [f"- {x}" for x in ins["actions"]]
    L += ["", f"## {tf('rep_weather', lang)}"]
    if w["available"]:
        if w.get("demo"):
            L.append(f"> ⚠️ {tf('demo_banner', lang)}")
        sep = "، " if lang in ("ar", "ur") else "; "
        L.append(f"- {tf('rep_days', lang, n=w['days'])}{sep}{tf('rep_rain_total', lang, mm=w['rain_total_mm'])}{sep}"
                 f"{tf('rep_hottest', lang, c=w['hottest_c'])}")
        for a in w["alerts"]:
            L.append(f"- {'🔴' if a['level'] >= 5 else '🟠' if a['level'] >= 3 else '🟡'} {a['date']}: "
                     f"{tf('lvl_' + str(a['level']), lang)} — {sep.join(tf('hz_' + h, lang) for h in a['hazards'])}")
        if not w["alerts"]:
            L.append(f"- {tf('no_alerts', lang)}")
        L.append(f"_{tf('official_note', lang)}_")
    else:
        L.append(f"- {tf('forecast_unavailable', lang)}")
    if data.get("watering"):
        wt = data["watering"]
        L += ["", f"## {tf('rep_watering', lang)} ({crop_label(wt['crop']) if wt['crop'] else tf('neutral_crop', lang)})",
              f"| {tf('col_date', lang)} | {tf('col_action', lang)} | mm | {tf('col_litres', lang)} |", "|---|---|---|---|"]
        for d in wt["days"]:
            L.append(f"| {d['date']} | {tf('act_' + d['action'], lang)} | {d['mm']:g} | {d['litres'] if d['litres'] is not None else '—'} |")
        L.append(f"\n{tf('rep_avg', lang, b=wt['avg_need_before_rain_mm'], a=wt['avg_need_after_rain_mm'])}")
    if data.get("rotation"):
        r = data["rotation"]
        L += ["", f"## {tf('rep_rotation', lang)}",
              f"- {tf('rep_rot_now', lang)}: {' → '.join(crop_label(c) for c in r['current'])} ({r['current_score']}/100)",
              f"- {tf('rep_rot_best', lang)}: {' → '.join(crop_label(c) for c in r['best'])} ({r['best_score']}/100)"]
        if not r.get("scores_are_local"):
            L.append(f"- _{tf('rep_rot_region', lang)}_")
    if data.get("photos"):
        L += ["", f"## {tf('rep_photos', lang)}"] + [f"- {p}" for p in data["photos"]] + [f"_{tf('photo_disclaimer', lang)}_"]
    L += ["", "---", f"_{tf('rep_footer', lang)}_"]
    return "\n".join(L)
