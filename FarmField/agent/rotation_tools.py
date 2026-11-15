"""Agent-side wrappers around the teammates' rotation tools (recommend / list_crops / get_climate /
summary_for_voice). The wrappers validate input, fill defaults from the farm profile, and attach
the facts the agent must always disclose (data quality, location coverage, caveats).
No crop knowledge or thresholds are invented here: every score comes from backend.py."""
from __future__ import annotations

import functools
import math
import re

import numpy as np
import pandas as pd

from . import config as C
from . import team_bridge
from .crops import resolve_crops

LEVEL_ORDER = ["Low", "Medium", "High"]


def _team():
    return team_bridge.load()


def supported_crops() -> list[str]:
    return list(_team().list_crops())


# ------------------------------------------------------------------ data facts (read-only, from climate.csv)
@functools.lru_cache(maxsize=1)
def rotation_site() -> dict:
    """Coordinates of the single NASA POWER point in the teammates' climate.csv (from its header)."""
    lat, lon = C.ROTATION_SITE_FALLBACK
    try:
        head = C.TEAM_CLIMATE_CSV.read_text(encoding="utf-8", errors="ignore")[:3000]
        m = re.search(r"latitude\s+(-?[\d.]+)\s+longitude\s+(-?[\d.]+)", head)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
    except OSError:
        pass
    return dict(lat=lat, lon=lon, label=C.ROTATION_SITE_LABEL["en"], labels=dict(C.ROTATION_SITE_LABEL))


def _haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def location_check(lat, lon) -> dict:
    s = rotation_site()
    if lat is None or lon is None:
        return dict(rotation_site=s, farm_known=False, scores_are_local=False, distance_km=None)
    d = round(_haversine_km(float(lat), float(lon), s["lat"], s["lon"]), 1)
    return dict(rotation_site=s, farm_known=True, distance_km=d, scores_are_local=d <= C.ROTATION_MAX_KM)


@functools.lru_cache(maxsize=1)
def data_quality() -> dict:
    """Facts about the rainfall in climate.csv, computed the same way as the teammates' climate.py
    (years with >= 350 days). Read-only. These numbers feed the standard caveats."""
    if team_bridge.load() is not None and team_bridge.IS_FAKE:
        return dict(available=False, reason="FAKE stub in use")
    try:
        text = C.TEAM_CLIMATE_CSV.read_text(encoding="utf-8").splitlines()
        start = next(i for i, line in enumerate(text) if line.startswith("YEAR"))
        df = pd.read_csv(C.TEAM_CLIMATE_CSV, skiprows=start).replace(-999, np.nan)
    except Exception as e:
        return dict(available=False, reason=f"{type(e).__name__}: {e}")
    days = df.groupby("YEAR")["DOY"].count()
    full = days[days >= 350].index
    rain = df[df["YEAR"].isin(full)].groupby("YEAR")["PRECTOTCORR"].sum()
    wet_year = int(rain.idxmax())
    rest = rain.drop(wet_year)

    def trend(s):
        return float(np.polyfit(s.index, s.values, 1)[0] / s.mean() * 100)

    clim = _team().get_climate()
    supply_factor = 1 + clim.get("rain_trend_pct", 0) / 100 * 5      # exactly what backend.py applies
    out = dict(
        available=True,
        mean_rain_mm=round(float(rain.mean()), 1),
        median_rain_mm=round(float(rain.median()), 1),
        wettest_year=wet_year, wettest_year_rain_mm=round(float(rain.max()), 0),
        wettest_day_mm=round(float(df["PRECTOTCORR"].max()), 1),
        mean_rain_without_wettest_year_mm=round(float(rest.mean()), 1),
        rain_trend_raw_pct=round(trend(rain), 2),
        rain_trend_without_wettest_year_pct=round(trend(rest), 2),
        rain_trend_used_pct=clim.get("rain_trend_pct"),
        water_supply_boost_pct=round((supply_factor - 1) * 100, 0),
        missing_values=int(df.isna().sum().sum()),
    )
    try:   # how many of the backend's candidate rotations get a perfect water score
        be = team_bridge.backend
        scores = [be.score_rotation(r, clim, {"irrigation_mm": C.DEFAULT_IRRIGATION_MM}, {})
                  for r in be.generate_rotations()]
        out["rotations_checked"] = len(scores)
        out["rotations_with_water_score_100"] = sum(s["factor_scores"]["water"] >= 100 for s in scores)
    except Exception:
        pass
    return out


# ------------------------------------------------------------------ caveats (always attached)
def standard_caveats(result: dict | None = None) -> list[dict]:
    """Codes + English text. The UI/agent translate by code (i18n.CAVEATS). Numbers come from data_quality()."""
    q = data_quality()
    cav = [
        dict(code="placeholder_scores", text="The crop values in the scoring rules are rough placeholders "
             "(backend.py says 'Replace with real ones later'), not agronomic measurements."),
        dict(code="no_soil_data", text="There is no soil measurement in the data; the soil score comes only "
             "from crop traits (legume before a hungry crop, deep roots)."),
        dict(code="irrigation_estimate", text="The irrigation amount is a farmer estimate."),
    ]
    if q.get("available"):
        cav.append(dict(code="reanalysis_rain", text=(
            f"Rainfall is a NASA POWER (MERRA-2) reanalysis estimate, not a rain gauge. {q['wettest_year']} shows "
            f"{q['wettest_year_rain_mm']:.0f} mm, which looks overstated. Mean {q['mean_rain_mm']} mm vs median "
            f"{q['median_rain_mm']} mm.")))
        cav.append(dict(code="water_optimistic", text=(
            f"The water score is likely optimistic: the rain trend used is {q['rain_trend_used_pct']}% "
            f"(raw {q['rain_trend_raw_pct']}%, only {q['rain_trend_without_wettest_year_pct']}% without "
            f"{q['wettest_year']}), which raises the water supply by {q['water_supply_boost_pct']:.0f}%."
            + (f" {q['rotations_with_water_score_100']} of {q['rotations_checked']} rotations get water score 100."
               if "rotations_checked" in q else ""))))
    else:
        cav.append(dict(code="reanalysis_rain", text="Rainfall is a NASA POWER (MERRA-2) reanalysis estimate."))
        cav.append(dict(code="water_optimistic", text="The water score is likely optimistic."))
    gaps = []
    if result:
        for r in [result.get("existing"), *(result.get("alternatives") or [])]:
            gaps += (r or {}).get("data_gaps") or []
    cav.append(dict(code="data_gaps", text=("Data gaps reported by the tool: " + "; ".join(dict.fromkeys(gaps)))
                    if gaps else "The tool reported no data gaps, but that does NOT mean the data is complete."))
    return cav


# ------------------------------------------------------------------ helpers
def _weight(v):
    """Accept the 3 farmer choices or any number; keep within what backend.py handles sensibly."""
    if v is None:
        return None
    if isinstance(v, str):
        v = C.PRIORITY_CHOICES.get(v.strip().lower().replace(" ", "_"), v)
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    # backend normalises by the sum of weights; negative weights give meaningless scores.
    return min(max(v, min(C.PRIORITY_CHOICES.values())), max(C.PRIORITY_CHOICES.values()))


def _irrigation(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return min(max(v, 0.0), float(C.IRRIGATION_MAX_MM))


def explain_risk(level: str) -> dict:
    """Low risk = good. Maps the backend's level to a plain meaning + colour (no new thresholds)."""
    return {"Low": dict(level="Low", colour="green", meaning="low risk (good)"),
            "Medium": dict(level="Medium", colour="orange", meaning="some risk"),
            "High": dict(level="High", colour="red", meaning="high risk (needs attention)")}.get(
        level, dict(level=str(level), colour="grey", meaning="unknown"))


def build_compare(results: dict) -> dict | None:
    alts = results.get("alternatives") or []
    if not alts:
        return None
    ex, best = results["existing"], alts[0]
    rows = []
    for f in ("soil", "water", "climate", "income"):
        rows.append(dict(factor=f, existing_score=ex["factor_scores"][f], best_score=best["factor_scores"][f],
                         existing_risk=ex["risk_meters"][f], best_risk=best["risk_meters"][f],
                         difference=round(best["factor_scores"][f] - ex["factor_scores"][f], 1)))
    return dict(existing_rotation=ex["rotation"], best_rotation=best["rotation"],
                existing_total=ex["total_score"], best_total=best["total_score"],
                total_difference=round(best["total_score"] - ex["total_score"], 1), rows=rows)


def build_replay(results: dict, clim: dict) -> dict:
    wy = results.get("worst_year") or {}
    alts, walts = results.get("alternatives") or [], wy.get("alternatives") or []
    options = [dict(rotation=a["rotation"], normal_total=a["total_score"], driest_total=w["total_score"],
                    normal_water=a["factor_scores"]["water"], driest_water=w["factor_scores"]["water"])
               for a, w in zip(alts, walts)]
    ex, wex = results["existing"], wy.get("existing") or results["existing"]
    best_normal = alts[0]["rotation"] if alts else None
    best_driest = max(walts, key=lambda r: r["total_score"])["rotation"] if walts else None
    return dict(driest_year=clim.get("worst_year"), driest_year_rain_mm=clim.get("worst_year_rain_mm"),
                average_rain_mm=clim.get("annual_rain_mm"),
                median_rain_mm=data_quality().get("median_rain_mm"),     # mean is inflated by one extreme year
                existing=dict(rotation=ex["rotation"], normal_total=ex["total_score"],
                              driest_total=wex["total_score"], normal_water=ex["factor_scores"]["water"],
                              driest_water=wex["factor_scores"]["water"]),
                options=options, ranking_changes_in_driest_year=bool(best_normal and best_driest != best_normal),
                best_in_driest_year=best_driest,
                note="Same rotations re-scored with the driest year's rainfall (not re-ranked).")


def _validate_rotation(existing_rotation):
    valid = supported_crops()
    if isinstance(existing_rotation, str):
        existing_rotation = [w for w in re.split(r"[,،;/]+|\s+(?:and|و|ও|aur|और)\s+", existing_rotation) if w.strip()]
    if not existing_rotation:
        return None, dict(error="empty_rotation", message="Name at least one crop you grow now.",
                          supported_crops=valid)
    ok, bad = resolve_crops(existing_rotation, valid)
    if bad:
        return None, dict(error="unsupported_crop", unsupported=bad, supported_crops=valid,
                          message="These crops are not supported by the rotation tool: " + ", ".join(bad))
    return ok, None


# ------------------------------------------------------------------ the tools the LLM can call
def recommend(existing_rotation, irrigation_mm=None, water=None, soil=None, income=None,
              _profile=None, _ctx=None, **_):
    """Wrapper around agent_tools.recommend(). Missing values come from the farm profile, then defaults."""
    rot, err = _validate_rotation(existing_rotation)
    if err:
        return err
    prof = _profile or {}
    used, defaults = {}, []
    for k in C.PRIORITY_KEYS:
        v = _weight({"water": water, "soil": soil, "income": income}[k])
        v = v if v is not None else _weight(prof.get(k))
        if v is None:
            v = C.DEFAULT_PRIORITY
            defaults.append(k)
        used[k] = v
    irr = _irrigation(irrigation_mm)
    irr = irr if irr is not None else _irrigation(prof.get("irrigation_mm"))
    if irr is None:
        irr = float(C.DEFAULT_IRRIGATION_MM)
        defaults.append("irrigation_mm")
    try:
        res = _team().recommend(rot, irrigation_mm=irr, **used)
    except KeyError as e:          # should not happen after validation; never crash the chat
        return dict(error="unsupported_crop", unsupported=[str(e)], supported_crops=supported_crops())
    clim = _team().get_climate()
    ctx = _ctx or {}
    out = dict(
        existing=res["existing"], alternatives=res["alternatives"], worst_year=res["worst_year"],
        inputs_used=dict(existing_rotation=rot, irrigation_mm=irr, **used),
        defaults_used=defaults,
        score_scale="scores are 0-100 (higher is better)", score_scale_max=100,
        risk_meter_legend="Low = low risk = good; Medium = some risk; High = high risk.",
        location=location_check(ctx.get("lat"), ctx.get("lon")),
        compare=build_compare(res), replay=build_replay(res, clim),
        caveats=standard_caveats(res), data_quality=data_quality(),
        fake_stub=team_bridge.IS_FAKE,
    )
    return out


def list_crops(**_):
    return dict(crops=supported_crops(), fake_stub=team_bridge.IS_FAKE,
                note="Only these crops are supported by the rotation tool.")


def get_climate(**_):
    clim = _team().get_climate()
    return dict(**clim, rotation_site=rotation_site(), data_quality=data_quality(),
                fake_stub=team_bridge.IS_FAKE,
                note="Climate summary of the single NASA POWER point used by the rotation tool.")


def rotation_what_if(existing_rotation, rain_change_pct=0.0, irrigation_change_pct=0.0, temp_delta_c=0.0,
                     _profile=None, _ctx=None, **_):
    """Re-score with less/more rain or irrigation via the teammates' backend.get_recommendations().
    Temperature does not enter backend scores (its 'climate' factor uses crop traits only), so for
    'hotter' we also run the per-location heat/water what-if and say that rotation scores do not change."""
    base = recommend(existing_rotation, _profile=_profile, _ctx=_ctx)
    if "error" in base:
        return base
    inp = base["inputs_used"]
    r = float(rain_change_pct or 0) / 100
    i = float(irrigation_change_pct or 0) / 100
    clim = dict(_team().get_climate())
    clim["annual_rain_mm"] = clim["annual_rain_mm"] * (1 + r)
    clim["worst_year_rain_mm"] = clim["worst_year_rain_mm"] * (1 + r)
    irr = max(inp["irrigation_mm"] * (1 + i), 0.0)
    pri = {k: inp[k] for k in C.PRIORITY_KEYS}
    be = team_bridge.backend
    new = be.get_recommendations(clim, {"irrigation_mm": irr}, pri, inp["existing_rotation"])

    def brief(x):
        return dict(rotation=x["rotation"], total_score=x["total_score"], water_score=x["factor_scores"]["water"],
                    water_risk=x["risk_meters"]["water"])
    out = dict(scenario=dict(rain_change_pct=rain_change_pct, irrigation_change_pct=irrigation_change_pct,
                             temp_delta_c=temp_delta_c, irrigation_mm_after=round(irr, 1)),
               before=dict(existing=brief(base["existing"]), best=brief(base["alternatives"][0])),
               after=dict(existing=brief(new["existing"]), best=brief(new["alternatives"][0])),
               best_rotation_changes=new["alternatives"][0]["rotation"] != base["alternatives"][0]["rotation"],
               score_scale_max=100, inputs_used=inp, defaults_used=base["defaults_used"], location=base["location"],
               caveats=base["caveats"], fake_stub=team_bridge.IS_FAKE)
    if temp_delta_c:
        out["temperature_note"] = ("Rotation scores do not change with temperature in the current scoring rules; "
                                   "see heat_and_water for the effect of heat at this location.")
        try:
            from .local_climate import simulate_what_if
            s = rotation_site()
            ctx = _ctx or {}
            out["heat_and_water"] = simulate_what_if(ctx.get("lat", s["lat"]), ctx.get("lon", s["lon"]),
                                                     temp_delta_c=temp_delta_c, rain_change_pct=rain_change_pct)
        except Exception as e:
            out["heat_and_water"] = dict(error=f"{type(e).__name__}: {e}")
    return out


def summary_for_voice(existing_rotation, _profile=None, _ctx=None, **_):
    """Behind config.ENABLE_VOICE_TOOL (default OFF). The teammates' summary_for_voice(results) needs a
    results dict, which the LLM cannot pass, so this runs recommend() first. English only."""
    base = recommend(existing_rotation, _profile=_profile, _ctx=_ctx)
    if "error" in base:
        return base
    res = {k: base[k] for k in ("existing", "alternatives", "worst_year")}
    return dict(voice_text=_team().summary_for_voice(res), language="en", fake_stub=team_bridge.IS_FAKE)
