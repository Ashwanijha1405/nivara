"""OpenStreetMap Overpass API Infrastructure Client.

Fetches real critical infrastructure nodes (hospitals, power substations, secondary/primary roads)
directly from OpenStreetMap Overpass API and enriches them with real SRTM elevation data.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from app.ingestion.weather_client import WeatherClient


class InfrastructureAsset(BaseModel):
    """Normalized critical infrastructure entity."""

    id: str = Field(..., description="Unique OSM identifier (e.g. 'osm_node_123456')")
    name: str = Field(..., description="Name of the infrastructure facility")
    infra_type: str = Field(
        ...,
        description="Type category: 'hospital', 'power_station', 'power_substation', 'road_arterial', 'shelter'",
    )
    lat: float
    lon: float
    district: Optional[str] = Field(None, description="Administrative district name")
    state: Optional[str] = Field(None, description="Administrative state/region name")
    elevation_m: Optional[float] = Field(None, description="Terrain elevation in meters")
    dist_to_coast_km: Optional[float] = Field(None, description="Distance from coastline in km")
    land_cover_class: Optional[str] = Field(None, description="Land cover classification")
    raw_tags: Dict[str, Any] = Field(default_factory=dict, description="Raw OSM tags")


class InfraClient:
    """Client for querying live infrastructure assets from OSM Overpass API."""

    def __init__(
        self,
        endpoint_url: str = "https://overpass-api.de/api/interpreter",
        fallback_data_path: Optional[Path] = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        if fallback_data_path is not None:
            self.fallback_data_path = Path(fallback_data_path)
        else:
            self.fallback_data_path = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "data"
                / "sample_track"
                / "infrastructure_sample.json"
            )
        self.weather_client = WeatherClient()
        self._cached_live_assets: Optional[List[InfrastructureAsset]] = None

    def load_fallback_infrastructure(self) -> List[InfrastructureAsset]:
        """Load curated infrastructure points if live Overpass query is unreachable."""
        if not self.fallback_data_path.exists():
            return []

        with open(self.fallback_data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assets: List[InfrastructureAsset] = []
        for raw in data.get("assets", []):
            assets.append(
                InfrastructureAsset(
                    id=raw["id"],
                    name=raw["name"],
                    infra_type=raw["infra_type"],
                    lat=float(raw["lat"]),
                    lon=float(raw["lon"]),
                    district=raw.get("district"),
                    state=raw.get("state"),
                    elevation_m=float(raw["elevation_m"]) if raw.get("elevation_m") is not None else 5.0,
                    dist_to_coast_km=float(raw["dist_to_coast_km"]) if raw.get("dist_to_coast_km") is not None else 10.0,
                    land_cover_class=raw.get("land_cover_class", "urban"),
                    raw_tags=raw.get("raw_tags", {}),
                )
            )
        return assets

    def build_overpass_query(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        limit: int = 50,
    ) -> str:
        """Construct Overpass QL query string with specific tags."""
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        return f"""[out:json][timeout:20];
(
  node["amenity"="hospital"]({bbox});
  node["power"="substation"]({bbox});
  node["amenity"="shelter"]({bbox});
);
out body {limit};"""

    async def fetch_infrastructure(
        self,
        min_lat: float = 21.2,
        min_lon: float = 86.8,
        max_lat: float = 22.8,
        max_lon: float = 88.9,
    ) -> List[InfrastructureAsset]:
        """Fetch live infrastructure via Overpass API and enrich with real SRTM elevation.

        Caches the response in memory for the session so repeated calls are instant.
        """
        if self._cached_live_assets is not None and len(self._cached_live_assets) >= 10:
            return self._cached_live_assets

        query = self.build_overpass_query(min_lat, min_lon, max_lat, max_lon, limit=45)
        headers = {
            "User-Agent": "Nivara-CycloneMVP/0.1",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.endpoint_url,
                    data={"data": query},
                    headers=headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    elements = data.get("elements", [])
                    if elements:
                        parsed_assets: List[InfrastructureAsset] = []
                        coords: List[tuple[float, float]] = []

                        for el in elements:
                            tags = el.get("tags", {})
                            name = (
                                tags.get("name")
                                or tags.get("name:en")
                                or tags.get("operator")
                                or f"Infrastructure Node #{el.get('id')}"
                            )
                            if "hospital" in tags.get("amenity", ""):
                                itype = "hospital"
                            elif tags.get("power") == "substation":
                                itype = "power_substation"
                            elif tags.get("amenity") == "shelter":
                                itype = "shelter"
                            else:
                                itype = "road_arterial"

                            lat = float(el.get("lat", 0.0))
                            lon = float(el.get("lon", 0.0))
                            if lat and lon:
                                # Determine district from tags or coordinates
                                district = tags.get("addr:district") or tags.get("is_in:district")
                                if not district:
                                    if lat < 21.9 and lon < 87.9:
                                        district = "Purba Medinipur"
                                    elif lat < 22.4 and lon >= 88.0:
                                        district = "South 24 Parganas"
                                    elif lat >= 22.4 and lon < 88.4:
                                        district = "Kolkata"
                                    else:
                                        district = "North 24 Parganas"

                                parsed_assets.append(
                                    InfrastructureAsset(
                                        id=f"osm_{el.get('type', 'node')}_{el.get('id')}",
                                        name=name,
                                        infra_type=itype,
                                        lat=lat,
                                        lon=lon,
                                        district=district,
                                        state="West Bengal",
                                        raw_tags=tags,
                                    )
                                )
                                coords.append((lat, lon))

                        # Enrich with real SRTM elevation from Open-Meteo
                        if coords:
                            elevations = await self.weather_client.fetch_elevation_batch(coords)
                            for idx, asset in enumerate(parsed_assets):
                                asset.elevation_m = elevations[idx] if idx < len(elevations) else 5.0
                                # Calculate approximate coastal distance
                                coast_lat = 21.55 + 0.05 * (asset.lon - 87.0)
                                delta_lat = max(0.0, asset.lat - coast_lat)
                                asset.dist_to_coast_km = round(delta_lat * 111.0, 1)
                                asset.land_cover_class = (
                                    "urban"
                                    if "Kolkata" in (asset.district or "")
                                    else "wetland"
                                    if (asset.dist_to_coast_km or 10.0) < 5.0
                                    else "cropland"
                                )

                        if len(parsed_assets) >= 10:
                            self._cached_live_assets = parsed_assets
                            return parsed_assets
        except Exception:
            # Overpass network or rate issue -> fallback
            pass

        fallback = self.load_fallback_infrastructure()
        self._cached_live_assets = fallback
        return fallback
