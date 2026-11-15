"""Agent loop with a fake LLM, grounding, cache, fallback chain, safety rules, mock mode."""
import json
import shutil
import sys
import types

import pytest

from .. import agent as A
from .. import config as C
from .. import grounding as G
from .. import llm

from .conftest import needs_team


def tool_call(name, args, cid="c1"):
    return {"content": None, "tool_calls": [{"id": cid, "type": "function",
                                             "function": {"name": name, "arguments": json.dumps(args)}}]}


def final(answer, why="", conf="high", sugg=("a", "b")):
    return {"content": "```json\n" + json.dumps({"answer": answer, "why": why, "confidence": conf,
                                                 "suggestions": list(sugg)}, ensure_ascii=False) + "\n```"}


# ------------------------------------------------------------------ grounding unit tests
def test_extract_numbers_handles_local_digits():
    assert G.extract_numbers("درجتها ٨٠٫٨ من ١٠٠") == [80.8, 100.0]
    assert G.extract_numbers("স্কোর ৮০.৮") == [80.8]
    assert G.extract_numbers("1,700 mm on 2024-08-19") == [1700.0, 2024.0, 8.0, 19.0]


def test_grounded_and_ungrounded():
    allowed = G.allowed_numbers([{"total_score": 68.8, "notes": ["2024 shows 2652 mm"]}])
    assert G.ungrounded_numbers("Score 68.8, about 69, in 2024", allowed) == []
    assert G.ungrounded_numbers("Score 75 out of 68.8", allowed) == [75.0]
    assert G.strip_numbers("Good rotation. It scores 75. Try it.", [75.0]) == "Good rotation. Try it."


# ------------------------------------------------------------------ agent loop
@needs_team
def test_rotation_question_full_loop(fake_llm):
    from .. import team_bridge
    raw = team_bridge.load().recommend(["wheat", "tomato"])
    ex, best = raw["existing"]["total_score"], raw["alternatives"][0]["total_score"]
    calls = fake_llm([tool_call("recommend", {"existing_rotation": ["قمح", "طماطم"]}),
                      final(f"جرّب الخيار الأفضل. درجته {best} من 100.", f"السبب: {ex} الحالية.")])
    r = A.ask_agent("وش أزرع بعد القمح والطماطم؟", {"lang": "ar", "lat": 23.7, "lon": 57.9})
    assert r["meta"]["tools_used"] == ["recommend"] and r["meta"]["grounding"]["ungrounded"] == []
    tool_msg = [m for m in calls[1] if m["role"] == "tool"][0]
    assert f'"total_score": {ex}' in tool_msg["content"]                    # real teammate output went to the model
    assert r["confidence"] == "medium"                                      # placeholder scores: never "high"
    assert r["compare"]["best_total"] == best and r["replay"]["driest_year"] == team_bridge.team.get_climate()["worst_year"]
    assert r["risk"]["soil"]["level"] in ("Low", "Medium", "High")
    assert len(r["suggestions"]) == 3 and all(a["tool"] == "rotation_what_if" for a in r["actions"])
    assert any("250" in n for n in r["notices"])                            # defaults told to the farmer
    assert "MERRA-2" in r["why"] and "%" in r["why"]                        # caveats in the hidden part
    assert r["profile_updates"]["existing_rotation"] == ["wheat", "tomato"]
    assert r["ask_profile"] == ["water", "soil", "income", "irrigation_mm"]


@needs_team
def test_far_farm_gets_region_warning_and_low_confidence(fake_llm):
    fake_llm([tool_call("recommend", {"existing_rotation": ["wheat"]}), final("Grow cowpea next.")])
    r = A.ask_agent("what next after wheat?", {"lang": "en", "lat": 17.02, "lon": 54.08})
    assert "covers only" in r["answer"] and "not for your farm" in r["answer"] and r["confidence"] == "low"


@needs_team
def test_unsupported_crop_answer_lists_supported(fake_llm):
    fake_llm([tool_call("recommend", {"existing_rotation": ["date palm"]}), final("ok")])
    r = A.ask_agent("what after date palm?", {"lang": "en"})
    assert "not supported" in r["answer"] and "okra" in r["answer"]


@needs_team
def test_profile_is_not_asked_again(fake_llm):
    fake_llm([tool_call("recommend", {"existing_rotation": ["wheat"]}), final("Grow cowpea next.")])
    prof = {"water": 2.0, "irrigation_mm": 300.0, "asked": ["soil"]}
    r = A.ask_agent("next after wheat?", {"lang": "en", "profile": prof})
    assert r["ask_profile"] == ["income"]


def test_number_grounding_retry_then_success(fake_llm):
    calls = fake_llm([tool_call("get_climate_risk", {}), final("Heat days are 999 this year."),
                      final("Heat risk is high this year.")])
    r = A.ask_agent("is it hot?", {"lang": "en", "lat": 23.7067, "lon": 57.9065})
    g = r["meta"]["grounding"]
    assert g["retried"] and g["ungrounded"] == [999.0] and g["ungrounded_after_retry"] == []
    assert "CORRECTION" in calls[-1][-1]["content"] and "999" not in r["answer"]


def test_number_grounding_removes_number_and_lowers_confidence(fake_llm):
    fake_llm([tool_call("get_climate_risk", {}), final("Risk is high. Heat days are 999.", conf="high")])
    r = A.ask_agent("is it hot?", {"lang": "en", "lat": 23.7067, "lon": 57.9065})
    assert "999" not in r["answer"] and r["answer"].startswith("Risk is high")
    assert r["confidence"] == "low" and r["meta"]["grounding"]["removed"] == [999.0]


def test_chemical_dose_refused_without_llm(monkeypatch):
    monkeypatch.setattr(A, "chat", lambda *a, **k: pytest.fail("LLM called"))
    r = A.ask_agent("كم مل من المبيد لكل لتر للطماطم؟", {"lang": "ar"})
    assert "الإرشاد" in r["answer"]


def test_dose_in_model_output_is_removed(fake_llm):
    fake_llm([final("Spray 20 ml per litre of water.")])
    r = A.ask_agent("my tomato leaves have spots", {"lang": "en"})
    assert "20" not in r["answer"] and "extension office" in r["answer"]


def test_cache_hit_and_invalidation_when_prompt_changes(fake_llm, monkeypatch, tmp_path):
    pdir = tmp_path / "prompts"
    shutil.copytree(C.PROMPT_DIR, pdir)
    monkeypatch.setattr(C, "PROMPT_DIR", pdir)
    calls = fake_llm([final("Hello farmer.")])
    A.ask_agent("q", {"lang": "en"})
    n = len(calls)
    assert A.ask_agent("q", {"lang": "en"})["meta"]["cached"] is True and len(calls) == n
    v1 = A.prompt_version()
    (pdir / "system.txt").write_text((pdir / "system.txt").read_text(encoding="utf-8") + "\nNew rule.",
                                     encoding="utf-8")
    assert A.prompt_version() != v1
    r = A.ask_agent("q", {"lang": "en"})
    assert r["meta"]["cached"] is False and len(calls) == n + 1


def test_all_providers_down_gives_friendly_answer(monkeypatch):
    def boom(messages, tools=None):
        raise A.AllProvidersFailed("down")
    monkeypatch.setattr(A, "chat", boom)
    r = A.ask_agent("q", {"lang": "ar"})
    assert r["meta"]["error"] and r["answer"]
    assert not list(C.CACHE_DIR.glob("ans_*")) if C.CACHE_DIR.exists() else True


def test_bad_json_from_model_is_survivable(fake_llm):
    fake_llm([{"content": "just plain text"}])
    r = A.ask_agent("q", {"lang": "en"})
    assert r["answer"] == "just plain text" and r["confidence"] == "low"


# ------------------------------------------------------------------ provider fallback chain
class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._body = code, body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self._body


def test_fallback_gemini_to_groq_to_openrouter(monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setenv(k, "test-key")
    monkeypatch.setattr(llm, "_down_until", {})
    seen = []

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.append(url)
        if "googleapis" in url:
            return _Resp(429)
        if "groq" in url:
            raise ConnectionError("groq down")
        return _Resp(200, {"choices": [{"message": {"content": "hi"}}]})
    monkeypatch.setattr(llm.requests, "post", fake_post)
    msg, name = llm.chat([{"role": "user", "content": "x"}])
    assert name == "openrouter" and msg["content"] == "hi" and len(seen) == 3
    with pytest.raises(llm.AllProvidersFailed):          # gemini + groq cooling down, openrouter fails
        monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(500))
        llm.chat([{"role": "user", "content": "x"}])


def test_no_keys_means_all_failed(monkeypatch):
    monkeypatch.setattr(llm, "_down_until", {})
    with pytest.raises(llm.AllProvidersFailed, match="no API key"):
        llm.chat([{"role": "user", "content": "x"}])


def test_secrets_come_before_env(monkeypatch):
    fake_st = types.ModuleType("streamlit")
    fake_st.secrets = {"GROQ_API_KEY": "from-secrets"}
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setenv("GROQ_API_KEY", "from-env")
    monkeypatch.setenv("GEMINI_API_KEY", "only-env")
    assert C.get_secret("GROQ_API_KEY") == "from-secrets" and C.get_secret("GEMINI_API_KEY") == "only-env"


# ------------------------------------------------------------------ mock mode
@needs_team
def test_mock_mode_uses_real_tools_and_no_llm(monkeypatch):
    monkeypatch.setattr(C, "USE_MOCK", True)
    monkeypatch.setattr(A, "chat", lambda *a, **k: pytest.fail("LLM was called in mock mode"))
    r = A.ask_agent("গম আর টমেটোর পরে কী চাষ করব?", {"lang": "bn"})
    from .. import team_bridge
    ex = team_bridge.load().recommend(["wheat", "tomato"])["existing"]["total_score"]
    assert r["meta"]["provider"] == "mock" and r["compare"]["existing_total"] == ex
    r = A.ask_agent("who won the football match?", {"lang": "en"})
    assert "only help with farming" in r["answer"]


@needs_team
def test_whatif_action_button(monkeypatch):
    monkeypatch.setattr(C, "USE_MOCK", True)
    act = {"tool": "rotation_what_if", "args": {"existing_rotation": ["wheat", "tomato"], "irrigation_change_pct": -50}}
    r = A.ask_agent("What if I have half the irrigation water?", {"lang": "en", "action": act})
    assert r["meta"]["tools_used"] == ["rotation_what_if"] and r["whatif"]["scenario"]["irrigation_change_pct"] == -50


@needs_team
def test_voice_tool_behind_flag(fake_llm, monkeypatch):
    monkeypatch.setattr(C, "ENABLE_VOICE_TOOL", True)
    fake_llm([tool_call("summary_for_voice", {"existing_rotation": ["wheat", "tomato"]}), final("Listen below.")])
    r = A.ask_agent("read it to me: wheat then tomato", {"lang": "en"})
    assert r["voice_text"].startswith("Your current rotation, wheat, tomato, scores ")
