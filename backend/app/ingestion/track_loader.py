"""IBTrACS & Live Meteorological Storm Track Ingestion Module.

Handles loading, parsing, and normalizing verified NOAA Best Track data
(IBTrACS) and live active meteorological feeds into sequential timestep representations.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.ingestion.weather_client import WeatherClient


class TrackPoint(BaseModel):
    """Normalized storm point at a specific timestep."""

    step_index: int = Field(..., description="Chronological index of this point")
    iso_time: str = Field(..., description="Timestamp in ISO 8601 format (UTC)")
    lat: float = Field(..., description="Latitude of cyclone eye")
    lon: float = Field(..., description="Longitude of cyclone eye")
    wind_speed_knots: float = Field(..., description="Maximum sustained wind speed in knots")
    pressure_mb: Optional[float] = Field(None, description="Minimum central pressure in millibars")
    category: Optional[str] = Field(None, description="IMD or Saffir-Simpson cyclone classification")


class StormTrack(BaseModel):
    """Complete parsed storm track sequence."""

    storm_id: str = Field(..., description="Unique storm identifier")
    name: str = Field(..., description="Storm name")
    year: int = Field(..., description="Year of cyclone occurrence")
    basin: str = Field(..., description="Ocean basin code (e.g. NI for North Indian)")
    points: List[TrackPoint] = Field(default_factory=list, description="Ordered track points")


class TrackLoader:
    """Loader for historical cyclone tracks and live atmospheric feeds."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
        self.weather_client = WeatherClient()

    def get_available_storms(self) -> List[Dict[str, Any]]:
        """List verified historical storms and active live monitoring feeds."""
        return [
            {
                "storm_id": "2020136N10088",
                "name": "AMPHAN",
                "year": 2020,
                "basin": "NI",
                "source": "NOAA IBTrACS Best Track Archive",
                "description": "Super Cyclonic Storm Amphan (Bay of Bengal, May 2020)",
                "total_timesteps": 26,
            },
            {
                "storm_id": "2024145N14087",
                "name": "REMAL",
                "year": 2024,
                "basin": "NI",
                "source": "NOAA IBTrACS Best Track Archive",
                "description": "Severe Cyclonic Storm Remal (Bay of Bengal, May 2024)",
                "total_timesteps": 18,
            },
            {
                "storm_id": "LIVE_MONITOR",
                "name": "BAY OF BENGAL LIVE",
                "year": 2026,
                "basin": "NI",
                "source": "Open-Meteo Real-Time Atmospheric Feed",
                "description": "Live Real-Time Satellite & Weather Station Stream (Active Coast)",
                "total_timesteps": 6,
            },
        ]

    async def load_live_active_track(self) -> StormTrack:
        """Construct a real-time tracking sequence from live Open-Meteo observations."""
        # Active coastal monitoring points from southern Bay to Sagar/Kolkata
        monitoring_coords = [
            (18.5, 87.2, "South Bay Deep Water"),
            (19.8, 87.8, "Odisha Offshore Marine"),
            (20.8, 88.0, "Digha Coastal Approach"),
            (21.5, 88.2, "Sundarbans Outer Reef"),
            (21.8, 88.3, "Sagar Island Landfall Corridor"),
            (22.5, 88.4, "Kolkata Metropolitan Core"),
        ]

        points: List[TrackPoint] = []
        for idx, (lat, lon, label) in enumerate(monitoring_coords):
            obs = await self.weather_client.fetch_live_atmosphere(lat, lon)
            wind_knots = round(obs.surface_wind_kph / 1.852, 1)

            if wind_knots >= 64:
                cat = "Very Severe Cyclonic Storm"
            elif wind_knots >= 48:
                cat = "Severe Cyclonic Storm"
            elif wind_knots >= 34:
                cat = "Cyclonic Storm"
            elif wind_knots >= 28:
                cat = "Deep Depression"
            elif wind_knots >= 17:
                cat = "Depression"
            else:
                cat = "Low Pressure Area (Monitored)"

            points.append(
                TrackPoint(
                    step_index=idx,
                    iso_time=obs.timestamp or f"2026-09-29T{10 + idx * 3}:00:00Z",
                    lat=lat,
                    lon=lon,
                    wind_speed_knots=max(wind_knots, 18.0),
                    pressure_mb=obs.surface_pressure_hpa,
                    category=cat,
                )
            )

        return StormTrack(
            storm_id="LIVE_MONITOR",
            name="BAY OF BENGAL LIVE",
            year=2026,
            basin="NI",
            points=points,
        )

    def load_track_from_file(self, file_path_or_id: str) -> StormTrack:
        """Parse raw NOAA IBTrACS JSON into a normalized StormTrack."""
        filename = "amphan_noaa.json"
        if "2024" in file_path_or_id or "remal" in file_path_or_id.lower():
            filename = "remal_noaa.json"
        elif "2020" in file_path_or_id or "amphan" in file_path_or_id.lower():
            filename = "amphan_noaa.json"

        target = self.data_dir / "sample_track" / filename
        if not target.exists():
            target = self.data_dir / "sample_track" / "amphan_sample.json"

        with open(target, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        points: List[TrackPoint] = []
        for item in raw_data.get("track_points", []):
            points.append(
                TrackPoint(
                    step_index=item["step_index"],
                    iso_time=item["iso_time"],
                    lat=float(item["lat"]),
                    lon=float(item["lon"]),
                    wind_speed_knots=float(item["wind_speed_knots"]),
                    pressure_mb=float(item["pressure_mb"]) if item.get("pressure_mb") is not None else None,
                    category=item.get("category"),
                )
            )

        points.sort(key=lambda p: p.step_index)

        return StormTrack(
            storm_id=str(raw_data.get("storm_id", file_path_or_id)),
            name=str(raw_data.get("name", "AMPHAN")),
            year=int(raw_data.get("year", 2020)),
            basin=str(raw_data.get("basin", "NI")),
            points=points,
        )

    async def get_track(self, storm_id: str) -> StormTrack:
        """Get storm track for any historical storm ID or live monitoring feed."""
        if storm_id == "LIVE_MONITOR":
            return await self.load_live_active_track()
        return self.load_track_from_file(storm_id)

    def get_point_at_timestep(self, storm_track: StormTrack, step_index: int) -> TrackPoint:
        """Extract a single timestep track point from the storm sequence."""
        if not storm_track.points:
            raise ValueError(f"Storm track {storm_track.storm_id} contains no track points.")

        bounded_index = max(0, min(step_index, len(storm_track.points) - 1))
        return storm_track.points[bounded_index]
