"""Fetch daily NASA POWER data for any point (free, no key). Cached on disk.
Returns None on ANY failure so the caller can fall back to the stored files."""
import datetime as dt
import logging

import pandas as pd
import requests

from . import config as C

log = logging.getLogger("soilsense.power")
URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = "T2M,T2M_MAX,T2M_MIN,RH2M,WS2M,PRECTOTCORR,ALLSKY_SFC_SW_DWN"


def fetch_daily(lat: float, lon: float):
    cache = C.CACHE_DIR / f"power_{lat:.2f}_{lon:.2f}.csv"
    try:
        if cache.exists():
            return pd.read_csv(cache, index_col=0, parse_dates=True)
        end = dt.date.today() - dt.timedelta(days=7)
        r = requests.get(URL, timeout=60, params=dict(
            parameters=PARAMS, community="AG", latitude=round(lat, 4), longitude=round(lon, 4),
            start="20000101", end=end.strftime("%Y%m%d"), format="JSON"))
        r.raise_for_status()
        data = r.json()["properties"]["parameter"]
        df = pd.DataFrame(data)
        df.index = pd.to_datetime(df.index, format="%Y%m%d")
        df.index.name = "date"
        df = df.replace(-999, float("nan")).interpolate(limit=5, limit_area="inside").dropna(subset=["T2M"])
        C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.round(3).to_csv(cache)
        return df
    except Exception as e:  # network blocked, API down, unexpected format...
        log.warning("NASA POWER fetch failed: %s", e)
        return None
