import numpy as np
import pandas as pd

def load_power_csv(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    header_row = next(i for i, line in enumerate(lines) if line.startswith("YEAR"))
    df = pd.read_csv(path, skiprows=header_row)
    df = df.replace(-999, np.nan)          
    return df

def climate_summary(path):
    df = load_power_csv(path)

   
    days = df.groupby("YEAR")["DOY"].count()
    full_years = days[days >= 350].index
    df = df[df["YEAR"].isin(full_years)]

    rain_by_year = df.groupby("YEAR")["PRECTOTCORR"].sum()    # mm per year
    temp_by_year = df.groupby("YEAR")["T2M"].mean()           # average C per year

    rain_slope = np.polyfit(rain_by_year.index, rain_by_year.values, 1)[0]
    temp_slope = np.polyfit(temp_by_year.index, temp_by_year.values, 1)[0]

    rain_mean = float(rain_by_year.mean())
    trend_pct = float(rain_slope / rain_mean * 100)

    return {
        "annual_rain_mm": round(rain_mean, 1),
        "rain_trend_pct": round(max(-5.0, min(5.0, trend_pct)), 2),   # capped, see below
        "rain_trend_raw_pct": round(trend_pct, 2),
        "temp_trend_c": round(float(temp_slope), 3),
        "avg_temp_c": round(float(temp_by_year.mean()), 1),
        "worst_year_rain_mm": round(float(rain_by_year.min()), 1),
        "worst_year": int(rain_by_year.idxmin()),
        "years_used": f"{int(rain_by_year.index.min())}-{int(rain_by_year.index.max())}",
    }
df = load_power_csv("climate.csv")
print(df.groupby("YEAR")["PRECTOTCORR"].sum().round(0))
if __name__ == "__main__":
    print(climate_summary("climate.csv"))   