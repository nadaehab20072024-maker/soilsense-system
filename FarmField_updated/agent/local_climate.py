"""Per-location climate tools (NASA POWER). No LLM in here: every number the agent says comes from these.
Used for weather/water questions. Rotation questions go to rotation_tools (teammates' backend)."""
from __future__ import annotations

import functools
import json
import math

import numpy as np
import pandas as pd

from . import config as C
from .crops import kc_for

LEVELS = ["low", "moderate", "high", "very_high"]
HAZARDS = {
    "heat": ("heat_days", f"days per year with max temperature >= {C.HEAT_DAY_C:.0f} C"),
    "water_stress": ("deficit_mm", "yearly crop-water demand (ET0) minus rainfall, mm"),
    "extreme_rain": ("rain_max_day", "wettest single day, mm"),
}


# ---------------------------------------------------------------- data access
def _haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


@functools.lru_cache(maxsize=1)
def load_sites() -> list[dict]:
    return json.loads((C.PROC_DIR / "sites.json").read_text(encoding="utf-8"))


def nearest_site(lat: float, lon: float):
    best = min(load_sites(), key=lambda s: _haversine_km(lat, lon, s["lat"], s["lon"]))
    return best, _haversine_km(lat, lon, best["lat"], best["lon"])


def _add_et0(df: pd.DataFrame, lat: float) -> pd.DataFrame:
    """Reference evapotranspiration, Hargreaves method (FAO-56 eq. 52). Needs only T and latitude."""
    df = df.copy()
    doy = df.index.dayofyear.values
    phi = math.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-math.tan(phi) * np.tan(delta), -1, 1))
    ra = (24 * 60 / np.pi) * 0.0820 * dr * (ws * math.sin(phi) * np.sin(delta)
                                           + math.cos(phi) * np.cos(delta) * np.sin(ws))
    trange = np.clip(df["T2M_MAX"] - df["T2M_MIN"], 0, None)
    df["ET0"] = (0.0023 * (df["T2M"] + 17.8) * np.sqrt(trange) * 0.408 * ra).clip(lower=0)
    return df


@functools.lru_cache(maxsize=8)
def _load_local(site_id: str) -> pd.DataFrame:
    site = next(s for s in load_sites() if s["id"] == site_id)
    df = pd.read_csv(C.PROC_DIR / f"{site_id}.csv.gz", index_col=0, parse_dates=True)
    return _add_et0(df, site["lat"])


def get_data(lat: float, lon: float):
    """-> (daily dataframe with ET0, site info dict, list of notes)."""
    lat, lon = float(lat), float(lon)
    site, dist = nearest_site(lat, lon)
    notes: list[str] = []
    if dist > C.LOCAL_SITE_MAX_KM and C.USE_POWER_API:
        from .power_api import fetch_daily
        df = fetch_daily(lat, lon)
        if df is not None:
            info = dict(id=f"power_{lat:.2f}_{lon:.2f}", lat=lat, lon=lon, distance_km=0.0,
                        source="NASA POWER API (this exact location)")
            return _add_et0(df, lat), info, notes
    if dist > C.LOCAL_SITE_MAX_KM:
        notes.append(f"No data for this exact location; using the nearest stored site, {dist:.0f} km away.")
    info = dict(id=site["id"], lat=site["lat"], lon=site["lon"], distance_km=round(dist, 1),
                source="NASA POWER stored file")
    return _load_local(site["id"]), info, notes


# ---------------------------------------------------------------- yearly stats
def yearly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(df.index.year)
    out = pd.DataFrame({
        "days": g.size(),
        "tmean": g["T2M"].mean(),
        "tmax_peak": g["T2M_MAX"].max(),
        "heat_days": g["T2M_MAX"].apply(lambda s: int((s >= C.HEAT_DAY_C).sum())),
        "rain_mm": g["PRECTOTCORR"].sum(),
        "rain_max_day": g["PRECTOTCORR"].max(),
        "et0_mm": g["ET0"].sum(),
    })
    out["deficit_mm"] = out["et0_mm"] - out["rain_mm"]
    return out


def _complete(ym: pd.DataFrame) -> pd.DataFrame:
    return ym[ym["days"] >= C.COMPLETE_YEAR_DAYS]


def _pctile(value: float, history: pd.Series) -> float:
    return float((history < value).mean() * 100 + 0.5 * (history == value).mean() * 100)


def _level(p: float) -> str:
    lo, mid, hi = C.RISK_BINS
    return LEVELS[0] if p < lo else LEVELS[1] if p < mid else LEVELS[2] if p < hi else LEVELS[3]


def _hazard_block(row, comp) -> tuple[dict, list[float]]:
    out, pcts = {}, []
    for name, (col, what) in HAZARDS.items():
        p = _pctile(float(row[col]), comp[col])
        pcts.append(p)
        out[name] = dict(value=round(float(row[col]), 1), what=what,
                         percentile_vs_history=round(p), level=_level(p))
    return out, pcts


def _quality_notes(row) -> list[str]:
    notes = []
    if row["rain_max_day"] > 200:
        notes.append("A daily rainfall above 200 mm is a satellite/reanalysis estimate and may be overstated.")
    if row["days"] < C.COMPLETE_YEAR_DAYS:
        notes.append("This year is not finished yet, so its totals are partial.")
    return notes


# ---------------------------------------------------------------- tools
def climate_summary(lat, lon, **_):
    df, site, notes = get_data(lat, lon)
    comp = _complete(yearly_metrics(df))
    slope = float(np.polyfit(comp.index.values, comp["tmean"].values, 1)[0] * 10)
    first10, last5 = comp.iloc[:10], comp.tail(5)
    wet = int(comp["rain_mm"].idxmax())
    if comp.loc[wet, "rain_mm"] > 5 * comp["rain_mm"].median():
        notes.append(f"The rainfall total for {wet} is extreme compared with other years; "
                     "the satellite/reanalysis data may overstate it.")
    return dict(
        site=site, notes=notes,
        years=f"{int(comp.index.min())}-{int(comp.index.max())}",
        mean_temp_c=round(float(comp["tmean"].mean()), 1),
        warming_c_per_decade=round(slope, 2),
        last5_vs_first10_temp_diff_c=round(float(last5["tmean"].mean() - first10["tmean"].mean()), 2),
        typical_yearly_peak_temp_c=round(float(comp["tmax_peak"].median()), 1),
        median_heat_days_per_year=int(comp["heat_days"].median()),
        median_yearly_rain_mm=round(float(comp["rain_mm"].median()), 0),
        driest_year=int(comp["rain_mm"].idxmin()), wettest_year=int(comp["rain_mm"].idxmax()),
        method="NASA POWER daily data; ET0 by Hargreaves.",
    )


def climate_risk(lat, lon, year=None, **_):
    df, site, notes = get_data(lat, lon)
    ym = yearly_metrics(df)
    comp = _complete(ym)
    year = int(year) if year else int(comp.index.max())
    if year not in ym.index:
        return dict(error=f"No data for {year}", site=site)
    row = ym.loc[year]
    hazards, pcts = _hazard_block(row, comp)
    overall = max((h["level"] for h in hazards.values()), key=LEVELS.index)
    return dict(site=site, year=year, hazards=hazards, overall_level=overall,
                overall_score_0_100=round(float(np.mean(pcts))),
                how_to_read="Levels compare this year with the same place's own history (2000 onward).",
                notes=notes + _quality_notes(row))


def water_guidance(lat, lon, crop=None, **_):
    """Monthly irrigation estimate. Crop names come from the teammates' list_crops()."""
    from .rotation_tools import supported_crops
    from .crops import resolve_crop
    df, site, notes = get_data(lat, lon)
    comp = _complete(yearly_metrics(df))
    years = list(comp.index[-5:])
    sub = df[df.index.year.isin(years)]
    valid = supported_crops()
    name = resolve_crop(crop, valid) if crop else None
    if crop and not name:
        notes.append(f"'{crop}' is not in the supported crop list {valid}; crop-neutral estimate used.")
    k = kc_for(name)
    if name and k["kc"] == 1.0 and "crop-neutral" in k["kc_source"]:
        notes.append(f"No verified FAO-56 coefficient for '{name}'; crop-neutral estimate (Kc = 1.0) used.")
    kc = k["kc"]
    by = lambda col: sub.groupby([sub.index.year, sub.index.month])[col].sum().unstack().median()
    et0, rain = by("ET0"), by("PRECTOTCORR")
    need = (kc * et0 - rain).clip(lower=0)
    months = [dict(month=int(m), et0_mm=round(float(et0[m]), 0), rain_mm=round(float(rain[m]), 1),
                   irrigation_need_mm=round(float(need[m]), 0)) for m in range(1, 13)]
    peak = sorted(months, key=lambda r: -r["irrigation_need_mm"])[:3]
    return dict(site=site, crop=name, kc_used=kc, kc_source=k["kc_source"], kc_status=k["kc_status"],
                based_on_years=[int(y) for y in years],
                monthly=months, peak_months=[p["month"] for p in peak],
                yearly_irrigation_need_mm=round(float(need.sum()), 0),
                note="Estimate from weather only (median of recent years). Real needs depend on soil, "
                     "irrigation method and crop stage.",
                notes=notes)


def replay_worst_year(lat, lon, hazard="overall", **_):
    df, site, notes = get_data(lat, lon)
    ym = yearly_metrics(df)
    comp = _complete(ym)
    cols = {k: v[0] for k, v in HAZARDS.items()}
    pct = pd.DataFrame({k: comp[c].rank(pct=True) * 100 for k, c in cols.items()})
    pct["overall"] = pct.mean(axis=1)
    if hazard not in pct.columns:
        return dict(error=f"hazard must be one of {list(pct.columns)}")
    year = int(pct[hazard].idxmax())
    sub = df[df.index.year == year]
    hist = df[df.index.year.isin(comp.index)]
    med_month = hist.groupby(hist.index.month)["T2M"].mean()
    months = []
    for m in range(1, 13):
        s = sub[sub.index.month == m]
        months.append(dict(month=m, rain_mm=round(float(s["PRECTOTCORR"].sum()), 1),
                           mean_temp_c=round(float(s["T2M"].mean()), 1),
                           typical_mean_temp_c=round(float(med_month[m]), 1)))
    hottest, wettest = sub["T2M_MAX"].idxmax(), sub["PRECTOTCORR"].idxmax()
    hazards, _p = _hazard_block(ym.loc[year], comp)
    return dict(site=site, worst_year=year, chosen_by=hazard, hazards=hazards,
                hottest_day=dict(date=str(hottest.date()), max_temp_c=round(float(sub.loc[hottest, "T2M_MAX"]), 1)),
                wettest_day=dict(date=str(wettest.date()), rain_mm=round(float(sub.loc[wettest, "PRECTOTCORR"]), 1)),
                typical_year=dict(rain_mm=round(float(comp["rain_mm"].median()), 0),
                                  heat_days=int(comp["heat_days"].median())),
                this_year=dict(rain_mm=round(float(ym.loc[year, "rain_mm"]), 0),
                               heat_days=int(ym.loc[year, "heat_days"])),
                monthly=months, notes=notes + _quality_notes(ym.loc[year]))


def simulate_what_if(lat, lon, temp_delta_c=0.0, rain_change_pct=0.0, year=None, **_):
    df, site, notes = get_data(lat, lon)
    ym = yearly_metrics(df)
    comp = _complete(ym)
    year = int(year) if year else int(comp.index.max())
    sub = df[df.index.year == year].copy()
    for c in ("T2M", "T2M_MAX", "T2M_MIN"):
        sub[c] = sub[c] + float(temp_delta_c)
    sub["PRECTOTCORR"] = sub["PRECTOTCORR"] * (1 + float(rain_change_pct) / 100)
    new = yearly_metrics(_add_et0(sub, site["lat"])).iloc[0]   # ET0 is recomputed from the shifted temperatures
    old = ym.loc[year]
    before, _a = _hazard_block(old, comp)
    after, _b = _hazard_block(new, comp)
    keys = ["heat_days", "rain_mm", "et0_mm", "deficit_mm"]
    return dict(site=site, base_year=year, scenario=dict(temp_delta_c=temp_delta_c, rain_change_pct=rain_change_pct),
                before={k: round(float(old[k]), 1) for k in keys},
                after={k: round(float(new[k]), 1) for k in keys},
                risk_before={k: v["level"] for k, v in before.items()},
                risk_after={k: v["level"] for k, v in after.items()},
                notes=notes + _quality_notes(old))
