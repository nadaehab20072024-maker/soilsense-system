import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

CORE_COLS = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M", "PRECTOTCORR"]
OPTIONAL_COLS = ["ALLSKY_SFC_SW_DWN"]
MAX_GAP_DAYS = 5


def parse_raw(path: Path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("YEAR"))
    header = "\n".join(lines[:start])
    lat = float(re.search(r"latitude\s+(-?[\d.]+)", header).group(1))
    lon = float(re.search(r"longitude\s+(-?[\d.]+)", header).group(1))
    m = re.search(r"=\s*([\d.]+)\s*meters", header)
    elev = float(m.group(1)) if m else None

    df = pd.read_csv(path, skiprows=start).dropna(axis=1, how="all")
    df["date"] = pd.to_datetime(df["YEAR"].astype(str) + "-" + df["DOY"].astype(str), format="%Y-%j")
    df = df.drop(columns=["YEAR", "DOY"]).set_index("date").sort_index()
    df = df.replace(-999, np.nan)
    cols = [c for c in CORE_COLS + OPTIONAL_COLS if c in df.columns]
    return df[cols], lat, lon, elev


def clean(df: pd.DataFrame):

    missing_before = int(df.isna().sum().sum())
    df = df.interpolate(limit=MAX_GAP_DAYS, limit_area="inside")
    filled = missing_before - int(df.isna().sum().sum())
    n_before = len(df)
    ok = df[CORE_COLS].notna().all(axis=1)
    df = df.loc[: ok[ok].index.max()]            
    return df, filled, n_before - len(df)


def main():
    C.PROC_DIR.mkdir(parents=True, exist_ok=True)
    sites = []
    for path in sorted(C.RAW_DIR.glob("*.csv")):
        site_id = path.stem.split("_")[0]
        df, lat, lon, elev = parse_raw(path)
        df, filled, trimmed = clean(df)
        df.round(3).to_csv(C.PROC_DIR / f"{site_id}.csv.gz", index_label="date")
        sites.append(dict(id=site_id, lat=lat, lon=lon, elevation_m=elev,
                          start=str(df.index.min().date()), end=str(df.index.max().date()),
                          n_days=len(df), filled_values=filled, trimmed_trailing_days=trimmed,
                          columns=list(df.columns), source_file=path.name))
        print(f"{site_id}: {lat}N {lon}E  {df.index.min().date()} -> {df.index.max().date()}  "
              f"{len(df)} days, interpolated {filled} values, trimmed {trimmed} trailing days")
    (C.PROC_DIR / "sites.json").write_text(json.dumps(sites, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
