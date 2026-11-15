"""Vega-Lite specs for the overview and report pages (rendered with st.vega_lite_chart, no extra package).
All values come from the forecast rows built by weather.build_days()."""
from __future__ import annotations

from . import config as C
from .weather import LEVELS

SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"


def level_chart(days: list[dict], x_label, level_name, hazard_name, today_label: str | None, y_title: str) -> dict:
    """One bar per day, height = level + 1 (so level 0 is still visible), coloured green ... red."""
    names = [level_name(l) for l in range(6)]
    data = [{"x": x_label(d["date"]), "h": d["level"] + 1, "level": names[d["level"]], "what": hazard_name(d["top"])}
            for d in days]
    sort = [r["x"] for r in data]
    layers = [{"mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
               "encoding": {"x": {"field": "x", "type": "nominal", "sort": sort, "title": None, "axis": {"labelAngle": -40}},
                            "y": {"field": "h", "type": "quantitative", "title": y_title,
                                  "scale": {"domain": [0, 6]}, "axis": {"values": [1, 2, 3, 4, 5, 6], "labels": False}},
                            "color": {"field": "level", "type": "nominal",
                                      "scale": {"domain": names, "range": [LEVELS[l]["colour"] for l in range(6)]},
                                      "legend": {"orient": "top", "title": None}},
                            "tooltip": [{"field": "x", "title": " "}, {"field": "level", "title": " "},
                                        {"field": "what", "title": " "}]}}]
    if today_label and today_label in sort:
        layers.append({"data": {"values": [{"x": today_label}]}, "mark": {"type": "rule", "color": "#C62828", "size": 2},
                       "encoding": {"x": {"field": "x", "type": "nominal", "sort": sort}}})
    return {"$schema": SCHEMA, "height": 220, "data": {"values": data}, "layer": layers}


def temperature_chart(days: list[dict], x_label, names: dict, today_label: str | None) -> dict:
    data, sort = [], []
    for d in days:
        if d.get("tmax_c") is None:
            continue
        x = x_label(d["date"])
        sort.append(x)
        data += [{"x": x, "s": names["max"], "c": d["tmax_c"]}, {"x": x, "s": names["min"], "c": d["tmin_c"]}]
    lim = C.HEAT_TMAX_C[0]
    layers = [
        {"mark": {"type": "line", "point": True, "strokeWidth": 3},
         "encoding": {"x": {"field": "x", "type": "nominal", "sort": sort, "title": None, "axis": {"labelAngle": -40}},
                      "y": {"field": "c", "type": "quantitative", "title": "°C", "scale": {"zero": False}},
                      "color": {"field": "s", "type": "nominal", "scale": {"domain": [names["max"], names["min"]],
                                                                             "range": ["#E65100", "#1E88E5"]},
                                "legend": {"orient": "top", "title": None}},
                      "tooltip": [{"field": "x", "title": " "}, {"field": "s", "title": " "}, {"field": "c", "title": "°C"}]}},
        {"data": {"values": [{"lim": lim}]}, "mark": {"type": "rule", "strokeDash": [6, 4], "color": "#C62828"},
         "encoding": {"y": {"field": "lim", "type": "quantitative"}}},
    ]
    if today_label and today_label in sort:
        layers.append({"data": {"values": [{"x": today_label}]}, "mark": {"type": "rule", "color": "#C62828", "size": 2},
                       "encoding": {"x": {"field": "x", "type": "nominal", "sort": sort}}})
    return {"$schema": SCHEMA, "height": 220, "data": {"values": data}, "layer": layers}


def level_count_chart(days: list[dict], level_name, x_title: str) -> dict:
    """How many coming days fall in each level (horizontal bars, red at the top)."""
    names = [level_name(l) for l in range(6)]
    counts = {l: 0 for l in range(6)}
    for d in days:
        counts[d["level"]] += 1
    data = [{"level": names[l], "n": counts[l], "o": 5 - l} for l in range(5, -1, -1)]
    return {"$schema": SCHEMA, "height": 200, "data": {"values": data},
            "mark": {"type": "bar", "cornerRadiusEnd": 4},
            "encoding": {"y": {"field": "level", "type": "nominal", "sort": [r["level"] for r in data], "title": None},
                         "x": {"field": "n", "type": "quantitative", "title": x_title, "axis": {"tickMinStep": 1}},
                         "color": {"field": "level", "type": "nominal", "legend": None,
                                   "scale": {"domain": names, "range": [LEVELS[l]["colour"] for l in range(6)]}},
                         "tooltip": [{"field": "level", "title": " "}, {"field": "n", "title": x_title}]}}
