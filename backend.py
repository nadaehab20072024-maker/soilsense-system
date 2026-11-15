import itertools

def crop(family, legume, water, root, heat, drought, n_demand, income):
    return dict(family=family, legume=legume, water=water, root=root,
                heat=heat, drought=drought, n_demand=n_demand, income=income)

# Rough placeholder values. Replace with real ones later.
CROPS = {
    "wheat":        crop("Poaceae",        False, 450, 2, 2, 2, 2, 3),
    "barley":       crop("Poaceae",        False, 350, 2, 3, 4, 1, 2),
    "sorghum":      crop("Poaceae",        False, 400, 3, 5, 4, 2, 2),
    "pearl_millet": crop("Poaceae",        False, 300, 3, 5, 5, 1, 2),
    "cowpea":       crop("Fabaceae",       True,  350, 2, 5, 4, 0, 3),
    "chickpea":     crop("Fabaceae",       True,  300, 3, 3, 3, 0, 3),
    "tomato":       crop("Solanaceae",     False, 500, 2, 3, 2, 2, 5),
    "onion":        crop("Amaryllidaceae", False, 450, 1, 3, 2, 1, 4),
    "sesame":       crop("Pedaliaceae",    False, 300, 3, 5, 5, 1, 3),
    "okra":         crop("Malvaceae",      False, 400, 2, 5, 3, 1, 3),
}

def generate_rotations(length=3):
    """All 3-year rotations with no crop family touching itself.
    The rotation loops, so the last crop is checked against the first."""
    for combo in itertools.product(CROPS, repeat=length):
        nxt = combo[1:] + combo[:1]
        ok = all(CROPS[a]["family"] != CROPS[b]["family"] for a, b in zip(combo, nxt))
        if ok and combo[0] == min(combo):      # skip duplicate cycles
            yield list(combo)

def clip(x):
    return max(0, min(100, x))

def risk_level(score):
    return "Low" if score >= 70 else "Medium" if score >= 45 else "High"

def score_rotation(rotation, climate, soil, priorities):
    reasons, gaps = [], []
    pairs = list(zip(rotation, rotation[1:] + rotation[:1]))

    # Soil health: legumes before hungry crops, deep roots
    soil_s = 50
    for a, b in pairs:
        if CROPS[a]["legume"] and CROPS[b]["n_demand"] == 2:
            soil_s += 15
            reasons.append(f"{a} (a legume) before {b} adds nitrogen to the soil")
    deep = sum(CROPS[c]["root"] == 3 for c in rotation)
    soil_s += 5 * deep
    if deep:
        reasons.append(f"{deep} deep-rooted crop(s) help break up compacted soil")

    # Water: supply vs need
    supply = climate["annual_rain_mm"] + soil.get("irrigation_mm", 0)
    supply *= 1 + climate.get("rain_trend_pct", 0) / 100 * 5
    need = sum(CROPS[c]["water"] for c in rotation) / len(rotation)
    water_s = clip(100 * supply / need)
    if water_s < 50:
        reasons.append("Water need is well above expected supply")
        gaps.append("Irrigation amount is a farmer estimate, please verify locally")

    # Climate fit: heat and drought tolerance
    tol = sum(CROPS[c]["heat"] + CROPS[c]["drought"] for c in rotation) / (2 * len(rotation))
    climate_s = 20 * tol
    if climate.get("temp_trend_c", 0) > 0:
        reasons.append("Warming trend detected, so heat-tolerant crops score higher")

    income_s = 20 * sum(CROPS[c]["income"] for c in rotation) / len(rotation)

    factors = {"soil": clip(soil_s), "water": water_s,
               "climate": climate_s, "income": income_s}
    w = {k: priorities.get(k, 1.0) for k in factors}
    total = sum(factors[k] * w[k] for k in factors) / sum(w.values())

    return {
        "rotation": rotation,
        "total_score": round(total, 1),
        "factor_scores": {k: round(v, 1) for k, v in factors.items()},
        "risk_meters": {k: risk_level(v) for k, v in factors.items()},
        "reasons": reasons or ["No strong benefits or risks found by the rules"],
        "data_gaps": gaps,
    }

def get_recommendations(climate, soil, priorities, existing):
    """THE function your UI and AI teammates call."""
    def ranked(clim):
        results = [score_rotation(r, clim, soil, priorities) for r in generate_rotations()]
        return sorted(results, key=lambda r: r["total_score"], reverse=True)

    normal = ranked(climate)
    alternatives = [r for r in normal
                    if set(r["rotation"]) != set(existing)][:2]

    worst = dict(climate, annual_rain_mm=climate["worst_year_rain_mm"])
    return {
        "existing": score_rotation(existing, climate, soil, priorities),
        "alternatives": alternatives,
        "worst_year": {
            "existing": score_rotation(existing, worst, soil, priorities),
            "alternatives": [score_rotation(a["rotation"], worst, soil, priorities)
                             for a in alternatives],
        },
    }

from climate import climate_summary

climate = climate_summary("climate.csv")