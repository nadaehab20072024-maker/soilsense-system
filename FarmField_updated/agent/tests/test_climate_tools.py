"""Per-location climate tools (ported from the original 13 tests)."""
import pandas as pd
import pytest

from .. import config as C
from .. import data_prep
from .. import local_climate as cl

SITE3 = (23.7067, 57.9065)


def test_processed_files_are_clean():
    for s in cl.load_sites():
        df = pd.read_csv(C.PROC_DIR / f"{s['id']}.csv.gz", index_col=0, parse_dates=True)
        assert df[data_prep.CORE_COLS].notna().all().all()
        assert (df[data_prep.CORE_COLS] != -999).all().all()
        assert df.index.is_monotonic_increasing and not df.index.duplicated().any()
        assert (df["T2M_MAX"] >= df["T2M_MIN"]).all()


def test_nearest_site_and_far_warning():
    site, dist = cl.nearest_site(*SITE3)
    assert site["id"] == "site3" and dist < 1
    r = cl.climate_risk(25.5, 56.3)
    assert r["site"]["distance_km"] > C.LOCAL_SITE_MAX_KM and r["notes"]


def test_et0_is_physically_plausible():
    df, _, _ = cl.get_data(*SITE3)
    yearly = cl.yearly_metrics(df)
    assert yearly.loc[2023, "et0_mm"] == pytest.approx(1700, abs=500)
    assert (df["ET0"] >= 0).all()


def test_risk_structure():
    r = cl.climate_risk(*SITE3)
    assert r["overall_level"] in cl.LEVELS and 0 <= r["overall_score_0_100"] <= 100
    assert set(r["hazards"]) == set(cl.HAZARDS)


def test_worst_year_is_a_real_complete_year():
    r = cl.replay_worst_year(*SITE3)
    assert 2001 <= r["worst_year"] <= 2025 and len(r["monthly"]) == 12
    assert "error" in cl.replay_worst_year(*SITE3, hazard="nonsense")


def test_what_if_hotter_means_more_heat_and_water_demand():
    r = cl.simulate_what_if(*SITE3, temp_delta_c=2, rain_change_pct=-30)
    assert r["after"]["heat_days"] > r["before"]["heat_days"]
    assert r["after"]["et0_mm"] > r["before"]["et0_mm"]
    assert r["after"]["rain_mm"] < r["before"]["rain_mm"]


def test_water_guidance_uses_team_crop_list_and_fao56():
    r = cl.water_guidance(*SITE3, crop="tomato")
    assert r["kc_used"] == 1.15 and "FAO-56" in r["kc_source"] and r["kc_status"] == "needs expert review"
    assert cl.water_guidance(*SITE3, crop="طماطم")["crop"] == "tomato"          # Arabic name resolved
    okra = cl.water_guidance(*SITE3, crop="okra")                                 # not in FAO-56 Table 12
    assert okra["kc_used"] == 1.0 and "crop-neutral" in okra["kc_source"] and okra["notes"]
    palm = cl.water_guidance(*SITE3, crop="date_palm")                            # not a supported crop
    assert palm["crop"] is None and palm["kc_used"] == 1.0 and "not in the supported crop list" in palm["notes"][0]
