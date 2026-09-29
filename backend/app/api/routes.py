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
from app.data_sources.gdacs.gdacs_adapter import GDACSAdapter
from app.data_sources.gee.gee_adapter import GEEAdapter
from app.data_sources.ibtracs.ibtracs_adapter import IBTrACSAdapter
from app.data_sources.imd.imd_adapter import IMDAdapter
from app.data_sources.open_meteo.open_meteo_adapter import OpenMeteoAdapter
from app.data_sources.osm.osm_adapter import OSMAdapter
from app.domain.cyclone import LiveCycloneStatusResponse
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
gdacs_adapter = GDACSAdapter(
    base_url=settings.gdacs_base_url,
    timeout_seconds=settings.gdacs_timeout_seconds,
    cache_ttl_seconds=settings.gdacs_cache_ttl_seconds,
)
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
    gdacs_adapter=gdacs_adapter,
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

# In-memory caches keyed strictly by storm_id + step_index + timestamp
_storm_risk_cache: Dict[str, Dict[str, Any]] = {}
_storm_advisory_cache: Dict[str, Dict[str, Any]] = {}


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

    # Check if GDACS currently has an active tropical system in North Indian Ocean
    try:
        gdacs_status = await gdacs_adapter.get_live_cyclone_status()
        if gdacs_status.live_status == "ACTIVE" and gdacs_status.cyclone:
            c = gdacs_status.cyclone
            catalog.insert(
                0,
                {
                    "storm_id": f"GDACS_{c.event_id}",
                    "name": c.storm_name.upper(),
                    "season": 2026,
                    "basin": "NI",
                    "peak_intensity": c.intensity_text or f"Active Storm ({c.alert_level or 'ALERT'})",
                    "peak_winds_knots": c.wind_speed_kts,
                    "min_pressure_mb": c.central_pressure_mb,
                    "landfall_area": ", ".join(c.affected_countries) if c.affected_countries else "Coastal Sector",
                    "landfall_date": "Active Live Storm",
                    "total_timesteps": len(c.track) if c.track else 1,
                    "provenance": {
                        "source": "GDACS (UN OCHA / EC JRC)",
                        "status": "LIVE",
                        "dataset": "Real-Time Tropical Cyclone Ingestion",
                    },
                },
            )
    except Exception:
        pass

    return catalog


@router.get("/storms/live", summary="Get real-time cyclone status from GDACS", response_model=LiveCycloneStatusResponse)
async def get_live_cyclone_status() -> LiveCycloneStatusResponse:
    """Retrieve real-time cyclone status from GDACS (ACTIVE, CALM, or UNAVAILABLE)."""
    return await gdacs_adapter.get_live_cyclone_status()


@router.get("/storms/live/track", summary="Get GeoJSON trajectory and hazard polygons for active cyclone")
async def get_live_cyclone_track() -> Dict[str, Any]:
    """Retrieve full live storm track and hazard polygons as GeoJSON.
    
    Returns empty FeatureCollection if no active cyclone (CALM), or UNAVAILABLE status representation.
    """
    return await gdacs_adapter.get_live_track_geojson()


@router.get("/storms/live/risk", summary="Evaluate infrastructure risk for currently active cyclone")
async def get_live_cyclone_risk() -> Dict[str, Any]:
    """Compute decomposed hazard, exposure, vulnerability, and modelled risk for active GDACS cyclone.
    
    Returns empty FeatureCollection if no active cyclone (CALM), or UNAVAILABLE status representation.
    """
    gdacs_status = await gdacs_adapter.get_live_cyclone_status()
    now_str = gdacs_status.fetched_at

    if gdacs_status.live_status == "UNAVAILABLE":
        return {
            "type": "FeatureCollection",
            "properties": {
                "status": "UNAVAILABLE",
                "live_status": "UNAVAILABLE",
                "source": "GDACS (UN OCHA / EC JRC)",
                "data_mode": "LIVE",
                "retrieved_at": now_str,
                "last_successful_sync": gdacs_status.last_successful_sync,
                "message": gdacs_status.message,
            },
            "features": [],
            "assets": [],
        }

    if gdacs_status.live_status == "CALM" or not gdacs_status.cyclone:
        return {
            "type": "FeatureCollection",
            "properties": {
                "status": "CALM",
                "live_status": "CALM",
                "source": "GDACS (UN OCHA / EC JRC)",
                "data_mode": "LIVE",
                "retrieved_at": now_str,
                "last_successful_sync": gdacs_status.last_successful_sync,
                "message": "No active tropical cyclone in North Indian Ocean basin (Bay of Bengal / Arabian Sea).",
            },
            "features": [],
            "assets": [],
        }

    c = gdacs_status.cyclone
    infra_assets = await osm_adapter.fetch_infrastructure()

    evaluated_assets: List[ModelledRiskResult] = []
    for asset in infra_assets:
        res = risk_engine.evaluate_asset(
            asset=asset,
            cyclone_lat=c.current_lat,
            cyclone_lon=c.current_lon,
            cyclone_wind_knots=c.wind_speed_kts,
            data_mode=DataMode.LIVE,
        )
        evaluated_assets.append(res)

    evaluated_assets.sort(key=lambda a: a.modelled_risk_score, reverse=True)

    features = []
    for a in evaluated_assets:
        features.append(
            {
                "type": "Feature",
                "id": a.id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [a.longitude, a.latitude],
                },
                "properties": a.model_dump(),
            }
        )

    return {
        "type": "FeatureCollection",
        "properties": {
            "status": "ACTIVE",
            "live_status": "ACTIVE",
            "storm_name": c.storm_name,
            "event_id": c.event_id,
            "source": "GDACS (UN OCHA / EC JRC)",
            "data_mode": "LIVE",
            "retrieved_at": now_str,
            "last_successful_sync": gdacs_status.last_successful_sync,
        },
        "cyclone_center": {"lat": c.current_lat, "lon": c.current_lon},
        "wind_speed_knots": c.wind_speed_kts,
        "wind_speed_kmh": c.wind_speed_kmh,
        "alert_level": c.alert_level,
        "total_assets_evaluated": len(evaluated_assets),
        "critical_assets_count": sum(1 for a in evaluated_assets if a.risk_level in ["CRITICAL", "HIGH"]),
        "assets": [a.model_dump() for a in evaluated_assets],
        "features": features,
    }



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

    # Check cache first (storm_id + step_index + timestamp)
    cache_key = f"{track.storm_id}_{target_point.step_index}_{target_point.timestamp}"
    if cache_key in _storm_risk_cache:
        return _storm_risk_cache[cache_key]

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

    # Format into canonical GeoJSON
    features = []
    for a in evaluated_assets:
        features.append(
            {
                "type": "Feature",
                "id": a.id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        a.longitude,
                        a.latitude,
                    ],
                },
                "properties": a.model_dump(),
            }
        )

    has_hazard_data = target_point.wind_speed_knots is not None and target_point.wind_speed_knots >= 0
    response_payload = {
        "type": "FeatureCollection",
        "storm_id": track.storm_id,
        "storm_name": track.name,
        "step_index": target_point.step_index,
        "timestamp": target_point.timestamp,
        "cyclone_center": {"lat": target_point.lat, "lon": target_point.lon},
        "wind_speed_knots": target_point.wind_speed_knots,
        "category": target_point.category,
        "hazard_status": "AVAILABLE" if has_hazard_data else "UNAVAILABLE",
        "data_available": has_hazard_data,
        "total_assets_evaluated": len(evaluated_assets),
        "critical_assets_count": sum(1 for a in evaluated_assets if a.risk_level in ["CRITICAL", "HIGH"]),
        "assets": [a.model_dump() for a in evaluated_assets],
        "features": features,
        "provenance": track.provenance.model_dump(),
    }
    _storm_risk_cache[cache_key] = response_payload
    return response_payload


@router.get("/storms/{storm_id}/timesteps/{step_index}/risk", include_in_schema=False)
async def get_storm_timestep_risk_alias(
    storm_id: str,
    step_index: int,
) -> Dict[str, Any]:
    """Backwards-compatible path alias for timestep risk evaluation."""
    return await get_storm_timestep_risk(storm_id=storm_id, step_index=step_index)


@router.get("/storms/{storm_id}/advisory", summary="Grounded operational briefing from Gemini 3.7 Flash")
async def get_storm_advisory(
    storm_id: str,
    step_index: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Generate Gemini 3.7 Flash operational advisory grounded on evaluated assets."""
    risk_data = await get_storm_timestep_risk(storm_id=storm_id, step_index=step_index)
    actual_step = risk_data.get("step_index", step_index)
    timestamp = risk_data.get("timestamp", "")
    advisory_cache_key = f"{storm_id}_{actual_step}_{timestamp}"

    if advisory_cache_key in _storm_advisory_cache:
        return _storm_advisory_cache[advisory_cache_key]

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

    advisory_payload = {
        "storm_id": storm_id,
        "storm_name": risk_data.get("storm_name"),
        "step_index": actual_step,
        "timestamp": timestamp,
        "advisories": advisories,
        "disclaimer": "AI-GENERATED ADVISORY — Grounded on modelled risk inputs. Review with SDMA protocols.",
    }
    _storm_advisory_cache[advisory_cache_key] = advisory_payload
    return advisory_payload


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
