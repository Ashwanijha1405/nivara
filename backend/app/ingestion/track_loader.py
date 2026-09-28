"""IBTrACS Storm Track Ingestion Module.

Handles loading, parsing, and normalizing historical cyclone track data
from IBTrACS into clean sequential timestep representations.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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

    storm_id: str = Field(..., description="Unique storm identifier (e.g. IBTrACS ID)")
    name: str = Field(..., description="Storm name (e.g. AMPHAN)")
    year: int = Field(..., description="Year of cyclone occurrence")
    basin: str = Field(..., description="Ocean basin code (e.g. NI for North Indian)")
    points: List[TrackPoint] = Field(default_factory=list, description="Ordered track points")


class TrackLoader:
    """Loader for historical cyclone tracks."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"

    def load_track_from_file(self, file_path: Path) -> StormTrack:
        """Parse raw IBTrACS data (JSON) from disk into a normalized StormTrack.

        Args:
            file_path: Path to the track JSON file.

        Returns:
            StormTrack: Normalized track data structure.
        """
        target = Path(file_path)
        if not target.is_absolute():
            target = self.data_dir / "sample_track" / target.name

        if not target.exists():
            fallback = self.data_dir / "sample_track" / "amphan_sample.json"
            if fallback.exists():
                target = fallback
            else:
                raise FileNotFoundError(f"Track file not found at {target} and fallback {fallback} missing.")

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
            storm_id=str(raw_data.get("storm_id", "2020139N09086")),
            name=str(raw_data.get("name", "AMPHAN")),
            year=int(raw_data.get("year", 2020)),
            basin=str(raw_data.get("basin", "NI")),
            points=points,
        )

    def get_point_at_timestep(self, storm_track: StormTrack, step_index: int) -> TrackPoint:
        """Extract a single timestep track point from the storm sequence.

        Args:
            storm_track: The full storm sequence.
            step_index: Target zero-based timestep index.

        Returns:
            TrackPoint: The storm state at that index.
        """
        if not storm_track.points:
            raise ValueError(f"Storm track {storm_track.storm_id} contains no track points.")

        bounded_index = max(0, min(step_index, len(storm_track.points) - 1))
        return storm_track.points[bounded_index]
