"""Watering schedule and charts.

Daily (recent + coming days): crop water need = Kc x ET0 (FAO-56 Penman-Monteith ET0 from Open-Meteo)
  "before rain"  = crop need
  "after rain"   = what is still needed after counting rain (simple soil bucket, config values need expert review)
Monthly (typical year): the same idea from NASA POWER history (local_climate.water_guidance).
Charts are returned as Vega-Lite specs (st.vega_lite_chart), so no extra package is needed."""
from __future__ import annotations

from . import config as C
from .crops import kc_for, resolve_crop


def daily_schedule(days: list[dict], crop: str | None, valid_crops: list[str], area_m2: float | None = None,
                   method_efficiency: float = 1.0) -> dict:
    name = resolve_crop(crop, valid_crops) if crop else None
    k = kc_for(name)
    store, rows = 0.0, []
    for i, d in enumerate(days):
        et0 = d.get("et0_mm")
        if et0 is None:
            continue
        need = round(k["kc"] * et0, 1)                                   # before rain
        rain = float(d.get("rain_mm") or 0.0)
        eff = rain * C.EFFECTIVE_RAIN_FRACTION if rain >= C.MIN_EFFECTIVE_RAIN_MM else 0.0
        store = min(store + eff, C.SOIL_STORE_MM)
        used = min(store, need)
        store -= used
        net = round(max(need - used, 0.0), 1)                            # after rain
        gross = round(net / method_efficiency, 1) if method_efficiency else net
        nxt = days[i + 1] if i + 1 < len(days) else None
        if net <= 0.5:
            action = "skip_rain" if rain >= C.MIN_EFFECTIVE_RAIN_MM or used > 0 else "skip"
        elif nxt and (nxt.get("rain_mm") or 0) * C.EFFECTIVE_RAIN_FRACTION >= net and nxt.get("when") != "past":
            action = "wait_rain"
        elif any(h["key"].startswith("heat") for h in d.get("hazards", [])):
            action = "water_early"
        else:
            action = "water"
        rows.append(dict(date=d["date"], when=d["when"], level=d.get("level"), colour=d.get("colour"),
                         et0_mm=et0, need_before_rain_mm=need, rain_mm=round(rain, 1), rain_used_mm=round(used, 1),
                         need_after_rain_mm=net, irrigate_mm=gross,
                         litres=round(gross * area_m2) if area_m2 else None, action=action))
    future = [r for r in rows if r["when"] != "past"] or rows
    avg = lambda key, rs: round(sum(r[key] for r in rs) / len(rs), 1) if rs else 0.0
    return dict(crop=name, kc=k["kc"], kc_source=k["kc_source"], kc_status=k["kc_status"], rows=rows,
                avg_need_before_rain_mm=avg("need_before_rain_mm", rows), avg_need_after_rain_mm=avg("need_after_rain_mm", rows),
                coming_total_irrigation_mm=round(sum(r["irrigate_mm"] for r in future), 1),
                coming_total_litres=round(sum(r["litres"] or 0 for r in future)) if area_m2 else None,
                area_m2=area_m2, method_efficiency=method_efficiency,
                note="1 mm of water = 1 litre per square metre. Simple estimate; soil, crop stage and "
                     "irrigation method change the real need.",
                settings=dict(effective_rain_fraction=C.EFFECTIVE_RAIN_FRACTION, min_effective_rain_mm=C.MIN_EFFECTIVE_RAIN_MM,
                              soil_store_mm=C.SOIL_STORE_MM, status="needs expert review"))


def monthly_typical(lat, lon, crop=None) -> dict:
    from .local_climate import water_guidance
    g = water_guidance(lat, lon, crop=crop)
    rows = [dict(month=m["month"], need_before_rain_mm=round(g["kc_used"] * m["et0_mm"], 0), rain_mm=m["rain_mm"],
                 need_after_rain_mm=m["irrigation_need_mm"]) for m in g["monthly"]]
    return dict(crop=g["crop"], kc=g["kc_used"], kc_source=g["kc_source"], rows=rows, years=g["based_on_years"],
                avg_need_after_rain_mm=round(sum(r["need_after_rain_mm"] for r in rows) / 12, 0),
                yearly_need_after_rain_mm=g["yearly_irrigation_need_mm"], site=g["site"], notes=g["notes"])


# ------------------------------------------------------------------ chart specs (Vega-Lite)
SERIES_COLOURS = {"before": "#F9A825", "rain": "#1E88E5", "after": "#2E7D32"}


def chart_spec(rows: list[dict], x_field: str, x_labels: dict, names: dict, avg_value: float, avg_label: str,
               today: str | None = None, y_title: str = "mm") -> tuple[list[dict], dict]:
    """Grouped bars: need before rain / rain / need after rain, plus a dashed average line.
    names = {"before": ..., "rain": ..., "after": ...} in the user's language."""
    data = []
    order = ["before", "rain", "after"]
    for r in rows:
        x = x_labels.get(r[x_field], str(r[x_field]))
        for s, key in (("before", "need_before_rain_mm"), ("rain", "rain_mm"), ("after", "need_after_rain_mm")):
            data.append({"x": x, "series": names[s], "mm": r[key], "order": order.index(s)})
    domain = [names[s] for s in order]
    colours = [SERIES_COLOURS[s] for s in order]
    x_sort = [x_labels.get(r[x_field], str(r[x_field])) for r in rows]
    layers = [
        {"mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
         "encoding": {
             "x": {"field": "x", "type": "nominal", "sort": x_sort, "title": None, "axis": {"labelAngle": -40}},
             "xOffset": {"field": "series", "sort": domain},
             "y": {"field": "mm", "type": "quantitative", "title": y_title},
             "color": {"field": "series", "type": "nominal", "scale": {"domain": domain, "range": colours},
                       "legend": {"orient": "top", "title": None}},
             "tooltip": [{"field": "x", "title": " "}, {"field": "series", "title": " "},
                         {"field": "mm", "title": y_title}]}},
        {"data": {"values": [{"avg": avg_value, "label": f"{avg_label}: {avg_value:g} {y_title}"}]},
         "layer": [
             {"mark": {"type": "rule", "strokeDash": [6, 4], "color": "#37474F", "size": 2},
              "encoding": {"y": {"field": "avg", "type": "quantitative"}}},
             {"mark": {"type": "text", "align": "left", "dx": 4, "dy": -8, "color": "#37474F", "fontWeight": "bold"},
              "encoding": {"y": {"field": "avg", "type": "quantitative"}, "text": {"field": "label"},
                           "x": {"value": 0}}}]},
    ]
    if today and today in x_sort:
        layers.append({"data": {"values": [{"x": today}]},
                       "mark": {"type": "rule", "color": "#C62828", "size": 2},
                       "encoding": {"x": {"field": "x", "type": "nominal", "sort": x_sort}}})
    spec = {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "height": 300,
            "data": {"values": data}, "layer": layers}
    return data, spec
