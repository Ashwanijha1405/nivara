"""Risk & Vulnerability Modeling Domain Entities.

Deconstructs risk into transparent components:
Hazard -> Exposure -> Vulnerability -> Modelled Risk -> Potential Impact.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.domain.provenance import DataSourceMeta

RiskClassification = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]


class HazardComponent(BaseModel):
    """Physical environmental hazard forces active at the asset location."""

    wind_speed_knots: float
    wind_gusts_kph: float
    wind_hazard_score: float = Field(..., ge=0.0, le=1.0, description="Normalized wind hazard [0, 1]")
    storm_surge_risk_score: float = Field(..., ge=0.0, le=1.0, description="Surge inundation hazard [0, 1]")
    cyclone_proximity_km: float


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
    """Complete decomposed risk evaluation for an infrastructure entity."""

    asset_id: str
    asset_name: str
    category: str
    district: str
    state: str
    modelled_risk_score: float = Field(..., ge=0.0, le=1.0, description="Composite Modelled Risk index")
    risk_level: RiskClassification
    hazard: HazardComponent
    exposure: ExposureComponent
    vulnerability: VulnerabilityComponent
    impact: ImpactConsequence
    explanation: str = Field(..., description="Human-readable breakdown explaining how the score was calculated")
    provenance: DataSourceMeta
