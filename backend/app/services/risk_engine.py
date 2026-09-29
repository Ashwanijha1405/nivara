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
from app.data_sources.gee.gee_adapter import GEEAdapter


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
        gee_adapter: Optional[GEEAdapter] = None,
    ) -> None:
        self.circulation_radius_km = circulation_radius_km
        self.surge_threshold_elevation_m = surge_threshold_elevation_m
        self.coastal_surge_buffer_km = coastal_surge_buffer_km
        self.gee_adapter = gee_adapter or GEEAdapter()

    def evaluate_hazard(
        self,
        cyclone_lat: float,
        cyclone_lon: float,
        cyclone_wind_knots: Optional[float],
        asset_lat: float,
        asset_lon: float,
        asset_elevation_m: float = 5.0,
        dist_to_coast_km: float = 10.0,
        central_pressure_mb: Optional[float] = None,
    ) -> HazardComponent:
        """Evaluate dynamic atmospheric and hydrodynamic hazard at the asset location.

        Incorporates:
        - Hydrodynamic coastal storm surge: inverted barometer + shelf shoaling + wind stress setup
        - Net inundation depth (surge water level minus asset elevation)
        - Tropical cyclone spatial rainfall band intensity & 24h accumulation
        - Pluvial drainage depression accumulation depth
        """
        dist_km = compute_haversine_distance_km(cyclone_lat, cyclone_lon, asset_lat, asset_lon)

        # Unavailable hazard input state
        if cyclone_wind_knots is None or cyclone_wind_knots < 0:
            return HazardComponent(
                wind_speed_knots=0.0,
                wind_gusts_kph=0.0,
                wind_hazard_score=0.0,
                storm_surge_risk_score=0.0,
                surge_height_m=0.0,
                inundation_depth_m=0.0,
                rainfall_rate_mmh=0.0,
                rainfall_accum_24h_mm=0.0,
                pluvial_flood_depth_m=0.0,
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
                surge_height_m=0.0,
                inundation_depth_m=0.0,
                rainfall_rate_mmh=0.0,
                rainfall_accum_24h_mm=0.0,
                pluvial_flood_depth_m=0.0,
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

        # ── 1. Hydrodynamic Storm Surge Physics ──
        # Central pressure (use reported or Atkinson-Holliday wind-pressure derivation for NIO)
        if central_pressure_mb is not None and central_pressure_mb > 850.0:
            pc = float(central_pressure_mb)
        else:
            wind_kmh = cyclone_wind_knots * 1.852
            pc = max(890.0, 1010.0 - 0.024 * (wind_kmh ** 1.5))

        # Inverted Barometer Effect: ~1 cm per hPa drop below 1013.25 hPa
        delta_p = max(0.0, 1013.25 - pc)
        barometric_setup_m = round(0.0101 * delta_p, 2)

        # Coastal Shelf Shoaling Factor (concave shallow Bay head vs peninsular shelf)
        if asset_lat >= 21.0:
            shoal_factor = 1.40  # Sundarbans / Head Bay
        elif asset_lat >= 19.5:
            shoal_factor = 1.20  # Odisha Arc (Paradip/Chandipur)
        else:
            shoal_factor = 1.05  # Peninsular coast

        # Wind Stress Setup
        wind_setup_m = round(0.00042 * (cyclone_wind_knots ** 1.82) * shoal_factor, 2)
        peak_coast_surge_m = barometric_setup_m + wind_setup_m

        # Inland decay over land roughness from shoreline
        if dist_to_coast_km <= 35.0:
            local_surge_m = round(peak_coast_surge_m * math.exp(-0.065 * dist_to_coast_km) * proximity_factor, 2)
        else:
            local_surge_m = 0.0

        # Net inundation depth above terrain
        inundation_depth_m = max(0.0, round(local_surge_m - asset_elevation_m, 2))

        # Surge hazard score
        if inundation_depth_m >= 3.0:
            surge_hazard = 1.0
        elif inundation_depth_m >= 1.5:
            surge_hazard = round(0.75 + 0.25 * ((inundation_depth_m - 1.5) / 1.5), 3)
        elif inundation_depth_m > 0.0:
            surge_hazard = round(0.35 + 0.40 * (inundation_depth_m / 1.5), 3)
        else:
            surge_hazard = round(min(1.0, (wind_ratio ** 1.4) * proximity_factor * (1.0 if dist_to_coast_km < 15.0 else 0.3)), 3)

        # ── 2. Spatial Rainfall & Pluvial Flooding Physics ──
        # Radial rainband intensity
        core_rain_rate = 25.0 + 0.35 * cyclone_wind_knots  # mm/hr at eyewall
        rain_rate_mmh = round(core_rain_rate * math.exp(-0.5 * (((dist_km - 35.0) / 75.0) ** 2)), 1)
        rain_accum_24h_mm = min(550.0, round(rain_rate_mmh * 8.5 * proximity_factor, 1))

        # Pluvial pooling in flat drainage depressions (< 4m ASL)
        if rain_accum_24h_mm > 45.0:
            elevation_pooling_mult = 1.0 + max(0.0, 3.5 - asset_elevation_m) * 0.25
            pluvial_depth_m = max(0.0, round(((rain_accum_24h_mm - 45.0) / 1000.0) * elevation_pooling_mult, 2))
        else:
            pluvial_depth_m = 0.0

        return HazardComponent(
            wind_speed_knots=round(local_wind_knots, 1),
            wind_gusts_kph=round(local_gusts_kph, 1),
            wind_hazard_score=wind_hazard,
            storm_surge_risk_score=surge_hazard,
            surge_height_m=local_surge_m,
            inundation_depth_m=inundation_depth_m,
            rainfall_rate_mmh=rain_rate_mmh,
            rainfall_accum_24h_mm=rain_accum_24h_mm,
            pluvial_flood_depth_m=pluvial_depth_m,
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
        central_pressure_mb: Optional[float] = None,
    ) -> ModelledRiskResult:
        """Run complete decomposed risk assessment for a single asset."""
        hazard = self.evaluate_hazard(
            cyclone_lat=cyclone_lat,
            cyclone_lon=cyclone_lon,
            cyclone_wind_knots=cyclone_wind_knots,
            asset_lat=asset.lat,
            asset_lon=asset.lon,
            asset_elevation_m=asset.elevation_m,
            dist_to_coast_km=asset.dist_to_coast_km,
            central_pressure_mb=central_pressure_mb,
        )

        exposure = self.evaluate_exposure(
            dist_to_coast_km=asset.dist_to_coast_km,
            proximity_km=hazard.cyclone_proximity_km,
        )

        land_mult = 0.85
        if self.gee_adapter:
            try:
                lc = self.gee_adapter.get_land_cover_at_point(asset.lat, asset.lon)
                land_mult = lc.surface_roughness_multiplier
            except Exception:
                land_mult = 0.85

        vulnerability = self.evaluate_vulnerability(
            elevation_m=asset.elevation_m,
            category=asset.category,
            land_cover_multiplier=land_mult,
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
                f"Surge Inundation {hazard.inundation_depth_m:.1f}m ({hazard.surge_height_m:.1f}m surge ASL), "
                f"24h Rain {hazard.rainfall_accum_24h_mm:.0f}mm (Pluvial pooling {hazard.pluvial_flood_depth_m:.1f}m), "
                f"Coastal Exposure {exposure.coastal_exposure_score:.2f} ({asset.dist_to_coast_km:.1f}km to shore), "
                f"Elevation Vulnerability {vulnerability.elevation_vulnerability_score:.2f} ({asset.elevation_m:.1f}m ASL), "
                f"Sector Criticality {vulnerability.asset_criticality_score:.2f} ({asset.category.value})."
            )

        impact = self.evaluate_impact(risk_score, asset.category, hazard)

        if asset.category in (AssetCategory.ROAD, AssetCategory.BRIDGE):
            if risk_score >= 0.70 or hazard.inundation_depth_m >= 0.30 or hazard.pluvial_flood_depth_m >= 0.45:
                access_status = "IMPASSABLE"
            elif risk_score >= 0.40 or hazard.inundation_depth_m > 0.05 or hazard.pluvial_flood_depth_m >= 0.20:
                access_status = "VULNERABLE"
            else:
                access_status = "PASSABLE"
        else:
            access_status = "PASSABLE"

        isolation_risk = impact.estimated_isolation_risk

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
            access_status=access_status,
            isolation_risk=isolation_risk,
            surge_height_m=hazard.surge_height_m,
            inundation_depth_m=hazard.inundation_depth_m,
            rainfall_accum_24h_mm=hazard.rainfall_accum_24h_mm,
            pluvial_flood_depth_m=hazard.pluvial_flood_depth_m,
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
