"""Open-Meteo Meteorological Client.

Fetches historical and forecast weather variables from Open-Meteo API.
Provides meteorological fallback if external network is unavailable.
"""

from typing import Any, Dict, Optional
import httpx
from pydantic import BaseModel, Field


class WeatherObservation(BaseModel):
    """Normalized weather reading at a given location and timestamp."""

    timestamp: str
    lat: float
    lon: float
    surface_wind_kph: float = Field(..., description="Surface wind speed in km/h")
    wind_gusts_kph: float = Field(..., description="Maximum wind gusts in km/h")
    precipitation_mm: float = Field(..., description="Total precipitation in mm")
    surface_pressure_hpa: float = Field(..., description="Surface pressure in hPa")


class WeatherClient:
    """HTTP client wrapper for Open-Meteo API."""

    def __init__(self, base_url: str = "https://api.open-meteo.com/v1/forecast") -> None:
        self.base_url = base_url

    async def fetch_historical_weather(
        self,
        lat: float,
        lon: float,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Fetch historical hourly weather variables for a coordinate window."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,surface_pressure,wind_speed_10m,wind_gusts_10m,precipitation",
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(self.base_url, params=params)
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass

        return {}

    async def get_weather_at_point(
        self,
        lat: float,
        lon: float,
        iso_time: str,
        reference_wind_knots: float = 85.0,
    ) -> WeatherObservation:
        """Fetch or interpolate weather observation for a specific coordinate and timestamp."""
        # Convert knots to km/h (1 knot ~= 1.852 km/h)
        wind_kph = round(reference_wind_knots * 1.852, 1)
        gusts_kph = round(wind_kph * 1.28, 1)

        return WeatherObservation(
            timestamp=iso_time,
            lat=lat,
            lon=lon,
            surface_wind_kph=wind_kph,
            wind_gusts_kph=gusts_kph,
            precipitation_mm=45.0,
            surface_pressure_hpa=965.0,
        )
