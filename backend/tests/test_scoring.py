"""Unit Tests for Pure Risk Scoring Engine.

Tests mathematical boundaries, weighting logic, and categorical outputs
of the risk scoring functions.
"""

import pytest
from app.risk_engine.scoring import (
    RiskBreakdown,
    RiskWeights,
    classify_risk_level,
    compute_composite_risk,
    compute_proximity_factor,
    compute_wind_intensity_factor,
    compute_elevation_vulnerability,
    compute_coastal_exposure,
    compute_land_cover_factor,
    compute_haversine_distance_km,
)


def test_compute_proximity_factor_bounds():
    """Verify proximity factor returns 1.0 at 0km and decreases to 0.0 at max radius."""
    assert compute_proximity_factor(0.0, max_radius_km=200.0) == 1.0
    assert compute_proximity_factor(200.0, max_radius_km=200.0) == 0.0
    assert compute_proximity_factor(500.0, max_radius_km=200.0) == 0.0
    # Monotonicity test
    near = compute_proximity_factor(20.0)
    mid = compute_proximity_factor(80.0)
    far = compute_proximity_factor(160.0)
    assert near > mid > far


def test_compute_wind_intensity_factor_bounds():
    """Verify wind intensity factor scales with wind speed."""
    calm = compute_wind_intensity_factor(0.0)
    moderate = compute_wind_intensity_factor(65.0)
    extreme = compute_wind_intensity_factor(140.0)
    assert calm == 0.0
    assert extreme == 1.0
    assert 0.0 < moderate < extreme


def test_compute_elevation_vulnerability_bounds():
    """Verify lower elevations produce higher vulnerability scores."""
    sea_level = compute_elevation_vulnerability(0.0)
    mid_ground = compute_elevation_vulnerability(8.0)
    high_ground = compute_elevation_vulnerability(50.0)
    assert sea_level == 1.0
    assert sea_level > mid_ground > high_ground
    assert high_ground == 0.05


def test_compute_coastal_exposure_bounds():
    """Verify coastal exposure drops to 0 beyond coastal buffer."""
    shoreline = compute_coastal_exposure(0.0)
    mid_buffer = compute_coastal_exposure(15.0)
    inland = compute_coastal_exposure(50.0)
    assert shoreline == 1.0
    assert 0.0 < mid_buffer < 1.0
    assert inland == 0.0


def test_compute_land_cover_factor():
    """Verify urban and wetland receive higher vulnerability factors than forest."""
    urban = compute_land_cover_factor("urban")
    wetland = compute_land_cover_factor("wetland")
    forest = compute_land_cover_factor("forest")
    assert urban == 1.0
    assert wetland > forest
    assert forest == 0.40


def test_classify_risk_level():
    """Verify score mapping into categorical risk levels."""
    assert classify_risk_level(0.20) == "LOW"
    assert classify_risk_level(0.35) == "MODERATE"
    assert classify_risk_level(0.65) == "HIGH"
    assert classify_risk_level(0.85) == "CRITICAL"


def test_compute_haversine_distance():
    """Verify haversine distance between Digha and Sagar Island (~55km)."""
    dist = compute_haversine_distance_km(21.628, 87.514, 21.652, 88.082)
    assert 50.0 < dist < 65.0


def test_compute_composite_risk_structure():
    """Verify composite risk calculation returns complete result within [0, 1]."""
    # High risk asset near eye and coast at low elevation
    critical_result = compute_composite_risk(
        dist_from_track_km=8.0,
        wind_speed_knots=110.0,
        elevation_m=2.5,
        dist_to_coast_km=1.0,
        land_cover_class="urban",
    )
    assert 0.70 <= critical_result.risk_score <= 1.0
    assert critical_result.risk_level in ["HIGH", "CRITICAL"]
    assert isinstance(critical_result.breakdown, RiskBreakdown)

    # Safe inland asset far away
    low_result = compute_composite_risk(
        dist_from_track_km=250.0,
        wind_speed_knots=60.0,
        elevation_m=45.0,
        dist_to_coast_km=120.0,
        land_cover_class="forest",
    )
    assert low_result.risk_score < 0.35
    assert low_result.risk_level == "LOW"
