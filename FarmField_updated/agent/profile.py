from __future__ import annotations

from . import config as C

PROFILE_FIELDS = ("lat", "lon", "lang", "crop", "existing_rotation", "irrigation_mm", *C.PRIORITY_KEYS)
QUESTION_KEYS = (*C.PRIORITY_KEYS, "irrigation_mm")


def new_profile(context: dict | None = None) -> dict:
    p = {"asked": []}
    return merge_context(p, context)


def merge_context(profile: dict, context: dict | None) -> dict:
    for k in PROFILE_FIELDS:
        v = (context or {}).get(k)
        if v is not None:
            profile[k] = v
    profile.setdefault("asked", [])
    return profile


def apply_updates(profile: dict, updates: dict | None) -> dict:
    for k, v in (updates or {}).items():
        if k in PROFILE_FIELDS and v is not None:
            profile[k] = v
    return profile


def open_questions(profile: dict) -> list[str]:
    asked = set(profile.get("asked") or [])
    return [k for k in QUESTION_KEYS if profile.get(k) is None and k not in asked]


def mark_asked(profile: dict, keys) -> dict:
    asked = profile.setdefault("asked", [])
    for k in keys:
        if k not in asked:
            asked.append(k)
    return profile


def summary(profile: dict) -> str:
    parts = []
    for k in ("existing_rotation", "irrigation_mm", *C.PRIORITY_KEYS):
        if profile.get(k) is not None:
            parts.append(f"{k}={profile[k]}")
    return ", ".join(parts) or "nothing yet"
