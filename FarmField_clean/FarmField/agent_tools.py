from backend import CROPS, get_recommendations
from climate import climate_summary

CLIMATE = climate_summary("climate.csv")

def recommend(existing_rotation, irrigation_mm=250, water=1.0, soil=1.0, income=1.0):
    return get_recommendations(
        CLIMATE,
        {"irrigation_mm": irrigation_mm},
        {"water": water, "soil": soil, "income": income},
        existing_rotation,
    )

def list_crops():
    return list(CROPS)

def get_climate():
    return CLIMATE

def summary_for_voice(results):
    ex = results["existing"]
    lines = [f"Your current rotation, {', '.join(ex['rotation'])}, scores {ex['total_score']} out of 100."]
    for i, alt in enumerate(results["alternatives"], 1):
        lines.append(f"Option {i} is {', '.join(alt['rotation'])}, scoring {alt['total_score']}. "
                     + " ".join(alt["reasons"][:2]))
    wy = results["worst_year"]
    lines.append(f"In the driest year on record, your current rotation would score "
                 f"{wy['existing']['total_score']}, compared with "
                 f"{wy['alternatives'][0]['total_score']} for option 1.")
    lines.append("These are suggestions to discuss with a local agricultural expert, not final advice.")
    return " ".join(lines)