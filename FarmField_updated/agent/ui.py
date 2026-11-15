"""render_agent_chat(context=None): the whole chat UI, safe to drop into an existing Streamlit app.

Rules kept on purpose:
  * never calls st.set_page_config
  * no global CSS: RTL styling targets only this widget's own container (.st-key-ss_agent_root)
  * every session_state and widget key starts with "ss_agent_"
"""
from __future__ import annotations

import streamlit as st

from . import config as C
from . import profile as P
from . import team_bridge
from .agent import ask_agent
from .i18n import crop_name, t
from .voice import read_aloud_button
from .voice_input import voice_question
from . import vision as V
from .i18n_farm import tf

K = "ss_agent_"          # prefix for every key
FACTORS = ("soil", "water", "climate", "income")


def _state(name, default):
    return st.session_state.setdefault(K + name, default)


def _root():
    try:
        return st.container(key=K + "root")       # Streamlit >= 1.39 adds the CSS class .st-key-ss_agent_root
    except TypeError:                              # older Streamlit: no key -> plain container, no RTL CSS
        return st.container()


def _rot(rot, lang):
    return " → ".join(crop_name(c, lang) for c in rot or [])


def _queue(question=None, action=None, label=None):
    st.session_state[K + "pending"] = dict(question=question or label or "", action=action)


# ------------------------------------------------------------------ pieces of one answer
def _risk_block(risk: dict, lang: str):
    if not risk:
        return
    st.caption(t("risk_title", lang) + " — " + t("risk_legend", lang))
    cols = st.columns(len(risk))
    for col, (f, r) in zip(cols, risk.items()):
        col.markdown(f"**{t('f_' + f, lang)}**  \n{t('risk_' + r['level'], lang)}")


def _compare_block(cmp: dict, lang: str):
    head = f"| {t('col_factor', lang)} | {t('col_now', lang)} | {t('col_best', lang)} |\n|---|---|---|\n"
    rows = "".join(
        f"| {t('f_' + r['factor'], lang)} | {r['existing_score']:g} · {t('risk_' + r['existing_risk'], lang)} "
        f"| {r['best_score']:g} · {t('risk_' + r['best_risk'], lang)} |\n" for r in cmp["rows"])
    total = f"| **{t('col_total', lang)}** | **{cmp['existing_total']:g}** | **{cmp['best_total']:g}** |\n"
    st.markdown(f"{_rot(cmp['existing_rotation'], lang)}  ⟶  {_rot(cmp['best_rotation'], lang)}")
    st.markdown(head + rows + total)
    st.caption(t("risk_legend", lang))


def _replay_story(rp: dict, lang: str) -> str:
    best = (rp.get("options") or [{}])[0]
    s = t("replay_story", lang, year=rp["driest_year"], rain=f"{rp['driest_year_rain_mm']:g}",
          avg=f"{rp['average_rain_mm']:g}",
          med=t("replay_median", lang, m=f"{rp['median_rain_mm']:g}") if rp.get("median_rain_mm") else "",
          ex=_rot(rp["existing"]["rotation"], lang),
          ex_n=f"{rp['existing']['normal_total']:g}", ex_d=f"{rp['existing']['driest_total']:g}",
          best=_rot(best.get("rotation"), lang), b_n=f"{best.get('normal_total', 0):g}",
          b_d=f"{best.get('driest_total', 0):g}")
    if rp.get("ranking_changes_in_driest_year"):
        s += " " + t("replay_flip", lang, best=_rot(rp["best_in_driest_year"], lang))
    return s


def _profile_block(i: int, m: dict, lang: str, prof: dict):
    keys = m["result"].get("ask_profile") or []
    if not keys or m.get("profile_done"):
        return
    P.mark_asked(prof, keys)                      # shown once -> never asked again in later answers
    with st.container(border=True):
        st.markdown("**" + t("prio_title", lang) + "**")
        choices = list(C.PRIORITY_CHOICES)        # not_important / normal / very_important
        for k in keys:
            if k in C.PRIORITY_KEYS:
                st.radio(t("p_" + k, lang), choices, index=1, horizontal=True, key=f"{K}prio_{k}_{i}",
                         format_func=lambda c: t("c_" + c, lang))
            elif k == "irrigation_mm":
                st.number_input(t("irr_q", lang), min_value=0, max_value=C.IRRIGATION_MAX_MM,
                                value=int(C.DEFAULT_IRRIGATION_MM), step=50, key=f"{K}irr_{i}",
                                help=t("irr_hint", lang, d=C.DEFAULT_IRRIGATION_MM))
                st.caption(t("irr_hint", lang, d=C.DEFAULT_IRRIGATION_MM))

        def apply():
            for k in keys:
                if k in C.PRIORITY_KEYS:
                    prof[k] = C.PRIORITY_CHOICES[st.session_state[f"{K}prio_{k}_{i}"]]
                elif k == "irrigation_mm":
                    prof[k] = float(st.session_state[f"{K}irr_{i}"])
            m["profile_done"] = True
            _queue(question=m.get("question"))

        def skip():
            m["profile_done"] = True

        c1, c2 = st.columns(2)
        c1.button(t("apply", lang), key=f"{K}apply_{i}", on_click=apply, type="primary")
        c2.button(t("skip", lang), key=f"{K}skip_{i}", on_click=skip)


def _assistant(i: int, m: dict, lang: str, last: bool, prof: dict):
    r = m["result"]
    st.markdown(r["answer"])
    read_aloud_button(r["answer"], lang)
    for n in r.get("notices") or []:
        st.caption("ℹ️ " + n)
    _risk_block(r.get("risk"), lang)
    if r.get("compare"):
        with st.expander(t("compare", lang), expanded=False):
            _compare_block(r["compare"], lang)
    if r.get("replay"):
        open_key = f"{K}replay_open_{i}"
        st.button(t("replay", lang), key=f"{K}replay_{i}",
                  on_click=lambda: st.session_state.__setitem__(open_key, True))
        if st.session_state.get(open_key):
            st.info(_replay_story(r["replay"], lang))
    if r.get("voice_text") and C.ENABLE_VOICE_TOOL:              # voice is optional and OFF by default
        with st.expander("🔊 " + t("voice_text", lang), expanded=False):
            st.write(r["voice_text"])
    if r.get("why"):
        with st.expander(t("why", lang), expanded=False):        # hidden "read more"
            st.markdown(r["why"])
    if last:
        _profile_block(i, m, lang, prof)
        acts = r.get("actions") or []
        for j, label in enumerate(r.get("suggestions") or []):
            act = acts[j] if j < len(acts) else None
            st.button(label, key=f"{K}sugg_{i}_{j}", on_click=_queue,
                      kwargs=dict(question=label, action=act))


# ------------------------------------------------------------------ photo analysis
def _photo_report(rep: dict, lang: str):
    if rep.get("error"):
        key = {"no_vision": "photo_no_vision", "too_big": "photo_too_big"}.get(rep["error"], "photo_failed")
        st.warning(tf(key, lang, mb=C.PHOTO_MAX_MB) if key == "photo_too_big" else tf(key, lang))
        return
    st.markdown("**" + tf("photo_report", lang) + "**")
    if not rep.get("is_plant"):
        st.info(tf("ph_not_plant", lang))
        return
    st.markdown(f"🌿 **{tf('ph_plant', lang)}:** {rep.get('plant_guess', '')}")
    sections = [("ph_obs", rep.get("observations")), ("ph_checks", rep.get("checks")),
                ("ph_safe", rep.get("safe_actions")), ("ph_expert", rep.get("see_expert_if"))]
    if rep.get("observations"):
        st.markdown(f"**{tf('ph_obs', lang)}**\n" + "\n".join(f"- {x}" for x in rep["observations"]))
    if rep.get("possible_problems"):
        colour = {"low": "🟢", "medium": "🟠", "high": "🔴"}
        st.markdown(f"**{tf('ph_problems', lang)}**\n" + "\n".join(
            f"- {colour[p['likelihood']]} **{p['name']}** ({tf('lk_' + p['likelihood'], lang)}) — {p['signs']}"
            for p in rep["possible_problems"]))
    for key, items in sections[1:]:
        if items:
            st.markdown(f"**{tf(key, lang)}**\n" + "\n".join(f"- {x}" for x in items))
    st.caption(f"{tf('ph_quality', lang)}: {tf('q_' + rep.get('image_quality', 'fair'), lang)} · "
               f"{t('confidence', lang)}: {t(rep.get('confidence', 'low'), lang)} · {rep.get('provider', '')}")
    st.warning("⚠️ " + tf("photo_disclaimer", lang))


def _photo_input(lang: str, prof: dict, msgs: list):
    """Camera or gallery -> vision model -> photo report in the chat. Widgets reset after each photo."""
    n = st.session_state.setdefault(K + "photo_n", 0)
    with st.expander(tf("photo_add", lang), expanded=False):
        tab_cam, tab_up = st.tabs([tf("photo_camera", lang), tf("photo_gallery", lang)])
        with tab_cam:
            cam = st.camera_input(tf("photo_take", lang), key=f"{K}cam_{n}")
        with tab_up:
            up = st.file_uploader(tf("photo_pick", lang), type=["jpg", "jpeg", "png", "webp", "heic"],
                                  key=f"{K}upl_{n}")
        note = st.text_input(tf("photo_note", lang), key=f"{K}photo_note_{n}")
        pic = cam or up
        if st.button(tf("photo_analyze", lang), key=f"{K}photo_go_{n}", disabled=pic is None, type="primary"):
            raw = pic.getvalue()
            with st.spinner(t("thinking", lang)):
                rep = V.analyze_plant_photo(raw, lang, crop=prof.get("crop"), note=note)
            try:
                import base64
                thumb = base64.b64decode(V.prepare_image(raw, 360)[0].split(",", 1)[1])
            except Exception:
                thumb = None
            msgs.append({"role": "user", "content": tf("photo_user_msg", lang) + (f": {note}" if note else ""),
                         "image": thumb})
            msgs.append({"role": "assistant", "kind": "photo", "content": V.short_summary(rep), "photo": rep})
            if V.short_summary(rep):
                prof.setdefault("photo_notes", []).append(V.short_summary(rep))
            st.session_state[K + "photo_n"] = n + 1
            st.rerun()


# ------------------------------------------------------------------ entry point
def render_agent_chat(context: dict | None = None):
    context = dict(context or {})
    msgs = _state("msgs", [])
    prof = _state("profile", P.new_profile(context))
    P.merge_context(prof, context)                # host app values win, never asked again

    root = _root()
    with root:
        # ---- language: from the host app, or chosen on the first screen
        if context.get("lang") in C.LANG_NAMES:
            lang = context["lang"]
        else:
            cur = _state("lang", C.DEFAULT_LANG)
            idx = C.ENABLED_LANGS.index(cur) if cur in C.ENABLED_LANGS else 0
            lang = st.radio(t("choose_language", cur), C.ENABLED_LANGS, index=idx, horizontal=True,
                            key=K + "lang_choice", format_func=lambda c: C.LANG_NAMES[c])
            st.session_state[K + "lang"] = lang
        prof["lang"] = lang
        if lang in C.RTL_LANGS:     # scoped to this container only
            st.markdown(f"<style>.st-key-{K}root{{direction:rtl;text-align:right}}</style>", unsafe_allow_html=True)

        st.subheader("🌱 " + t("title", lang))
        team_bridge.load()
        if team_bridge.IS_FAKE:
            st.warning(t("fake_warning", lang) + f"  \n`{team_bridge.IMPORT_ERROR}`")
        if C.USE_MOCK:
            st.caption("🧪 " + t("mock_badge", lang))

        for i, m in enumerate(msgs):
            with st.chat_message(m["role"]):
                if m["role"] == "user":
                    st.markdown(m["content"])
                    if m.get("image"):
                        st.image(m["image"], width=220)
                elif m.get("kind") == "photo":
                    _photo_report(m["photo"], lang)
                else:
                    _assistant(i, m, lang, last=(i == len(msgs) - 1), prof=prof)

        if msgs:
            st.button(t("clear", lang), key=K + "clear",
                      on_click=lambda: st.session_state.__setitem__(K + "msgs", []))

        _photo_input(lang, prof, msgs)
        spoken = voice_question(lang, K)
        typed = st.chat_input(t("ask", lang), key=K + "input")
        pending = st.session_state.pop(K + "pending", None)
        if spoken:
            pending = dict(question=spoken, action=None)
        if typed:
            pending = dict(question=typed, action=None)
        if pending and pending.get("question"):
            q, action = pending["question"], pending.get("action")
            history = [{"role": x["role"], "content": x["content"] if x["role"] == "user" or "result" not in x
                        else x["result"]["answer"]} for x in msgs[-6:] if x.get("content")]
            msgs.append({"role": "user", "content": q})
            ctx = {k: prof.get(k) for k in ("lat", "lon", "crop")}
            ctx.update(lang=lang, profile=prof, action=action)
            if context.get("photo_note"):
                ctx["photo_note"] = context["photo_note"]
            elif any(x.get("kind") == "photo" for x in msgs[-4:]):
                ctx["photo_note"] = (prof.get("photo_notes") or [""])[-1]
            with st.spinner(t("thinking", lang)):
                r = ask_agent(q, ctx, history)
            P.apply_updates(prof, r.get("profile_updates"))
            msgs.append({"role": "assistant", "content": r["answer"], "result": r, "question": q})
            st.rerun()
