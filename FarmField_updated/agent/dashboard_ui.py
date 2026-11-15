"""Streamlit panels for: coming weather with a red->green danger scale, alerts by level, the watering
schedule chart (before / after rain + average), and the farm report with AI insights.

Same integration rules as the chat: no st.set_page_config, no global CSS (inline styles + one scoped RTL
rule), every key starts with "ss_agent_". Entry points:
    render_farm_dashboard(context=None)   # all three tabs
    render_weather_panel(context=None) / render_irrigation_panel(context=None) / render_farm_report(context=None)
"""
from __future__ import annotations

import datetime as dt
import html

import streamlit as st

from . import config as C
from . import farm_report as FR
from . import irrigation as IR
from . import profile as P
from . import rotation_tools as RT
from . import weather as W
from .i18n import crop_name, t
from .i18n_farm import month_names, tf

K = "ss_agent_"
ICON = {"sunny": "☀️", "mostly_sunny": "🌤️", "partly_cloudy": "⛅", "cloudy": "☁️", "fog": "🌫️", "drizzle": "🌦️",
        "light_rain": "🌦️", "rain": "🌧️", "showers": "🌧️", "heavy_rain": "🌧️", "thunderstorm": "⛈️",
        "thunderstorm_hail": "⛈️", "snow": "🌨️", "unknown": "❔", "wind": "💨", "heat": "🌡️", "dust": "🏜️"}


def _icon(key: str) -> str:
    if key == "wind_5":
        return "🌀"
    return ICON.get(key) or ICON.get(key.rsplit("_", 1)[0], "❔")


def _esc(x) -> str:
    return html.escape(str(x))


def _profile(context):
    prof = st.session_state.setdefault(K + "profile", P.new_profile(context))
    P.merge_context(prof, context or {})
    return prof


def _farm(prof):
    return st.session_state.setdefault(K + "farm", FR.new_farm_info(prof))


def _lang(context) -> str:
    if (context or {}).get("lang") in C.LANG_NAMES:
        return context["lang"]
    return st.session_state.get(K + "lang", C.DEFAULT_LANG)


def _location(context, prof, farm):
    for src in (context or {}, farm, prof):
        if src.get("lat") is not None and src.get("lon") is not None:
            return float(src["lat"]), float(src["lon"])
    s = RT.rotation_site()
    return s["lat"], s["lon"]


def _root(name):
    try:
        return st.container(key=K + name)
    except TypeError:
        return st.container()


def _rtl(name, lang):
    if lang in C.RTL_LANGS:
        st.markdown(f"<style>.st-key-{K}{name}{{direction:rtl;text-align:right}}</style>", unsafe_allow_html=True)


def _chip(level: int, lang: str) -> str:
    c = W.LEVELS[level]["colour"]
    fg = "#1B1B1B" if level == 2 else "#FFFFFF"
    return (f"<span style='background:{c};color:{fg};border-radius:999px;padding:2px 10px;font-weight:700;"
            f"font-size:0.85rem;display:inline-block;line-height:1.3'>{_esc(tf('lvl_' + str(level), lang))}</span>")


def _day_name(d, lang):
    return tf("hz_" + d["top"], lang)


def _fmt_date(date: str, lang: str) -> str:
    d = dt.date.fromisoformat(date)
    if d == dt.date.today():
        return tf("today", lang)
    return f"{d.day} {month_names(lang)[d.month - 1]}"


@st.cache_data(ttl=C.FORECAST_TTL_S, show_spinner=False)
def _overview(lat, lon, demo):
    return W.weather_overview(lat, lon)


# ------------------------------------------------------------------ danger scale
def danger_scale_html(lang: str) -> str:
    cells = "".join(
        f"<div style='flex:1;background:{W.LEVELS[l]['colour']};color:{'#1B1B1B' if l == 2 else '#FFF'};"
        f"padding:6px 4px;text-align:center;font-size:0.78rem;font-weight:700'>{_esc(tf('lvl_' + str(l), lang))}</div>"
        for l in (5, 4, 3, 2, 1, 0))
    return (f"<div style='font-size:0.85rem;margin:2px 0 4px 0'>{_esc(tf('scale_title', lang))}</div>"
            f"<div style='display:flex;border-radius:10px;overflow:hidden'>{cells}</div>")


def _day_card(d, lang) -> str:
    c = d["colour"]
    lines = [f"🌡️ {d['tmax_c']:.0f}° / {d['tmin_c']:.0f}°" if d["tmax_c"] is not None else ""]
    if d["rain_mm"]:
        lines.append(f"🌧️ {d['rain_mm']:g} mm")
    if d["gust_kmh"] is not None:
        lines.append(f"💨 {d['gust_kmh']:.0f} km/h")
    if d.get("dust_ugm3") is not None:
        lines.append(f"🏜️ {d['dust_ugm3']:.0f} µg/m³")
    body = "<br>".join(f"<bdi dir='ltr'>{_esc(x)}</bdi>" for x in lines if x)      # keep "36° / 24°" order in RTL
    return (f"<div style='border:2px solid {c};border-top:8px solid {c};border-radius:12px;padding:8px;"
            f"min-height:170px;background:{c}14'>"
            f"<div style='font-weight:700'>{_esc(_fmt_date(d['date'], lang))}</div>"
            f"<div style='font-size:1.8rem;line-height:2.2rem'>{_icon(d['top'])}</div>"
            f"<div style='font-weight:700'>{_esc(_day_name(d, lang))}</div>"
            f"<div style='margin:4px 0'>{_chip(d['level'], lang)}</div>"
            f"<div style='font-size:0.82rem'>{body}</div></div>")


def _alert_box(a, lang) -> str:
    c = a["colour"]
    names = "، ".join if lang == "ar" else ", ".join
    hz = names(f"{_icon(h['key'])} {tf('hz_' + h['key'], lang)}" for h in a["hazards"] if h["level"] >= 2)
    adv = "".join(f"<li>{_esc(tf(k, lang))}</li>" for k in a["advice"])
    return (f"<div style='border-inline-start:8px solid {c};background:{c}1F;border-radius:10px;padding:10px 14px;"
            f"margin:6px 0'><div style='font-weight:700'>{_chip(a['level'], lang)} &nbsp; "
            f"{_esc(_fmt_date(a['date'], lang))} — {_esc(hz)}</div><ul style='margin:6px 0 0 0'>{adv}</ul></div>")


# ------------------------------------------------------------------ panels
def render_weather_panel(context=None, _inside=False):
    lang, prof = _lang(context), _profile(context)
    lat, lon = _location(context, prof, _farm(prof))
    box = _root("weather_root") if not _inside else st.container()
    with box:
        if not _inside:
            _rtl("weather_root", lang)
        st.subheader(tf("weather_title", lang))
        ov = _overview(lat, lon, C.WEATHER_DEMO)
        if not ov.get("available"):
            st.warning(tf("forecast_unavailable", lang))
            st.caption(str(ov.get("error", ""))[:200])
            return ov
        if ov.get("demo"):
            st.error("⚠️ " + tf("demo_banner", lang))
        st.markdown(danger_scale_html(lang), unsafe_allow_html=True)
        st.caption(tf("location_caption", lang, lat=f"{lat:.3f}", lon=f"{lon:.3f}"))
        coming = [d for d in ov["days"] if d["when"] != "past"]
        for start in range(0, len(coming), 4):
            cols = st.columns(4)
            for col, d in zip(cols, coming[start:start + 4]):
                col.markdown(_day_card(d, lang), unsafe_allow_html=True)
        st.markdown("#### " + tf("alerts_title", lang))
        if ov["alerts"]:
            for a in ov["alerts"]:
                st.markdown(_alert_box(a, lang), unsafe_allow_html=True)
        else:
            st.success(tf("no_alerts", lang))
        st.caption("⚠️ " + tf("official_note", lang))
        past = [d for d in ov["days"] if d["when"] == "past"]
        if past:
            with st.expander(tf("past_days", lang)):
                cols = st.columns(min(len(past), 7))
                for col, d in zip(cols, past[-7:]):
                    col.markdown(_day_card(d, lang), unsafe_allow_html=True)
        st.caption(tf("sources_weather", lang))
    return ov


def _vl(spec):
    try:
        st.vega_lite_chart(spec=spec, use_container_width=True)
    except TypeError:
        st.vega_lite_chart(spec=spec)


def render_irrigation_panel(context=None, _inside=False):
    lang, prof = _lang(context), _profile(context)
    farm = _farm(prof)
    lat, lon = _location(context, prof, farm)
    box = _root("water_root") if not _inside else st.container()
    with box:
        if not _inside:
            _rtl("water_root", lang)
        st.subheader(tf("water_title", lang))
        crops = RT.supported_crops()
        default = farm.get("crop_now") or prof.get("crop") or (farm.get("crops") or [None])[0]
        opts = ["__none__"] + crops
        c1, c2 = st.columns(2)
        crop = c1.selectbox(tf("crop_select", lang), opts, index=opts.index(default) if default in opts else 0,
                            key=K + "irr_crop", format_func=lambda c: tf("neutral_crop", lang) if c == "__none__"
                            else crop_name(c, lang))
        area = c2.number_input(tf("area", lang), min_value=0, max_value=1_000_000,
                               value=int(farm.get("area_m2") or 0), step=100, key=K + "irr_area")
        crop = None if crop == "__none__" else crop
        eff = FR.METHOD_EFFICIENCY.get(farm.get("method") or "unknown", 1.0)
        ov = _overview(lat, lon, C.WEATHER_DEMO)
        if ov.get("available"):
            if ov.get("demo"):
                st.error("⚠️ " + tf("demo_banner", lang))
            sch = IR.daily_schedule(ov["days"], crop, crops, area_m2=area or None, method_efficiency=eff)
            st.session_state[K + "last_schedule"] = sch
            m1, m2, m3 = st.columns(3)
            tot = f"{sch['coming_total_irrigation_mm']:g} mm"
            if sch["coming_total_litres"]:
                tot += f" · {sch['coming_total_litres']:,} L"
            m1.metric(tf("metric_coming", lang), tot)
            m2.metric(tf("metric_avg_before", lang), f"{sch['avg_need_before_rain_mm']:g} mm")
            m3.metric(tf("metric_avg_after", lang), f"{sch['avg_need_after_rain_mm']:g} mm")
            names = {s: tf("s_" + s, lang) for s in ("before", "rain", "after")}
            labels = {r["date"]: _fmt_date(r["date"], lang) for r in sch["rows"]}
            today = tf("today", lang) if any(r["when"] == "today" for r in sch["rows"]) else None
            _data, spec = IR.chart_spec(sch["rows"], "date", labels, names, sch["avg_need_after_rain_mm"],
                                        tf("avg_label", lang), today=today)
            st.caption(tf("chart_daily", lang))
            _vl(spec)
            head = (f"| {tf('col_date', lang)} | {tf('col_weather', lang)} | {names['before']} | {names['rain']} | "
                    f"{names['after']} | {tf('col_litres', lang)} | {tf('col_action', lang)} |\n|---|---|---|---|---|---|---|\n")
            rows = "".join(
                f"| {_esc(_fmt_date(r['date'], lang))} | {_chip(r['level'], lang)} | {r['need_before_rain_mm']:g} | "
                f"{r['rain_mm']:g} | **{r['irrigate_mm']:g}** | {r['litres'] if r['litres'] is not None else '—'} | "
                f"{_esc(tf('act_' + r['action'], lang))} |\n" for r in sch["rows"] if r["when"] != "past")
            st.markdown(head + rows, unsafe_allow_html=True)
        else:
            st.warning(tf("forecast_unavailable", lang))
        try:
            mon = IR.monthly_typical(lat, lon, crop)
            names = {s: tf("s_" + s, lang) for s in ("before", "rain", "after")}
            labels = {i + 1: m for i, m in enumerate(month_names(lang))}
            _d, spec = IR.chart_spec(mon["rows"], "month", labels, names, mon["avg_need_after_rain_mm"],
                                     tf("avg_label", lang))
            st.caption(tf("chart_monthly", lang) + f" ({mon['years'][0]}–{mon['years'][-1]})")
            _vl(spec)
        except Exception as e:      # local NASA data missing: the daily chart still works
            st.caption(f"{type(e).__name__}")
        st.caption("ℹ️ " + tf("mm_note", lang))


def _farm_form(lang, prof, farm):
    crops = RT.supported_crops()
    with st.form(K + "farm_form"):
        st.markdown("**" + tf("farm_info", lang) + "**")
        name = st.text_input(tf("f_name", lang), value=farm.get("name") or "", key=K + "ff_name")
        c1, c2 = st.columns(2)
        lat = c1.number_input(tf("f_lat", lang), -90.0, 90.0, float(farm.get("lat") or RT.rotation_site()["lat"]),
                              format="%.4f", key=K + "ff_lat")
        lon = c2.number_input(tf("f_lon", lang), -180.0, 180.0, float(farm.get("lon") or RT.rotation_site()["lon"]),
                              format="%.4f", key=K + "ff_lon")
        sel = st.multiselect(tf("f_crops", lang), crops, default=[c for c in farm.get("crops") or [] if c in crops],
                             format_func=lambda c: crop_name(c, lang), key=K + "ff_crops")
        now_opts = [""] + crops
        crop_now = st.selectbox(tf("f_crop_now", lang), now_opts,
                                index=now_opts.index(farm.get("crop_now")) if farm.get("crop_now") in now_opts else 0,
                                format_func=lambda c: crop_name(c, lang) if c else "—", key=K + "ff_crop_now")
        c3, c4 = st.columns(2)
        stage = c3.selectbox(tf("f_stage", lang), FR.STAGES, index=FR.STAGES.index(farm.get("stage") or "growing"),
                             format_func=lambda s: tf("stage_" + s, lang), key=K + "ff_stage")
        methods = list(FR.METHOD_EFFICIENCY)
        method = c4.selectbox(tf("f_method", lang), methods, index=methods.index(farm.get("method") or "unknown"),
                              format_func=lambda s: tf("method_" + s, lang), key=K + "ff_method")
        status = st.radio(tf("f_status", lang), FR.STATUSES, index=FR.STATUSES.index(farm.get("status") or "good"),
                          horizontal=True, format_func=lambda s: tf("status_" + s, lang), key=K + "ff_status")
        c5, c6 = st.columns(2)
        area = c5.number_input(tf("f_area", lang) + " (m²)", 0, 1_000_000, int(farm.get("area_m2") or 0), 100,
                               key=K + "ff_area")
        last = c6.date_input(tf("f_last_irr", lang), value=dt.date.fromisoformat(farm["last_irrigation"])
                             if farm.get("last_irrigation") else None, key=K + "ff_last")
        notes = st.text_area(tf("f_notes", lang), value=farm.get("notes") or "", key=K + "ff_notes", max_chars=600)
        if st.form_submit_button(tf("save", lang)):
            farm.update(name=name, lat=lat, lon=lon, crops=sel, crop_now=crop_now, stage=stage, method=method,
                        status=status, area_m2=area or None, last_irrigation=last.isoformat() if last else None,
                        notes=notes, updated=dt.datetime.now().isoformat(timespec="minutes"))
            prof.update(lat=lat, lon=lon)
            if crop_now:
                prof["crop"] = crop_now
            if sel:
                prof["existing_rotation"] = sel
            st.success(tf("saved", lang))


def render_farm_report(context=None, _inside=False):
    lang, prof = _lang(context), _profile(context)
    farm = _farm(prof)
    box = _root("report_root") if not _inside else st.container()
    with box:
        if not _inside:
            _rtl("report_root", lang)
        _farm_form(lang, prof, farm)
        if st.button(tf("make_report", lang), key=K + "make_report", type="primary"):
            lat, lon = _location(context, prof, farm)
            with st.spinner(t("thinking", lang)):
                ov = _overview(lat, lon, C.WEATHER_DEMO)
                crops = RT.supported_crops()
                eff = FR.METHOD_EFFICIENCY.get(farm.get("method") or "unknown", 1.0)
                sch = IR.daily_schedule(ov["days"], farm.get("crop_now") or prof.get("crop"), crops,
                                        farm.get("area_m2"), eff) if ov.get("available") else None
                rot = RT.recommend(farm["crops"], _profile=prof, _ctx={"lat": lat, "lon": lon}) if farm.get("crops") else None
                data = FR.build_report_data(farm, ov, sch, rot, prof.get("photo_notes"))
                ins = FR.ai_insights(data, lang)
                md = FR.to_markdown(data, ins, lang, crop_label=lambda c: crop_name(c, lang))
            st.session_state[K + "report"] = dict(md=md, data=data, insights=ins)
        rep = st.session_state.get(K + "report")
        if rep:
            with st.container(border=True):
                st.markdown(rep["md"])
            st.download_button(tf("download_md", lang), rep["md"].encode("utf-8"),
                               file_name=f"soilsense_farm_report_{rep['data']['date']}.md", mime="text/markdown",
                               key=K + "dl_report")


def render_farm_dashboard(context=None):
    context = dict(context or {})
    with _root("dash_root"):
        if context.get("lang") in C.LANG_NAMES:
            lang = context["lang"]
        else:
            cur = st.session_state.get(K + "lang", C.DEFAULT_LANG)
            idx = C.ENABLED_LANGS.index(cur) if cur in C.ENABLED_LANGS else 0
            lang = st.radio(t("choose_language", cur), C.ENABLED_LANGS, index=idx, horizontal=True,
                            key=K + "dash_lang_choice", format_func=lambda c: C.LANG_NAMES[c])
            st.session_state[K + "lang"] = lang
        context["lang"] = lang
        _rtl("dash_root", lang)
        tabs = st.tabs([tf("tab_weather", lang), tf("tab_water", lang), tf("tab_report", lang)])
        with tabs[0]:
            render_weather_panel(context, _inside=True)
        with tabs[1]:
            render_irrigation_panel(context, _inside=True)
        with tabs[2]:
            render_farm_report(context, _inside=True)


# ================================================================== main page: overview first
def _kpi(title: str, value: str, colour: str | None = None, sub: str = "") -> str:
    edge = colour or "#7E8CE0"
    return (f"<div style='border:1px solid {edge}66;border-top:5px solid {edge};border-radius:14px;padding:14px 16px;"
            f"background:{edge}12;min-height:110px'><div style='font-size:0.9rem;opacity:.85'>{_esc(title)}</div>"
            f"<div style='font-size:1.9rem;font-weight:700;line-height:2.6rem'><bdi dir='ltr'>{_esc(value)}</bdi></div>"
            f"<div style='font-size:0.8rem;opacity:.75'><bdi>{_esc(sub)}</bdi></div></div>")


def _kpi_row(cards):
    cols = st.columns(len(cards))
    for col, html_ in zip(cols, cards):
        col.markdown(html_, unsafe_allow_html=True)


def meter_html(level: int, lang: str) -> str:
    """Gradient meter green -> red with a marker on today's level (like a fuel gauge)."""
    stops = ",".join(W.LEVELS[l]["colour"] for l in range(6))
    pos = (level + 0.5) / 6 * 100
    labels = "".join(f"<div style='flex:1;text-align:center;font-size:0.72rem;font-weight:600'>"
                     f"{_esc(tf('lvl_' + str(l), lang).split(' (')[0])}</div>" for l in range(6))
    return (f"<div style='direction:ltr;max-width:720px;margin:6px 0 2px 0'>"
            f"<div style='position:relative;height:30px'>"
            f"<div style='position:absolute;left:calc({pos:.1f}% - 11px);top:0;width:0;height:0;"
            f"border-left:11px solid transparent;border-right:11px solid transparent;border-top:16px solid #FFFFFF;"
            f"filter:drop-shadow(0 0 2px #000)'></div></div>"
            f"<div style='height:22px;border-radius:999px;background:linear-gradient(to right,{stops});"
            f"box-shadow:inset 0 0 0 1px #00000022'></div>"
            f"<div style='display:flex;margin-top:4px'>{labels}</div></div>")


def _checks_html(d: dict, lang: str) -> str:
    rows = []

    def row(ok, text, lvl):
        icon = "✅" if ok else "⚠️"
        colour = "inherit" if ok else W.LEVELS[lvl]["colour"]
        rows.append(f"<div style='margin:3px 0;color:{colour}'>{icon} {_esc(text)}</div>")

    def lvl_of(prefix):
        return max([h["level"] for h in d["hazards"] if h["key"].startswith(prefix)], default=0)
    if d.get("tmax_c") is not None:
        row(lvl_of("heat") < 2, tf("chk_heat", lang, v=f"{d['tmax_c']:.0f}", lim=C.HEAT_TMAX_C[0]), lvl_of("heat"))
    if d.get("gust_kmh") is not None:
        row(lvl_of("wind") < 2, tf("chk_wind", lang, v=f"{d['gust_kmh']:.0f}", lim=C.WIND_GUST_KMH[0]), lvl_of("wind"))
    row(lvl_of("rain") < 2 and d["condition"] not in ("heavy_rain",),
        tf("chk_rain", lang, v=f"{d['rain_mm']:g}", lim=C.RAIN_MM_DAY[0]), max(lvl_of("rain"), 2))
    if d.get("dust_ugm3") is not None:
        row(lvl_of("dust") < 2, tf("chk_dust", lang, v=f"{d['dust_ugm3']:.0f}", lim=C.DUST_UGM3[0]), max(lvl_of("dust"), 2))
    else:
        rows.append(f"<div style='margin:3px 0;opacity:.7'>➖ {_esc(tf('chk_dust_na', lang))}</div>")
    storm = d["condition"] in ("thunderstorm", "thunderstorm_hail")
    row(not storm, tf("chk_storm", lang), d["level"])
    return "".join(rows)


def _greeting(lang, farm):
    try:
        from zoneinfo import ZoneInfo
        hour = dt.datetime.now(ZoneInfo(C.TIMEZONE)).hour
    except Exception:
        hour = dt.datetime.now().hour
    name = farm.get("name") or tf("farmer", lang)
    return tf("greet_morning" if 4 <= hour < 12 else "greet_evening", lang, name=name)


def _lang_picker(context, key):
    if (context or {}).get("lang") in C.LANG_NAMES:
        return context["lang"]
    cur = st.session_state.get(K + "lang", C.DEFAULT_LANG)
    idx = C.ENABLED_LANGS.index(cur) if cur in C.ENABLED_LANGS else 0
    lang = st.radio(t("choose_language", cur), C.ENABLED_LANGS, index=idx, horizontal=True, key=K + key,
                    format_func=lambda c: C.LANG_NAMES[c])
    st.session_state[K + "lang"] = lang
    return lang


def _schedule_for(ov, farm, prof, crop=None):
    crops = RT.supported_crops()
    crop = crop or farm.get("crop_now") or prof.get("crop") or (farm.get("crops") or [None])[0]
    eff = FR.METHOD_EFFICIENCY.get(farm.get("method") or "unknown", 1.0)
    return IR.daily_schedule(ov["days"], crop, crops, area_m2=farm.get("area_m2"), method_efficiency=eff)


def _report_link(lang):
    try:
        st.page_link(C.REPORT_PAGE, label=tf("go_report", lang), icon=None)
    except Exception:          # not a multipage app (tests, single-file use)
        pass


def render_home_overview(context=None):
    """The main page: big danger meter first, then KPI cards, why-this-level, coming days, alerts and charts."""
    from . import charts as CH
    context = dict(context or {})
    prof = _profile(context)
    farm = FR.new_farm_info(prof)
    with _root("home_root"):
        lang = _lang_picker(context, "home_lang_choice")
        _rtl("home_root", lang)
        lat, lon = _location(context, prof, farm)
        ov = _overview(lat, lon, C.WEATHER_DEMO)
        st.markdown(f"## {_esc(_greeting(lang, farm))}")
        if not ov.get("available"):
            st.warning(tf("forecast_unavailable", lang))
            return ov
        if ov.get("demo"):
            st.error("⚠️ " + tf("demo_banner", lang))
        days = ov["days"]
        today = next((d for d in days if d["when"] == "today"), next((d for d in days if d["when"] == "future"), days[-1]))
        coming = [d for d in days if d["when"] != "past"]
        worst = max(coming, key=lambda d: d["level"]) if coming else today

        # ---- 1. the meter (first thing the farmer sees)
        st.markdown(f"**{_esc(tf('status_title', lang))}**")
        st.markdown(meter_html(today["level"], lang), unsafe_allow_html=True)
        c = today["colour"]
        st.markdown(f"<div style='font-size:1.25rem;font-weight:700;color:{c};margin-top:6px'>"
                    f"<span style='display:inline-block;width:16px;height:16px;border-radius:50%;background:{c};"
                    f"vertical-align:middle'></span> {_icon(today['top'])} {_esc(_day_name(today, lang))} — "
                    f"{_esc(tf('lvl_' + str(today['level']), lang))}</div>"
                    f"<div style='margin:4px 0 2px 0'>{_esc(tf('msg_' + str(today['level']), lang))}</div>",
                    unsafe_allow_html=True)
        if worst["level"] > today["level"]:
            st.markdown(f"<div style='color:{worst['colour']};font-weight:700'>⚠️ "
                        f"{_esc(tf('worst_coming', lang, date=_fmt_date(worst['date'], lang), lvl=tf('lvl_' + str(worst['level']), lang)))}"
                        f"</div>", unsafe_allow_html=True)
        st.caption(tf("location_caption", lang, lat=f"{lat:.3f}", lon=f"{lon:.3f}"))

        # ---- 2. KPI cards
        sch = _schedule_for(ov, farm, prof)
        st.session_state[K + "last_schedule"] = sch
        row_today = next((r for r in sch["rows"] if r["date"] == today["date"]), None)
        n_alerts = len(ov["alerts"])
        top_alert = ov["alerts"][0]["colour"] if ov["alerts"] else W.LEVELS[0]["colour"]
        water_today = f"{row_today['irrigate_mm']:g} mm" if row_today else "—"
        litres_today = f"{row_today['litres']:,} L" if row_today and row_today["litres"] is not None else ""
        week = f"{sch['coming_total_irrigation_mm']:g} mm"
        _kpi_row([
            _kpi(tf("kpi_temp", lang), f"{today['tmax_c']:.0f}° / {today['tmin_c']:.0f}°" if today["tmax_c"] is not None
                 else "—", W.LEVELS[max([h['level'] for h in today['hazards'] if h['key'].startswith('heat')], default=0)]["colour"]),
            _kpi(tf("kpi_rain", lang), f"{today['rain_mm']:g} mm",
                 sub=f"{tf('rain_chance', lang)}: {today['rain_chance_pct']}%" if today.get("rain_chance_pct") is not None else ""),
            _kpi(tf("kpi_water_today", lang), water_today, "#2E7D32", litres_today or tf("act_" + row_today["action"], lang)
                 if row_today else ""),
            _kpi(tf("kpi_alerts", lang), str(n_alerts), top_alert,
                 tf("lvl_" + str(ov["alerts"][0]["level"]), lang) if n_alerts else tf("no_alerts", lang)),
        ])
        st.write("")
        _kpi_row([
            _kpi(tf("kpi_gust", lang), f"{today['gust_kmh']:.0f} km/h" if today.get("gust_kmh") is not None else "—"),
            _kpi(tf("kpi_dust", lang), f"{today['dust_ugm3']:.0f} µg/m³" if today.get("dust_ugm3") is not None else "—"),
            _kpi(tf("kpi_week_water", lang), week, "#1E88E5",
                 f"{sch['coming_total_litres']:,} L" if sch.get("coming_total_litres") else ""),
            _kpi(tf("kpi_avg", lang), f"{sch['avg_need_after_rain_mm']:g} mm", "#F9A825",
                 f"{tf('s_before', lang)}: {sch['avg_need_before_rain_mm']:g} mm"),
        ])

        # ---- 3. why this level (evidence, like a checklist)
        st.markdown(f"#### {_esc(tf('why_level', lang))}")
        st.markdown(_checks_html(today, lang), unsafe_allow_html=True)

        # ---- 4. coming days + alerts
        st.markdown(f"#### {_esc(tf('week_title', lang))}")
        st.markdown(danger_scale_html(lang), unsafe_allow_html=True)
        for start in range(0, len(coming), 4):
            cols = st.columns(4)
            for col, d in zip(cols, coming[start:start + 4]):
                col.markdown(_day_card(d, lang), unsafe_allow_html=True)
        st.markdown("#### " + tf("alerts_title", lang))
        if ov["alerts"]:
            for a in ov["alerts"]:
                st.markdown(_alert_box(a, lang), unsafe_allow_html=True)
        else:
            st.success(tf("no_alerts", lang))
        st.caption("⚠️ " + tf("official_note", lang))

        # ---- 5. charts
        xl = lambda date: _fmt_date(date, lang)
        today_lbl = tf("today", lang) if any(d["when"] == "today" for d in days) else None
        c1, c2 = st.columns(2)
        with c1:
            st.caption(tf("chart_levels", lang))
            _vl(CH.level_chart(days, xl, lambda l: tf("lvl_" + str(l), lang).split(" (")[0],
                               lambda k: tf("hz_" + k, lang), today_lbl, tf("level_axis", lang)))
        with c2:
            st.caption(tf("chart_temp", lang))
            _vl(CH.temperature_chart(days, xl, {"max": tf("t_max", lang), "min": tf("t_min", lang)}, today_lbl))
        st.markdown(f"#### {_esc(tf('water_title', lang))}")
        names = {s: tf("s_" + s, lang) for s in ("before", "rain", "after")}
        _d, spec = IR.chart_spec(sch["rows"], "date", {r["date"]: xl(r["date"]) for r in sch["rows"]}, names,
                                 sch["avg_need_after_rain_mm"], tf("avg_label", lang), today=today_lbl)
        st.caption(tf("chart_daily", lang))
        _vl(spec)
        st.markdown(f"**{_esc(tf('schedule_title', lang))}**")
        head = (f"| {tf('col_date', lang)} | {tf('col_weather', lang)} | {names['after']} (mm) | {tf('col_litres', lang)} | "
                f"{tf('col_action', lang)} |\n|---|---|---|---|---|\n")
        rows = "".join(f"| {_esc(xl(r['date']))} | {_chip(r['level'], lang)} | **{r['irrigate_mm']:g}** | "
                       f"{r['litres'] if r['litres'] is not None else '—'} | {_esc(tf('act_' + r['action'], lang))} |\n"
                       for r in sch["rows"] if r["when"] != "past")
        st.markdown(head + rows, unsafe_allow_html=True)
        st.caption("ℹ️ " + tf("mm_note", lang) + " · " + tf("sources_weather", lang))
        _report_link(lang)
    return ov


# ================================================================== report page
def _insight_card(ins: dict, level: int, lang: str):
    c = W.LEVELS[level]["colour"]
    st.markdown(f"<div style='border-inline-start:8px solid {c};background:{c}1A;border-radius:12px;padding:14px 18px;"
                f"font-size:1.35rem;font-weight:700'>{_esc(ins['headline'])}</div>", unsafe_allow_html=True)
    if ins.get("summary"):
        st.markdown(f"<div style='border:1px solid #7E8CE066;border-radius:12px;padding:12px 16px;margin-top:10px;"
                    f"line-height:1.9'><b>{_esc(tf('rep_summary', lang))}</b><br>{_esc(ins['summary'])}</div>",
                    unsafe_allow_html=True)
    st.caption(tf("src_" + ins["source"], lang))
    st.markdown(f"**{tf('rp_why', lang)}**\n" + "\n".join(f"- {x}" for x in ins["why"]))
    st.markdown(f"**{tf('rp_meaning', lang)}**\n\n{ins['meaning']}")
    st.markdown(f"**{tf('rp_actions', lang)}**\n" + "\n".join(f"- {x}" for x in ins["actions"]))


def _build_report(context, prof, farm, lang):
    lat, lon = _location(context, prof, farm)
    info = dict(farm, lat=lat, lon=lon)
    ov = _overview(lat, lon, C.WEATHER_DEMO)
    sch = _schedule_for(ov, farm, prof) if ov.get("available") else None
    rot = RT.recommend(info["crops"], _profile=prof, _ctx={"lat": lat, "lon": lon}) if info.get("crops") else None
    data = FR.build_report_data(info, ov, sch, rot, prof.get("photo_notes"))
    ins = FR.ai_insights(data, lang)
    md = FR.to_markdown(data, ins, lang, crop_label=lambda c: crop_name(c, lang))
    return dict(md=md, data=data, insights=ins, days=ov.get("days", []), schedule=sch, lang=lang)


def render_report_page(context=None):
    """Separate page. The report is made AUTOMATICALLY from what is already known (location, weather, watering
    plan, crops and photos from the chat) - no form. Re-made when the day, place, crops or language change."""
    from . import charts as CH
    context = dict(context or {})
    prof = _profile(context)
    farm = FR.new_farm_info(prof)                      # built from the chat profile + host context, never asked
    with _root("rp_root"):
        lang = _lang_picker(context, "rp_lang_choice")
        _rtl("rp_root", lang)
        st.markdown(f"## {_esc(tf('report_page_title', lang))}")
        lat, lon = _location(context, prof, farm)
        sig = (dt.date.today().isoformat(), round(lat, 3), round(lon, 3), lang, tuple(farm.get("crops") or []),
                          farm.get("crop_now"), len(prof.get("photo_notes") or []))
        refresh = st.button(tf("refresh", lang), key=K + "rp_refresh")
        rep = st.session_state.get(K + "report")
        if refresh or not rep or rep.get("sig") != sig:
            with st.spinner(t("thinking", lang)):
                rep = _build_report(context, prof, farm, lang)
            rep["sig"] = sig
            st.session_state[K + "report"] = rep
        st.caption(f"{rep['data']['date']} · 📍 {lat:.3f}, {lon:.3f} · {tf('rp_auto_note', lang)}")
        worst = (rep["data"]["weather"].get("worst_day") or {}).get("level", 0)
        _insight_card(rep["insights"], worst, lang)

        st.markdown(f"### {tf('rp_charts', lang)}")
        days = rep["days"]
        coming = [d for d in days if d["when"] != "past"]
        xl = lambda date: _fmt_date(date, lang)
        today_lbl = tf("today", lang) if any(d["when"] == "today" for d in days) else None
        if coming:
            c1, c2 = st.columns(2)
            with c1:
                st.caption(tf("level_days", lang))
                _vl(CH.level_count_chart(coming, lambda l: tf("lvl_" + str(l), lang).split(" (")[0], tf("days_axis", lang)))
            with c2:
                st.caption(tf("chart_levels", lang))
                _vl(CH.level_chart(coming, xl, lambda l: tf("lvl_" + str(l), lang).split(" (")[0],
                                   lambda k: tf("hz_" + k, lang), today_lbl, tf("level_axis", lang)))
        sch = rep.get("schedule")
        if sch:
            names = {s: tf("s_" + s, lang) for s in ("before", "rain", "after")}
            _d, spec = IR.chart_spec(sch["rows"], "date", {r["date"]: xl(r["date"]) for r in sch["rows"]}, names,
                                     sch["avg_need_after_rain_mm"], tf("avg_label", lang), today=today_lbl)
            st.caption(tf("chart_daily", lang))
            _vl(spec)
        if days:
            st.caption(tf("chart_temp", lang))
            _vl(CH.temperature_chart(days, xl, {"max": tf("t_max", lang), "min": tf("t_min", lang)}, today_lbl))

        with st.expander(tf("rp_full", lang)):
            st.markdown(rep["md"])
        st.download_button(tf("download_md", lang), rep["md"].encode("utf-8"),
                           file_name=f"soilsense_farm_report_{rep['data']['date']}.md", mime="text/markdown",
                           key=K + "dl_report")
    return rep
