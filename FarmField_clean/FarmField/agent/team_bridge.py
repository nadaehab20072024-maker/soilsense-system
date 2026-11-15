"""Safe, read-only bridge to the teammates' rotation code (agent_tools.py / backend.py / climate.py).

Their files are NEVER edited. Two problems are handled here instead:
  * agent_tools.py, backend.py and climate.py read "climate.csv" with a RELATIVE path at import time
    -> we temporarily chdir to config.REPO_ROOT while importing.
  * climate.py prints a table at import time -> stdout is silenced during the import.
If the import fails (e.g. testing this folder alone), a clearly marked FAKE stub is used and
IS_FAKE / IMPORT_ERROR tell the UI to show a warning.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import threading

from . import config as C

_LOCK = threading.Lock()
IS_FAKE = False
IMPORT_ERROR: str | None = None
IMPORT_STDOUT_CHARS = 0      # how much their import printed (silenced)
team = None                  # agent_tools module (or the stub)
backend = None               # backend module (or the stub), used only for what-if re-scoring


def _import_real():
    global IMPORT_STDOUT_CHARS
    if C.FORCE_FAKE_TEAM:
        raise ImportError("SS_AGENT_FORCE_FAKE is set")
    if "agent_tools" in sys.modules and "backend" in sys.modules:   # host app already imported them
        return sys.modules["agent_tools"], sys.modules["backend"]
    if not (C.REPO_ROOT / "agent_tools.py").exists():
        raise ImportError(f"agent_tools.py not found in {C.REPO_ROOT}")
    root = str(C.REPO_ROOT)
    with _LOCK:
        old_cwd = os.getcwd()
        added = root not in sys.path
        if added:
            sys.path.insert(0, root)
        buf = io.StringIO()
        try:
            os.chdir(root)
            with contextlib.redirect_stdout(buf):
                import agent_tools as at     # noqa: E402  (their module)
                import backend as be         # noqa: E402
        finally:
            os.chdir(old_cwd)
            IMPORT_STDOUT_CHARS = len(buf.getvalue())
    return at, be


class _FakeTeam:
    """FAKE stub with the same signatures. Every value is a placeholder; nothing here is real data."""
    FAKE = True
    CROPS = {c: {} for c in ["wheat", "barley", "sorghum", "pearl_millet", "cowpea", "chickpea",
                              "tomato", "onion", "sesame", "okra"]}
    CLIMATE = dict(annual_rain_mm=0.0, rain_trend_pct=0.0, rain_trend_raw_pct=0.0, temp_trend_c=0.0,
                   avg_temp_c=0.0, worst_year_rain_mm=0.0, worst_year=0, years_used="FAKE")

    @staticmethod
    def _r(rot):
        return dict(rotation=list(rot), total_score=50.0,
                    factor_scores=dict(soil=50.0, water=50.0, climate=50.0, income=50.0),
                    risk_meters=dict(soil="Medium", water="Medium", climate="Medium", income="Medium"),
                    reasons=["FAKE STUB: teammates' agent_tools.py was not imported"],
                    data_gaps=["FAKE STUB: these scores are not real"])

    def get_recommendations(self, climate, soil, priorities, existing):
        for c in existing:
            if c not in self.CROPS:
                raise KeyError(c)
        alts = [self._r(["cowpea", "sorghum", "sesame"]), self._r(["chickpea", "tomato", "sesame"])]
        alts = [a for a in alts if set(a["rotation"]) != set(existing)][:2] or [self._r(["barley", "cowpea", "okra"])]
        return dict(existing=self._r(existing), alternatives=alts,
                    worst_year=dict(existing=self._r(existing), alternatives=[self._r(a["rotation"]) for a in alts]))

    def recommend(self, existing_rotation, irrigation_mm=250, water=1.0, soil=1.0, income=1.0):
        return self.get_recommendations(self.CLIMATE, {"irrigation_mm": irrigation_mm},
                                        {"water": water, "soil": soil, "income": income}, existing_rotation)

    def list_crops(self):
        return list(self.CROPS)

    def get_climate(self):
        return dict(self.CLIMATE)

    def summary_for_voice(self, results):
        return "FAKE STUB voice summary."


def load(force_reload: bool = False):
    """Import (once) and return the teammates' module, or the FAKE stub."""
    global team, backend, IS_FAKE, IMPORT_ERROR
    if team is not None and not force_reload:
        return team
    try:
        team, backend = _import_real()
        IS_FAKE, IMPORT_ERROR = False, None
    except Exception as e:   # ImportError, FileNotFoundError from their relative path, anything
        stub = _FakeTeam()
        team, backend = stub, stub
        IS_FAKE, IMPORT_ERROR = True, f"{type(e).__name__}: {e}"
    return team


def status() -> dict:
    load()
    return dict(is_fake=IS_FAKE, error=IMPORT_ERROR, repo_root=str(C.REPO_ROOT),
                silenced_import_output_chars=IMPORT_STDOUT_CHARS)
