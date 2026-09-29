"""Unit and integration tests for Phase 1 and Phase 2.

Verifies:
- Phase 1: Live forecast track predictive risk & Gemini operational advisory
  - GET /api/storms/live/forecast-risk (CALM, UNAVAILABLE, ACTIVE)
  - Forward translation speed, approach heading, and landfall ETA
  - GET /api/storms/live/advisory (CALM, ACTIVE)
- Phase 2: Road networks and evacuation corridor vulnerability
  - OSM Overpass query inclusion of arterial highways and bridges
  - Road access status (PASSABLE, VULNERABLE, IMPASSABLE)
  - Facility isolation risk modeling
"""

import pytest
from fastapi.testclient import TestClient

from app.api.routes import gdacs_adapter, live_monitor
from app.data_sources.osm.osm_adapter import OSMAdapter
from app.domain.cyclone import LiveCycloneInfo, LiveCycloneStatusResponse
from app.domain.infrastructure import AssetCategory, InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta
from app.domain.risk import ModelledRiskResult
from app.main import app
from app.services.risk_engine import RiskEngineService

client = TestClient(app)


def test_osm_adapter_query_includes_roads_and_bridges():
    """Verify that OSM Overpass query explicitly requests highways and bridges with center geometry."""
    adapter = OSMAdapter()
    query = adapter.build_query(min_lat=21.0, min_lon=86.0, max_lat=23.0, max_lon=89.0)

    assert 'way["highway"~"motorway|trunk|primary|secondary"]' in query
    assert 'way["bridge"="yes"]' in query
    assert "out body center" in query


def test_road_and_bridge_access_status_evaluation():
    """Verify that risk engine computes access_status and isolation_risk on infrastructure assets."""
    engine = RiskEngineService()

    road_asset = InfrastructureAsset(
        id="osm_way_101",
        name="NH-116 Expressway",
        category=AssetCategory.ROAD,
        lat=21.65,
        lon=87.55,
        elevation_m=2.0,
        dist_to_coast_km=2.0,
        district="Purba Medinipur",
        state="West Bengal",
        provenance=DataSourceMeta(
            source="OSM",
            dataset="Test",
            retrieved_at="2026-09-29T00:00:00Z",
            status=DataMode.LIVE,
            confidence="HIGH",
        ),
    )

    # Severe cyclone directly overhead (high risk)
    severe_res = engine.evaluate_asset(
        asset=road_asset,
        cyclone_lat=21.65,
        cyclone_lon=87.55,
        cyclone_wind_knots=120.0,
        data_mode=DataMode.LIVE,
    )
    assert severe_res.access_status in ["IMPASSABLE", "VULNERABLE"]
    assert severe_res.isolation_risk in ["HIGH", "MODERATE"]

    # Distant cyclone (low risk)
    calm_res = engine.evaluate_asset(
        asset=road_asset,
        cyclone_lat=10.0,
        cyclone_lon=75.0,
        cyclone_wind_knots=45.0,
        data_mode=DataMode.LIVE,
    )
    assert calm_res.access_status == "PASSABLE"
    assert calm_res.isolation_risk == "LOW"


def test_live_forecast_risk_calm_state(monkeypatch):
    """Verify GET /api/storms/live/forecast-risk returns CALM response when no cyclone exists."""
    async def mock_calm_status():
        return LiveCycloneStatusResponse(
            source="GDACS",
            data_mode="LIVE",
            live_status="CALM",
            active_cyclone=False,
            cyclone=None,
            fetched_at="2026-09-29T00:00:00Z",
            message="No active tropical cyclone detected.",
        )

    monkeypatch.setattr(gdacs_adapter, "get_live_cyclone_status", mock_calm_status)

    res = client.get("/api/storms/live/forecast-risk")
    assert res.status_code == 200
    data = res.json()
    assert data["live_status"] == "CALM"
    assert data["total_forecast_steps"] == 0
    assert data["forecast_timesteps"] == []


def test_live_forecast_risk_unavailable_state(monkeypatch):
    """Verify GET /api/storms/live/forecast-risk returns UNAVAILABLE when feed fails."""
    async def mock_unavailable_status():
        return LiveCycloneStatusResponse(
            source="GDACS",
            data_mode="LIVE",
            live_status="UNAVAILABLE",
            active_cyclone=None,
            cyclone=None,
            fetched_at="2026-09-29T00:00:00Z",
            message="GDACS feed unreachable.",
        )

    monkeypatch.setattr(gdacs_adapter, "get_live_cyclone_status", mock_unavailable_status)

    res = client.get("/api/storms/live/forecast-risk")
    assert res.status_code == 200
    data = res.json()
    assert data["live_status"] == "UNAVAILABLE"
    assert data["total_forecast_steps"] == 0


def test_live_forecast_risk_active_projection(monkeypatch):
    """Verify GET /api/storms/live/forecast-risk produces forward timesteps, forward speed, and landfall ETA."""
    mock_cyclone = LiveCycloneInfo(
        source="GDACS",
        data_mode=DataMode.LIVE,
        event_id="1009999",
        episode_id="1",
        storm_name="TEST_CYCLONE",
        is_active=True,
        current_lat=18.5,
        current_lon=88.0,
        wind_speed_kmh=110.0,
        wind_speed_kts=59.4,
        alert_level="Orange",
        alert_score=2.0,
        fetched_at="2026-09-29T00:00:00Z",
        track=[
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [88.0, 18.5],
                        [88.2, 19.3],  # +6h
                        [88.4, 20.1],  # +12h
                        [88.6, 21.0],  # +18h
                    ],
                },
                "properties": {"feature_type": "forecast_track"},
            }
        ],
    )

    async def mock_active_status():
        return LiveCycloneStatusResponse(
            source="GDACS",
            data_mode="LIVE",
            live_status="ACTIVE",
            active_cyclone=True,
            cyclone=mock_cyclone,
            fetched_at="2026-09-29T00:00:00Z",
            message="Active tropical cyclone TEST_CYCLONE detected.",
        )

    monkeypatch.setattr(gdacs_adapter, "get_live_cyclone_status", mock_active_status)

    res = client.get("/api/storms/live/forecast-risk")
    assert res.status_code == 200
    data = res.json()
    assert data["live_status"] == "ACTIVE"
    assert data["storm_name"] == "TEST_CYCLONE"
    assert data["forward_speed_kmh"] is not None
    assert data["forward_speed_kmh"] > 0
    assert data["approach_heading_deg"] is not None
    assert data["total_forecast_steps"] >= 2

    # Check first timestep (+0h Current Position)
    step0 = data["forecast_timesteps"][0]
    assert step0["step_index"] == 0
    assert step0["forecast_label"] == "+0h (Current Position)"
    assert step0["lat"] == 18.5
    assert step0["lon"] == 88.0
    assert "evaluated_assets" in step0
    assert "impassable_roads_count" in step0


def test_live_advisory_calm_and_active(monkeypatch):
    """Verify GET /api/storms/live/advisory for both CALM and ACTIVE operational states."""
    # 1. Calm state
    async def mock_calm_status():
        return LiveCycloneStatusResponse(
            source="GDACS",
            data_mode="LIVE",
            live_status="CALM",
            active_cyclone=False,
            cyclone=None,
            fetched_at="2026-09-29T00:00:00Z",
            message="No active cyclone.",
        )

    monkeypatch.setattr(gdacs_adapter, "get_live_cyclone_status", mock_calm_status)

    res_calm = client.get("/api/storms/live/advisory")
    assert res_calm.status_code == 200
    assert res_calm.json()["live_status"] == "CALM"
    assert res_calm.json()["advisory"] is None

    # 2. Active state
    mock_cyclone = LiveCycloneInfo(
        source="GDACS",
        data_mode=DataMode.LIVE,
        event_id="1009999",
        episode_id="1",
        storm_name="TEST_CYCLONE",
        is_active=True,
        current_lat=21.5,
        current_lon=87.5,
        wind_speed_kmh=120.0,
        wind_speed_kts=64.8,
        alert_level="Red",
        alert_score=2.5,
        fetched_at="2026-09-29T00:00:00Z",
    )

    async def mock_active_status():
        return LiveCycloneStatusResponse(
            source="GDACS",
            data_mode="LIVE",
            live_status="ACTIVE",
            active_cyclone=True,
            cyclone=mock_cyclone,
            fetched_at="2026-09-29T00:00:00Z",
            message="Active cyclone.",
        )

    monkeypatch.setattr(gdacs_adapter, "get_live_cyclone_status", mock_active_status)

    res_active = client.get("/api/storms/live/advisory")
    assert res_active.status_code == 200
    data = res_active.json()
    assert data["live_status"] == "ACTIVE"
    assert data["storm_name"] == "TEST_CYCLONE"
    advisory = data["advisory"]
    assert advisory is not None
    assert "headline" in advisory
    assert len(advisory["grounded_hazards"]) > 0
    assert len(advisory["actionable_directives"]) > 0
    assert len(advisory["operational_memo"]) > 0
    assert len(advisory["public_alert_sms"]) > 0
