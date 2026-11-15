"""The agent loop: question -> LLM picks tools -> tools return real numbers -> checked JSON answer.

ask_agent(question, context, history) is plain Python (no Streamlit). It never raises for LLM outages.
Returned dict (the UI renders it):
  answer       max 3 short sentences (+ code-added coverage line when needed)
  why          reasoning, numbers, caveats, sources, confidence (shown in a collapsed "read more")
  confidence   "high" | "medium" | "low"
  suggestions  2-3 follow-up button labels
  sources      list of strings
  extras: actions (what-if buttons, parallel to suggestions), notices, compare, replay, risk, whatif,
          ask_profile, profile_updates, meta
"""
from __future__ import annotations

import hashlib
import json
import re

from . import config as C
from . import grounding as G
from . import guards
from . import mock
from . import profile as P
from . import rotation_tools as RT
from . import team_bridge
from .i18n import caveat_text, crop_name, crops_text, t
from .llm import AllProvidersFailed, chat
from .tools_schema import LOCATION_TOOLS, ROTATION_TOOLS, build_tools, validate_args

DEFAULT_CTX = dict(lat=None, lon=None, crop=None, lang=C.DEFAULT_LANG)
CONF_ORDER = ["low", "medium", "high"]


# ------------------------------------------------------------------ prompt + cache
def _system_prompt(ctx: dict, profile: dict) -> str:
    gloss = "\n".join(f"- {g['local']} = {g['standard']}"
                      for g in json.loads(C.GLOSSARY_PATH.read_text(encoding="utf-8")))
    site = RT.rotation_site()
    return (C.PROMPT_DIR / "system.txt").read_text(encoding="utf-8").format(
        lang_name=C.LANG_NAMES.get(ctx["lang"], "English"), lat=ctx["lat"], lon=ctx["lon"],
        crop=ctx["crop"] or "not specified", profile=P.summary(profile), glossary=gloss,
        rotation_site=f"{site['label']}, {site['lat']}N {site['lon']}E")


def prompt_version() -> str:
    """Changes whenever the prompt, glossary or tool schemas change -> old cached answers stop being used."""
    schema, _f, _s = build_tools()
    blob = (C.PROMPT_DIR / "system.txt").read_text(encoding="utf-8") \
        + C.GLOSSARY_PATH.read_text(encoding="utf-8") + json.dumps(schema, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:10]


def _cache_path(question: str, ctx: dict, profile: dict, action):
    prof = {k: profile.get(k) for k in ("existing_rotation", "irrigation_mm", *C.PRIORITY_KEYS)}
    key = json.dumps([prompt_version(), question.strip().lower(), ctx["lat"], ctx["lon"], ctx["crop"],
                      ctx["lang"], prof, action, team_bridge.IS_FAKE], sort_keys=True, default=str)
    return C.CACHE_DIR / ("ans_" + hashlib.sha1(key.encode()).hexdigest() + ".json")


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    for candidate in (text, (re.search(r"\{.*\}", text, re.S) or [None])[0]):
        if candidate:
            try:
                d = json.loads(candidate)
                if isinstance(d, dict):
                    return d
            except json.JSONDecodeError:
                pass
    return {"answer": text, "why": "", "confidence": "low", "suggestions": []}


# ------------------------------------------------------------------ tools
def _prepare_args(name: str, args: dict, ctx: dict) -> dict:
    args = {k: v for k, v in (args or {}).items() if v is not None}
    if name in LOCATION_TOOLS:
        lat = ctx["lat"] if ctx["lat"] is not None else RT.rotation_site()["lat"]
        lon = ctx["lon"] if ctx["lon"] is not None else RT.rotation_site()["lon"]
        args = {"lat": lat, "lon": lon, **args}
        if name == "get_water_guidance" and not args.get("crop") and ctx["crop"]:
            args["crop"] = ctx["crop"]
    if "existing_rotation" in args:                    # farmer words -> valid names (unknown words kept)
        rot = args["existing_rotation"]
        rot = [rot] if isinstance(rot, str) else list(rot)
        valid = RT.supported_crops()
        from .crops import resolve_crop
        args["existing_rotation"] = [resolve_crop(w, valid) or w for w in rot]
    for k in C.PRIORITY_KEYS:                          # snap to the three choices
        if isinstance(args.get(k), (int, float)) and not isinstance(args.get(k), bool):
            args[k] = min(C.PRIORITY_CHOICES.values(), key=lambda c: abs(c - float(args[k])))
    if isinstance(args.get("irrigation_mm"), int):
        args["irrigation_mm"] = float(args["irrigation_mm"])
    return args


def run_tool(name: str, args: dict, ctx: dict, profile: dict, funcs: dict, schema: list) -> dict:
    func = funcs.get(name)
    if func is None:
        return {"error": f"unknown tool {name}"}
    args = _prepare_args(name, args, ctx)
    if name in ROTATION_TOOLS and "existing_rotation" not in args and profile.get("existing_rotation"):
        args["existing_rotation"] = profile["existing_rotation"]
    probs = validate_args(schema, name, {k: v for k, v in args.items() if k not in ("lat", "lon")}
                          if name not in LOCATION_TOOLS else args)
    unsupported = [p for p in probs if p.startswith("existing_rotation: not supported")]
    if unsupported:           # let the wrapper produce the friendly unsupported-crop result
        probs = [p for p in probs if p not in unsupported]
    if probs:
        return {"error": "invalid_arguments", "problems": probs}
    try:
        if name in ROTATION_TOOLS:
            return func(**args, _profile=profile, _ctx=ctx)
        return func(**args)
    except Exception as e:      # let the model explain the problem instead of crashing the app
        return {"error": f"{type(e).__name__}: {e}"}


# ------------------------------------------------------------------ post-processing (hard rules)
def _lower(conf: str, cap: str) -> str:
    return CONF_ORDER[min(CONF_ORDER.index(conf), CONF_ORDER.index(cap))]


def _sentences(text: str, n: int = 3) -> str:
    parts = [p for p in re.split(r"(?<=[.!?؟।])\s+", (text or "").strip()) if p]
    return " ".join(parts[:n])


def _whatif_actions(lang: str, rotation: list[str] | None) -> tuple[list[str], list[dict]]:
    if rotation:
        acts = [dict(label=t("wi_less_rain", lang), tool="rotation_what_if",
                     args={"existing_rotation": rotation, "rain_change_pct": -30}),
                dict(label=t("wi_less_water", lang), tool="rotation_what_if",
                     args={"existing_rotation": rotation, "irrigation_change_pct": -50}),
                dict(label=t("wi_hotter", lang), tool="rotation_what_if",
                     args={"existing_rotation": rotation, "temp_delta_c": 2})]
    else:
        acts = [dict(label=t("wi_hotter", lang), tool="simulate_what_if", args={"temp_delta_c": 2}),
                dict(label=t("wi_less_rain", lang), tool="simulate_what_if", args={"rain_change_pct": -30})]
    return [a["label"] for a in acts], acts


def finalize(raw: dict, log: list[dict], ctx: dict, profile: dict, question: str, provider: str,
             sources_map: dict, grounding_meta: dict | None = None) -> dict:
    lang = ctx["lang"]
    conf = raw.get("confidence") if raw.get("confidence") in CONF_ORDER else "medium"
    answer = _sentences(str(raw.get("answer", "")))
    why = str(raw.get("why", "") or "")
    notices, extras = [], {}
    names = [e["name"] for e in log]

    # ---- distance cap for the per-location tools (from the original project)
    far = max([e["result"].get("site", {}).get("distance_km", 0) for e in log
               if isinstance(e["result"].get("site"), dict)], default=0)
    conf = _lower(conf, "low" if far > C.DIST_LOW_KM else "medium" if far > C.DIST_MEDIUM_KM else "high")

    # ---- rotation tool rules
    rot = next((e for e in log if e["name"] in ("recommend", "rotation_what_if") and "error" not in e["result"]), None)
    rot_err = next((e for e in log if e["name"] in ROTATION_TOOLS and e["result"].get("error") == "unsupported_crop"),
                   None)
    if rot_err:
        r = rot_err["result"]
        answer = t("unsupported", lang, bad=", ".join(r["unsupported"]), ok=crops_text(r["supported_crops"], lang))
        conf = "high"
    if rot:
        res = rot["result"]
        conf = _lower(conf, "medium")                    # placeholder scoring rules -> never "high"
        loc = res.get("location") or {}
        s_info = loc.get("rotation_site") or RT.rotation_site()
        site = (s_info.get("labels") or {}).get(lang) or s_info["label"]
        if not loc.get("scores_are_local"):
            line = (t("region_far", lang, site=site, d=loc["distance_km"]) if loc.get("farm_known")
                    else t("region_unknown", lang, site=site))
            answer = (answer + " " + line).strip()
            if loc.get("farm_known"):
                conf = "low"
        if res.get("defaults_used"):
            inp = res.get("inputs_used", {})
            items = [t("d_" + k, lang, v=f"{inp.get(k, 0):g}") if k == "irrigation_mm" else t("d_" + k, lang)
                     for k in res["defaults_used"]]
            notices.append(t("defaults_used", lang, items=("، " if lang == "ar" else ", ").join(items)))
        notices.append(t("caveat_line", lang))
        q = res.get("data_quality") or RT.data_quality()
        cav_lines = [caveat_text(c, lang, q) for c in res.get("caveats", [])]
        why = (why + "\n\n**" + t("caveats", lang) + ":**\n" + "\n".join("- " + c for c in cav_lines)).strip()
        if rot["name"] == "recommend":
            extras["compare"] = res.get("compare")
            extras["replay"] = res.get("replay")
            best = (res.get("alternatives") or [{}])[0]
            extras["risk"] = {f: RT.explain_risk(lvl) for f, lvl in (best.get("risk_meters") or {}).items()}
            extras["profile_updates"] = {"existing_rotation": res["inputs_used"]["existing_rotation"],
                                         **{k: res["inputs_used"][k] for k in ("irrigation_mm", *C.PRIORITY_KEYS)
                                            if k not in res.get("defaults_used", [])}}
            extras["ask_profile"] = [k for k in P.open_questions(profile) if k in res.get("defaults_used", [])]
        else:
            extras["whatif"] = {k: res.get(k) for k in ("scenario", "before", "after", "temperature_note",
                                                         "best_rotation_changes")}
            hw = res.get("heat_and_water") or {}
            if hw.get("before") and hw.get("after"):
                notices.append(t("wi_temp_note", lang, h0=hw["before"]["heat_days"], h1=hw["after"]["heat_days"]))
        if res.get("fake_stub"):
            conf = "low"
    voice = next((e["result"] for e in log if e["name"] == "summary_for_voice" and "voice_text" in e["result"]), None)
    if voice:
        extras["voice_text"] = voice["voice_text"]
    if ctx.get("photo_note"):
        notices.append(t("photo_hint", lang))

    # ---- chemical doses never leave this function
    if guards.answer_has_dose(answer) or guards.answer_has_dose(why):
        answer, why, conf = t("refuse_chemical", lang), "", "high"
        extras = {}

    # ---- suggestions (+ what-if buttons that call the what-if tool)
    llm_sugg = [s for s in (raw.get("suggestions") or []) if isinstance(s, str)]
    rotation = (rot["result"].get("inputs_used") or {}).get("existing_rotation") if rot else None
    if rot or any(n in LOCATION_TOOLS for n in names):
        labels, actions = _whatif_actions(lang, rotation)
        if not rot:      # climate answers: keep one LLM follow-up + what-if buttons
            labels, actions = (llm_sugg[:1] + labels)[:3], ([None] * len(llm_sugg[:1]) + actions)[:3]
    else:
        labels, actions = llm_sugg[:3], [None] * len(llm_sugg[:3])

    sources = list(dict.fromkeys(sources_map[n] for n in names if n in sources_map))
    if why or sources:
        why = (why + "\n\n" + t("sources", lang) + ": " + " · ".join(sources)
               + "\n" + t("confidence", lang) + ": " + t(conf, lang)).strip()
    return dict(answer=answer, why=why, confidence=conf, suggestions=labels, sources=sources,
                actions=actions, notices=notices, **extras,
                meta=dict(provider=provider, tools_used=names, cached=False, fake_stub=team_bridge.IS_FAKE,
                          grounding=grounding_meta or {}))


def _grounding(raw: dict, log: list[dict], question: str) -> tuple[list[float], set]:
    allowed = G.allowed_numbers([e["result"] for e in log] + [e["args"] for e in log], [question])
    bad = G.ungrounded_numbers(str(raw.get("answer", "")) + " " + str(raw.get("why", "")), allowed)
    return bad, allowed


def _refusal(code: str, lang: str) -> dict:
    return dict(answer=t(code, lang), why="", confidence="high", suggestions=[], sources=[], actions=[], notices=[],
                meta=dict(provider="rules", tools_used=[], cached=False, fake_stub=team_bridge.IS_FAKE, grounding={}))


# ------------------------------------------------------------------ entry point
def ask_agent(question: str, context: dict | None = None, history: list | None = None, use_cache: bool = True) -> dict:
    """context (all optional): lat, lon, crop, lang, profile (farm profile dict), action ({tool, args}),
    photo_note.  history: [{"role": "user"|"assistant", "content": str}, ...].  Never raises for LLM outages."""
    context = dict(context or {})
    profile = P.merge_context(dict(context.pop("profile", None) or {}), context)
    action = context.pop("action", None)
    ctx = {**DEFAULT_CTX, **{k: v for k, v in context.items() if v is not None}}
    if ctx["lang"] not in C.LANG_NAMES:
        ctx["lang"] = C.DEFAULT_LANG
    lang = ctx["lang"]
    schema, funcs, sources_map = build_tools()

    if guards.asks_chemical_dose(question):                       # hard rule, no LLM needed
        return _refusal("refuse_chemical", lang)

    log: list[dict] = []

    def call(name, args):
        res = run_tool(name, args, ctx, profile, funcs, schema)
        log.append(dict(name=name, args=_prepare_args(name, args, ctx), result=res))
        return res

    # ---- Mock mode: real tools, template text, no LLM
    if C.USE_MOCK:
        if action:
            call(action["tool"], action.get("args") or {})
        else:
            kind, what = mock.plan(question, ctx, profile, RT.supported_crops())
            if kind == "refuse":
                return _refusal(what, lang)
            if kind == "ask":
                r = _refusal(what, lang)
                r["answer"] += " " + t("supported_list", lang, ok=crops_text(RT.supported_crops(), lang))
                return r | {"confidence": "medium"}
            for name, args in what:
                call(name, args)
        raw = mock.write(lang, log)
        bad, _ = _grounding(raw, log, question)
        out = finalize(raw, log, ctx, profile, question, "mock", sources_map,
                       dict(checked=True, ungrounded=bad, retried=False))
        return out

    cache_file = _cache_path(question, ctx, profile, action)
    cacheable = use_cache and not history
    if cacheable and cache_file.exists():
        hit = json.loads(cache_file.read_text(encoding="utf-8"))
        hit["meta"]["cached"] = True
        return hit

    messages = [{"role": "system", "content": _system_prompt(ctx, profile)}, *(history or []),
                {"role": "user", "content": question}]
    provider = "none"
    try:
        if action:                    # button click: run the what-if tool first, then let the model explain
            cid = "action_1"
            res = call(action["tool"], action.get("args") or {})
            messages.append({"role": "assistant", "content": None, "tool_calls": [{"id": cid, "type": "function",
                             "function": {"name": action["tool"], "arguments": json.dumps(action.get("args") or {})}}]})
            messages.append({"role": "tool", "tool_call_id": cid, "content": json.dumps(res, ensure_ascii=False,
                                                                                        default=str)})
        for _ in range(C.MAX_TOOL_ROUNDS):
            msg, provider = chat(messages, schema)
            calls = msg.get("tool_calls")
            if not calls:
                break
            messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                res = call(name, args if isinstance(args, dict) else {})
                messages.append({"role": "tool", "tool_call_id": c.get("id", name),
                                 "content": json.dumps(res, ensure_ascii=False, default=str)})
        else:                        # too many tool rounds: force a final answer without tools
            msg, provider = chat(messages, None)

        raw = _parse_json(msg.get("content"))
        if guards.answer_has_dose(str(raw.get("answer", "")) + " " + str(raw.get("why", ""))):
            raw = {"answer": t("refuse_chemical", lang), "why": "", "confidence": "high", "suggestions": []}
        bad, allowed = _grounding(raw, log, question)
        gmeta = dict(checked=True, ungrounded=bad, retried=False, removed=[])
        if bad:                      # number grounding: retry ONCE with a correction message
            gmeta["retried"] = True
            messages += [{"role": "assistant", "content": msg.get("content") or ""},
                         {"role": "user", "content": "CORRECTION: these numbers are not in any tool result: "
                          f"{bad}. Rewrite the same JSON using only numbers from the tool results."}]
            msg, provider = chat(messages, None)
            raw2 = _parse_json(msg.get("content"))
            bad2 = G.ungrounded_numbers(str(raw2.get("answer", "")) + " " + str(raw2.get("why", "")), allowed)
            raw = raw2
            if bad2:                 # still wrong: remove those numbers and lower confidence
                raw["answer"] = G.strip_numbers(str(raw.get("answer", "")), bad2)
                raw["why"] = G.strip_numbers(str(raw.get("why", "")), bad2) + "\n\n" + t("removed_numbers", ctx["lang"])
                raw["confidence"] = _lower(raw.get("confidence") if raw.get("confidence") in CONF_ORDER
                                           else "medium", "low")
                gmeta["removed"] = bad2
            gmeta["ungrounded_after_retry"] = bad2
    except AllProvidersFailed:
        return dict(answer=t("busy", lang), why="", confidence="low", suggestions=[], sources=[], actions=[],
                    notices=[], meta=dict(provider="none", tools_used=[], cached=False, error=True,
                                          fake_stub=team_bridge.IS_FAKE, grounding={}))

    result = finalize(raw, log, ctx, profile, question, provider, sources_map, gmeta)
    if cacheable and result["answer"]:
        C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")
    return result


__all__ = ["ask_agent", "prompt_version", "finalize", "run_tool", "crop_name"]
