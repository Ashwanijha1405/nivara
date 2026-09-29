"""Stage 2 Verification Tests: Timestep Differentiability, Unavailable Hazard State, and Caching.

Verifies:
1. Different timesteps produce different cyclone positions/proximity when track differs.
2. Hazard data is not silently converted into a fake calculated LOW risk when hazard input is unavailable.
3. Same storm + same timestep reuses cached data without repeating expensive calculation/request.
4. Different timesteps distinguish cache keys and do not return the same cached result.
"""

import pytest
from fastapi.testclient import TestClient

from app.domain.infrastructure import AssetCategory, InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta
from app.main import app
from app.risk_engine.scoring import compute_composite_risk
from app.services.risk_engine import RiskEngineService
from app.api.routes import _storm_risk_cache, _storm_advisory_cache

client = TestClient(app)


def test_different_timesteps_produce_different_positions_and_proximity():
    """Verify different timesteps produce distinct cyclone positions and asset proximity."""
    res_step0 = client.get("/api/storms/2020136N10088/risk?step_index=0")
    res_step20 = client.get("/api/storms/2020136N10088/risk?step_index=20")

    assert res_step0.status_code == 200
    assert res_step20.status_code == 200

    d0 = res_step0.json()
    d20 = res_step20.json()

    assert d0["step_index"] == 0
    assert d20["step_index"] == 20
    assert d0["cyclone_center"] != d20["cyclone_center"]

    # Timestep 0 is deep in southern Bay of Bengal (~9.5 N)
    assert d0["cyclone_center"]["lat"] < 12.0
    # Timestep 20 approaches West Bengal / Odisha corridor (>20 N)
    assert d20["cyclone_center"]["lat"] > 20.0

    # Assets in West Bengal are far at step 0 (>1000km) and close at step 20 (<300km)
    asset0_prox = d0["assets"][0]["hazard"]["cyclone_proximity_km"]
    asset20_prox = d20["assets"][0]["hazard"]["cyclone_proximity_km"]
    assert asset0_prox > 1000.0
    assert asset20_prox < 300.0

    # Step 0 records center wind and OUT_OF_RANGE status
    assert d0["assets"][0]["hazard"]["storm_center_wind_knots"] == 30.0
    assert d0["assets"][0]["hazard"]["hazard_status"] == "OUT_OF_RANGE"
    assert d0["assets"][0]["risk_level"] == "LOW"

    # Step 20 records active hazard forces
    assert d20["assets"][0]["hazard"]["hazard_status"] == "AVAILABLE"
    assert d20["assets"][0]["hazard"]["wind_hazard_score"] > 0.0


def test_unavailable_hazard_data_not_converted_to_fake_low_risk():
    """Verify missing/unavailable hazard input sets UNAVAILABLE risk level, NOT calculated LOW."""
    engine = RiskEngineService()

    dummy_asset = InfrastructureAsset(
        id="osm_node_202",
        name="Kakdwip General Hospital",
        category=AssetCategory.HOSPITAL,
        lat=21.875,
        lon=88.188,
        elevation_m=2.5,
        dist_to_coast_km=3.0,
        district="South 24 Parganas",
        state="West Bengal",
        provenance=DataSourceMeta(
            source="OpenStreetMap",
            dataset="Overpass",
            status=DataMode.LIVE,
        ),
    )

    # 1. Test None cyclone wind in RiskEngineService
    result_none = engine.evaluate_asset(
        asset=dummy_asset,
        cyclone_lat=21.85,
        cyclone_lon=88.20,
        cyclone_wind_knots=None,
    )
    assert result_none.risk_level == "UNAVAILABLE"
    assert result_none.risk_level != "LOW"
    assert result_none.hazard.hazard_status == "UNAVAILABLE"
    assert result_none.hazard.data_available is False
    assert "Hazard data unavailable" in result_none.explanation

    # 2. Test negative cyclone wind
    result_neg = engine.evaluate_asset(
        asset=dummy_asset,
        cyclone_lat=21.85,
        cyclone_lon=88.20,
        cyclone_wind_knots=-5.0,
    )
    assert result_neg.risk_level == "UNAVAILABLE"
    assert result_neg.hazard.data_available is False

    # 3. Test mathematical scoring engine directly
    res_scoring = compute_composite_risk(
        dist_from_track_km=10.0,
        wind_speed_knots=None,
        elevation_m=2.5,
        dist_to_coast_km=3.0,
        land_cover_class="urban",
    )
    assert res_scoring.risk_level == "UNAVAILABLE"
    assert res_scoring.risk_level != "LOW"


def test_same_storm_same_timestep_reuses_cache():
    """Verify requesting same storm and timestep reuses cached result."""
    # Ensure cache has entry after first call
    res1 = client.get("/api/storms/2020136N10088/risk?step_index=5")
    assert res1.status_code == 200
    data1 = res1.json()

    cache_keys_before = list(_storm_risk_cache.keys())
    expected_prefix = "2020136N10088_5"
    assert any(k.startswith(expected_prefix) for k in cache_keys_before)

    # Second call returns from cache
    res2 = client.get("/api/storms/2020136N10088/risk?step_index=5")
    assert res2.status_code == 200
    data2 = res2.json()

    assert data1 == data2


def test_different_timesteps_distinguish_cache_keys():
    """Verify different timesteps produce distinct cache keys and distinct results."""
    res_step0 = client.get("/api/storms/2020136N10088/risk?step_index=0")
    res_step15 = client.get("/api/storms/2020136N10088/risk?step_index=15")

    d0 = res_step0.json()
    d15 = res_step15.json()

    # Step index must not be cross-contaminated
    assert d0["step_index"] == 0
    assert d15["step_index"] == 15
    assert d0["timestamp"] != d15["timestamp"]
    assert d0["cyclone_center"] != d15["cyclone_center"]

    # Cache entries exist for both distinct timesteps
    keys = list(_storm_risk_cache.keys())
    assert any(k.startswith("2020136N10088_0") for k in keys)
    assert any(k.startswith("2020136N10088_15") for k in keys)


def test_catalog_storms_track_resolution():
    """Verify all storms in catalog including Fani 2019117N10087 resolve track waypoints."""
    for storm_id in ["2020136N10088", "2024145N14087", "2019117N10087"]:
        res = client.get(f"/api/storms/{storm_id}/track")
        assert res.status_code == 200
        data = res.json()
        points = [f for f in data.get("features", []) if f.get("properties", {}).get("feature_type") == "storm_center"]
        assert len(points) > 10, f"Expected >10 waypoints for {storm_id}, got {len(points)}"
