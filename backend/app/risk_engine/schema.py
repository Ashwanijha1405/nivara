"""GeoJSON and Data Contract Pydantic Models for Risk Output.

Matches the exact GeoJSON specification documented in docs/data_contract.md.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field
from app.risk_engine.scoring import RiskBreakdown, RiskLevel


class PointGeometry(BaseModel):
    """GeoJSON Point geometry."""

    type: Literal["Point"] = "Point"
    coordinates: Tuple[float, float] = Field(..., description="[longitude, latitude]")


class LineStringGeometry(BaseModel):
    """GeoJSON LineString geometry."""

    type: Literal["LineString"] = "LineString"
    coordinates: List[Tuple[float, float]] = Field(..., description="List of [lon, lat] pairs")


class InfraRiskProperties(BaseModel):
    """Properties for an infrastructure risk point feature."""

    id: str = Field(..., description="Asset identifier")
    name: str = Field(..., description="Facility name")
    infra_type: str = Field(..., description="hospital, power_station, power_substation, road_arterial, shelter")
    district: Optional[str] = Field(None, description="District name")
    state: Optional[str] = Field(None, description="State/province name")
    elevation_m: float = Field(..., description="Elevation in meters")
    dist_to_track_km: float = Field(..., description="Distance from storm eye in km")
    dist_to_coast_km: float = Field(..., description="Distance from coastline in km")
    land_cover_class: str = Field(..., description="Land cover type")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Composite risk score")
    risk_level: RiskLevel = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
    risk_breakdown: RiskBreakdown


class InfraRiskFeature(BaseModel):
    """GeoJSON Feature representing a risk-evaluated infrastructure asset."""

    type: Literal["Feature"] = "Feature"
    id: Optional[str] = None
    geometry: PointGeometry
    properties: InfraRiskProperties


class TimestepRiskCollectionProperties(BaseModel):
    """Metadata attached to a timestep risk FeatureCollection."""

    storm_id: str
    step_index: int
    timestamp: str
    storm_center: Tuple[float, float] = Field(..., description="[longitude, latitude]")
    storm_wind_knots: float
    total_assets_evaluated: int


class TimestepRiskFeatureCollection(BaseModel):
    """Top-level GeoJSON FeatureCollection returned by the risk engine."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    properties: TimestepRiskCollectionProperties
    features: List[InfraRiskFeature] = Field(default_factory=list)


class TrackPointProperties(BaseModel):
    """Properties for storm center point along track."""

    feature_type: Literal["storm_center"] = "storm_center"
    step_index: int
    timestamp: str
    wind_speed_knots: float
    wind_speed_kph: float
    pressure_mb: Optional[float] = None
    cyclone_category: Optional[str] = None
    is_landfall_point: bool = False


class TrackPathProperties(BaseModel):
    """Properties for full storm trajectory line."""

    feature_type: Literal["track_path"] = "track_path"
    storm_id: str


class StormTrackFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection representing the storm path and eye points."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    properties: Dict[str, Any]
    features: List[Dict[str, Any]] = Field(default_factory=list)
