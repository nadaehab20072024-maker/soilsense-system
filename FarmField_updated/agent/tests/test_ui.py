"""UI integration checks. Part 1 uses a recording fake Streamlit (always runs).
Part 2 uses Streamlit's real AppTest (runs only where streamlit is installed)."""
import importlib
import sys
from pathlib import Path

import pytest

from .. import config as C

from . import fake_streamlit
from .conftest import needs_team

APP = str(Path(__file__).with_name("dummy_host_app.py"))


@pytest.fixture
def fake_st(monkeypatch):
    st = fake_streamlit.make()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setitem(sys.modules, "streamlit.components", st.components)
    monkeypatch.setitem(sys.modules, "streamlit.components.v1", st.components.v1)
    for mod in [m for m in list(sys.modules) if m.startswith(__package__.rsplit(".", 1)[0] + ".") and
                m.rsplit(".", 1)[1] in ("voice", "voice_input")]:
        monkeypatch.delitem(sys.modules, mod)
    pkg = __package__.rsplit(".", 1)[0]
    sys.modules.pop(pkg + ".ui", None)
    ui = importlib.import_module(pkg + ".ui")   # bind ui to the fake module
    st._ui = ui
    monkeypatch.setattr(C, "USE_MOCK", True)
    yield st
    sys.modules.pop(ui.__name__, None)


def _agent_keys(st):
    host = {"input", "profile", "msgs", "lang"}
    return [k for k in st._rec["keys"] if k not in host]


@needs_team
def test_integration_keys_css_and_no_page_config(fake_st):
    st = fake_st
    fake_streamlit.run(st, APP)                                   # first screen
    assert "radio" in st._rec["calls"]                            # language picker shown
    st.session_state["ss_agent_lang_choice"] = "ar"
    st._rec["inputs"].append("وش أزرع بعد القمح والطماطم؟")
    fake_streamlit.run(st, APP)
    msgs = st.session_state["ss_agent_msgs"]
    assert [m["role"] for m in msgs] == ["user", "assistant"] and "لوبيا" in msgs[1]["content"]
    # click: replay, apply priorities, then a what-if suggestion
    st._rec["clicks"].add("ss_agent_replay_1")
    fake_streamlit.run(st, APP)
    assert any("2023" in x for x in st._rec["texts"])           # driest-year story rendered
    st.session_state["ss_agent_prio_water_1"] = "very_important"
    st._rec["clicks"].add("ss_agent_apply_1")
    fake_streamlit.run(st, APP)
    prof = st.session_state["ss_agent_profile"]
    assert prof["water"] == 2.0 and set(prof["asked"]) == {"water", "soil", "income", "irrigation_mm"}
    assert len(st.session_state["ss_agent_msgs"]) == 4            # re-asked once with the new priorities
    assert st.session_state["ss_agent_msgs"][-1]["result"]["ask_profile"] == []   # never asked twice
    st._rec["clicks"].add("ss_agent_sugg_3_0")
    fake_streamlit.run(st, APP)
    assert st.session_state["ss_agent_msgs"][-1]["result"]["meta"]["tools_used"] == ["rotation_what_if"]

    assert "set_page_config" not in st._rec["calls"]
    bad = [k for k in _agent_keys(st) if not k.startswith("ss_agent_")]
    assert bad == []
    assert all(k.startswith("ss_agent_") for k in st.session_state if k not in {"msgs", "lang", "input", "profile"})
    assert st.session_state["msgs"] == "HOST VALUE" and st.session_state["lang"] == "host-lang"
    assert st._rec["styles"] and all(".st-key-ss_agent_root{" in s and s.count("{") == 1 for s in st._rec["styles"])


def test_fake_warning_visible_when_team_module_missing(fake_st, monkeypatch):
    from .. import team_bridge
    monkeypatch.setattr(C, "FORCE_FAKE_TEAM", True)
    monkeypatch.setattr(team_bridge, "team", None)
    try:
        team_bridge.load()
        fake_streamlit.run(fake_st, APP)
        assert "warning" in fake_st._rec["calls"] and any("FAKE" in x for x in fake_st._rec["texts"])
    finally:
        monkeypatch.setattr(C, "FORCE_FAKE_TEAM", False)
        team_bridge.load(force_reload=True)


def test_context_from_host_skips_language_picker(fake_st):
    ui = fake_st._ui
    ui.render_agent_chat({"lang": "en", "lat": 23.7, "lon": 57.9, "crop": "tomato"})
    assert "radio" not in fake_st._rec["calls"]
    assert fake_st.session_state["ss_agent_profile"]["crop"] == "tomato"


# ------------------------------------------------------------------ real Streamlit AppTest
@needs_team
def test_apptest_real_streamlit(monkeypatch):
    testing = pytest.importorskip("streamlit.testing.v1")
    monkeypatch.setattr(C, "USE_MOCK", True)
    at = testing.AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    at.chat_input[0].set_value("What should I grow after wheat and tomatoes?").run()
    assert not at.exception
    assert at.session_state["msgs"] == "HOST VALUE"            # host key untouched
    msgs = at.session_state["ss_agent_msgs"]
    assert msgs[-1]["role"] == "assistant" and "cowpea" in msgs[-1]["content"]
    at.button(key="ss_agent_replay_1").click().run()
    assert not at.exception and any("2023" in i.value for i in at.info)
