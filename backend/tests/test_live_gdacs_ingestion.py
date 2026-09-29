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

from app.data_sources.gdacs.gdacs_adapter import GDACSAdapter, calculate_bearing
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


def test_calculate_bearing():
    """Verify forward azimuth calculation and edge cases."""
    # North
    assert calculate_bearing(20.0, 85.0, 21.0, 85.0) == 0.0
    # East along equator (great circle coincides with equator)
    assert calculate_bearing(0.0, 85.0, 0.0, 86.0) == 90.0
    # East at 20N (initial great circle azimuth is ~89.8 deg)
    assert pytest.approx(calculate_bearing(20.0, 85.0, 20.0, 86.0), abs=0.5) == 90.0
    # South
    assert calculate_bearing(20.0, 85.0, 19.0, 85.0) == 180.0
    # West along equator
    assert calculate_bearing(0.0, 85.0, 0.0, 84.0) == 270.0
    # Identical coordinates must return None (strictly no synthetic heading)
    assert calculate_bearing(20.0, 85.0, 20.0, 85.0) is None


@pytest.mark.anyio
async def test_gdacs_active_nio_event_processing(monkeypatch):
    """Verify detailed parsing, classification, and anti-fabrication for an active NIO storm."""
    adapter = GDACSAdapter()

    mock_search_features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [88.5, 18.2]},
            "properties": {
                "eventtype": "TC",
                "eventid": 999999,
                "episodeid": 1,
                "eventname": "TEST_STORM",
                "iscurrent": "true",
                "alertlevel": "Orange",
                "alertscore": 2.5,
                "fromdate": "2026-09-29T00:00:00",
                "datemodified": "2026-09-29T12:00:00",
                "iso3": "IND",
                "affectedcountries": [{"countryname": "India", "iso3": "IND"}],
                "severitydata": {
                    "severity": 120.0,
                    "severitytext": "Severe Cyclonic Storm (120 km/h)",
                },
                # Notice: central pressure NOT provided by GDACS
            },
        }
    ]

    mock_geometry_payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[87.0, 16.0], [88.0, 17.5]],
                },
                "properties": {"forecast": False, "Class": "Line_Line_0"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[88.0, 17.5], [89.0, 19.0]],
                },
                "properties": {"forecast": True, "Class": "Line_Line_1"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[86.0, 15.0], [90.0, 15.0], [90.0, 20.0], [86.0, 20.0], [86.0, 15.0]]],
                },
                "properties": {"Class": "Poly_Cones", "polygonlabel": "Uncertainty Cones"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[87.5, 17.0], [89.5, 17.0], [89.5, 19.0], [87.5, 19.0], [87.5, 17.0]]],
                },
                "properties": {"Class": "Poly_Red", "polygonlabel": "120 km/h"},
            },
        ],
    }

    async def mock_fetch_active():
        return mock_search_features

    async def mock_fetch_geo(event_id, episode_id):
        return mock_geometry_payload

    monkeypatch.setattr(adapter, "fetch_active_tropical_cyclones", mock_fetch_active)
    monkeypatch.setattr(adapter, "fetch_detailed_geometry", mock_fetch_geo)

    status = await adapter.get_live_cyclone_status()
    assert status.live_status == "ACTIVE"
    assert status.active_cyclone is True
    assert status.cyclone is not None
    assert status.cyclone.storm_name == "TEST_STORM"
    assert status.cyclone.current_lat == 18.2
    assert status.cyclone.current_lon == 88.5
    assert status.cyclone.wind_speed_kmh == 120.0
    assert status.cyclone.wind_speed_kts == round(120.0 / 1.852, 1)

    # Anti-fabrication check: central_pressure_mb must be null when GDACS does not provide it
    assert status.cyclone.central_pressure_mb is None

    # Heading safely derived from observed track coordinates: from (16.0, 87.0) to (17.5, 88.0)
    assert status.cyclone.heading_deg is not None
    assert 20.0 < status.cyclone.heading_deg < 40.0  # Approx North-East

    # GeoJSON track features
    track_geojson = await adapter.get_live_track_geojson()
    assert track_geojson["type"] == "FeatureCollection"
    assert track_geojson["properties"]["status"] == "ACTIVE"
    assert len(track_geojson["features"]) == 5  # 1 storm center Point + 2 LineStrings + 2 Polygons

    # Check feature classification
    types = [f["properties"].get("feature_type") for f in track_geojson["features"]]
    assert "storm_center" in types
    assert "observed_track" in types
    assert "forecast_track" in types
    assert "uncertainty_cone" in types
    assert "wind_hazard_polygon" in types


@pytest.mark.anyio
async def test_global_active_cyclone_outside_nio_is_ignored(monkeypatch):
    """Verify that an active hurricane in Mexico/Pacific is rejected and basin reports CALM."""
    adapter = GDACSAdapter()

    mexico_feature = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-110.9, 27.8]},
            "properties": {
                "eventtype": "TC",
                "eventid": 1001325,
                "episodeid": 36,
                "eventname": "POLO-26",
                "iscurrent": "true",
                "iso3": "MEX",
                "country": "Mexico",
                "affectedcountries": [{"countryname": "Mexico", "iso3": "MEX"}],
            },
        }
    ]

    async def mock_fetch_active():
        return mexico_feature

    monkeypatch.setattr(adapter, "fetch_active_tropical_cyclones", mock_fetch_active)

    status = await adapter.get_live_cyclone_status()
    assert status.live_status == "CALM"
    assert status.active_cyclone is False
    assert status.cyclone is None
    assert "No active tropical cyclone detected in North Indian Ocean basin" in status.message


@pytest.mark.anyio
async def test_caching_and_last_sync_retention(monkeypatch):
    """Verify in-memory caching and retention of last successful sync time on error."""
    adapter = GDACSAdapter(cache_ttl_seconds=120)

    call_count = 0

    async def mock_fetch_active():
        nonlocal call_count
        call_count += 1
        return []

    monkeypatch.setattr(adapter, "fetch_active_tropical_cyclones", mock_fetch_active)

    # First call: makes HTTP request
    status1 = await adapter.get_live_cyclone_status()
    assert call_count == 1
    assert status1.live_status == "CALM"
    last_sync = status1.last_successful_sync
    assert last_sync is not None

    # Second immediate call: served from in-memory cache, call_count remains 1
    status2 = await adapter.get_live_cyclone_status()
    assert call_count == 1
    assert status2 is status1

    # Simulate network failure on expired cache
    adapter._last_fetch_utc = None  # Force cache invalidation

    async def mock_fetch_fail():
        raise TimeoutError("Simulated network timeout")

    monkeypatch.setattr(adapter, "fetch_active_tropical_cyclones", mock_fetch_fail)

    status_fail = await adapter.get_live_cyclone_status()
    assert status_fail.live_status == "UNAVAILABLE"
    assert status_fail.active_cyclone is None
    # Verify retention of last_successful_sync
    assert status_fail.last_successful_sync == last_sync
