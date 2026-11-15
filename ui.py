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
                else:
                    _assistant(i, m, lang, last=(i == len(msgs) - 1), prof=prof)

        if msgs:
            st.button(t("clear", lang), key=K + "clear",
                      on_click=lambda: st.session_state.__setitem__(K + "msgs", []))

        typed = st.chat_input(t("ask", lang), key=K + "input")
        pending = st.session_state.pop(K + "pending", None)
        if typed:
            pending = dict(question=typed, action=None)
        if pending and pending.get("question"):
            q, action = pending["question"], pending.get("action")
            history = [{"role": x["role"], "content": x["content"] if x["role"] == "user" else x["result"]["answer"]}
                       for x in msgs[-6:]]
            msgs.append({"role": "user", "content": q})
            ctx = {k: prof.get(k) for k in ("lat", "lon", "crop")}
            ctx.update(lang=lang, profile=prof, action=action)
            if context.get("photo_note"):
                ctx["photo_note"] = context["photo_note"]
            with st.spinner(t("thinking", lang)):
                r = ask_agent(q, ctx, history)
            P.apply_updates(prof, r.get("profile_updates"))
            msgs.append({"role": "assistant", "content": r["answer"], "result": r, "question": q})
            st.rerun()
