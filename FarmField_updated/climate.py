import numpy as np
import pandas as pd
from scipy.stats import theilslopes

# --- data-quality settings (explain these in the README) -------------------
MAX_PLAUSIBLE_DAILY_MM = 200   # above this, a daily rainfall value is treated as suspect (next-highest day in the record is about 152 mm)
SPIKE_WINDOW_DAYS = 10         # days around a suspect value that are checked as part of the same episode
SPIKE_MIN_MM = 20              # inside that window, only days above this are replaced


def load_power_csv(path):
    """Read a NASA POWER daily CSV, skipping the description lines at the top."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    header_row = next(i for i, line in enumerate(lines) if line.startswith("YEAR"))
    df = pd.read_csv(path, skiprows=header_row)
    df = df.replace(-999, np.nan)          # POWER uses -999 for missing values
    return df


def clean_rainfall(df):
    """Find and correct suspect daily rainfall values.

    Rule: any day above MAX_PLAUSIBLE_DAILY_MM starts a 'spike episode'. Days within
    +/- SPIKE_WINDOW_DAYS of it that also exceed SPIKE_MIN_MM are replaced with the
    median rainfall for that day of the year across all other years (about 0 mm in an
    arid region). The original values are kept in PRECTOTCORR_RAW.

    Returns (cleaned_df, corrections) where corrections lists what was changed."""
    df = df.copy()
    df["PRECTOTCORR_RAW"] = df["PRECTOTCORR"]
    df["_t"] = df["YEAR"] * 366 + df["DOY"]               # one number that orders days in time

    seeds = df[df["PRECTOTCORR"] > MAX_PLAUSIBLE_DAILY_MM]
    suspect = pd.Series(False, index=df.index)
    for _, s in seeds.iterrows():
        near = (df["_t"] - s["_t"]).abs() <= SPIKE_WINDOW_DAYS
        suspect |= near & (df["PRECTOTCORR"] > SPIKE_MIN_MM)

    # typical rain for each day of the year, taken from days that are not suspect
    typical = df[~suspect].groupby("DOY")["PRECTOTCORR"].median()
    df.loc[suspect, "PRECTOTCORR"] = df.loc[suspect, "DOY"].map(typical).fillna(0.0)

    corrections = []
    for year, g in df[suspect].groupby("YEAR"):
        corrections.append({
            "year": int(year),
            "days_corrected": int(len(g)),
            "first_doy": int(g["DOY"].min()),
            "last_doy": int(g["DOY"].max()),
            "raw_total_mm": round(float(g["PRECTOTCORR_RAW"].sum()), 1),
            "corrected_total_mm": round(float(g["PRECTOTCORR"].sum()), 1),
            "max_raw_daily_mm": round(float(g["PRECTOTCORR_RAW"].max()), 1),
        })
    return df.drop(columns="_t"), corrections


def climate_summary(path):
    """Turn a POWER daily file into the 'climate' dictionary the scorer needs."""
    raw = load_power_csv(path)
    df, corrections = clean_rainfall(raw)

    # keep only years with nearly full data (the current year is usually partial)
    days = df.groupby("YEAR")["DOY"].count()
    df = df[df["YEAR"].isin(days[days >= 350].index)]

    rain_by_year = df.groupby("YEAR")["PRECTOTCORR"].sum()        # mm per year (corrected)
    raw_by_year = df.groupby("YEAR")["PRECTOTCORR_RAW"].sum()     # mm per year (as downloaded)
    temp_by_year = df.groupby("YEAR")["T2M"].mean()               # average C per year

    # robust statistics: not thrown off by a single unusual year
    rain_typical = float(rain_by_year.median())
    rain_slope = theilslopes(rain_by_year.values, rain_by_year.index)[0]
    temp_slope = theilslopes(temp_by_year.values, temp_by_year.index)[0]
    trend_pct = float(rain_slope / rain_typical * 100)

    return {
        "annual_rain_mm": round(rain_typical, 1),
        "rain_trend_pct": round(max(-5.0, min(5.0, trend_pct)), 2),   # capped at +/-5% per year
        "rain_trend_raw_pct": round(trend_pct, 2),
        "temp_trend_c": round(float(temp_slope), 3),
        "avg_temp_c": round(float(temp_by_year.mean()), 1),
        "worst_year_rain_mm": round(float(rain_by_year.min()), 1),
        "worst_year": int(rain_by_year.idxmin()),
        "years_used": f"{int(rain_by_year.index.min())}-{int(rain_by_year.index.max())}",
        # data-quality information, shown in the app and the report
        "corrections": corrections,
        "raw_rain_by_year": {int(k): round(float(v), 1) for k, v in raw_by_year.items()},
        "corrected_rain_by_year": {int(k): round(float(v), 1) for k, v in rain_by_year.items()},
    }


if __name__ == "__main__":
    out = climate_summary("climate.csv")
    for k, v in out.items():
        if k not in ("raw_rain_by_year", "corrected_rain_by_year"):
            print(k, ":", v)
