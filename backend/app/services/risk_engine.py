"""Decomposed Risk & Vulnerability Modeling Engine.

Explicitly separates:
Hazard -> Exposure -> Vulnerability -> Modelled Risk -> Potential Impact.

Pure, transparent, explainable formulas.
Output is strictly designated as "Modelled Risk".
"""

import math
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.infrastructure import AssetCategory, InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta
from app.domain.risk import (
    ExposureComponent,
    HazardComponent,
    ImpactConsequence,
    ModelledRiskResult,
    RiskClassification,
    VulnerabilityComponent,
)


def compute_haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


class RiskEngineService:
    """Scientific service evaluating decomposed geospatial risk for critical infrastructure."""

    def __init__(
        self,
        circulation_radius_km: float = 300.0,
        surge_threshold_elevation_m: float = 12.0,
        coastal_surge_buffer_km: float = 35.0,
    ) -> None:
        self.circulation_radius_km = circulation_radius_km
        self.surge_threshold_elevation_m = surge_threshold_elevation_m
        self.coastal_surge_buffer_km = coastal_surge_buffer_km

    def evaluate_hazard(
        self,
        cyclone_lat: float,
        cyclone_lon: float,
        cyclone_wind_knots: Optional[float],
        asset_lat: float,
        asset_lon: float,
    ) -> HazardComponent:
        """Evaluate dynamic atmospheric and hydrodynamic hazard at the asset location."""
        dist_km = compute_haversine_distance_km(cyclone_lat, cyclone_lon, asset_lat, asset_lon)

        # Unavailable hazard input state
        if cyclone_wind_knots is None or cyclone_wind_knots < 0:
            return HazardComponent(
                wind_speed_knots=0.0,
                wind_gusts_kph=0.0,
                wind_hazard_score=0.0,
                storm_surge_risk_score=0.0,
                cyclone_proximity_km=dist_km,
                storm_center_wind_knots=None,
                hazard_status="UNAVAILABLE",
                data_available=False,
            )

        center_wind = round(float(cyclone_wind_knots), 1)

        # Proximity decay factor
        if dist_km >= self.circulation_radius_km:
            return HazardComponent(
                wind_speed_knots=0.0,
                wind_gusts_kph=0.0,
                wind_hazard_score=0.0,
                storm_surge_risk_score=0.0,
                cyclone_proximity_km=dist_km,
                storm_center_wind_knots=center_wind,
                hazard_status="OUT_OF_RANGE",
                data_available=True,
            )

        proximity_factor = (1.0 - (dist_km / self.circulation_radius_km)) ** 1.5

        # Wind intensity normalized against Super Cyclone threshold (140 kts)
        wind_ratio = min(cyclone_wind_knots / 140.0, 1.0)
        local_wind_knots = cyclone_wind_knots * proximity_factor
        local_wind_kph = local_wind_knots * 1.852
        local_gusts_kph = local_wind_kph * 1.35

        wind_hazard = round(min(1.0, (wind_ratio ** 1.2) * proximity_factor), 3)

        # Surge hazard is highest near eyewall with intense onshore wind
        surge_hazard = round(min(1.0, (wind_ratio ** 1.4) * proximity_factor), 3)

        return HazardComponent(
            wind_speed_knots=round(local_wind_knots, 1),
            wind_gusts_kph=round(local_gusts_kph, 1),
            wind_hazard_score=wind_hazard,
            storm_surge_risk_score=surge_hazard,
            cyclone_proximity_km=dist_km,
            storm_center_wind_knots=center_wind,
            hazard_status="AVAILABLE",
            data_available=True,
        )

    def evaluate_exposure(
        self,
        dist_to_coast_km: float,
        proximity_km: float,
    ) -> ExposureComponent:
        """Evaluate spatial exposure relative to maritime surge buffer and eyewall."""
        if dist_to_coast_km >= self.coastal_surge_buffer_km:
            coastal_score = 0.0
        else:
            coastal_score = round(1.0 - (dist_to_coast_km / self.coastal_surge_buffer_km), 3)

        in_path = proximity_km < 120.0
        eyewall_zone = proximity_km < 45.0

        return ExposureComponent(
            distance_to_coastline_km=dist_to_coast_km,
            coastal_exposure_score=coastal_score,
            in_projected_path=in_path,
            eyewall_buffer_zone=eyewall_zone,
        )

    def evaluate_vulnerability(
        self,
        elevation_m: float,
        category: AssetCategory,
        land_cover_multiplier: float = 0.8,
    ) -> VulnerabilityComponent:
        """Evaluate intrinsic physical and sectoral vulnerability."""
        if elevation_m <= 1.5:
            elev_score = 1.0
        elif elevation_m >= self.surge_threshold_elevation_m:
            elev_score = 0.05
        else:
            elev_score = round(1.0 - (0.95 * ((elevation_m - 1.5) / (self.surge_threshold_elevation_m - 1.5))), 3)

        # Criticality scoring: hospitals & power substations are irreplaceable lifelines
        criticality_map = {
            AssetCategory.HOSPITAL: 1.0,
            AssetCategory.POWER_GRID: 0.95,
            AssetCategory.SHELTER: 0.85,
            AssetCategory.AIRPORT: 0.80,
            AssetCategory.PORT: 0.75,
            AssetCategory.BRIDGE: 0.70,
            AssetCategory.ROAD: 0.60,
            AssetCategory.EMERGENCY: 0.90,
        }
        crit_score = criticality_map.get(category, 0.50)

        return VulnerabilityComponent(
            terrain_elevation_m=elevation_m,
            elevation_vulnerability_score=elev_score,
            asset_criticality_score=crit_score,
            land_cover_multiplier=land_cover_multiplier,
        )

    def evaluate_impact(
        self,
        modelled_risk: float,
        category: AssetCategory,
        hazard: HazardComponent,
    ) -> ImpactConsequence:
        """Project operational disruptions and emergency actions."""
        prob = round(min(1.0, modelled_risk * 1.05), 2)

        if modelled_risk >= 0.75:
            isolation = "HIGH"
            priority = "IMMEDIATE"
            summary = (
                f"Severe structural risk from {hazard.wind_speed_knots}kt sustained winds and storm-surge inundation. "
                f"Critical {category.value} facility operations likely disrupted within 6 hours."
            )
        elif modelled_risk >= 0.50:
            isolation = "MODERATE"
            priority = "STAGED"
            summary = (
                f"Moderate storm impact expected. Peripheral inundation and power loss probable. "
                f"Pre-stage emergency backup generators and flood barriers."
            )
        else:
            isolation = "LOW"
            priority = "MONITOR"
            summary = "Direct hazard exposure remains within manageable operational tolerances. Continue monitoring."

        return ImpactConsequence(
            service_disruption_probability=prob,
            estimated_isolation_risk=isolation,
            evacuation_priority=priority,
            consequence_summary=summary,
        )

    def evaluate_asset(
        self,
        asset: InfrastructureAsset,
        cyclone_lat: float,
        cyclone_lon: float,
        cyclone_wind_knots: Optional[float],
        data_mode: DataMode = DataMode.MODELLED,
    ) -> ModelledRiskResult:
        """Run complete decomposed risk assessment for a single asset."""
        hazard = self.evaluate_hazard(
            cyclone_lat=cyclone_lat,
            cyclone_lon=cyclone_lon,
            cyclone_wind_knots=cyclone_wind_knots,
            asset_lat=asset.lat,
            asset_lon=asset.lon,
        )

        exposure = self.evaluate_exposure(
            dist_to_coast_km=asset.dist_to_coast_km,
            proximity_km=hazard.cyclone_proximity_km,
        )

        vulnerability = self.evaluate_vulnerability(
            elevation_m=asset.elevation_m,
            category=asset.category,
        )

        # Distinguish between unavailable hazard input, out-of-range calm, and active threat
        if hazard.hazard_status == "UNAVAILABLE":
            risk_score = 0.0
            classification: RiskClassification = "UNAVAILABLE"
            explanation = (
                f"Hazard data unavailable for this timestep (cyclone wind/hazard observations missing). "
                f"Risk score cannot be evaluated."
            )
        elif hazard.hazard_status == "OUT_OF_RANGE":
            risk_score = 0.0
            classification = "LOW"
            center_info = f"{hazard.storm_center_wind_knots:.0f} kts" if hazard.storm_center_wind_knots is not None else "measured"
            explanation = (
                f"Calculated LOW risk: asset is {hazard.cyclone_proximity_km:.0f}km from cyclone center "
                f"(outside {self.circulation_radius_km:.0f}km storm circulation radius). "
                f"Storm center wind is {center_info}, but local hazard force is negligible."
            )
        else:
            h_term = 0.40 * (0.6 * hazard.wind_hazard_score + 0.4 * hazard.storm_surge_risk_score)
            e_term = 0.30 * (0.7 * exposure.coastal_exposure_score + 0.3 * (1.0 if exposure.in_projected_path else 0.2))
            v_term = 0.30 * (0.6 * vulnerability.elevation_vulnerability_score + 0.4 * vulnerability.asset_criticality_score)
            risk_score = round(min(1.0, h_term + e_term + v_term), 2)

            if risk_score >= 0.75:
                classification = "CRITICAL"
            elif risk_score >= 0.50:
                classification = "HIGH"
            elif risk_score >= 0.25:
                classification = "MODERATE"
            else:
                classification = "LOW"

            explanation = (
                f"Modelled Risk {risk_score:.2f} computed from: "
                f"Wind Hazard {hazard.wind_hazard_score:.2f} ({hazard.wind_speed_knots} kts at {hazard.cyclone_proximity_km:.0f}km), "
                f"Coastal Exposure {exposure.coastal_exposure_score:.2f} ({asset.dist_to_coast_km:.1f}km to shore), "
                f"Elevation Vulnerability {vulnerability.elevation_vulnerability_score:.2f} ({asset.elevation_m:.1f}m ASL), "
                f"Sector Criticality {vulnerability.asset_criticality_score:.2f} ({asset.category.value})."
            )

        impact = self.evaluate_impact(risk_score, asset.category, hazard)

        now_utc = datetime.now(timezone.utc).isoformat()
        return ModelledRiskResult(
            id=asset.id,
            name=asset.name,
            category=asset.category.value,
            latitude=asset.lat,
            longitude=asset.lon,
            risk_score=risk_score,
            risk_level=classification,
            hazard=hazard,
            exposure=exposure,
            vulnerability=vulnerability,
            impact=impact,
            explanation=explanation,
            district=asset.district,
            state=asset.state,
            asset_id=asset.id,
            asset_name=asset.name,
            modelled_risk_score=risk_score,
            provenance=DataSourceMeta(
                source="Nivara Risk Modeling Engine",
                dataset="Decomposed Hazard-Exposure-Vulnerability Synthesis",
                retrieved_at=now_utc,
                status=data_mode,
                confidence="HIGH",
                is_forecast=True,
                attribution="Modelled synthesis based on OpenStreetMap nodes and Open-Meteo terrain",
            ),
        )
