"""Wrappers around the teammates' tools, schemas, crop handling, bridge."""
import json
import os
import subprocess
import sys


from soilsense_agent import config as C
from soilsense_agent import rotation_tools as RT
from soilsense_agent import team_bridge
from soilsense_agent.crops import resolve_crop, resolve_crops
from soilsense_agent.tools_schema import build_tools, validate_args

from .conftest import ROOT, needs_team

CROPS10 = ["wheat", "barley", "sorghum", "pearl_millet", "cowpea", "chickpea", "tomato", "onion", "sesame", "okra"]


# ------------------------------------------------------------------ bridge
@needs_team
def test_bridge_imports_real_module_without_changing_cwd_or_printing(capsys):
    cwd = os.getcwd()
    team = team_bridge.load()
    assert not team_bridge.IS_FAKE and os.getcwd() == cwd
    assert team_bridge.IMPORT_STDOUT_CHARS > 0           # climate.py printed, and it was silenced
    assert capsys.readouterr().out == ""
    assert team.list_crops() == CROPS10


def test_fake_stub_when_import_fails():
    code = ("import sys; sys.path.insert(0, %r); from soilsense_agent import team_bridge as b; "
            "from soilsense_agent import rotation_tools as RT; b.load(); "
            "r = RT.recommend(['wheat','tomato']); "
            "print(b.IS_FAKE, r['fake_stub'], 'FAKE' in r['existing']['data_gaps'][0])") % str(ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={**os.environ, "SS_AGENT_FORCE_FAKE": "true"}, cwd="/")
    assert out.stdout.split() == ["True", "True", "True"], out.stderr


# ------------------------------------------------------------------ crop words
def test_crop_words_in_three_languages_map_to_valid_names():
    assert resolve_crop("القمح", CROPS10) == "wheat"
    assert resolve_crop("طماطم", CROPS10) == "tomato"
    assert resolve_crop("Tomatoes", CROPS10) == "tomato"
    assert resolve_crop("ছোলা", CROPS10) == "chickpea"
    assert resolve_crop("pearl millet", CROPS10) == "pearl_millet"
    assert resolve_crop("ذرة", CROPS10) is None            # ambiguous on purpose (maize or sorghum)
    assert resolve_crops(["قمح", "mango"], CROPS10) == (["wheat"], ["mango"])


@needs_team
def test_invalid_crop_never_raises_keyerror():
    r = RT.recommend(["wheat", "mango"])
    assert r["error"] == "unsupported_crop" and r["unsupported"] == ["mango"] and r["supported_crops"] == CROPS10
    assert RT.recommend([])["error"] == "empty_rotation"


# ------------------------------------------------------------------ recommend wrapper
@needs_team
def test_recommend_wrapper_matches_team_output_and_reports_defaults():
    r = RT.recommend(["قمح", "طماطم"])
    raw = team_bridge.team.recommend(["wheat", "tomato"])
    assert r["existing"] == raw["existing"] and r["alternatives"] == raw["alternatives"]
    assert r["existing"]["total_score"] == 68.8
    assert r["defaults_used"] == ["water", "soil", "income", "irrigation_mm"]
    assert r["inputs_used"]["irrigation_mm"] == 250.0
    assert r["compare"]["best_rotation"] == ["cowpea", "tomato", "sesame"] and len(r["compare"]["rows"]) == 4
    assert r["replay"]["driest_year"] == 2023 and r["replay"]["ranking_changes_in_driest_year"] is True
    codes = [c["code"] for c in r["caveats"]]
    assert codes == ["placeholder_scores", "no_soil_data", "irrigation_estimate", "reanalysis_rain",
                     "water_optimistic", "data_gaps"]
    assert "does NOT mean the data is complete" in r["caveats"][-1]["text"]


@needs_team
def test_profile_values_are_used_and_weights_stay_in_range():
    r = RT.recommend(["wheat"], _profile={"water": 2.0, "irrigation_mm": 100})
    assert r["inputs_used"]["water"] == 2.0 and r["inputs_used"]["irrigation_mm"] == 100
    assert r["defaults_used"] == ["soil", "income"]
    r = RT.recommend(["wheat"], water=-5, soil="very_important", irrigation_mm=99999)
    assert r["inputs_used"]["water"] == 0.5 and r["inputs_used"]["soil"] == 2.0
    assert r["inputs_used"]["irrigation_mm"] == C.IRRIGATION_MAX_MM


@needs_team
def test_data_quality_matches_verified_facts():
    q = RT.data_quality()
    assert q["mean_rain_mm"] == 221.3 and q["median_rain_mm"] == 102.2 and q["wettest_year"] == 2024
    assert q["rain_trend_raw_pct"] == 10.42 and q["rain_trend_without_wettest_year_pct"] == 1.51
    assert q["water_supply_boost_pct"] == 25
    assert q["rotations_with_water_score_100"] == q["rotations_checked"] == 144


@needs_team
def test_location_check():
    assert RT.location_check(23.7, 57.9)["scores_are_local"] is True
    far = RT.location_check(17.02, 54.08)
    assert far["scores_are_local"] is False and far["distance_km"] > 500
    assert RT.location_check(None, None)["farm_known"] is False


@needs_team
def test_rotation_what_if_less_water_lowers_or_keeps_scores_and_heat_is_explained():
    r = RT.rotation_what_if(["wheat", "tomato"], irrigation_change_pct=-100)
    assert r["after"]["existing"]["water_score"] < r["before"]["existing"]["water_score"]
    h = RT.rotation_what_if(["wheat", "tomato"], temp_delta_c=2)
    assert h["after"]["existing"]["total_score"] == h["before"]["existing"]["total_score"]
    assert "do not change with temperature" in h["temperature_note"]
    assert h["heat_and_water"]["after"]["heat_days"] >= h["heat_and_water"]["before"]["heat_days"]


# ------------------------------------------------------------------ schemas
def test_schema_built_from_real_signature():
    schema, funcs, sources = build_tools()
    rec = next(t["function"] for t in schema if t["function"]["name"] == "recommend")
    props = rec["parameters"]["properties"]
    assert list(props) == ["existing_rotation", "irrigation_mm", "water", "soil", "income"]
    assert rec["parameters"]["required"] == ["existing_rotation"]
    assert props["existing_rotation"]["items"]["enum"] == RT.supported_crops()
    assert props["water"]["enum"] == [0.5, 1.0, 2.0]
    assert set(funcs) == set(sources) and "summary_for_voice" not in funcs      # voice OFF by default
    json.dumps(schema)                                                            # serialisable


def test_voice_tool_only_behind_flag(monkeypatch):
    monkeypatch.setattr(C, "ENABLE_VOICE_TOOL", True)
    _s, funcs, _src = build_tools()
    assert "summary_for_voice" in funcs


def test_validate_args():
    schema, _f, _s = build_tools()
    assert validate_args(schema, "recommend", {"existing_rotation": ["wheat"], "water": 2.0}) == []
    assert validate_args(schema, "recommend", {}) == ["missing existing_rotation"]
    probs = validate_args(schema, "recommend", {"existing_rotation": ["mango"], "water": 7, "foo": 1})
    assert any("not supported" in p for p in probs) and any("water must be one of" in p for p in probs)
    assert any("unknown argument foo" in p for p in probs)
    assert validate_args(schema, "nope", {}) == ["unknown tool nope"]
