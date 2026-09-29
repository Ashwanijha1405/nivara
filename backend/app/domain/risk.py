"""Risk & Vulnerability Modeling Domain Entities.

Deconstructs risk into transparent components:
Hazard -> Exposure -> Vulnerability -> Modelled Risk -> Potential Impact.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.domain.provenance import DataSourceMeta

RiskClassification = Literal["LOW", "MODERATE", "HIGH", "CRITICAL", "UNAVAILABLE"]


class HazardComponent(BaseModel):
    """Physical environmental hazard forces active at the asset location."""

    wind_speed_knots: float = 0.0
    wind_gusts_kph: float = 0.0
    wind_hazard_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Normalized wind hazard [0, 1]")
    storm_surge_risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Surge inundation hazard [0, 1]")
    cyclone_proximity_km: float
    storm_center_wind_knots: Optional[float] = None
    hazard_status: Literal["AVAILABLE", "OUT_OF_RANGE", "UNAVAILABLE"] = "AVAILABLE"
    data_available: bool = True


class ExposureComponent(BaseModel):
    """Spatial and geographical exposure of the entity."""

    distance_to_coastline_km: float
    coastal_exposure_score: float = Field(..., ge=0.0, le=1.0)
    in_projected_path: bool
    eyewall_buffer_zone: bool


class VulnerabilityComponent(BaseModel):
    """Intrinsic physical and structural vulnerability of the asset."""

    terrain_elevation_m: float
    elevation_vulnerability_score: float = Field(..., ge=0.0, le=1.0, description="High when near sea level")
    asset_criticality_score: float = Field(..., ge=0.0, le=1.0, description="Healthcare/Grid vs Secondary")
    land_cover_multiplier: float = Field(..., ge=0.0, le=1.0)


class ImpactConsequence(BaseModel):
    """Projected operational and human impact."""

    service_disruption_probability: float = Field(..., ge=0.0, le=1.0)
    estimated_isolation_risk: str  # HIGH, MODERATE, LOW
    evacuation_priority: str  # IMMEDIATE, STAGED, MONITOR
    consequence_summary: str


class ModelledRiskResult(BaseModel):
    """Complete decomposed risk evaluation for an infrastructure entity.
    
    Canonical shared structure:
    - id, name, category
    - latitude, longitude
    - risk_score, risk_level
    - hazard, exposure, vulnerability
    """

    id: str = Field(default="", description="Asset unique identifier")
    name: str = Field(default="", description="Asset name")
    category: str = Field(default="", description="Asset category")
    latitude: float = Field(default=0.0, description="WGS84 latitude [-90, 90]")
    longitude: float = Field(default=0.0, description="WGS84 longitude [-180, 180]")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Composite risk index [0, 1]")
    risk_level: RiskClassification
    hazard: HazardComponent
    exposure: ExposureComponent
    vulnerability: VulnerabilityComponent
    impact: ImpactConsequence
    explanation: str = Field(..., description="Human-readable breakdown explaining how the score was calculated")
    provenance: DataSourceMeta
    district: str = ""
    state: str = ""

    # Backwards compatibility aliases
    asset_id: str = ""
    asset_name: str = ""
    modelled_risk_score: float = 0.0

    def model_post_init(self, __context: Any) -> None:
        if not self.id and self.asset_id:
            self.id = self.asset_id
        elif not self.asset_id and self.id:
            self.asset_id = self.id

        if not self.name and self.asset_name:
            self.name = self.asset_name
        elif not self.asset_name and self.name:
            self.asset_name = self.name

        if not self.risk_score and self.modelled_risk_score:
            self.risk_score = self.modelled_risk_score
        elif not self.modelled_risk_score and self.risk_score:
            self.modelled_risk_score = self.risk_score
