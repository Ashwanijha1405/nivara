"""OpenStreetMap Overpass API Infrastructure Client.

Fetches critical infrastructure points (hospitals, power grid assets, arterial roads)
within a specified geographic bounding box. Includes resilient local fallback.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field


class InfrastructureAsset(BaseModel):
    """Normalized critical infrastructure entity."""

    id: str = Field(..., description="Unique OSM identifier (e.g. 'osm_hosp_01')")
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
    """Client for querying infrastructure assets from OSM Overpass API or local cache."""

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

    def load_cached_infrastructure(self) -> List[InfrastructureAsset]:
        """Load curated infrastructure points from local storage."""
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
    ) -> str:
        """Construct Overpass QL query string for key infrastructure types."""
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        return f"""
        [out:json][timeout:8];
        (
          node["amenity"="hospital"]({bbox});
          node["power"="substation"]({bbox});
          node["power"="plant"]({bbox});
        );
        out center 60;
        """

    async def fetch_infrastructure(
        self,
        min_lat: float = 21.0,
        min_lon: float = 86.5,
        max_lat: float = 23.5,
        max_lon: float = 89.5,
    ) -> List[InfrastructureAsset]:
        """Fetch infrastructure via Overpass API with immediate fallback to curated cache."""
        query = self.build_overpass_query(min_lat, min_lon, max_lat, max_lon)
        cached_assets = self.load_cached_infrastructure()

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.post(self.endpoint_url, data={"data": query})
                if response.status_code == 200:
                    data = response.json()
                    elements = data.get("elements", [])
                    if elements:
                        fetched: List[InfrastructureAsset] = []
                        for el in elements:
                            tags = el.get("tags", {})
                            name = tags.get("name", "Unnamed Facility")
                            if "hospital" in tags.get("amenity", ""):
                                itype = "hospital"
                            elif tags.get("power") == "plant":
                                itype = "power_station"
                            elif tags.get("power") == "substation":
                                itype = "power_substation"
                            else:
                                itype = "road_arterial"

                            lat = el.get("lat") or el.get("center", {}).get("lat")
                            lon = el.get("lon") or el.get("center", {}).get("lon")
                            if lat and lon:
                                fetched.append(
                                    InfrastructureAsset(
                                        id=f"osm_{el.get('type')}_{el.get('id')}",
                                        name=name,
                                        infra_type=itype,
                                        lat=float(lat),
                                        lon=float(lon),
                                        district=tags.get("addr:district") or tags.get("is_in:district"),
                                        state="West Bengal",
                                        raw_tags=tags,
                                    )
                                )
                        if len(fetched) >= 5:
                            return fetched
        except Exception:
            # Overpass rate limit or network unreachable -> rely on cached assets
            pass

        return cached_assets
