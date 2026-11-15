"""Tool registry + JSON schemas the LLM sees (OpenAI function-calling format).

Rotation schemas are built from the REAL signatures of the teammates' functions (inspect.signature),
so if they add/rename a parameter the schema follows. Crop enums come from list_crops()."""
from __future__ import annotations

import inspect

from . import config as C
from . import local_climate as LC
from . import rotation_tools as RT
from . import team_bridge

_LOC = {
    "lat": {"type": "number", "description": "Latitude. Omit to use the farm location from context."},
    "lon": {"type": "number", "description": "Longitude. Omit to use the farm location from context."},
}

PARAM_DOCS = {
    "existing_rotation": "Crops the farmer grows now, in order (treated as a cycle). Use ONLY names from the enum; "
                         "translate the farmer's words first. If a crop is not in the enum, do not call this tool.",
    "irrigation_mm": "Yearly irrigation water in mm (farmer estimate). Omit to use the farm profile or the default.",
    "water": "Priority weight for saving water: 0.5 not important, 1.0 normal, 2.0 very important. Omit if unknown.",
    "soil": "Priority weight for soil health: 0.5 not important, 1.0 normal, 2.0 very important. Omit if unknown.",
    "income": "Priority weight for income: 0.5 not important, 1.0 normal, 2.0 very important. Omit if unknown.",
}


def _json_type(default):
    if isinstance(default, bool):
        return "boolean"
    if isinstance(default, (int, float)):
        return "number"
    return "string"


def schema_from_signature(func, name: str, description: str, crops: list[str]) -> dict:
    """Build a JSON schema from a teammate function's real signature."""
    props, required = {}, []
    for p in inspect.signature(func).parameters.values():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) or p.name.startswith("_"):
            continue
        if p.name == "existing_rotation":
            prop = {"type": "array", "minItems": 1, "items": {"type": "string", "enum": crops}}
        else:
            prop = {"type": _json_type(p.default)}
            if p.name in C.PRIORITY_KEYS:
                prop["enum"] = sorted(set(C.PRIORITY_CHOICES.values()))
            if p.name == "irrigation_mm":
                prop.update(minimum=0, maximum=C.IRRIGATION_MAX_MM)
        prop["description"] = PARAM_DOCS.get(p.name, p.name) + (
            f" Default {p.default}." if p.default is not inspect.Parameter.empty else "")
        props[p.name] = prop
        if p.default is inspect.Parameter.empty:
            required.append(p.name)
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": props, "required": required}}}


def _tool(name, description, props=None, required=None, loc=True):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": {**(_LOC if loc else {}), **(props or {})}, "required": required or []}}}


def build_tools() -> tuple[list[dict], dict, dict]:
    """-> (TOOLS_SCHEMA, TOOL_FUNCS, TOOL_SOURCES)."""
    team = team_bridge.load()
    crops = RT.supported_crops()
    rot_arr = {"type": "array", "minItems": 1, "items": {"type": "string", "enum": crops},
               "description": PARAM_DOCS["existing_rotation"]}
    schema = [
        # ---- teammates' rotation tools (rotation questions)
        schema_from_signature(team.recommend, "recommend",
                              "Crop ROTATION advice: scores the farmer's current rotation and gives the 2 best "
                              "3-crop alternatives, plus a re-score for the driest year. Covers ONE location only "
                              "(the rotation site); always tell the farmer if their farm is elsewhere.", crops),
        _tool("list_crops", "The only crops the rotation tool supports.", loc=False),
        _tool("get_climate", "Rainfall and temperature summary of the rotation site (driest year, trend).", loc=False),
        _tool("rotation_what_if",
              "What-if for a rotation: less/more rain, less/more irrigation water, or hotter weather. "
              "Use for 'what if it rains less / I have less water / it gets hotter'.",
              {"existing_rotation": rot_arr,
               "rain_change_pct": {"type": "number", "description": "Percent change in rainfall, e.g. -30."},
               "irrigation_change_pct": {"type": "number", "description": "Percent change in irrigation, e.g. -50."},
               "temp_delta_c": {"type": "number", "description": "Degrees C hotter, e.g. 2."}},
              ["existing_rotation"], loc=False),
        # ---- my per-location climate tools (weather / water questions)
        _tool("get_climate_summary",
              "Long-term climate at the farm location: average temperature, warming trend, typical rainfall, heat days."),
        _tool("get_climate_risk",
              "Climate risk levels (heat, water stress, extreme rain) for a year, compared with local history.",
              {"year": {"type": "integer", "description": "Optional. Default: last complete year."}}),
        _tool("get_water_guidance",
              "Estimated monthly irrigation need for one crop and the months with highest water demand.",
              {"crop": {"type": "string", "enum": crops, "description": "Optional crop (supported list only)."}}),
        _tool("replay_worst_year",
              "Find and describe the worst past year at this location (hottest, driest or wettest).",
              {"hazard": {"type": "string", "enum": ["overall", "heat", "water_stress", "extreme_rain"]}}),
        _tool("simulate_what_if",
              "Weather what-if at the farm location: hotter/cooler or more/less rain (heat days, water demand).",
              {"temp_delta_c": {"type": "number", "description": "Degrees C to add to all temperatures."},
               "rain_change_pct": {"type": "number", "description": "Percent change in rainfall, e.g. -30."}}),
    ]
    funcs = {
        "recommend": RT.recommend, "list_crops": RT.list_crops, "get_climate": RT.get_climate,
        "rotation_what_if": RT.rotation_what_if,
        "get_climate_summary": LC.climate_summary, "get_climate_risk": LC.climate_risk,
        "get_water_guidance": LC.water_guidance, "replay_worst_year": LC.replay_worst_year,
        "simulate_what_if": LC.simulate_what_if,
    }
    rot_src = "SoilSense team rotation model (backend.py, placeholder crop values) + NASA POWER climate.csv"
    sources = {
        "recommend": rot_src, "rotation_what_if": rot_src, "list_crops": "SoilSense team crop list (backend.py)",
        "get_climate": "NASA POWER (MERRA-2) climate.csv, rotation site",
        "get_climate_summary": "NASA POWER (MERRA-2): temperature and rainfall history",
        "get_climate_risk": "NASA POWER (MERRA-2): compared with the site's own history",
        "get_water_guidance": "NASA POWER (MERRA-2) + Hargreaves ET0 + FAO-56 Table 12 Kc (needs expert review)",
        "replay_worst_year": "NASA POWER (MERRA-2): daily data, 2000 onward",
        "simulate_what_if": "NASA POWER (MERRA-2) + simple what-if shift; not a forecast",
    }
    if C.ENABLE_VOICE_TOOL:
        schema.append(_tool("summary_for_voice", "Short English text of the rotation advice for reading aloud.",
                            {"existing_rotation": rot_arr}, ["existing_rotation"], loc=False))
        funcs["summary_for_voice"] = RT.summary_for_voice
        sources["summary_for_voice"] = rot_src
    return schema, funcs, sources


ROTATION_TOOLS = {"recommend", "rotation_what_if", "summary_for_voice"}
LOCATION_TOOLS = {"get_climate_summary", "get_climate_risk", "get_water_guidance", "replay_worst_year",
                  "simulate_what_if"}


def validate_args(schema: list[dict], name: str, args: dict) -> list[str]:
    """Light JSON-schema check (no extra dependency). Returns a list of problems."""
    tool = next((t["function"] for t in schema if t["function"]["name"] == name), None)
    if tool is None:
        return [f"unknown tool {name}"]
    params = tool["parameters"]
    probs = [f"missing {r}" for r in params.get("required", []) if r not in args]
    for k, v in args.items():
        spec = params["properties"].get(k)
        if spec is None:
            probs.append(f"unknown argument {k}")
            continue
        typ = spec.get("type")
        if typ == "number" and not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            probs.append(f"{k} must be a number")
        elif typ == "integer" and not isinstance(v, int):
            probs.append(f"{k} must be an integer")
        elif typ == "string" and not isinstance(v, str):
            probs.append(f"{k} must be a string")
        elif typ == "array":
            if not isinstance(v, list) or len(v) < spec.get("minItems", 0):
                probs.append(f"{k} must be a non-empty list")
            else:
                enum = spec.get("items", {}).get("enum")
                bad = [x for x in v if enum and x not in enum]
                if bad:
                    probs.append(f"{k}: not supported {bad}")
        if "enum" in spec and v not in spec["enum"]:
            probs.append(f"{k} must be one of {spec['enum']}")
    return probs
