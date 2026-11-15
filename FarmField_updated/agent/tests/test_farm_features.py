"""Weather levels + alerts, watering schedule + charts, farm report + AI insights, photo analysis.
No network and no LLM: Open-Meteo responses and the model are faked."""
import datetime as dt
import io
import json
import sys

import pytest

from .. import config as C
from .. import farm_report as FR
from .. import irrigation as IR
from .. import llm
from .. import vision as V
from .. import weather as W
from . import fake_streamlit
from .conftest import needs_team

CROPS = ["wheat", "barley", "sorghum", "pearl_millet", "cowpea", "chickpea", "tomato", "onion", "sesame", "okra"]
TODAY = dt.date(2026, 11, 15)


# ------------------------------------------------------------------ severity levels
@pytest.mark.parametrize("kw,level,top", [
    (dict(code=0, tmax=35, rain=0, gust=20, dust=10), 0, "sunny"),
    (dict(code=2, tmax=35, rain=0, gust=20, dust=10), 1, "partly_cloudy"),
    (dict(code=0, tmax=35, rain=0, gust=20, dust=50), 1, "dust_1"),          # meteoblue light-green class
    (dict(code=61, tmax=30, rain=3, gust=20), 2, "light_rain"),
    (dict(code=0, tmax=35, gust=45), 2, "wind_2"),                           # Beaufort 6
    (dict(code=0, tmax=46, gust=20), 3, "heat_3"),
    (dict(code=95, tmax=30, rain=5, gust=30), 3, "thunderstorm"),
    (dict(code=0, tmax=35, gust=20, dust=600), 4, "dust_4"),                 # dust storm
    (dict(code=96, tmax=30, rain=10, gust=30), 4, "thunderstorm_hail"),
    (dict(code=80, tmax=30, rain=40, gust=125), 5, "wind_5"),                # hurricane-force gusts
    (dict(code=63, tmax=30, rain=130, gust=40), 5, "rain_5"),
])
def test_classify_day_levels(kw, level, top):
    d = W.classify_day(**kw)
    assert d["level"] == level and d["top"] == top and d["colour"] == W.LEVELS[level]["colour"]


def test_level_colours_go_from_green_to_red():
    assert W.LEVELS[0]["colour"] == "#2E7D32" and W.LEVELS[5]["colour"] == "#C62828"
    assert C.WIND_GUST_KMH == (39, 62, 89, 118) and C.DUST_UGM3 == (80, 160, 450, 1000)


# ------------------------------------------------------------------ forecast download (faked)
def _fake_api(monkeypatch, fail=False):
    calls = []
    dates = [(TODAY + dt.timedelta(days=i - 2)).isoformat() for i in range(5)]

    class R:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    def get(url, params=None, timeout=None):
        calls.append((url, params))
        if fail:
            raise ConnectionError("offline")
        if "air-quality" in url:
            times = [f"{d}T{h:02d}:00" for d in dates for h in (0, 12)]
            return R({"hourly": {"time": times, "dust": [10, 30, 20, 700, 15, 25, 5, 5, None, 50]}})
        return R({"timezone": "Asia/Muscat", "daily": {
            "time": dates, "weather_code": [0, 2, 95, 0, 61], "temperature_2m_max": [36, 37, 31, 47, 30],
            "temperature_2m_min": [24, 25, 23, 30, 22], "precipitation_sum": [0, 0, 30, 0, 4],
            "precipitation_probability_max": [0, 5, 80, 0, 60], "wind_gusts_10m_max": [20, 25, 70, 30, 40],
            "et0_fao_evapotranspiration": [6.5, 6.8, 3.0, 8.5, 4.0]}})
    monkeypatch.setattr(W.requests, "get", get)
    monkeypatch.setattr(W, "_CACHE", {})
    monkeypatch.setattr(C, "WEATHER_DEMO", False)
    return calls


def test_fetch_forecast_params_dust_and_cache(monkeypatch):
    calls = _fake_api(monkeypatch)
    fc = W.fetch_forecast(23.7, 57.9)
    url, params = calls[0]
    assert url == C.FORECAST_URL and params["timezone"] == "auto"
    assert params["past_days"] == C.FORECAST_PAST_DAYS and params["forecast_days"] == C.FORECAST_DAYS
    assert set(params["daily"].split(",")) == set(W.DAILY_VARS)
    assert fc["dust_by_day"][(TODAY + dt.timedelta(days=-1)).isoformat()] == 700       # daily max of hourly dust
    W.fetch_forecast(23.7, 57.9)
    assert len(calls) == 2                                                               # 2nd call served from cache


def test_offline_gives_unavailable_not_made_up_data(monkeypatch):
    _fake_api(monkeypatch, fail=True)
    assert W.fetch_forecast(23.7, 57.9)["available"] is False
    assert W.weather_overview(23.7, 57.9)["available"] is False


def test_build_days_and_alerts(monkeypatch):
    _fake_api(monkeypatch)
    days = W.build_days(W.fetch_forecast(23.7, 57.9), today=TODAY)
    assert [d["when"] for d in days] == ["past", "past", "today", "future", "future"]
    assert [d["level"] for d in days] == [0, 4, 3, 3, 2]          # day 2: dust 700 = dust storm; day 4: heat 47
    al = W.alerts(days)
    assert [a["date"] for a in al] == [days[2]["date"], days[3]["date"], days[4]["date"]]   # worst first, no past
    assert "adv_storm" in al[0]["advice"] and al[1]["advice"] == ["adv_heat"] and set(al[2]["advice"]) == {"adv_rain", "adv_wind"}


# ------------------------------------------------------------------ watering
def _days(rows):
    out = []
    for i, (et0, rain, when) in enumerate(rows):
        out.append(dict(date=f"2026-11-{10 + i:02d}", when=when, et0_mm=et0, rain_mm=rain, level=0,
                        colour="#2E7D32", hazards=[]))
    return out


def test_schedule_before_and_after_rain():
    days = _days([(5, 0, "past"), (5, 0, "today"), (5, 0, "future"), (4, 20, "future"), (5, 0, "future")])
    s = IR.daily_schedule(days, "tomato", CROPS, area_m2=100, method_efficiency=0.9)
    r = s["rows"]
    assert s["kc"] == 1.15 and r[0]["need_before_rain_mm"] == 5.8
    assert r[2]["action"] == "wait_rain"                         # rain expected tomorrow covers the need
    assert r[3]["rain_used_mm"] == 4.6 and r[3]["need_after_rain_mm"] == 0 and r[3]["action"] == "skip_rain"
    assert r[4]["need_after_rain_mm"] == 0                       # stored rain (16 - 4.6) still covers the next day
    assert r[1]["irrigate_mm"] == round(5.8 / 0.9, 1) and r[1]["litres"] == round(r[1]["irrigate_mm"] * 100)
    assert s["avg_need_before_rain_mm"] == round(sum(x["need_before_rain_mm"] for x in r) / 5, 1)
    assert s["settings"]["status"] == "needs expert review"


def test_schedule_neutral_crop_and_small_rain_ignored():
    s = IR.daily_schedule(_days([(5, 1.5, "today")]), None, CROPS)
    assert s["kc"] == 1.0 and s["rows"][0]["rain_used_mm"] == 0 and s["rows"][0]["need_after_rain_mm"] == 5
    assert IR.daily_schedule(_days([(5, 0, "today")]), "okra", CROPS)["kc"] == 1.0     # no FAO-56 value


def test_chart_spec_has_three_series_and_average_line():
    rows = [dict(date="d1", need_before_rain_mm=5, rain_mm=0, need_after_rain_mm=5),
            dict(date="d2", need_before_rain_mm=4, rain_mm=10, need_after_rain_mm=0)]
    data, spec = IR.chart_spec(rows, "date", {"d1": "Mon"}, {"before": "B", "rain": "R", "after": "A"}, 2.5, "Avg",
                               today="Mon")
    assert len(data) == 6 and {d["series"] for d in data} == {"B", "R", "A"}
    assert spec["layer"][0]["encoding"]["xOffset"]["field"] == "series"
    assert spec["layer"][1]["data"]["values"][0]["avg"] == 2.5 and spec["layer"][1]["layer"][0]["mark"]["type"] == "rule"
    assert spec["layer"][2]["mark"]["color"] == "#C62828"         # today marker
    json.dumps(spec)


@needs_team
def test_monthly_typical_from_nasa():
    m = IR.monthly_typical(23.7067, 57.9065, "tomato")
    assert len(m["rows"]) == 12 and m["kc"] == 1.15
    assert all(r["need_after_rain_mm"] <= r["need_before_rain_mm"] for r in m["rows"])


# ------------------------------------------------------------------ farm report + AI insights
def _report_data():
    W_ = dict(available=True, demo=True, days=W.build_days(W.demo_forecast(TODAY), today=TODAY))
    W_["alerts"] = W.alerts(W_["days"])
    sch = IR.daily_schedule(W_["days"], "tomato", CROPS, area_m2=500)
    info = FR.new_farm_info({})
    info.update(name="Test farm", crops=["wheat", "tomato"], status="some_problems")
    return FR.build_report_data(info, W_, sch, None, ["tomato: leaf spots (medium)"])


def test_report_data_and_rule_insights_in_three_languages(monkeypatch):
    monkeypatch.setattr(C, "USE_MOCK", True)
    d = _report_data()
    assert d["weather"]["worst_day"]["level"] == 5 and d["watering"]["crop"] == "tomato"
    for lang in ("ar", "en", "bn"):
        ins = FR.ai_insights(d, lang)
        assert ins["source"] == "rules" and 2 <= len(ins["why"]) <= 5 and ins["headline"] and ins["actions"]
        md = FR.to_markdown(d, ins, lang)
        assert md.count("\n## ") >= 4 and FR.tf("demo_banner", lang) in md


def _fake_chat(monkeypatch, replies, module):
    calls = []

    def chat(messages, tools=None, providers=None, max_tokens=None):
        calls.append(dict(messages=messages, providers=providers))
        if isinstance(replies, Exception):
            raise replies
        return {"content": replies[min(len(calls), len(replies)) - 1]}, "fake"
    monkeypatch.setattr(module, "chat", chat)
    return calls


def test_ai_insights_grounding_retry_and_strip(monkeypatch):
    d = _report_data()
    bad = json.dumps({"insights": ["Rain will be 999 mm.", "Prepare the farm."], "priority_action": "Check drains."})
    calls = _fake_chat(monkeypatch, [bad], FR)
    ins = FR.ai_insights(d, "en")
    assert len(calls) == 2 and "CORRECTION" in calls[1]["messages"][-1]["content"]
    assert ins["source"] == "ai" and ins["insights"] == ["Prepare the farm."] and ins["grounding"]["removed"] == [999.0]


def test_ai_insights_falls_back_to_rules(monkeypatch):
    _fake_chat(monkeypatch, llm.AllProvidersFailed("down"), FR)
    assert FR.ai_insights(_report_data(), "ar")["source"] == "rules"
    dose = json.dumps({"insights": ["Spray 20 ml per litre now."], "priority_action": ""})
    _fake_chat(monkeypatch, [dose], FR)
    assert FR.ai_insights(_report_data(), "en")["source"] == "rules"          # dose text never shown


# ------------------------------------------------------------------ photo analysis
def _jpeg(w=3000, h=2000):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 140, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def test_prepare_image_shrinks():
    url, info = V.prepare_image(_jpeg())
    assert url.startswith("data:image/jpeg;base64,") and max(info["width"], info["height"]) == C.IMAGE_MAX_PX
    assert info["sent_bytes"] < info["original_bytes"]


def test_photo_without_key_or_in_mock(monkeypatch):
    assert V.analyze_plant_photo(_jpeg(10, 10), "en")["error"] == "no_vision"            # no keys (conftest)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(C, "USE_MOCK", True)
    assert V.analyze_plant_photo(_jpeg(10, 10), "en")["error"] == "no_vision"
    assert V.analyze_plant_photo(b"", "en")["error"] == "empty"


def test_photo_analysis_sends_image_and_enforces_rules(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    reply = json.dumps({"is_plant": True, "plant_guess": "tomato", "observations": ["brown spots on lower leaves"],
                        "possible_problems": [{"name": "early blight", "likelihood": "high", "signs": "rings"}],
                        "checks": ["look under the leaves"], "safe_actions": ["remove bad leaves",
                                                                              "spray 5 ml per litre of X"],
                        "see_expert_if": ["spots spread fast"], "image_quality": "good", "confidence": "high"})
    calls = _fake_chat(monkeypatch, ["```json\n" + reply + "\n```"], V)
    rep = V.analyze_plant_photo(_jpeg(), "ar", crop="tomato", note="spots")
    content = calls[0]["messages"][0]["content"]
    assert content[1]["type"] == "image_url" and content[1]["image_url"]["url"].startswith("data:image/jpeg")
    assert "Arabic" in content[0]["text"] and calls[0]["providers"] is C.VISION_PROVIDERS
    assert rep["safe_actions"] == ["remove bad leaves"] and rep["removed_dose_text"] is True
    assert rep["confidence"] == "medium"                     # "high" is never allowed
    assert V.short_summary(rep) == "tomato: early blight (high)"


def test_photo_not_a_plant(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    _fake_chat(monkeypatch, [json.dumps({"is_plant": False, "confidence": "medium"})], V)
    rep = V.analyze_plant_photo(_jpeg(50, 50), "en")
    assert rep["is_plant"] is False and rep["confidence"] == "low"


def test_vision_providers_skip_empty_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(llm, "_down_until", {})
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: pytest.fail("called a provider with no model"))
    with pytest.raises(llm.AllProvidersFailed):
        llm.chat([{"role": "user", "content": "x"}], providers=[p for p in C.VISION_PROVIDERS if p["name"] == "openrouter"])


# ------------------------------------------------------------------ UI (fake Streamlit)
@pytest.fixture
def fake_st(monkeypatch):
    import importlib
    st = fake_streamlit.make()
    for name, mod in (("streamlit", st), ("streamlit.components", st.components),
                      ("streamlit.components.v1", st.components.v1)):
        monkeypatch.setitem(sys.modules, name, mod)
    pkg = __package__.rsplit(".", 1)[0]
    for m in ("ui", "dashboard_ui", "voice", "voice_input"):
        sys.modules.pop(f"{pkg}.{m}", None)
    st._dash = importlib.import_module(pkg + ".dashboard_ui")
    st._ui = importlib.import_module(pkg + ".ui")
    monkeypatch.setattr(C, "USE_MOCK", True)
    monkeypatch.setattr(C, "WEATHER_DEMO", True)
    yield st
    for m in ("ui", "dashboard_ui"):
        sys.modules.pop(f"{pkg}.{m}", None)


@needs_team
def test_home_overview_meter_first_then_kpis_and_charts(fake_st):
    st = fake_st
    st._dash.render_home_overview({"lang": "ar", "lat": 23.7, "lon": 57.9})
    texts = st._rec["texts"]
    meter = next(i for i, x in enumerate(texts) if "linear-gradient(to right" in x)
    first_chart = st._rec["calls"].index("vega_lite_chart")
    first_kpi = next(i for i, x in enumerate(texts) if "border-top:5px solid" in x)
    assert meter < first_kpi                                             # the meter is the first thing shown
    assert st._rec["calls"].count("vega_lite_chart") == 3                # levels, temperature, watering
    assert first_chart > 0 and "set_page_config" not in st._rec["calls"]
    assert any("✅" in x or "⚠️" in x for x in texts)                    # why-this-level checklist
    assert all(k.startswith("ss_agent_") for k in st._rec["keys"]) and all(k.startswith("ss_agent_") for k in st.session_state)
    assert all(".st-key-ss_agent_home_root{" in s for s in st._rec["styles"])


def test_meter_marker_and_charts(fake_st):
    from .. import charts as CH
    meter_html = fake_st._dash.meter_html
    assert "left:calc(8.3% - 11px)" in meter_html(0, "en") and "left:calc(91.7% - 11px)" in meter_html(5, "en")
    days = W.build_days(W.demo_forecast(TODAY), today=TODAY)
    lv = CH.level_chart(days, str, str, str, TODAY.isoformat(), "L")
    assert len(lv["data"]["values"]) == len(days) and lv["layer"][-1]["mark"]["type"] == "rule"
    assert lv["layer"][0]["encoding"]["color"]["scale"]["range"][5] == "#C62828"
    tc = CH.temperature_chart(days, str, {"max": "Max", "min": "Min"}, None)
    assert len(tc["data"]["values"]) == 2 * len(days) and tc["layer"][1]["data"]["values"][0]["lim"] == C.HEAT_TMAX_C[0]
    cnt = CH.level_count_chart([d for d in days if d["when"] != "past"], str, "days")
    assert sum(r["n"] for r in cnt["data"]["values"]) == 7
    json.dumps([lv, tc, cnt])


@needs_team
def test_report_page_with_insight_card_and_charts(fake_st):
    st = fake_st
    st._dash.render_report_page({"lang": "ar", "lat": 23.7, "lon": 57.9})
    assert "ss_agent_report" not in st.session_state                     # nothing until the farmer asks
    st.session_state["ss_agent_ff_name"] = "مزرعة سالم"
    st.session_state["ss_agent_ff_status"] = "some_problems"
    st._rec["submit"].add("💾 احفظ المعلومات")
    st._rec["clicks"].add("ss_agent_make_report")
    st._rec["charts"].clear()
    st._dash.render_report_page({"lang": "ar", "lat": 23.7, "lon": 57.9})
    rep = st.session_state["ss_agent_report"]
    ins = rep["insights"]
    assert ins["headline"] and ins["why"] and ins["meaning"] and ins["actions"]
    assert any("ليش أشوف هذا؟" in x for x in st._rec["texts"]) and any("وش أسوي؟" in x for x in st._rec["texts"])
    assert len(st._rec["charts"]) == 4                                   # level count, level by day, watering, temperature
    assert rep["md"].startswith("# تقرير المزرعة: مزرعة سالم") and st._rec["downloads"]
    assert all(k.startswith("ss_agent_") for k in st._rec["keys"])


@needs_team
def test_photo_flow_in_chat(fake_st, monkeypatch):
    st = fake_st

    class Up:
        def getvalue(self):
            return _jpeg(800, 600)
    rep = dict(is_plant=True, plant_guess="tomato", observations=["spots"], possible_problems=[
        dict(name="leaf spot", likelihood="medium", signs="brown spots")], checks=[], safe_actions=["remove leaves"],
        see_expert_if=["it spreads"], image_quality="good", confidence="medium", provider="fake")
    monkeypatch.setattr(st._ui.V, "analyze_plant_photo", lambda *a, **k: rep)
    st._rec["uploads"]["ss_agent_upl_0"] = Up()
    st._rec["clicks"].add("ss_agent_photo_go_0")
    try:
        st._ui.render_agent_chat({"lang": "en"})
    except fake_streamlit.Rerun:
        pass
    msgs = st.session_state["ss_agent_msgs"]
    assert msgs[-1]["kind"] == "photo" and msgs[-2]["image"]
    assert st.session_state["ss_agent_profile"]["photo_notes"] == ["tomato: leaf spot (medium)"]
    assert st.session_state["ss_agent_photo_n"] == 1                     # widgets reset for the next photo
    st._ui.render_agent_chat({"lang": "en"})
    assert st._rec["images"] >= 1 and any("early hint" in x for x in st._rec["texts"])
    assert all(k.startswith("ss_agent_") for k in st._rec["keys"])
