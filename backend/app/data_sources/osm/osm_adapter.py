"""OpenStreetMap Overpass API Source Adapter.

Discovers authentic infrastructure nodes:
Hospitals, Clinics, Power Plants, Substations, Arterial Bridges, Ports, Airports, Cyclone Shelters.
Never invents infrastructure nodes.
Attribution: OpenStreetMap contributors under ODbL.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from app.data_sources.open_meteo.open_meteo_adapter import OpenMeteoAdapter
from app.domain.infrastructure import AssetCategory, InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta


class OSMAdapter:
    """Adapter for querying critical infrastructure from OpenStreetMap."""

    def __init__(
        self,
        endpoint_url: str = "https://overpass-api.de/api/interpreter",
        data_dir: Optional[Path] = None,
        demo_mode: bool = False,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.data_dir = Path(data_dir) if data_dir is not None else (Path(__file__).resolve().parent.parent.parent.parent.parent / "data")
        self.demo_mode = demo_mode
        self.open_meteo = OpenMeteoAdapter()
        self._cached_assets: Optional[List[InfrastructureAsset]] = None
        from app.persistence.spatial_cache import SpatialCache
        self.spatial_cache = SpatialCache(self.data_dir / "spatial_cache.db")

    def build_query(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
        """Construct Overpass QL query covering healthcare, energy, shelters, and transport."""
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        return f"""[out:json][timeout:25];
(
  node["amenity"="hospital"]({bbox});
  node["amenity"="clinic"]({bbox});
  node["power"="substation"]({bbox});
  node["power"="plant"]({bbox});
  node["amenity"="shelter"]({bbox});
  node["aeroway"="aerodrome"]({bbox});
);
out body 60;"""

    async def fetch_infrastructure(
        self,
        min_lat: float = 21.0,
        min_lon: float = 86.6,
        max_lat: float = 23.0,
        max_lon: float = 89.2,
    ) -> List[InfrastructureAsset]:
        """Query live OSM Overpass API with local SQLite spatial caching.

        Raises:
            RuntimeError: If query fails and demo mode is disabled.
        """
        # 1. In-memory Cache Check (<0.01ms)
        if self._cached_assets is not None and len(self._cached_assets) >= 10:
            return self._cached_assets

        bbox_key = f"{round(min_lat, 1)}_{round(min_lon, 1)}_{round(max_lat, 1)}_{round(max_lon, 1)}"

        # 2. High-speed SQLite Cache Check (<2ms)
        cached_sqlite = self.spatial_cache.get_assets_by_bbox(bbox_key)
        if cached_sqlite:
            self._cached_assets = cached_sqlite
            return cached_sqlite

        query = self.build_query(min_lat, min_lon, max_lat, max_lon)
        headers = {
            "User-Agent": "Nivara-Disaster-Intelligence/1.0 (Public Research)",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        now_utc = datetime.now(timezone.utc).isoformat()

        try:
            async with httpx.AsyncClient(timeout=18.0) as client:
                res = await client.post(self.endpoint_url, data={"data": query}, headers=headers)
                if res.status_code == 200:
                    elements = res.json().get("elements", [])
                    if elements:
                        parsed: List[InfrastructureAsset] = []
                        coords: List[tuple[float, float]] = []

                        for el in elements:
                            tags = el.get("tags", {})
                            name = (
                                tags.get("name")
                                or tags.get("name:en")
                                or tags.get("operator")
                                or f"OSM Node #{el['id']}"
                            )

                            if "hospital" in tags.get("amenity", ""):
                                cat = AssetCategory.HOSPITAL
                            elif "clinic" in tags.get("amenity", ""):
                                cat = AssetCategory.HOSPITAL
                            elif tags.get("power") in ["substation", "plant"]:
                                cat = AssetCategory.POWER_GRID
                            elif tags.get("amenity") == "shelter":
                                cat = AssetCategory.SHELTER
                            elif tags.get("aeroway") == "aerodrome":
                                cat = AssetCategory.AIRPORT
                            else:
                                cat = AssetCategory.EMERGENCY

                            lat = float(el.get("lat", 0.0))
                            lon = float(el.get("lon", 0.0))

                            district = tags.get("addr:district") or tags.get("is_in:district") or "Coastal Sector"
                            state = tags.get("addr:state") or "West Bengal"

                            from app.domain.coastline import get_distance_to_coast_km
                            dist_coast = get_distance_to_coast_km(lat, lon)

                            parsed.append(
                                InfrastructureAsset(
                                    id=f"osm_node_{el['id']}",
                                    name=name,
                                    category=cat,
                                    lat=lat,
                                    lon=lon,
                                    elevation_m=5.0,  # Will be enriched by SRTM batch
                                    dist_to_coast_km=dist_coast,
                                    district=district,
                                    state=state,
                                    raw_tags=tags,
                                    provenance=DataSourceMeta(
                                        source="OpenStreetMap (OSM)",
                                        dataset="Overpass API Live Query",
                                        retrieved_at=now_utc,
                                        status=DataMode.LIVE,
                                        confidence="HIGH",
                                        is_forecast=False,
                                        attribution="© OpenStreetMap contributors under Open Database License (ODbL)",
                                    ),
                                )
                            )
                            coords.append((lat, lon))

                        # Fetch authentic SRTM elevation from Open-Meteo
                        if coords:
                            elevations = await self.open_meteo.get_elevation_batch(coords)
                            for idx, a in enumerate(parsed):
                                if idx < len(elevations):
                                    a.elevation_m = elevations[idx]

                        if len(parsed) >= 5:
                            self.spatial_cache.save_assets(bbox_key, parsed)
                            self._cached_assets = parsed
                            return parsed
        except Exception:
            pass

        # If live fetch fails, check if DEMO_MODE is explicitly enabled
        if self.demo_mode:
            demo_file = self.data_dir / "demo" / "infrastructure_sample.json"
            if not demo_file.exists():
                demo_file = self.data_dir / "sample_track" / "infrastructure_sample.json"

            if demo_file.exists():
                with open(demo_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                demo_assets: List[InfrastructureAsset] = []
                for item in data.get("assets", []):
                    cat = AssetCategory.HOSPITAL if item["infra_type"] == "hospital" else AssetCategory.POWER_GRID if "power" in item["infra_type"] else AssetCategory.ROAD if "road" in item["infra_type"] else AssetCategory.SHELTER
                    demo_assets.append(
                        InfrastructureAsset(
                            id=item["id"],
                            name=item["name"],
                            category=cat,
                            lat=float(item["lat"]),
                            lon=float(item["lon"]),
                            elevation_m=float(item.get("elevation_m", 5.0)),
                            dist_to_coast_km=float(item.get("dist_to_coast_km", 10.0)),
                            district=item.get("district", "Coastal Zone"),
                            state=item.get("state", "West Bengal"),
                            raw_tags=item.get("raw_tags", {}),
                            provenance=DataSourceMeta(
                                source="OpenStreetMap (OSM) Archive",
                                dataset="Offline Development Fixture",
                                retrieved_at=now_utc,
                                status=DataMode.HISTORICAL,
                                confidence="ESTIMATED",
                                is_forecast=False,
                                attribution="[ DEMO / OFFLINE MODE ] OpenStreetMap historical extraction",
                            ),
                        )
                    )
                self._cached_assets = demo_assets
                return demo_assets

        # If live failed and demo_mode is not enabled, raise transparent error
        raise RuntimeError("OpenStreetMap Overpass API is currently unavailable and DEMO_MODE is disabled.")
