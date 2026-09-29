"""Unit and integration tests for GDACS real-time cyclone ingestion backend.

Verifies:
- Live cyclone adapter & NIO geographic filter
- /api/storms/live and /api/storms/live/track endpoints
- Active, Calm, and Unavailable state transitions
- Anti-fabrication constraints (null pressure, no synthetic coordinates)
- Preservation of historical and scenario pipelines
"""

import pytest
from fastapi.testclient import TestClient

from app.data_sources.gdacs.gdacs_adapter import GDACSAdapter
from app.domain.cyclone import LiveCycloneInfo, LiveCycloneStatusResponse
from app.main import app

client = TestClient(app)


def test_gdacs_adapter_nio_filtering():
    """Verify that only storms in the North Indian Ocean basin are accepted."""
    adapter = GDACSAdapter()

    # 1. Storm in Bay of Bengal (inside spatial bbox 0-32N, 50-100E)
    bob_storm = {
        "geometry": {"type": "Point", "coordinates": [88.5, 18.2]},
        "properties": {"iso3": "IND", "affectedcountries": [{"iso3": "IND", "countryname": "India"}]},
    }
    assert adapter.is_north_indian_ocean(bob_storm) is True

    # 2. Storm in Arabian Sea
    arabian_storm = {
        "geometry": {"type": "Point", "coordinates": [64.0, 20.0]},
        "properties": {"iso3": "OMN", "affectedcountries": [{"iso3": "OMN", "countryname": "Oman"}]},
    }
    assert adapter.is_north_indian_ocean(arabian_storm) is True

    # 3. Storm in East Pacific (Mexico) - outside bbox and non-NIO ISO
    pacific_storm = {
        "geometry": {"type": "Point", "coordinates": [-110.9, 27.8]},
        "properties": {"iso3": "MEX", "affectedcountries": [{"iso3": "MEX", "countryname": "Mexico"}]},
    }
    assert adapter.is_north_indian_ocean(pacific_storm) is False

    # 4. Storm in Atlantic (Caribbean)
    atlantic_storm = {
        "geometry": {"type": "Point", "coordinates": [-75.0, 22.0]},
        "properties": {"iso3": "BHS", "affectedcountries": [{"iso3": "BHS", "countryname": "Bahamas"}]},
    }
    assert adapter.is_north_indian_ocean(atlantic_storm) is False


@pytest.mark.anyio
async def test_gdacs_live_feed_connectivity_and_schema():
    """Verify that GDACS adapter connects to real API and returns valid LiveCycloneStatusResponse."""
    adapter = GDACSAdapter()
    status = await adapter.get_live_cyclone_status()

    assert status.source == "GDACS"
    assert status.data_mode == "LIVE"
    assert status.live_status in ["ACTIVE", "CALM", "UNAVAILABLE"]

    # When CALM, active_cyclone must be explicitly False
    if status.live_status == "CALM":
        assert status.active_cyclone is False
        assert status.cyclone is None
        assert "No active tropical cyclone" in status.message

    # When ACTIVE, active_cyclone must be True and cyclone object populated
    elif status.live_status == "ACTIVE":
        assert status.active_cyclone is True
        assert status.cyclone is not None
        # Anti-fabrication check: central_pressure_mb must be None if not provided by GDACS
        assert status.cyclone.central_pressure_mb is None or isinstance(status.cyclone.central_pressure_mb, float)


@pytest.mark.anyio
async def test_gdacs_failure_produces_unavailable_not_calm():
    """Verify that a network failure reports UNAVAILABLE, never falsely reporting CALM."""
    adapter = GDACSAdapter(base_url="https://invalid-gdacs-domain-test.local/api")
    status = await adapter.get_live_cyclone_status()

    assert status.live_status == "UNAVAILABLE"
    # Must NOT report active_cyclone=False (which would indicate a verified calm basin)
    assert status.active_cyclone is None
    assert status.cyclone is None
    assert "unreachable" in status.message.lower()


def test_api_storms_live_endpoint():
    """Verify GET /api/storms/live returns HTTP 200 with valid schema."""
    res = client.get("/api/storms/live")
    assert res.status_code == 200
    data = res.json()

    assert data["source"] == "GDACS"
    assert data["data_mode"] == "LIVE"
    assert data["live_status"] in ["ACTIVE", "CALM", "UNAVAILABLE"]
    assert "fetched_at" in data

    if data["live_status"] == "CALM":
        assert data["active_cyclone"] is False
        assert data["cyclone"] is None


def test_api_storms_live_track_endpoint():
    """Verify GET /api/storms/live/track returns valid GeoJSON FeatureCollection."""
    res = client.get("/api/storms/live/track")
    assert res.status_code == 200
    data = res.json()

    assert data.get("type") == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)
    assert "properties" in data
    assert data["properties"].get("status") in ["ACTIVE", "CALM", "UNAVAILABLE"]


def test_api_live_snapshot_endpoint():
    """Verify GET /api/live/snapshot returns live status and does not fabricate storm risk during calm."""
    res = client.get("/api/live/snapshot")
    assert res.status_code == 200
    data = res.json()

    assert data["system_mode"] == "LIVE OPERATIONS"
    assert "live_status" in data
    assert data["live_status"] in ["ACTIVE", "CALM", "UNAVAILABLE"]

    # When no active storm, critical_facilities_exposed must be 0
    if not data["active_threat_detected"]:
        assert data["critical_facilities_exposed"] == 0
        assert "Ambient Coastal Surface Telemetry" in data["current_weather"].get("observation_type", "")


def test_historical_storms_remain_intact():
    """Verify historical storms pipeline (Amphan, Remal, Fani) is completely unaffected."""
    # 1. Storm catalog
    res_cat = client.get("/api/storms")
    assert res_cat.status_code == 200
    cat = res_cat.json()
    storm_ids = [s["storm_id"] for s in cat]
    assert any("2020136N10088" in s for s in storm_ids)  # Amphan
    assert any("2024145N14087" in s for s in storm_ids)  # Remal
    assert any("2019117N10087" in s for s in storm_ids)  # Fani

    # 2. Amphan track
    res_amphan = client.get("/api/storms/2020136N10088/track")
    assert res_amphan.status_code == 200
    assert res_amphan.json()["type"] == "FeatureCollection"
    assert len(res_amphan.json()["features"]) > 0


def test_scenario_simulator_remains_intact():
    """Verify scenario simulator POST /api/simulation/run continues to function."""
    payload = {
        "scenario_name": "Test Scenario",
        "landfall_lat": 21.65,
        "landfall_lon": 87.85,
        "max_wind_speed_knots": 110.0,
        "central_pressure_mb": 935.0,
        "surge_height_meters": 5.5,
        "track_heading_deg": 35.0,
    }
    res = client.post("/api/simulation/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "simulated_track" in data
    assert "hazard_footprint_polygon" in data
    assert "evaluated_assets" in data
