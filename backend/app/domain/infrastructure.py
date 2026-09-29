"""Critical Infrastructure Domain Entities."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.domain.provenance import DataSourceMeta


class AssetCategory(str, Enum):
    """Classified critical infrastructure sectors."""

    HOSPITAL = "hospital"
    POWER_GRID = "power_grid"
    ROAD = "road"
    BRIDGE = "bridge"
    SHELTER = "shelter"
    PORT = "port"
    AIRPORT = "airport"
    EMERGENCY = "emergency_service"


class InfrastructureAsset(BaseModel):
    """Discovered real-world physical asset evaluated for risk."""

    id: str = Field(..., description="Unique persistent identifier (e.g. osm_node_98312011)")
    name: str = Field(..., description="Official facility name")
    category: AssetCategory
    lat: float
    lon: float
    latitude: float = 0.0
    longitude: float = 0.0
    elevation_m: float = Field(..., description="Elevation above mean sea level in meters")
    dist_to_coast_km: float = Field(..., description="Distance to maritime shoreline in km")
    district: str
    state: str
    raw_tags: Dict[str, Any] = Field(default_factory=dict, description="Original OSM key-value tags")
    provenance: DataSourceMeta

    def model_post_init(self, __context: Any) -> None:
        if not self.latitude and self.lat:
            self.latitude = self.lat
        elif not self.lat and self.latitude:
            self.lat = self.latitude

        if not self.longitude and self.lon:
            self.longitude = self.lon
        elif not self.lon and self.longitude:
            self.lon = self.longitude
