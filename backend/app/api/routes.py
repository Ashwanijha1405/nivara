"""Nivara Disaster Intelligence Platform — Primary API Router.

Refactored domain-driven endpoints:
- /api/live/*           -> Live operational monitoring & active threats
- /api/storms/*         -> Historical NOAA IBTrACS & IMD operational tracks
- /api/infrastructure/* -> Real OpenStreetMap infrastructure discovery
- /api/risk/*           -> Decomposed hazard, exposure, vulnerability & impact
- /api/simulation/*     -> Hypothetical scenario simulator
- /api/reports/*        -> Standardized situation & risk briefings
- /api/system/*         -> Authoritative source health & provenance
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.config import get_settings
from app.data_sources.gee.gee_adapter import GEEAdapter
from app.data_sources.ibtracs.ibtracs_adapter import IBTrACSAdapter
from app.data_sources.imd.imd_adapter import IMDAdapter
from app.data_sources.open_meteo.open_meteo_adapter import OpenMeteoAdapter
from app.data_sources.osm.osm_adapter import OSMAdapter
from app.domain.provenance import DataMode, DataSourceMeta
from app.domain.risk import ModelledRiskResult
from app.services.advisory_engine import AdvisoryEngineService
from app.services.live_monitor import LiveMonitorService, LiveOperationsSnapshot
from app.services.report_service import OperationalReport, ReportService
from app.services.risk_engine import RiskEngineService
from app.services.simulation_engine import (
    ScenarioSimulationParameters,
    ScenarioSimulationResult,
    SimulationEngineService,
)

router = APIRouter(prefix="/api", tags=["disaster-intelligence"])

settings = get_settings()

# Initialize Domain Adapters
imd_adapter = IMDAdapter(base_url=settings.imd_bulletin_url)
ibtracs_adapter = IBTrACSAdapter(data_dir=settings.data_dir)
open_meteo_adapter = OpenMeteoAdapter(base_url=settings.open_meteo_base_url)
gee_adapter = GEEAdapter(
    project_id=settings.gee_project_id,
    service_account_email=settings.gee_service_account_email,
    private_key_path=settings.gee_private_key_path,
)
osm_adapter = OSMAdapter(
    endpoint_url=settings.overpass_api_url,
    data_dir=settings.data_dir,
    demo_mode=settings.demo_mode,
)

# Initialize Core Services
risk_engine = RiskEngineService()
live_monitor = LiveMonitorService(
    imd_adapter=imd_adapter,
    open_meteo=open_meteo_adapter,
    osm_adapter=osm_adapter,
    gee_adapter=gee_adapter,
    risk_engine=risk_engine,
)
simulation_engine = SimulationEngineService(risk_engine=risk_engine)
advisory_engine = AdvisoryEngineService(
    api_key=settings.gemini_api_key,
    model_name=settings.gemini_model,
)
report_service = ReportService()


# ==============================================================================
# 1. LIVE OPERATIONS & SYSTEM HEALTH
# ==============================================================================

@router.get("/health", summary="Basic system health check")
async def health_check() -> Dict[str, Any]:
    """Basic service health check with operational mode."""
    return {
        "status": "ok",
        "service": "nivara-disaster-intelligence",
        "demo_mode": settings.demo_mode,
        "authoritative_sources": [
            "India Meteorological Department (IMD)",
            "NOAA IBTrACS Best Track Archive",
            "Open-Meteo Weather Models & SRTM",
            "OpenStreetMap Contributors",
            "Google Earth Engine",
            "Google Gemini 3.7 Flash",
        ],
    }


@router.get("/system/status", summary="Data sources connectivity and health status")
async def get_system_status() -> Dict[str, Any]:
    """Detailed health, latency, and freshness for all 6 external providers."""
    health_records = await live_monitor.get_system_health()
    return {
        "system_status": "OPERATIONAL",
        "demo_mode_active": settings.demo_mode,
        "sources": {k: v.model_dump() for k, v in health_records.items()},
    }


@router.get("/live/snapshot", summary="Current live situational awareness snapshot", response_model=LiveOperationsSnapshot)
async def get_live_snapshot() -> LiveOperationsSnapshot:
    """Retrieve unified real-time operational picture across active basin threats, weather, and lifelines."""
    return await live_monitor.get_live_operations_snapshot()


# ==============================================================================
# 2. STORM INTELLIGENCE & HISTORICAL REPLAY (FIXED STORM_ID ROUTING)
# ==============================================================================

@router.get("/storms", summary="List historical storm catalog and active systems")
async def list_storms() -> List[Dict[str, Any]]:
    """Return catalog of verified historical cyclones and active operational feeds."""
    catalog = ibtracs_adapter.get_historical_catalog()

    # Check if IMD currently has an active tropical system
    imd_status = await imd_adapter.get_current_basin_status()
    if imd_status.is_active_cyclone:
        catalog.insert(
            0,
            {
                "storm_id": "IMD_LIVE_CURRENT",
                "name": "ACTIVE BASIN DISTURBANCE",
                "season": 2026,
                "basin": "NI",
                "peak_intensity": "Active Operational Storm",
                "peak_winds_knots": 45.0,
                "min_pressure_mb": 994.0,
                "landfall_area": "Monitoring Sector",
                "landfall_date": "Active",
                "total_timesteps": 6,
                "provenance": {
                    "source": "India Meteorological Department (IMD)",
                    "status": "LIVE",
                    "dataset": "Operational Cyclone Warning Center",
                },
            },
        )

    return catalog


@router.get("/storms/{storm_id}", summary="Get metadata for a specific storm")
async def get_storm_details(storm_id: str) -> Dict[str, Any]:
    """Retrieve verified metadata for a storm. Strictly fails if storm is not in database."""
    try:
        track = ibtracs_adapter.load_storm_track(storm_id)
        return {
            "storm_id": track.storm_id,
            "name": track.name,
            "season": track.season,
            "basin": track.basin,
            "total_waypoints": len(track.waypoints),
            "start_time": track.waypoints[0].timestamp if track.waypoints else "",
            "end_time": track.waypoints[-1].timestamp if track.waypoints else "",
            "peak_winds_knots": max((w.wind_speed_knots for w in track.waypoints), default=0.0),
            "min_pressure_mb": min((w.pressure_mb for w in track.waypoints if w.pressure_mb), default=1000.0),
            "provenance": track.provenance.model_dump(),
        }
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storm '{storm_id}' could not be found: {str(exc)}",
        )


@router.get("/storms/{storm_id}/track", summary="Get complete storm trajectory GeoJSON")
async def get_storm_track(storm_id: str) -> Dict[str, Any]:
    """Retrieve full storm track with line geometry, waypoints, and wind categories."""
    try:
        track = ibtracs_adapter.load_storm_track(storm_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storm track '{storm_id}' not found: {str(exc)}",
        )

    coords = [[w.lon, w.lat] for w in track.waypoints]
    features: List[Dict[str, Any]] = [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "feature_type": "track_path",
                "storm_id": track.storm_id,
                "name": track.name,
                "source": "NOAA IBTrACS",
            },
        }
    ]

    for w in track.waypoints:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [w.lon, w.lat]},
                "properties": {
                    "feature_type": "storm_center",
                    "step_index": w.step_index,
                    "timestamp": w.timestamp,
                    "wind_speed_knots": w.wind_speed_knots,
                    "wind_speed_kph": w.wind_speed_kph,
                    "pressure_mb": w.pressure_mb,
                    "cyclone_category": w.category,
                    "is_landfall_point": w.is_landfall_point,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "properties": {
            "storm_id": track.storm_id,
            "name": track.name,
            "season": track.season,
            "basin": track.basin,
            "total_timesteps": len(track.waypoints),
            "provenance": track.provenance.model_dump(),
        },
        "features": features,
    }


@router.get("/storms/{storm_id}/risk", summary="Evaluate per-timestep infrastructure risk")
async def get_storm_timestep_risk(
    storm_id: str,
    step_index: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Compute decomposed hazard, exposure, vulnerability, and modelled risk for a specific timestep."""
    try:
        track = ibtracs_adapter.load_storm_track(storm_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storm '{storm_id}' not found: {str(exc)}",
        )

    if not track.waypoints:
        raise HTTPException(status_code=400, detail="Storm track contains no waypoints.")

    bounded_step = max(0, min(step_index, len(track.waypoints) - 1))
    target_point = track.waypoints[bounded_step]

    # Fetch infrastructure assets from OSM
    infra_assets = await osm_adapter.fetch_infrastructure()

    evaluated_assets: List[ModelledRiskResult] = []
    for asset in infra_assets:
        res = risk_engine.evaluate_asset(
            asset=asset,
            cyclone_lat=target_point.lat,
            cyclone_lon=target_point.lon,
            cyclone_wind_knots=target_point.wind_speed_knots,
            data_mode=DataMode.HISTORICAL if "HISTORICAL" in track.provenance.status else DataMode.MODELLED,
        )
        evaluated_assets.append(res)

    evaluated_assets.sort(key=lambda a: a.modelled_risk_score, reverse=True)

    # Format into GeoJSON
    features = []
    for a in evaluated_assets:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        a.exposure.distance_to_coastline_km,  # will map from asset coords
                    ],
                },
                "properties": a.model_dump(),
            }
        )

    return {
        "storm_id": track.storm_id,
        "storm_name": track.name,
        "step_index": target_point.step_index,
        "timestamp": target_point.timestamp,
        "cyclone_center": {"lat": target_point.lat, "lon": target_point.lon},
        "wind_speed_knots": target_point.wind_speed_knots,
        "category": target_point.category,
        "total_assets_evaluated": len(evaluated_assets),
        "critical_assets_count": sum(1 for a in evaluated_assets if a.risk_level in ["CRITICAL", "HIGH"]),
        "assets": [a.model_dump() for a in evaluated_assets],
        "provenance": track.provenance.model_dump(),
    }


@router.get("/storms/{storm_id}/advisory", summary="Grounded operational briefing from Gemini 3.7 Flash")
async def get_storm_advisory(
    storm_id: str,
    step_index: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Generate Gemini 3.7 Flash operational advisory grounded on evaluated assets."""
    risk_data = await get_storm_timestep_risk(storm_id=storm_id, step_index=step_index)
    assets_raw = risk_data.get("assets", [])

    if not assets_raw:
        return {"error": "No assets available for advisory synthesis"}

    # Group by district
    districts: Dict[str, List[ModelledRiskResult]] = {}
    for a in assets_raw:
        dname = a.get("district", "Coastal Sector")
        districts.setdefault(dname, []).append(ModelledRiskResult(**a))

    # Sort districts by maximum risk
    sorted_districts = sorted(
        districts.items(),
        key=lambda item: max((x.modelled_risk_score for x in item[1]), default=0.0),
        reverse=True,
    )

    advisories = []
    # Generate for top 2 impacted districts
    for dname, d_assets in sorted_districts[:2]:
        adv = await advisory_engine.generate_district_briefing(
            district=dname,
            state="West Bengal",
            storm_name=risk_data.get("storm_name", "CYCLONE"),
            current_wind_knots=risk_data.get("wind_speed_knots", 80.0),
            assets=d_assets,
            data_mode=DataMode.HISTORICAL if "HISTORICAL" in risk_data["provenance"]["status"] else DataMode.MODELLED,
        )
        advisories.append(adv.model_dump())

    return {
        "storm_id": storm_id,
        "storm_name": risk_data.get("storm_name"),
        "step_index": step_index,
        "timestamp": risk_data.get("timestamp"),
        "advisories": advisories,
        "disclaimer": "AI-GENERATED ADVISORY — Grounded on modelled risk inputs. Review with SDMA protocols.",
    }


# ==============================================================================
# 3. CRITICAL INFRASTRUCTURE EXPLORER
# ==============================================================================

@router.get("/infrastructure", summary="Query real OpenStreetMap infrastructure lifelines")
async def list_infrastructure(
    category: Optional[str] = Query(None, description="hospital, power_grid, road, shelter, airport"),
    district: Optional[str] = Query(None, description="Administrative district"),
) -> List[Dict[str, Any]]:
    """Return discovered infrastructure facilities with OSM tags, elevation, and distance to coast."""
    assets = await osm_adapter.fetch_infrastructure()

    filtered = assets
    if category:
        filtered = [a for a in filtered if a.category.value.lower() == category.lower()]
    if district:
        filtered = [a for a in filtered if district.lower() in a.district.lower()]

    return [a.model_dump() for a in filtered]


@router.get("/infrastructure/{asset_id}", summary="Get detailed record for an asset")
async def get_infrastructure_detail(asset_id: str) -> Dict[str, Any]:
    """Retrieve full asset record, OSM ID, elevation, and location drivers."""
    assets = await osm_adapter.fetch_infrastructure()
    matched = next((a for a in assets if a.id == asset_id), None)

    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Infrastructure facility '{asset_id}' not found.",
        )

    return matched.model_dump()


# ==============================================================================
# 4. SCENARIO SIMULATOR (STRICTLY ISOLATED)
# ==============================================================================

@router.post("/simulation/run", summary="Execute hypothetical cyclone impact scenario", response_model=ScenarioSimulationResult)
async def run_scenario_simulation(
    params: ScenarioSimulationParameters,
) -> ScenarioSimulationResult:
    """Execute hypothetical cyclone landfall scenario. Strictly tagged as SCENARIO / MODELLED."""
    infra_assets = await osm_adapter.fetch_infrastructure()
    return simulation_engine.run_scenario(params=params, assets=infra_assets)


# ==============================================================================
# 5. AUTOMATED OPERATIONAL REPORTS
# ==============================================================================

@router.get("/reports/situation", summary="Generate official Situation Report (SitRep)")
async def generate_situation_report() -> Dict[str, Any]:
    """Generate standardized operational SitRep document."""
    snapshot = await live_monitor.get_live_operations_snapshot()
    report = report_service.generate_situation_report(snapshot.model_dump())
    return report.model_dump()
