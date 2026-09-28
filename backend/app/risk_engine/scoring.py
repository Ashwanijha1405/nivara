"""Pure Mathematical Risk Scoring Engine.

Implements transparent, defensible, weighted risk calculations.
Pure functions only: no I/O, no network calls, fully unit-testable.

Architecture Reference (§5):
    risk_score(point, t) =
        w1 * proximity_factor(dist_from_track_at_t)
      + w2 * wind_intensity_factor(wind_speed_at_t)
      + w3 * elevation_vulnerability(elevation_m)
      + w4 * coastal_exposure(distance_to_coast)
      + w5 * land_cover_multiplier(land_cover_class)
"""

import math
from dataclasses import dataclass
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field


RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(frozen=True)
class RiskWeights:
    """Configurable weights for composite risk scoring."""

    proximity: float = 0.35
    wind_intensity: float = 0.25
    elevation: float = 0.20
    coastal_exposure: float = 0.15
    land_cover: float = 0.05


class RiskBreakdown(BaseModel):
    """Normalized components (0.0 to 1.0) contributing to total risk."""

    proximity_factor: float = Field(..., ge=0.0, le=1.0)
    wind_intensity_factor: float = Field(..., ge=0.0, le=1.0)
    elevation_vulnerability: float = Field(..., ge=0.0, le=1.0)
    coastal_exposure: float = Field(..., ge=0.0, le=1.0)
    land_cover_multiplier: float = Field(..., ge=0.0, le=1.0)


class RiskScoreResult(BaseModel):
    """Result of composite risk score evaluation."""

    risk_score: float = Field(..., ge=0.0, le=1.0, description="Composite score between 0.0 and 1.0")
    risk_level: RiskLevel = Field(..., description="Categorical classification")
    breakdown: RiskBreakdown


def compute_proximity_factor(distance_km: float, max_radius_km: float = 300.0) -> float:
    """Calculate normalized risk factor based on distance from the cyclone track center.

    Decreases smoothly with distance from eye; reaches 0.0 at or beyond max_radius_km.
    """
    if distance_km <= 0.0:
        return 1.0
    if distance_km >= max_radius_km:
        return 0.0

    # Smooth exponential decay curve reflecting cyclone gale wind radius
    factor = (1.0 - (distance_km / max_radius_km)) ** 1.5
    return round(max(0.0, min(1.0, factor)), 3)


def compute_wind_intensity_factor(wind_speed_knots: float, max_reference_knots: float = 140.0) -> float:
    """Calculate normalized wind intensity risk factor relative to Super Cyclone threshold."""
    if wind_speed_knots <= 0.0:
        return 0.0

    ratio = min(wind_speed_knots / max_reference_knots, 1.0)
    # Power curve reflecting aerodynamic force scaling with velocity squared
    factor = ratio ** 1.3
    return round(max(0.0, min(1.0, factor)), 3)


def compute_elevation_vulnerability(elevation_m: float, sea_level_threshold_m: float = 15.0) -> float:
    """Calculate surge and flooding vulnerability based on terrain elevation.

    Low coastal elevations under 5m have peak surge vulnerability.
    """
    if elevation_m <= 1.5:
        return 1.0
    if elevation_m >= sea_level_threshold_m:
        return 0.05

    # Linear interpolation between 1.5m and threshold
    factor = 1.0 - (0.95 * ((elevation_m - 1.5) / (sea_level_threshold_m - 1.5)))
    return round(max(0.0, min(1.0, factor)), 3)


def compute_coastal_exposure(distance_to_coast_km: float, coastal_buffer_km: float = 30.0) -> float:
    """Calculate exposure factor based on proximity to the coastline."""
    if distance_to_coast_km <= 0.0:
        return 1.0
    if distance_to_coast_km >= coastal_buffer_km:
        return 0.0

    factor = 1.0 - (distance_to_coast_km / coastal_buffer_km)
    return round(max(0.0, min(1.0, factor)), 3)


def compute_land_cover_factor(land_cover_class: str) -> float:
    """Determine vulnerability multiplier based on land cover type."""
    normalized = land_cover_class.strip().lower() if land_cover_class else "cropland"

    class_weights: Dict[str, float] = {
        "urban": 1.0,
        "wetland": 0.85,
        "water": 0.90,
        "cropland": 0.65,
        "forest": 0.40,
        "bare": 0.50,
    }
    return class_weights.get(normalized, 0.60)


def classify_risk_level(score: float) -> RiskLevel:
    """Categorize continuous score into discrete risk level: LOW, MEDIUM, HIGH, CRITICAL."""
    if score >= 0.75:
        return "CRITICAL"
    if score >= 0.55:
        return "HIGH"
    if score >= 0.30:
        return "MEDIUM"
    return "LOW"


def compute_haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in kilometers between two points."""
    r = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def compute_composite_risk(
    dist_from_track_km: float,
    wind_speed_knots: float,
    elevation_m: float,
    dist_to_coast_km: float,
    land_cover_class: str,
    weights: Optional[RiskWeights] = None,
) -> RiskScoreResult:
    """Compute the weighted composite risk score for a single infrastructure point.

    Modulates storm wind and surge impact by proximity to storm center so distant points
    correctly report negligible cyclone risk before storm arrival.
    """
    w = weights or RiskWeights()

    p_factor = compute_proximity_factor(dist_from_track_km, max_radius_km=300.0)
    w_factor = compute_wind_intensity_factor(wind_speed_knots)
    e_factor = compute_elevation_vulnerability(elevation_m)
    c_factor = compute_coastal_exposure(dist_to_coast_km)
    l_factor = compute_land_cover_factor(land_cover_class)

    # When cyclone is outside circulation buffer, dynamic hazard is inactive
    effective_wind = w_factor * p_factor
    effective_surge = ((w.elevation * e_factor) + (w.coastal_exposure * c_factor)) * p_factor

    raw_score = (
        (w.proximity * p_factor)
        + (w.wind_intensity * effective_wind)
        + effective_surge
        + (w.land_cover * l_factor * p_factor)
    )

    score = round(max(0.0, min(1.0, raw_score)), 2)
    level = classify_risk_level(score)

    breakdown = RiskBreakdown(
        proximity_factor=p_factor,
        wind_intensity_factor=w_factor,
        elevation_vulnerability=e_factor,
        coastal_exposure=c_factor,
        land_cover_multiplier=l_factor,
    )

    return RiskScoreResult(
        risk_score=score,
        risk_level=level,
        breakdown=breakdown,
    )
