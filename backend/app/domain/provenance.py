"""Data Provenance & Source Attribution Domain.

Enforces transparency across every pipeline response: tracks origin,
freshness, confidence, and authoritative status (LIVE, FORECAST, HISTORICAL, etc.).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DataMode(str, Enum):
    """Categorical classification of data authority."""

    LIVE = "LIVE"
    FORECAST = "FORECAST"
    HISTORICAL = "HISTORICAL"
    MODELLED = "MODELLED"
    SCENARIO = "SCENARIO"
    UNAVAILABLE = "UNAVAILABLE"


class SourceProvider(str, Enum):
    """Authoritative source entity."""

    IMD = "India Meteorological Department"
    NOAA_IBTRACS = "NOAA IBTrACS"
    OPEN_METEO = "Open-Meteo"
    GEE = "Google Earth Engine"
    OSM = "OpenStreetMap"
    NIVARA_RISK_ENGINE = "Nivara Risk Engine"
    GEMINI_LLM = "Google Gemini 3.7 Flash"
    GDACS = "GDACS (UN OCHA / EC JRC)"


class DataSourceMeta(BaseModel):
    """Standardized provenance metadata attached to every operational payload."""

    source: str = Field(..., description="Entity providing the data (e.g. IMD, Open-Meteo)")
    dataset: str = Field(..., description="Dataset name or API resource")
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of retrieval",
    )
    valid_time: Optional[str] = Field(None, description="Temporal validity horizon")
    status: DataMode = Field(..., description="LIVE, FORECAST, HISTORICAL, MODELLED, SCENARIO, or UNAVAILABLE")
    confidence: str = Field(default="HIGH", description="Confidence tier: HIGH, MODERATE, ESTIMATED")
    is_forecast: bool = Field(default=False, description="True if predictive forward-modelled")
    attribution: Optional[str] = Field(None, description="Copyright or attribution requirement")
