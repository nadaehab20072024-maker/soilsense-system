"""Coming weather for the farm: Open-Meteo forecast (free, no key) + CAMS dust, turned into
6 severity levels from 0 (ideal, green) to 5 (extreme, red), plus alerts by level.

No LLM here: every number shown comes from the forecast response. Thresholds live in config.py
(wind = Beaufort scale, dust = meteoblue classes, rain and heat = first guesses, needs expert review).
Forecasts are model output, NOT official warnings: the UI always says so."""
from __future__ import annotations

import datetime as dt
import time

import requests

from . import config as C

# level -> colour (red ... green) and short name key (translated in i18n_farm)
LEVELS = {
    0: dict(colour="#2E7D32", name="lvl_0"),   # ideal
    1: dict(colour="#7CB342", name="lvl_1"),   # good
    2: dict(colour="#FBC02D", name="lvl_2"),   # changeable / take care
    3: dict(colour="#FB8C00", name="lvl_3"),   # dangerous
    4: dict(colour="#E65100", name="lvl_4"),   # very dangerous
    5: dict(colour="#C62828", name="lvl_5"),   # extreme
}

# WMO weather code (Open-Meteo "weather_code") -> (condition key, level)
WMO = {0: ("sunny", 0), 1: ("mostly_sunny", 1), 2: ("partly_cloudy", 1), 3: ("cloudy", 1),
       45: ("fog", 2), 48: ("fog", 2), 51: ("drizzle", 2), 53: ("drizzle", 2), 55: ("drizzle", 2),
       56: ("drizzle", 2), 57: ("drizzle", 2), 61: ("light_rain", 2), 63: ("rain", 2), 65: ("heavy_rain", 3),
       66: ("rain", 3), 67: ("heavy_rain", 3), 71: ("snow", 3), 73: ("snow", 3), 75: ("snow", 3), 77: ("snow", 3),
       80: ("showers", 2), 81: ("showers", 2), 82: ("heavy_rain", 3), 85: ("snow", 3), 86: ("snow", 3),
       95: ("thunderstorm", 3), 96: ("thunderstorm_hail", 4), 99: ("thunderstorm_hail", 4)}

DAILY_VARS = ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
              "precipitation_probability_max", "wind_gusts_10m_max", "et0_fao_evapotranspiration"]

_CACHE: dict = {}


def _band(value, bounds) -> int:
    """bounds = lower limits of levels 2,3,4,5 -> returns 0 or 2..5."""
    if value is None:
        return 0
    lvl = 0
    for i, b in enumerate(bounds):
        if value >= b:
            lvl = i + 2
    return lvl


# ------------------------------------------------------------------ download
def _get(url, params):
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_forecast(lat: float, lon: float) -> dict:
    """Daily forecast (past + coming days) + daily max dust. Returns {"available": False, ...} on failure."""
    if C.WEATHER_DEMO:
        return demo_forecast()
    key = (round(float(lat), 2), round(float(lon), 2))
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < C.FORECAST_TTL_S:
        return hit[1]
    try:
        f = _get(C.FORECAST_URL, dict(latitude=lat, longitude=lon, daily=",".join(DAILY_VARS), timezone="auto",
                                      past_days=C.FORECAST_PAST_DAYS, forecast_days=C.FORECAST_DAYS))
    except Exception as e:
        return dict(available=False, error=f"{type(e).__name__}: {e}")
    out = dict(available=True, demo=False, lat=lat, lon=lon, timezone=f.get("timezone"),
               daily=f.get("daily", {}), units=f.get("daily_units", {}), dust_by_day={},
               source="Open-Meteo forecast (national weather models)")
    try:   # dust is optional: forecast still works without it
        a = _get(C.AIR_QUALITY_URL, dict(latitude=lat, longitude=lon, hourly="dust", timezone="auto",
                                          past_days=min(C.FORECAST_PAST_DAYS, 7), forecast_days=5))
        out["dust_by_day"] = daily_max(a.get("hourly", {}).get("time", []), a.get("hourly", {}).get("dust", []))
        out["source"] += " + CAMS dust (Open-Meteo Air Quality)"
    except Exception as e:
        out["dust_error"] = f"{type(e).__name__}: {e}"
    _CACHE[key] = (time.time(), out)
    return out


def daily_max(times, values) -> dict:
    best: dict = {}
    for t, v in zip(times, values):
        if v is None:
            continue
        d = t[:10]
        best[d] = max(best.get(d, v), v)
    return {d: round(v, 0) for d, v in best.items()}


# ------------------------------------------------------------------ severity
def classify_day(code=None, tmax=None, rain=None, gust=None, dust=None) -> dict:
    """-> {level, condition, hazards:[{key, level, value}], top}. The day's level is its worst hazard."""
    cond, base = WMO.get(int(code), ("unknown", 0)) if code is not None else ("unknown", 0)
    hazards = []
    if base >= 2:
        hazards.append(dict(key=cond, level=base, value=code))
    checks = [("wind", gust, C.WIND_GUST_KMH), ("rain", rain, C.RAIN_MM_DAY), ("heat", tmax, C.HEAT_TMAX_C),
              ("dust", dust, C.DUST_UGM3)]
    for key, val, bounds in checks:
        lvl = _band(val, bounds)
        if lvl:
            hazards.append(dict(key=f"{key}_{lvl}", level=lvl, value=val))
    # light dust (meteoblue "light green" class) makes an otherwise sunny day "good", not "ideal"
    level = max([h["level"] for h in hazards] + [base])
    if level == 0 and dust is not None and dust >= C.DUST_LIGHT_UGM3:
        level = 1
        hazards.append(dict(key="dust_1", level=1, value=dust))
    hazards.sort(key=lambda h: -h["level"])
    top = hazards[0]["key"] if hazards and hazards[0]["level"] >= level else cond
    return dict(level=level, condition=cond, hazards=hazards, top=top, colour=LEVELS[level]["colour"])


def build_days(fc: dict, today: dt.date | None = None) -> list[dict]:
    """One row per day with values + severity. `when` = past / today / future."""
    if not fc.get("available"):
        return []
    d = fc["daily"]
    today = today or dt.date.today()
    days = []
    for i, date in enumerate(d.get("time", [])):
        def g(k):
            v = d.get(k)
            return v[i] if v and i < len(v) else None
        dust = fc.get("dust_by_day", {}).get(date)
        sev = classify_day(g("weather_code"), g("temperature_2m_max"), g("precipitation_sum"),
                           g("wind_gusts_10m_max"), dust)
        day = dt.date.fromisoformat(date)
        when = "today" if day == today else ("past" if day < today else "future")
        days.append(dict(date=date, when=when, weather_code=g("weather_code"), tmax_c=g("temperature_2m_max"),
                         tmin_c=g("temperature_2m_min"), rain_mm=g("precipitation_sum") or 0.0,
                         rain_chance_pct=g("precipitation_probability_max"), gust_kmh=g("wind_gusts_10m_max"),
                         et0_mm=g("et0_fao_evapotranspiration"), dust_ugm3=dust, **sev))
    return days


ADVICE = {   # hazard family -> advice key (texts in i18n_farm, plain farm safety, no chemicals)
    "wind": "adv_wind", "rain": "adv_rain", "heavy_rain": "adv_rain", "showers": "adv_rain", "rain_2": "adv_rain",
    "thunderstorm": "adv_storm", "thunderstorm_hail": "adv_storm", "dust": "adv_dust", "heat": "adv_heat",
    "fog": "adv_fog", "drizzle": "adv_rain", "light_rain": "adv_rain", "snow": "adv_cold",
}


def _family(key: str) -> str:
    base = key.rsplit("_", 1)[0] if key[-1].isdigit() else key
    return base


def alerts(days: list[dict], min_level: int = 2) -> list[dict]:
    """Coming days (today included) at or above min_level, worst first."""
    out = []
    for d in days:
        if d["when"] == "past" or d["level"] < min_level:
            continue
        fams = list(dict.fromkeys(_family(h["key"]) for h in d["hazards"] if h["level"] >= min_level))
        out.append(dict(date=d["date"], level=d["level"], colour=d["colour"], hazards=d["hazards"],
                        advice=list(dict.fromkeys(ADVICE.get(f, "adv_general") for f in fams)), when=d["when"]))
    return sorted(out, key=lambda a: (-a["level"], a["date"]))


def weather_overview(lat: float, lon: float) -> dict:
    """Everything the weather panel and the report need, in one dict (also handy as an agent tool)."""
    fc = fetch_forecast(lat, lon)
    if not fc.get("available"):
        return dict(available=False, error=fc.get("error"))
    days = build_days(fc)
    coming = [d for d in days if d["when"] != "past"]
    return dict(available=True, demo=fc.get("demo", False), source=fc["source"], lat=lat, lon=lon,
                days=days, alerts=alerts(days), worst_level_coming=max([d["level"] for d in coming], default=0),
                dust_available=bool(fc.get("dust_by_day")),
                note="Model forecast, not an official warning. Always follow the national weather service.")


# ------------------------------------------------------------------ offline demo (clearly labelled)
def demo_forecast(today: dt.date | None = None) -> dict:
    """DEMO DATA, not a real forecast: one day of each level so the UI can be shown offline."""
    today = today or dt.date.today()
    rows = [  # code, tmax, tmin, rain, chance, gust, et0, dust
        (0, 36, 24, 0, 0, 20, 6.5, 30), (1, 37, 25, 0, 0, 25, 6.8, 50), (2, 39, 26, 0, 5, 30, 7.0, 35),
        (0, 41, 27, 0, 0, 28, 7.6, 60), (3, 38, 26, 0, 10, 45, 6.0, 120), (0, 46, 31, 0, 0, 35, 8.4, 200),
        (61, 33, 25, 4, 60, 40, 4.2, 40), (95, 31, 24, 30, 80, 70, 3.1, 30), (2, 35, 25, 0, 10, 30, 5.9, 600),
        (99, 29, 23, 60, 90, 95, 2.4, 25), (0, 36, 25, 0, 0, 25, 6.3, 30), (80, 30, 23, 120, 95, 125, 1.8, 20),
        (3, 34, 25, 6, 40, 30, 4.8, 30), (0, 37, 26, 0, 0, 22, 6.9, 30)]
    start = today - dt.timedelta(days=C.FORECAST_PAST_DAYS)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range(len(rows))]
    cols = list(zip(*rows))
    daily = dict(time=dates, weather_code=list(cols[0]), temperature_2m_max=list(cols[1]),
                 temperature_2m_min=list(cols[2]), precipitation_sum=list(cols[3]),
                 precipitation_probability_max=list(cols[4]), wind_gusts_10m_max=list(cols[5]),
                 et0_fao_evapotranspiration=list(cols[6]))
    return dict(available=True, demo=True, daily=daily, dust_by_day=dict(zip(dates, cols[7])),
                units={}, source="DEMO DATA (not a real forecast)")
