"""Scenario Simulation Engine.

Computes hypothetical cyclone landfall impacts, surge extents, and asset exposure.
Strictly tagged as:
"SCENARIO / MODELLED - NOT AN OFFICIAL FORECAST"
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.domain.cyclone import CycloneTrack, CycloneWaypoint
from app.domain.infrastructure import InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta
from app.domain.risk import ModelledRiskResult
from app.services.risk_engine import RiskEngineService


class ScenarioSimulationParameters(BaseModel):
    """User-controlled hypothetical scenario parameters."""

    scenario_name: str = Field(default="Hypothetical Bay Landfall Scenario")
    landfall_lat: float = Field(..., ge=15.0, le=25.0, description="Projected landfall latitude")
    landfall_lon: float = Field(..., ge=80.0, le=92.0, description="Projected landfall longitude")
    max_wind_speed_knots: float = Field(default=95.0, ge=30.0, le=160.0)
    central_pressure_mb: float = Field(default=945.0, ge=890.0, le=1010.0)
    surge_height_meters: float = Field(default=4.5, ge=0.5, le=12.0)
    track_heading_deg: float = Field(default=35.0, ge=0.0, le=360.0)
    simulation_hours: int = Field(default=24, ge=6, le=72)


class ScenarioImpactSummary(BaseModel):
    """High-level summary of simulated impact."""

    total_assets_at_risk: int
    critical_facilities_count: int
    hospitals_at_risk: int
    substations_at_risk: int
    worst_hit_district: str
    max_modelled_risk: float
    simulated_surge_corridor_km: float


class ScenarioSimulationResult(BaseModel):
    """Complete simulation output package."""

    parameters: ScenarioSimulationParameters
    simulated_track: List[CycloneWaypoint]
    hazard_footprint_polygon: List[List[float]]
    evaluated_assets: List[ModelledRiskResult]
    summary: ScenarioImpactSummary
    disclaimer: str = Field(
        default="SCENARIO / MODELLED — NOT AN OFFICIAL FORECAST. For preparedness simulation only."
    )
    provenance: DataSourceMeta


class SimulationEngineService:
    """Service generating hypothetical cyclone scenarios and evaluating synthetic exposure."""

    def __init__(self, risk_engine: Optional[RiskEngineService] = None) -> None:
        self.risk_engine = risk_engine or RiskEngineService()

    def run_scenario(
        self,
        params: ScenarioSimulationParameters,
        assets: List[InfrastructureAsset],
    ) -> ScenarioSimulationResult:
        """Run hypothetical scenario simulation across provided infrastructure assets."""
        now_utc = datetime.now(timezone.utc).isoformat()

        # Generate synthetic approach trajectory terminating at landfall_lat, landfall_lon
        waypoints: List[CycloneWaypoint] = []
        heading_rad = math.radians(params.track_heading_deg)

        # Build 6 sequential waypoints leading up to and crossing landfall
        step_count = 6
        for step_idx in range(step_count):
            hours_offset = (step_idx - 4) * 4  # step 4 is landfall (0h), steps 0-3 approach (-16h to -4h)
            progress = step_idx / (step_count - 1)

            # Backtrack coordinate based on heading
            back_dist_deg = (4 - step_idx) * 0.8
            lat = params.landfall_lat - back_dist_deg * math.cos(heading_rad)
            lon = params.landfall_lon - back_dist_deg * math.sin(heading_rad)

            # Wind speed builds toward landfall and decays inland
            if step_idx <= 4:
                wind = params.max_wind_speed_knots * (0.7 + 0.3 * (step_idx / 4))
            else:
                wind = params.max_wind_speed_knots * 0.65  # decay post landfall

            cat = (
                "Super Cyclonic Storm"
                if wind >= 120
                else "Extremely Severe Cyclonic Storm"
                if wind >= 90
                else "Very Severe Cyclonic Storm"
                if wind >= 64
                else "Severe Cyclonic Storm"
            )

            waypoints.append(
                CycloneWaypoint(
                    step_index=step_idx,
                    timestamp=f"+{hours_offset}h" if hours_offset >= 0 else f"{hours_offset}h",
                    lat=round(lat, 2),
                    lon=round(lon, 2),
                    wind_speed_knots=round(wind, 1),
                    wind_speed_kph=round(wind * 1.852, 1),
                    pressure_mb=params.central_pressure_mb,
                    category=cat,
                    cone_radius_km=round(30.0 + step_idx * 15.0, 1),
                    is_forecast=True,
                    is_landfall_point=(step_idx == 4),
                )
            )

        # Evaluate risk across all assets at simulated landfall
        landfall_pt = waypoints[4]
        evaluated: List[ModelledRiskResult] = []

        for asset in assets:
            res = self.risk_engine.evaluate_asset(
                asset=asset,
                cyclone_lat=landfall_pt.lat,
                cyclone_lon=landfall_pt.lon,
                cyclone_wind_knots=landfall_pt.wind_speed_knots,
                data_mode=DataMode.SCENARIO,
            )
            evaluated.append(res)

        evaluated.sort(key=lambda r: r.modelled_risk_score, reverse=True)

        crit_count = sum(1 for r in evaluated if r.risk_level in ["CRITICAL", "HIGH"])
        hosp_count = sum(1 for r in evaluated if r.category == "hospital" and r.risk_level in ["CRITICAL", "HIGH"])
        pwr_count = sum(1 for r in evaluated if r.category == "power_grid" and r.risk_level in ["CRITICAL", "HIGH"])

        worst_district = evaluated[0].district if evaluated else "Coastal Corridor"
        max_risk = evaluated[0].modelled_risk_score if evaluated else 0.0

        # Construct approximate 100km hazard polygon around landfall
        r_deg = 1.0
        c_lat, c_lon = params.landfall_lat, params.landfall_lon
        hazard_poly = [
            [round(c_lon - r_deg, 3), round(c_lat - r_deg, 3)],
            [round(c_lon + r_deg, 3), round(c_lat - r_deg, 3)],
            [round(c_lon + r_deg, 3), round(c_lat + r_deg, 3)],
            [round(c_lon - r_deg, 3), round(c_lat + r_deg, 3)],
            [round(c_lon - r_deg, 3), round(c_lat - r_deg, 3)],
        ]

        summary = ScenarioImpactSummary(
            total_assets_at_risk=len(evaluated),
            critical_facilities_count=crit_count,
            hospitals_at_risk=hosp_count,
            substations_at_risk=pwr_count,
            worst_hit_district=worst_district,
            max_modelled_risk=max_risk,
            simulated_surge_corridor_km=round(params.surge_height_meters * 8.5, 1),
        )

        return ScenarioSimulationResult(
            parameters=params,
            simulated_track=waypoints,
            hazard_footprint_polygon=hazard_poly,
            evaluated_assets=evaluated,
            summary=summary,
            disclaimer="SCENARIO / MODELLED — NOT AN OFFICIAL FORECAST. FOR PREPAREDNESS SIMULATION ONLY.",
            provenance=DataSourceMeta(
                source="Nivara Scenario Simulator",
                dataset="Hypothetical Hazard Footprint Projection",
                retrieved_at=now_utc,
                status=DataMode.SCENARIO,
                confidence="ESTIMATED",
                is_forecast=True,
                attribution="Hypothetical scenario based on user parameters. Not affiliated with official IMD forecasts.",
            ),
        )
