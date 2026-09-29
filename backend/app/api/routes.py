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

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.config import get_settings
from app.data_sources.gdacs.gdacs_adapter import GDACSAdapter, calculate_bearing
from app.data_sources.gee.gee_adapter import GEEAdapter
from app.data_sources.ibtracs.ibtracs_adapter import IBTrACSAdapter
from app.data_sources.imd.imd_adapter import IMDAdapter
from app.data_sources.open_meteo.open_meteo_adapter import OpenMeteoAdapter
from app.data_sources.osm.osm_adapter import OSMAdapter
from app.domain.coastline import get_distance_to_coast_km, haversine_km
from app.domain.cyclone import (
    ForecastTimestepRisk,
    LiveCycloneStatusResponse,
    LiveForecastRiskResponse,
)
from app.domain.provenance import DataMode, DataSourceMeta
from app.domain.risk import ModelledRiskResult
from app.services.advisory_engine import AdvisoryEngineService, VisualAssessmentSummary
from app.services.dispatch_engine import DispatchEngineService, DispatchRecord, RecipientContact
from app.services.live_monitor import LiveMonitorService, LiveOperationsSnapshot
from app.services.parametric_engine import (
    ParametricEngineService,
    ParametricEvaluationResult,
    ParametricPolicy,
    PayoutAuditCertificate,
)
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
dispatch_engine = DispatchEngineService(report_service=report_service)
parametric_engine = ParametricEngineService()

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


@router.get("/storms/live/forecast-risk", summary="Get predictive infrastructure impact along live forecast track")
async def get_live_forecast_risk() -> Dict[str, Any]:
    """Evaluate infrastructure risk across future forecast track waypoints (+0h, +6h, +12h, etc.)."""
    gdacs_status = await gdacs_adapter.get_live_cyclone_status()
    now_str = datetime.now(timezone.utc).isoformat()

    if gdacs_status.live_status == "UNAVAILABLE":
        return LiveForecastRiskResponse(
            live_status="UNAVAILABLE",
            total_forecast_steps=0,
            forecast_timesteps=[],
            message="Live GDACS cyclone tracking feed is currently unavailable.",
        ).model_dump()

    if gdacs_status.live_status == "CALM" or not gdacs_status.cyclone:
        return LiveForecastRiskResponse(
            live_status="CALM",
            total_forecast_steps=0,
            forecast_timesteps=[],
            message="No active tropical cyclone detected in North Indian Ocean basin. Forward forecast risk is calm.",
        ).model_dump()

    c = gdacs_status.cyclone
    infra_assets = await osm_adapter.fetch_infrastructure()

    # Extract forecast coordinates:
    forecast_points: List[Tuple[float, float, str]] = []  # (lat, lon, label)
    forecast_points.append((c.current_lat, c.current_lon, "+0h (Current Position)"))

    if c.track:
        step_idx = 1
        for tf in c.track:
            props = tf.get("properties") or {}
            if props.get("feature_type") == "forecast_track":
                geom = tf.get("geometry") or {}
                coords = geom.get("coordinates") or []
                if geom.get("type") == "LineString":
                    for pt in coords:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            p_lat = float(pt[1])
                            p_lon = float(pt[0])
                            # Avoid duplicate of step 0 if within 5km
                            if haversine_km(c.current_lat, c.current_lon, p_lat, p_lon) > 5.0:
                                label = f"+{step_idx * 6}h"
                                forecast_points.append((p_lat, p_lon, label))
                                step_idx += 1
                                if step_idx > 8:  # Cap at 48h (8 steps)
                                    break
                if step_idx > 8:
                    break

    # Derive forward speed and approach heading
    forward_speed_kmh: Optional[float] = None
    approach_heading: Optional[float] = c.heading_deg

    if len(forecast_points) >= 2:
        dist_0_1 = haversine_km(
            forecast_points[0][0],
            forecast_points[0][1],
            forecast_points[1][0],
            forecast_points[1][1],
        )
        forward_speed_kmh = round(dist_0_1 / 6.0, 1)  # 6 hours between bulletined forecast steps
        if approach_heading is None:
            approach_heading = calculate_bearing(
                forecast_points[0][0],
                forecast_points[0][1],
                forecast_points[1][0],
                forecast_points[1][1],
            )

    # Compute landfall ETA
    landfall_eta_hours: Optional[float] = None
    projected_landfall_district: Optional[str] = None

    # Check minimum distance to coast along track
    min_dist_coast = get_distance_to_coast_km(c.current_lat, c.current_lon)
    if min_dist_coast <= 15.0:
        landfall_eta_hours = 0.0
    else:
        for idx, (f_lat, f_lon, _) in enumerate(forecast_points):
            d_coast = get_distance_to_coast_km(f_lat, f_lon)
            if d_coast <= 15.0:
                landfall_eta_hours = float(idx * 6.0)
                break
        if landfall_eta_hours is None and forward_speed_kmh and forward_speed_kmh > 0:
            landfall_eta_hours = round(min_dist_coast / forward_speed_kmh, 1)

    # Evaluate risk at each timestep
    timesteps: List[ForecastTimestepRisk] = []
    base_wind_kts = c.wind_speed_kts or 45.0
    base_wind_kmh = c.wind_speed_kmh or round(base_wind_kts * 1.852, 1)

    for idx, (t_lat, t_lon, label) in enumerate(forecast_points):
        d_coast = get_distance_to_coast_km(t_lat, t_lon)
        decay_factor = 0.85 if (d_coast <= 10.0 and idx > 2) else 1.0
        step_wind_kts = round(base_wind_kts * decay_factor, 1)
        step_wind_kmh = round(base_wind_kmh * decay_factor, 1)

        step_evaluated: List[ModelledRiskResult] = []
        for asset in infra_assets:
            res = risk_engine.evaluate_asset(
                asset=asset,
                cyclone_lat=t_lat,
                cyclone_lon=t_lon,
                cyclone_wind_knots=step_wind_kts,
                data_mode=DataMode.LIVE,
            )
            step_evaluated.append(res)

        step_evaluated.sort(key=lambda a: a.modelled_risk_score, reverse=True)
        max_risk = max((a.modelled_risk_score for a in step_evaluated), default=0.0)
        crit_count = sum(1 for a in step_evaluated if a.risk_level in ["CRITICAL", "HIGH"])
        impassable_roads = sum(1 for a in step_evaluated if a.access_status == "IMPASSABLE")
        max_surge = max((a.surge_height_m for a in step_evaluated), default=0.0)
        max_rain = max((a.rainfall_accum_24h_mm for a in step_evaluated), default=0.0)

        top_district = "Coastal Sector"
        for a in step_evaluated:
            if a.district:
                top_district = a.district
                break

        if idx == 0 and not projected_landfall_district:
            projected_landfall_district = top_district

        timesteps.append(
            ForecastTimestepRisk(
                step_index=idx,
                forecast_label=label,
                lat=t_lat,
                lon=t_lon,
                wind_speed_knots=step_wind_kts,
                wind_speed_kmh=step_wind_kmh,
                max_risk_score=max_risk,
                critical_facilities_count=crit_count,
                impassable_roads_count=impassable_roads,
                peak_surge_m=max_surge,
                max_rainfall_24h_mm=max_rain,
                top_exposed_district=top_district,
                evaluated_assets=[a.model_dump() for a in step_evaluated],
            )
        )

    response = LiveForecastRiskResponse(
        live_status="ACTIVE",
        storm_name=c.storm_name,
        event_id=c.event_id,
        forward_speed_kmh=forward_speed_kmh,
        approach_heading_deg=approach_heading,
        landfall_eta_hours=landfall_eta_hours,
        projected_landfall_district=projected_landfall_district,
        total_forecast_steps=len(timesteps),
        forecast_timesteps=timesteps,
        provenance=DataSourceMeta(
            source="GDACS Forecast Track & Nivara Predictive Risk Engine",
            dataset="Dynamic Forward-Track Infrastructure Vulnerability Projection",
            retrieved_at=now_str,
            status=DataMode.LIVE,
            confidence="HIGH",
            is_forecast=True,
            attribution="GDACS forecast geometry combined with OpenStreetMap arterial assets",
        ),
        message=f"Forecast predictive risk modeled across {len(timesteps)} forward trajectory waypoints.",
    )
    return response.model_dump()


@router.get("/storms/live/advisory", summary="Get live operational emergency briefing and directives")
async def get_live_advisory(district: Optional[str] = None) -> Dict[str, Any]:
    """Generate Gemini 3.7 Flash operational emergency advisory for active cyclone."""
    gdacs_status = await gdacs_adapter.get_live_cyclone_status()
    now_str = datetime.now(timezone.utc).isoformat()

    if gdacs_status.live_status == "UNAVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "live_status": "UNAVAILABLE",
            "message": "Live GDACS data unavailable. Cannot generate active operational briefing.",
            "advisory": None,
        }

    if gdacs_status.live_status == "CALM" or not gdacs_status.cyclone:
        return {
            "status": "CALM",
            "live_status": "CALM",
            "message": "No active tropical cyclone detected in North Indian Ocean basin. Normal readiness protocols apply.",
            "advisory": None,
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

    target_district = district or (evaluated_assets[0].district if evaluated_assets and evaluated_assets[0].district else "Purba Medinipur")
    target_state = evaluated_assets[0].state if evaluated_assets and evaluated_assets[0].state else "West Bengal"
    district_assets = [a for a in evaluated_assets if not district or a.district == target_district]
    if not district_assets:
        district_assets = evaluated_assets

    briefing = await advisory_engine.generate_district_briefing(
        district=target_district,
        state=target_state,
        storm_name=c.storm_name,
        current_wind_knots=float(c.wind_speed_kts or 0.0),
        assets=district_assets,
        data_mode=DataMode.LIVE,
    )

    return {
        "status": "ACTIVE",
        "live_status": "ACTIVE",
        "storm_name": c.storm_name,
        "event_id": c.event_id,
        "district": target_district,
        "state": target_state,
        "advisory": briefing.model_dump(),
        "retrieved_at": now_str,
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


# ==============================================================================
# 6. GOOGLE EARTH ENGINE (GEE) SATELLITE LAYERS (PHASE 5)
# ==============================================================================

@router.get("/satellite/gee/status", summary="Operational status of Google Earth Engine integration")
async def get_gee_status() -> Dict[str, Any]:
    """Check connectivity and available datasets in Google Earth Engine."""
    status_obj = gee_adapter.get_status()
    return status_obj.model_dump()


@router.get("/satellite/gee/layers", summary="Available satellite raster overlay layers")
async def get_gee_layers() -> List[Dict[str, Any]]:
    """List available authentic satellite overlay layers (Sentinel-1 SAR, Dynamic World, SRTM)."""
    return gee_adapter.get_tile_layers()


@router.get("/satellite/sar-flood", summary="Sentinel-1 SAR surface water anomaly flood extent")
async def get_sar_flood_extent() -> Dict[str, Any]:
    """Retrieve Sentinel-1 SAR C-band water backscatter anomalies and flood polygons."""
    sar_data = gee_adapter.get_sar_flood_raster()
    return sar_data.model_dump()


@router.get("/satellite/land-cover", summary="Query 10m Dynamic World land cover at point")
async def get_point_land_cover(
    lat: float = Query(..., ge=15.0, le=25.0),
    lon: float = Query(..., ge=80.0, le=92.0),
) -> Dict[str, Any]:
    """Query Dynamic World 10m land cover class and physical surface roughness multiplier."""
    info = gee_adapter.get_land_cover_at_point(lat, lon)
    return info.model_dump()


# ==============================================================================
# 7. AUTOMATED EARLY-WARNING ADVISORY DISPATCH ENGINE (PHASE 6)
# ==============================================================================

class AdvisoryDispatchRequest(BaseModel):
    storm_name: str = "TROPICAL CYCLONE"
    alert_level: str = "Red"
    wind_speed_kmh: float = 120.0
    heading_deg: Optional[float] = None
    peak_surge_m: float = 2.5
    affected_districts: Optional[List[str]] = None
    channels: Optional[List[str]] = None
    recipient_ids: Optional[List[str]] = None


@router.get("/advisory/recipients", summary="Authoritative disaster management recipients directory")
async def get_advisory_recipients() -> List[Dict[str, Any]]:
    """List registered District Magistrates, Municipal Commissioners, and SEOC endpoints."""
    return [r.model_dump() for r in dispatch_engine.get_recipients()]


@router.get("/advisory/cap.xml", summary="Generate OASIS Common Alerting Protocol (CAP v1.2) XML")
async def get_cap_alert_xml() -> Response:
    """Generate official CAP v1.2 XML compliant emergency alert."""
    cyclone_status = await gdacs_adapter.get_live_cyclone_status()
    if cyclone_status.cyclone:
        c = cyclone_status.cyclone
        xml_str = dispatch_engine.generate_cap_xml(
            storm_name=c.storm_name,
            alert_level=c.alert_level or "Orange",
            wind_speed_kmh=c.wind_speed_kmh or 95.0,
            heading_deg=c.heading_deg,
            peak_surge_m=2.8,
            affected_districts=["Purba Medinipur", "South 24 Parganas"],
        )
    else:
        xml_str = dispatch_engine.generate_cap_xml(
            storm_name="EXERCISE_NORTH_INDIAN_OCEAN",
            alert_level="Yellow",
            wind_speed_kmh=65.0,
            heading_deg=35.0,
            peak_surge_m=1.2,
            affected_districts=["Coastal Zone"],
        )
    return Response(content=xml_str, media_type="application/xml")


@router.post("/advisory/dispatch", summary="Execute automated multi-channel advisory dispatch")
async def execute_advisory_dispatch(req: AdvisoryDispatchRequest) -> Dict[str, Any]:
    """Dispatch emergency warnings across CAP XML, Webhooks, SMS, and SitRep channels."""
    record = dispatch_engine.dispatch_advisories(
        storm_name=req.storm_name,
        alert_level=req.alert_level,
        wind_speed_kmh=req.wind_speed_kmh,
        heading_deg=req.heading_deg,
        peak_surge_m=req.peak_surge_m,
        affected_districts=req.affected_districts,
        channels=req.channels,
        recipient_ids=req.recipient_ids,
    )
    return record.model_dump()


@router.get("/advisory/dispatch/log", summary="Retrieve cryptographic dispatch audit ledger")
async def get_dispatch_log() -> List[Dict[str, Any]]:
    """Inspect verifiable dispatch log with SHA-256 receipts and delivery timestamps."""
    return [r.model_dump() for r in dispatch_engine.get_dispatch_log()]


# ==============================================================================
# 8. MULTIMODAL REASONING & PARAMETRIC LIQUIDITY TRIGGERS (PHASE 7)
# ==============================================================================

class MultimodalAnalyzeRequest(BaseModel):
    image_base64: str
    storm_name: str = "ACTIVE CYCLONE"
    context_metadata: Optional[Dict[str, Any]] = None


class ParametricEvaluateRequest(BaseModel):
    storm_name: str = "ACTIVE CYCLONE"
    wind_speed_kmh: float = 120.0
    peak_surge_m: float = 2.5
    landfall_eta_hours: Optional[float] = None
    impassable_roads_count: int = 0
    max_rainfall_24h_mm: float = 0.0


@router.post("/advisory/multimodal-analyze", summary="Gemini 3.7 Flash multimodal visual reasoning on satellite/map canvas")
async def analyze_multimodal_satellite_view(req: MultimodalAnalyzeRequest) -> Dict[str, Any]:
    """Execute Gemini 3.7 Flash visual reasoning on uploaded map/satellite snapshot."""
    assessment = await advisory_engine.analyze_multimodal_visual(
        image_base64=req.image_base64,
        storm_name=req.storm_name,
        context_metadata=req.context_metadata,
    )
    return assessment.model_dump()


@router.get("/parametric/policies", summary="List active parametric insurance contracts")
async def get_parametric_policies() -> List[Dict[str, Any]]:
    """List active index-linked parametric policies with trigger thresholds and coverage limits."""
    return [p.model_dump() for p in parametric_engine.get_policies()]


@router.post("/parametric/evaluate", summary="Evaluate parametric physical triggers and calculate pre-landfall payout")
async def evaluate_parametric_payout(req: ParametricEvaluateRequest) -> Dict[str, Any]:
    """Evaluate storm parameters against policy index gates and certify liquidity payouts."""
    result = parametric_engine.evaluate_policies(
        storm_name=req.storm_name,
        wind_speed_kmh=req.wind_speed_kmh,
        peak_surge_m=req.peak_surge_m,
        landfall_eta_hours=req.landfall_eta_hours,
        impassable_roads_count=req.impassable_roads_count,
        max_rainfall_24h_mm=req.max_rainfall_24h_mm,
    )
    return result.model_dump()


@router.get("/parametric/certificates", summary="Retrieve issued cryptographic parametric payout certificates")
async def get_payout_certificates() -> List[Dict[str, Any]]:
    """Retrieve audit ledger of certified pre-landfall parametric liquidity disbursements."""
    return [c.model_dump() for c in parametric_engine.get_issued_certificates()]
