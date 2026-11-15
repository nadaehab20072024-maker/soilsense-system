from datetime import date

WIDTH = 78


def _name(c):
    return c.replace("_", " ")


def _chain(rotation):
    return " -> ".join(_name(c) for c in rotation)


def _meters(r):
    return ", ".join(f"{k} {v.lower()}" for k, v in r["risk_meters"].items())


def _heading(text):
    return f"\n{text.upper()}\n{'-' * len(text)}"


def make_report(results, climate, farm_name="Your farm"):
    """results = output of get_recommendations(); climate = output of climate_summary()."""
    ex = results["existing"]
    alts = results["alternatives"]
    best = alts[0]
    wy = results["worst_year"]
    gain = round(best["total_score"] - ex["total_score"], 1)

    L = []
    L.append("=" * WIDTH)
    L.append(f"SOILSENSE REPORT: {farm_name}")
    L.append(f"Date: {date.today().isoformat()}")
    L.append("=" * WIDTH)

    L.append(_heading("1. Recommended action"))
    if gain > 0:
        L.append(f"Consider changing to: {_chain(best['rotation'])}")
        L.append(f"It scores {best['total_score']}/100, compared with {ex['total_score']}/100 for your "
                 f"current rotation ({_chain(ex['rotation'])}). That is {gain} points higher.")
    else:
        L.append(f"Your current rotation ({_chain(ex['rotation'])}) already scores as well as the "
                 f"alternatives. Keep it, and review the risks below.")

    L.append(_heading("2. Why"))
    for reason in best["reasons"]:
        L.append(f"- {reason}")

    L.append(_heading("3. Your rotation compared"))
    L.append(f"Current:      {_chain(ex['rotation'])}")
    L.append(f"              Score {ex['total_score']}/100. Risk levels: {_meters(ex)}")
    for i, a in enumerate(alts, 1):
        L.append(f"Suggestion {i}: {_chain(a['rotation'])}")
        L.append(f"              Score {a['total_score']}/100. Risk levels: {_meters(a)}")

    L.append(_heading(f"4. If a year like {climate['worst_year']} returns "
                      f"(the driest on record, {climate['worst_year_rain_mm']} mm)"))
    L.append(f"- Your current rotation would score {wy['existing']['total_score']}/100.")
    for i, a in enumerate(wy["alternatives"], 1):
        L.append(f"- Suggestion {i} ({_chain(a['rotation'])}) would score {a['total_score']}/100.")
    if wy["alternatives"]:
        stronger = max(wy["alternatives"], key=lambda r: r["total_score"])
        if stronger["total_score"] > wy["existing"]["total_score"]:
            L.append(f"- In a dry year, {_chain(stronger['rotation'])} holds up better than your "
                     f"current rotation.")

    L.append(_heading("5. Water and soil actions"))
    if best["factor_scores"]["water"] < 50:
        L.append("- Water supply is tight for this rotation. Plan irrigation carefully, and consider "
                 "mulching and drip irrigation to cut losses.")
    else:
        L.append("- Water supply looks adequate on average, but check irrigation before each season.")
    if any("nitrogen" in r for r in best["reasons"]):
        L.append("- Plant the legume before the crop that uses the most nitrogen, so the soil is "
                 "fed naturally.")
    L.append("- Keep fields covered between crops where possible (a cover crop or crop residue) to "
             "reduce erosion and protect soil moisture.")

    L.append(_heading("6. What this is based on"))
    L.append(f"- NASA POWER daily climate data, {climate['years_used']}: typical rainfall "
             f"{climate['annual_rain_mm']} mm/year, average temperature {climate['avg_temp_c']} C.")
    for c in climate.get("corrections", []):
        L.append(f"- Data correction: {c['days_corrected']} suspect rainfall days in {c['year']} "
                 f"(up to {c['max_raw_daily_mm']} mm in one day) were replaced with typical values.")

    L.append(_heading("7. Gaps and what to check locally"))
    for g in sorted(set(best["data_gaps"]) | set(ex["data_gaps"])):
        L.append(f"- {g}")
    L.append("- Crop values in this tool are simplified estimates.")
    L.append("- NASA POWER rainfall is a satellite and model estimate, not a rain gauge reading.")
    L.append("- Discuss this plan with a local agricultural expert before changing your rotation.")

    L.append("")
    L.append("SoilSense supports farmer and expert judgment. It does not replace it.")
    return "\n".join(L)
