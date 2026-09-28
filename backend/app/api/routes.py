"""FastAPI HTTP Route Definitions.

HTTP endpoints only. All business logic, ingestion, risk evaluation,
and advisory generation are delegated to their respective isolated modules.
"""

from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query, status

from app.advisory.gemini_client import GeminiAdvisoryClient
from app.advisory.prompts import DistrictRiskSummaryInput
from app.config import get_settings
from app.ingestion.gee_client import GEEClient
from app.ingestion.infra_client import InfraClient
from app.ingestion.track_loader import TrackLoader
from app.risk_engine.schema import (
    InfraRiskFeature,
    InfraRiskProperties,
    PointGeometry,
    StormTrackFeatureCollection,
    TimestepRiskCollectionProperties,
    TimestepRiskFeatureCollection,
)
from app.risk_engine.scoring import (
    compute_composite_risk,
    compute_haversine_distance_km,
)

router = APIRouter(prefix="/api", tags=["cyclone-forecast"])

# Module Singletons
settings = get_settings()
track_loader = TrackLoader(data_dir=settings.data_dir)
infra_client = InfraClient(
    endpoint_url=settings.overpass_api_url,
    fallback_data_path=settings.data_dir / "sample_track" / "infrastructure_sample.json",
)
gee_client = GEEClient(project_id=settings.gee_project_id)
gemini_client = GeminiAdvisoryClient(
    api_key=settings.gemini_api_key,
    model_name=settings.gemini_model_name,
)


@router.get(
    "/health",
    summary="Health check endpoint",
    response_model=Dict[str, str],
)
async def health_check() -> Dict[str, str]:
    """Basic service health check."""
    return {"status": "ok", "service": "nivara-backend"}


@router.get(
    "/storms",
    summary="List available historical cyclone tracks",
    response_model=List[Dict[str, Any]],
)
async def list_storms() -> List[Dict[str, Any]]:
    """Return catalog of available historical cyclone tracks for replay."""
    return [
        {
            "storm_id": "2020139N09086",
            "name": "AMPHAN",
            "year": 2020,
            "basin": "NI",
            "description": "Super Cyclonic Storm Amphan (Bay of Bengal, May 2020)",
            "start_time": "2020-05-18T00:00:00Z",
            "end_time": "2020-05-21T00:00:00Z",
            "total_timesteps": 9,
        }
    ]


@router.get(
    "/storms/{storm_id}/track",
    summary="Get full storm track sequence",
    response_model=StormTrackFeatureCollection,
)
async def get_storm_track(storm_id: str) -> StormTrackFeatureCollection:
    """Retrieve GeoJSON FeatureCollection of full storm trajectory and eye positions."""
    try:
        storm = track_loader.load_track_from_file(Path("amphan_sample.json"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storm track '{storm_id}' could not be loaded: {str(exc)}",
        )

    features: List[Dict[str, Any]] = []

    # 1. Trajectory line feature
    coords = [[p.lon, p.lat] for p in storm.points]
    features.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "feature_type": "track_path",
                "storm_id": storm.storm_id,
                "name": storm.name,
            },
        }
    )

    # 2. Eye center points for each timestep
    for idx, p in enumerate(storm.points):
        # Landfall is typically when the eye crosses coastal threshold (~step 6 in Amphan)
        is_landfall = idx == 6
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [p.lon, p.lat],
                },
                "properties": {
                    "feature_type": "storm_center",
                    "step_index": p.step_index,
                    "timestamp": p.iso_time,
                    "wind_speed_knots": p.wind_speed_knots,
                    "wind_speed_kph": round(p.wind_speed_knots * 1.852, 1),
                    "pressure_mb": p.pressure_mb,
                    "cyclone_category": p.category or "Extremely Severe Cyclonic Storm",
                    "is_landfall_point": is_landfall,
                },
            }
        )

    return StormTrackFeatureCollection(
        properties={
            "storm_id": storm.storm_id,
            "name": storm.name,
            "basin": storm.basin,
            "total_timesteps": len(storm.points),
            "start_time": storm.points[0].iso_time if storm.points else "",
            "end_time": storm.points[-1].iso_time if storm.points else "",
        },
        features=features,
    )


@router.get(
    "/storms/{storm_id}/timesteps/{step_index}/risk",
    summary="Get per-timestep risk GeoJSON",
    response_model=TimestepRiskFeatureCollection,
)
async def get_timestep_risk(
    storm_id: str,
    step_index: int,
) -> TimestepRiskFeatureCollection:
    """Compute and return infrastructure risk GeoJSON for a specific timestep."""
    try:
        storm = track_loader.load_track_from_file(Path("amphan_sample.json"))
        point = track_loader.get_point_at_timestep(storm, step_index)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track or timestep invalid: {str(exc)}",
        )

    # Load critical infrastructure assets
    raw_assets = await infra_client.fetch_infrastructure()

    risk_features: List[InfraRiskFeature] = []

    for asset in raw_assets:
        # Distance from cyclone eye at this timestep
        dist_km = compute_haversine_distance_km(point.lat, point.lon, asset.lat, asset.lon)

        # Elevation and coastal distance
        elev_m = (
            asset.elevation_m
            if asset.elevation_m is not None
            else gee_client.get_elevation_at_point(asset.lat, asset.lon)
        )
        coast_km = (
            asset.dist_to_coast_km
            if asset.dist_to_coast_km is not None
            else gee_client._estimate_coastal_distance_km(asset.lat, asset.lon)
        )
        lcover = asset.land_cover_class or gee_client.get_land_cover_at_point(asset.lat, asset.lon)

        # Compute pure risk score
        score_res = compute_composite_risk(
            dist_from_track_km=dist_km,
            wind_speed_knots=point.wind_speed_knots,
            elevation_m=elev_m,
            dist_to_coast_km=coast_km,
            land_cover_class=lcover,
        )

        props = InfraRiskProperties(
            id=asset.id,
            name=asset.name,
            infra_type=asset.infra_type,
            district=asset.district,
            state=asset.state or "West Bengal",
            elevation_m=round(elev_m, 1),
            dist_to_track_km=round(dist_km, 1),
            dist_to_coast_km=round(coast_km, 1),
            land_cover_class=lcover,
            risk_score=score_res.risk_score,
            risk_level=score_res.risk_level,
            risk_breakdown=score_res.breakdown,
        )

        risk_features.append(
            InfraRiskFeature(
                id=asset.id,
                geometry=PointGeometry(coordinates=(asset.lon, asset.lat)),
                properties=props,
            )
        )

    # Sort descending by risk score
    risk_features.sort(key=lambda f: f.properties.risk_score, reverse=True)

    collection_props = TimestepRiskCollectionProperties(
        storm_id=storm.storm_id,
        step_index=point.step_index,
        timestamp=point.iso_time,
        storm_center=(point.lon, point.lat),
        storm_wind_knots=point.wind_speed_knots,
        total_assets_evaluated=len(risk_features),
    )

    return TimestepRiskFeatureCollection(
        properties=collection_props,
        features=risk_features,
    )


@router.get(
    "/storms/{storm_id}/timesteps/{step_index}/advisory",
    summary="Get district early warning advisory text",
    response_model=Dict[str, Any],
)
async def get_timestep_advisory(
    storm_id: str,
    step_index: int,
) -> Dict[str, Any]:
    """Generate Gemini 3.7 Flash district advisory text and mocked dispatch."""
    # Obtain risk results for this timestep
    risk_fc = await get_timestep_risk(storm_id, step_index)

    # Group evaluated assets by district
    district_groups: Dict[str, List[InfraRiskFeature]] = {}
    for feat in risk_fc.features:
        dist_name = feat.properties.district or "Coastal Sector"
        district_groups.setdefault(dist_name, []).append(feat)

    # Identify top highest-risk district
    district_summaries: List[Dict[str, Any]] = []
    for dname, feats in district_groups.items():
        scores = [f.properties.risk_score for f in feats]
        max_score = max(scores) if scores else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0
        state = feats[0].properties.state or "West Bengal"

        critical_count = sum(1 for s in scores if s >= 0.60)
        top_assets = [
            {
                "name": f.properties.name,
                "infra_type": f.properties.infra_type,
                "risk_score": f.properties.risk_score,
                "elevation_m": f.properties.elevation_m,
                "dist_to_track_km": f.properties.dist_to_track_km,
                "dist_to_coast_km": f.properties.dist_to_coast_km,
            }
            for f in feats[:5]
        ]

        district_summaries.append(
            {
                "district": dname,
                "state": state,
                "max_risk_score": max_score,
                "avg_risk_score": avg_score,
                "critical_infra_count": critical_count,
                "top_assets": top_assets,
            }
        )

    district_summaries.sort(key=lambda d: d["max_risk_score"], reverse=True)
    worst_district = district_summaries[0] if district_summaries else None

    if not worst_district:
        return {
            "storm_id": storm_id,
            "step_index": step_index,
            "timestamp": risk_fc.properties.timestamp,
            "district_advisories": [],
        }

    # Query Gemini for top 1-2 worst hit districts
    advisories: List[Dict[str, Any]] = []
    for dinfo in district_summaries[:2]:
        inp = DistrictRiskSummaryInput(
            storm_name=storm_id,
            step_index=step_index,
            timestamp=risk_fc.properties.timestamp,
            district=dinfo["district"],
            state=dinfo["state"],
            max_risk_score=dinfo["max_risk_score"],
            avg_risk_score=dinfo["avg_risk_score"],
            critical_infra_count=dinfo["critical_infra_count"],
            impacted_assets=dinfo["top_assets"],
        )
        adv = await gemini_client.generate_district_advisory(inp)
        advisories.append(adv.model_dump())

    return {
        "storm_id": storm_id,
        "storm_name": "AMPHAN",
        "step_index": step_index,
        "timestamp": risk_fc.properties.timestamp,
        "summary": {
            "worst_hit_district": worst_district["district"],
            "highest_risk_score": worst_district["max_risk_score"],
            "total_critical_assets": sum(d["critical_infra_count"] for d in district_summaries),
        },
        "district_advisories": advisories,
    }
