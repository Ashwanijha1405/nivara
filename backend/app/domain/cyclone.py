"""Cyclone Tracking & Meteorological Domain Entities."""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.domain.provenance import DataSourceMeta


class CycloneWaypoint(BaseModel):
    """Observed or forecast waypoint along cyclone trajectory."""

    step_index: int
    timestamp: str
    lat: float
    lon: float
    wind_speed_knots: float
    wind_speed_kph: float
    pressure_mb: Optional[float] = None
    category: str
    cone_radius_km: float = 0.0
    heading_deg: Optional[float] = None
    is_forecast: bool = False
    is_landfall_point: bool = False


class WindWarningPolygon(BaseModel):
    """Geographic warning boundary for specific wind thresholds."""

    wind_threshold_knots: int
    severity: str
    coordinates: List[Tuple[float, float]]


class CycloneWarning(BaseModel):
    """Official cyclone alert bulletin issued by IMD or regional advisory center."""

    warning_id: str
    title: str
    severity: str  # YELLOW, ORANGE, RED, EMERGENCY
    affected_districts: List[str]
    affected_states: List[str]
    wind_warning: str
    surge_warning: str
    rainfall_warning: str
    issued_at: str
    valid_until: str
    source: str
    bulletin_url: Optional[str] = None


class CycloneTrack(BaseModel):
    """Full cyclone sequence including observed track, forecast track, and uncertainty cone."""

    storm_id: str
    name: str
    season: int
    basin: str
    active: bool = False
    waypoints: List[CycloneWaypoint] = Field(default_factory=list)
    cone_of_uncertainty: List[Tuple[float, float]] = Field(default_factory=list)
    wind_radii: List[WindWarningPolygon] = Field(default_factory=list)
    current_position: Optional[CycloneWaypoint] = None
    provenance: DataSourceMeta
