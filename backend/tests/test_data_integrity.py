"""Data Integrity and Domain Service Tests.

Verifies:
1. Requesting Storm B never returns Amphan.
2. Requesting invalid storm raises 404.
3. Risk engine cleanly separates Hazard, Exposure, Vulnerability, and Impact.
4. Provenance metadata is populated with valid status.
5. Scenario simulations are strictly marked as SCENARIO / MODELLED.
"""

import pytest
from fastapi.testclient import TestClient

from app.domain.infrastructure import AssetCategory, InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta
from app.main import app
from app.services.risk_engine import RiskEngineService
from app.services.simulation_engine import ScenarioSimulationParameters, SimulationEngineService

client = TestClient(app)


def test_storm_routing_integrity():
    """Verify that requesting Remal returns Remal, and invalid storm returns 404."""
    # 1. Remal request
    res_remal = client.get("/api/storms/2024145N14087")
    assert res_remal.status_code == 200
    assert res_remal.json()["name"] == "REMAL"
    assert res_remal.json()["season"] == 2024

    # 2. Amphan request
    res_amphan = client.get("/api/storms/2020136N10088")
    assert res_amphan.status_code == 200
    assert res_amphan.json()["name"] == "AMPHAN"
    assert res_amphan.json()["season"] == 2020

    # 3. Invalid storm request must return 404 (NEVER silently return Amphan)
    res_invalid = client.get("/api/storms/FAKE_STORM_9999")
    assert res_invalid.status_code == 404


def test_decomposed_risk_engine():
    """Verify Hazard, Exposure, Vulnerability, and Impact separation."""
    engine = RiskEngineService()

    dummy_asset = InfrastructureAsset(
        id="osm_node_101",
        name="Kakdwip Sub-Divisional Hospital",
        category=AssetCategory.HOSPITAL,
        lat=21.875,
        lon=88.188,
        elevation_m=3.2,
        dist_to_coast_km=4.5,
        district="South 24 Parganas",
        state="West Bengal",
        provenance=DataSourceMeta(
            source="OpenStreetMap",
            dataset="Overpass",
            status=DataMode.LIVE,
        ),
    )

    # Eyewall landfall conditions
    result = engine.evaluate_asset(
        asset=dummy_asset,
        cyclone_lat=21.85,
        cyclone_lon=88.20,
        cyclone_wind_knots=100.0,
    )

    # Check decomposed components exist
    assert hasattr(result, "hazard")
    assert hasattr(result, "exposure")
    assert hasattr(result, "vulnerability")
    assert hasattr(result, "impact")

    assert result.hazard.wind_hazard_score > 0.5
    assert result.exposure.coastal_exposure_score > 0.8
    assert result.vulnerability.elevation_vulnerability_score > 0.7
    assert result.vulnerability.asset_criticality_score == 1.0  # Hospital

    assert result.modelled_risk_score >= 0.5
    assert "Modelled Risk" in result.explanation
    assert result.provenance.status == DataMode.MODELLED


def test_simulation_disclaimer_integrity():
    """Verify scenario simulation output carries mandatory non-forecast disclaimer."""
    engine = RiskEngineService()
    sim_service = SimulationEngineService(risk_engine=engine)

    params = ScenarioSimulationParameters(
        scenario_name="Test Simulation",
        landfall_lat=21.65,
        landfall_lon=87.55,
        max_wind_speed_knots=115.0,
    )

    result = sim_service.run_scenario(params=params, assets=[])

    assert "SCENARIO / MODELLED" in result.disclaimer
    assert "NOT AN OFFICIAL FORECAST" in result.disclaimer
    assert result.provenance.status == DataMode.SCENARIO


def test_live_snapshot_endpoint():
    """Verify live snapshot returns current weather, provenance, and source health."""
    res = client.get("/api/live/snapshot")
    assert res.status_code == 200
    data = res.json()
    assert data["system_mode"] == "LIVE OPERATIONS"
    assert "source_health" in data
    assert "current_weather" in data
    assert data["provenance"]["status"] == "LIVE"


def test_system_status_endpoint():
    """Verify system health exposes all 5 authoritative sources."""
    res = client.get("/api/system/status")
    assert res.status_code == 200
    sources = res.json()["sources"]
    for expected in ["imd", "open_meteo", "osm", "gee", "ibtracs"]:
        assert expected in sources
        assert "status" in sources[expected]
        assert "latency_ms" in sources[expected]
