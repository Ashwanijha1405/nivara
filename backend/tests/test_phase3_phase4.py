"""Unit and integration tests for Phase 3 and Phase 4.

Phase 3: Hydrodynamic Storm-Surge Inundation & Coastal Depth Modeling
- Inverted barometer (barometric setup) physics
- Bay of Bengal bathymetric shoaling factor
- Wind stress setup physics
- Inland exponential decay and net surface inundation depth
- SimulationEngine multi-band surge depth zones (<1.5m, 1.5-3.0m, >3.0m)

Phase 4: Spatial Rainfall Prediction & Flooding Damage Pathways
- Radial rainband model and 24h accumulation
- Topographic pluvial pooling depth
- Water-over-road impassability logic (inundation >= 0.30m or pluvial >= 0.45m)
- Open-Meteo hourly precipitation forecast integration
"""

import pytest
from unittest.mock import patch, MagicMock

from app.domain.infrastructure import AssetCategory, InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta
from app.services.risk_engine import RiskEngineService
from app.services.simulation_engine import ScenarioSimulationParameters, SimulationEngineService
from app.data_sources.open_meteo.open_meteo_adapter import OpenMeteoAdapter


def _build_test_asset(
    asset_id: str,
    name: str,
    category: AssetCategory,
    lat: float,
    lon: float,
    elevation_m: float,
    dist_to_coast_km: float,
) -> InfrastructureAsset:
    return InfrastructureAsset(
        id=asset_id,
        name=name,
        category=category,
        lat=lat,
        lon=lon,
        elevation_m=elevation_m,
        dist_to_coast_km=dist_to_coast_km,
        district="Purba Medinipur",
        state="West Bengal",
        provenance=DataSourceMeta(
            source="OSM",
            dataset="Test",
            retrieved_at="2026-09-30T00:00:00Z",
            status=DataMode.LIVE,
            confidence="HIGH",
        ),
    )


# ==============================================================================
# PHASE 3 TESTS: Storm-Surge Inundation & Coastal Depth Modeling
# ==============================================================================


def test_hydrodynamic_surge_physics_shoaling_and_decay():
    """Verify barometric setup, bathymetric shoaling factor, wind stress, and inland decay."""
    engine = RiskEngineService()

    # Coastal asset in Head Bay / Sundarbans (lat=21.8, lon=88.5, low elevation=1.0m, dist_to_coast=0.5km)
    coastal_head_bay = _build_test_asset(
        asset_id="coastal_1",
        name="Sundarbans Embankment Road",
        category=AssetCategory.ROAD,
        lat=21.8,
        lon=88.5,
        elevation_m=1.0,
        dist_to_coast_km=0.5,
    )

    # Cyclone close to the asset (dist ~10 km, Cat 4 wind 120 kts, central pressure 940 hPa)
    res_surge = engine.evaluate_asset(
        asset=coastal_head_bay,
        cyclone_lat=21.85,
        cyclone_lon=88.55,
        cyclone_wind_knots=120.0,
        central_pressure_mb=940.0,
    )

    # 1. Barometric setup: ~0.0101 * (1013.25 - 940) = 0.74m
    # 2. Wind stress setup with k_shoal=1.40 for Head Bay: 0.00042 * (120)^1.82 * 1.40 = ~3.6m
    # 3. Open-coast surge ~ 4.3m
    # 4. Inland decay over 0.5km: minor decay (<10%)
    # 5. Net inundation depth = surge_local - elevation_m = ~4.0m - 1.0m = ~3.0m
    assert res_surge.hazard.surge_height_m > 3.0
    assert res_surge.hazard.inundation_depth_m > 2.0
    assert res_surge.inundation_depth_m == res_surge.hazard.inundation_depth_m
    assert res_surge.surge_height_m == res_surge.hazard.surge_height_m

    # Higher elevation inland asset should have lower or zero inundation
    high_inland = _build_test_asset(
        asset_id="inland_1",
        name="Inland Substation",
        category=AssetCategory.POWER_GRID,
        lat=22.5,
        lon=88.5,
        elevation_m=15.0,  # 15m elevation
        dist_to_coast_km=45.0,  # 45km from coast
    )

    res_inland = engine.evaluate_asset(
        asset=high_inland,
        cyclone_lat=21.85,
        cyclone_lon=88.55,
        cyclone_wind_knots=120.0,
        central_pressure_mb=940.0,
    )

    # Inundation depth should be zero because elevation exceeds decayed surge
    assert res_inland.hazard.inundation_depth_m == 0.0
    assert res_inland.inundation_depth_m == 0.0


def test_simulation_engine_multi_band_surge_zones():
    """Verify that SimulationEngine generates multi-band surge depth zones in scenario results."""
    sim_service = SimulationEngineService()
    params = ScenarioSimulationParameters(
        scenario_name="Amphan Cat 5 Simulation",
        landfall_lat=21.6,
        landfall_lon=88.2,
        max_wind_speed_knots=130.0,
        surge_height_meters=4.5,
        track_heading_deg=35.0,
        central_pressure_mb=925.0,
    )

    result = sim_service.run_scenario(params=params, assets=[])

    assert result.surge_depth_zones is not None
    assert len(result.surge_depth_zones) == 3

    zone_labels = [z["zone_label"] for z in result.surge_depth_zones]
    assert "> 3.0m (Extreme Surge)" in zone_labels
    assert "1.5m - 3.0m (Severe Inundation)" in zone_labels
    assert "< 1.5m (Peripheral Surge / Runoff)" in zone_labels

    for zone in result.surge_depth_zones:
        assert "polygon" in zone
        ring = zone["polygon"]
        assert len(ring) >= 4  # closed ring has at least 4 coordinates
        assert ring[0] == ring[-1]  # first and last equal
        assert "fill_color" in zone
        assert zone["fill_color"].startswith("#")


# ==============================================================================
# PHASE 4 TESTS: Rainfall Prediction & Road Inundation Impassability
# ==============================================================================


def test_radial_rainfall_prediction_and_pluvial_pooling():
    """Verify radial rainband accumulation and pluvial pooling depth in flat terrain."""
    engine = RiskEngineService()

    flat_road = _build_test_asset(
        asset_id="road_flat",
        name="Coastal Highway Flat Section",
        category=AssetCategory.ROAD,
        lat=21.6,
        lon=87.5,
        elevation_m=1.5,
        dist_to_coast_km=5.0,
    )

    # Cyclone eye at 30km distance (within heavy core rainband, wind ~97 kts = 180 km/h)
    res = engine.evaluate_asset(
        asset=flat_road,
        cyclone_lat=21.8,
        cyclone_lon=87.7,
        cyclone_wind_knots=97.0,
    )

    assert res.hazard.rainfall_rate_mmh > 10.0  # Intense tropical rainfall
    assert res.hazard.rainfall_accum_24h_mm > 100.0  # Severe 24h accumulation
    assert res.hazard.pluvial_flood_depth_m > 0.0  # Flat terrain accumulates pluvial water
    assert res.rainfall_accum_24h_mm == res.hazard.rainfall_accum_24h_mm
    assert res.pluvial_flood_depth_m == res.hazard.pluvial_flood_depth_m


def test_road_impassable_on_surge_inundation_water_over_road():
    """Verify road becomes IMPASSABLE when surge inundation depth >= 0.30m (approx 1 ft)."""
    engine = RiskEngineService()

    low_road = _build_test_asset(
        asset_id="coastal_sh_4",
        name="State Highway 4 Coastal Link",
        category=AssetCategory.ROAD,
        lat=21.65,
        lon=87.55,
        elevation_m=0.5,
        dist_to_coast_km=0.2,
    )

    # Severe cyclone causing > 1.5m surge inundation over low-lying road
    res = engine.evaluate_asset(
        asset=low_road,
        cyclone_lat=21.68,
        cyclone_lon=87.58,
        cyclone_wind_knots=108.0,
        central_pressure_mb=950.0,
    )

    assert res.hazard.inundation_depth_m >= 0.30
    assert res.access_status == "IMPASSABLE"


def test_road_passable_when_minimal_hazard():
    """Verify road remains PASSABLE when distant from storm and surge/pluvial flooding is negligible."""
    engine = RiskEngineService()

    high_road = _build_test_asset(
        asset_id="inland_nh",
        name="NH High Ground Bypass",
        category=AssetCategory.ROAD,
        lat=23.5,
        lon=86.5,
        elevation_m=50.0,
        dist_to_coast_km=180.0,
    )

    # Distant cyclone
    res = engine.evaluate_asset(
        asset=high_road,
        cyclone_lat=18.0,
        cyclone_lon=88.0,
        cyclone_wind_knots=40.0,
    )

    assert res.hazard.inundation_depth_m == 0.0
    assert res.hazard.pluvial_flood_depth_m < 0.20
    assert res.access_status == "PASSABLE"


@pytest.mark.anyio
async def test_open_meteo_hourly_precipitation_forecast():
    """Verify Open-Meteo adapter retrieves hourly precipitation series."""
    adapter = OpenMeteoAdapter()

    mock_payload = {
        "hourly": {
            "time": ["2026-09-30T00:00", "2026-09-30T01:00", "2026-09-30T02:00"],
            "precipitation": [5.2, 12.8, 25.4],
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        result = await adapter.get_hourly_precipitation_forecast(21.62, 87.51, hours=3)

        assert result == [5.2, 12.8, 25.4]
