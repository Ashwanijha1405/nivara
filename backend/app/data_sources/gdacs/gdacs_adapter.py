"""GDACS (Global Disaster Alert and Coordination System) Adapter.

Authoritative free real-time tropical cyclone data source operated by
United Nations OCHA and European Commission Joint Research Centre (EC JRC).
Provides live active cyclone detection, tracks, and wind hazard buffer polygons.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.domain.cyclone import LiveCycloneInfo, LiveCycloneStatusResponse
from app.domain.provenance import DataMode, DataSourceMeta

logger = logging.getLogger(__name__)

# North Indian Ocean (Bay of Bengal + Arabian Sea) bounding domain
NIO_MIN_LAT = 0.0
NIO_MAX_LAT = 32.0
NIO_MIN_LON = 50.0
NIO_MAX_LON = 100.0

NIO_AFFECTED_ISO3 = {
    "IND",  # India
    "BGD",  # Bangladesh
    "MMR",  # Myanmar
    "LKA",  # Sri Lanka
    "MDV",  # Maldives
    "OMN",  # Oman
    "YEM",  # Yemen
    "PAK",  # Pakistan
    "THA",  # Thailand (Andaman Sea coast)
}


class GDACSAdapter:
    """Adapter for querying operational cyclone information from GDACS."""

    def __init__(
        self,
        base_url: str = "https://www.gdacs.org/gdacsapi/api",
        timeout_seconds: float = 6.0,
        cache_ttl_seconds: int = 90,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds

        # In-memory operational cache
        self._cached_status: Optional[LiveCycloneStatusResponse] = None
        self._cached_geojson: Optional[Dict[str, Any]] = None
        self._last_fetch_utc: Optional[datetime] = None
        self._last_successful_sync_utc: Optional[str] = None

    def is_north_indian_ocean(self, feature: Dict[str, Any]) -> bool:
        """Evaluate whether a GDACS cyclone event belongs to the North Indian Ocean basin.

        Uses dual geographic verification:
        1. Coordinate bounds (0°N - 32°N, 50°E - 100°E: Bay of Bengal and Arabian Sea)
        2. Affected country ISO3 codes (India, Bangladesh, Myanmar, Sri Lanka, etc.)
        """
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates")
        props = feature.get("properties", {})

        in_spatial_bbox = False
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
            if NIO_MIN_LAT <= lat <= NIO_MAX_LAT and NIO_MIN_LON <= lon <= NIO_MAX_LON:
                in_spatial_bbox = True

        # Check affected country ISO codes
        in_affected_nations = False
        country_iso3 = props.get("iso3")
        if country_iso3 and country_iso3.upper() in NIO_AFFECTED_ISO3:
            in_affected_nations = True

        for c in props.get("affectedcountries", []):
            if isinstance(c, dict) and c.get("iso3", "").upper() in NIO_AFFECTED_ISO3:
                in_affected_nations = True
                break

        return in_spatial_bbox or in_affected_nations

    async def fetch_active_tropical_cyclones(self) -> List[Dict[str, Any]]:
        """Query GDACS active TC search endpoint."""
        url = f"{self.base_url}/events/geteventlist/SEARCH?eventtype=TC"
        headers = {
            "User-Agent": "Nivara-Disaster-Intelligence/1.0 (Public Research; Disaster Management)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                raise RuntimeError(f"GDACS API returned HTTP {res.status_code}: {res.text[:120]}")
            data = res.json()
            features = data.get("features", [])
            return features

    async def fetch_detailed_geometry(self, event_id: Any, episode_id: Any) -> Dict[str, Any]:
        """Fetch detailed event GeoJSON including track lines and wind buffer polygons."""
        url = f"{self.base_url}/polygons/getgeometry?eventtype=TC&eventid={event_id}&episodeid={episode_id}"
        headers = {
            "User-Agent": "Nivara-Disaster-Intelligence/1.0 (Public Research; Disaster Management)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                logger.warning("Failed to fetch GDACS geometry for event %s: HTTP %s", event_id, res.status_code)
                return {"type": "FeatureCollection", "features": []}
            return res.json()

    async def get_live_cyclone_status(self) -> LiveCycloneStatusResponse:
        """Fetch normalized live cyclone status from GDACS with in-memory caching."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        # Check in-memory cache
        if (
            self._cached_status is not None
            and self._last_fetch_utc is not None
            and (now - self._last_fetch_utc).total_seconds() < self.cache_ttl_seconds
        ):
            return self._cached_status

        try:
            features = await self.fetch_active_tropical_cyclones()
            self._last_successful_sync_utc = now_str
            self._last_fetch_utc = now

            # Filter for current active events
            current_events = [
                f for f in features
                if str(f.get("properties", {}).get("iscurrent", "")).lower() == "true"
                and f.get("properties", {}).get("eventtype") == "TC"
            ]

            # Filter for North Indian Ocean relevance
            nio_events = [f for f in current_events if self.is_north_indian_ocean(f)]

            if not nio_events:
                # Successfully verified that no active cyclone exists in the basin
                status = LiveCycloneStatusResponse(
                    source="GDACS",
                    data_mode="LIVE",
                    live_status="CALM",
                    active_cyclone=False,
                    cyclone=None,
                    fetched_at=now_str,
                    last_successful_sync=self._last_successful_sync_utc,
                    message="No active tropical cyclone detected in North Indian Ocean basin (Bay of Bengal / Arabian Sea).",
                )
                self._cached_status = status
                self._cached_geojson = {
                    "type": "FeatureCollection",
                    "features": [],
                    "properties": {
                        "status": "CALM",
                        "source": "GDACS (UN OCHA / EC JRC)",
                        "retrieved_at": now_str,
                    },
                }
                return status

            # Select the primary active NIO event (highest alert score or first)
            selected_feature = sorted(
                nio_events,
                key=lambda f: float(f.get("properties", {}).get("alertscore", 0.0)),
                reverse=True,
            )[0]

            props = selected_feature.get("properties", {})
            geom = selected_feature.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0])

            lon = float(coords[0]) if len(coords) >= 2 else 0.0
            lat = float(coords[1]) if len(coords) >= 2 else 0.0

            event_id = str(props.get("eventid", ""))
            episode_id = str(props.get("episodeid", ""))
            storm_name = props.get("eventname") or props.get("name") or f"TC-{event_id}"

            sev_data = props.get("severitydata", {})
            wind_kmh = float(sev_data.get("severity", 0.0)) if isinstance(sev_data, dict) else None
            wind_kts = round(wind_kmh / 1.852, 1) if wind_kmh is not None else None

            affected = [
                c.get("countryname") or c.get("iso3")
                for c in props.get("affectedcountries", [])
                if isinstance(c, dict)
            ]

            # Fetch detailed geometry for tracks and hazard polygons
            detailed_geo = await self.fetch_detailed_geometry(event_id, episode_id)
            geo_features = detailed_geo.get("features", [])

            # Categorize features
            track_features = []
            hazard_features = []

            for gf in geo_features:
                g_type = gf.get("geometry", {}).get("type", "")
                if "Line" in g_type:
                    track_features.append(gf)
                elif "Polygon" in g_type:
                    hazard_features.append(gf)

            cyclone_info = LiveCycloneInfo(
                source="GDACS",
                data_mode=DataMode.LIVE,
                event_id=event_id,
                episode_id=episode_id,
                storm_name=storm_name,
                is_active=True,
                current_lat=lat,
                current_lon=lon,
                wind_speed_kmh=wind_kmh,
                wind_speed_kts=wind_kts,
                intensity_text=sev_data.get("severitytext") if isinstance(sev_data, dict) else None,
                alert_level=props.get("alertlevel"),
                alert_score=float(props.get("alertscore", 0.0)),
                affected_countries=affected,
                issued_at=props.get("fromdate"),
                modified_at=props.get("datemodified"),
                fetched_at=now_str,
                central_pressure_mb=None,  # GDACS does not provide central pressure; strictly null
                heading_deg=None,          # Strictly null, never fabricated
                track=track_features,
                hazard_polygons=hazard_features,
                source_url=props.get("url", {}).get("report") if isinstance(props.get("url"), dict) else None,
                provenance=DataSourceMeta(
                    source="GDACS (UN OCHA / EC JRC)",
                    dataset="Global Disaster Alert & Coordination System - Tropical Cyclone Feed",
                    retrieved_at=now_str,
                    status=DataMode.LIVE,
                    confidence="HIGH",
                    is_forecast=True,
                    attribution="Data provided by GDACS (UN OCHA / EC JRC). Open public disaster data.",
                ),
            )

            status = LiveCycloneStatusResponse(
                source="GDACS",
                data_mode="LIVE",
                live_status="ACTIVE",
                active_cyclone=True,
                cyclone=cyclone_info,
                fetched_at=now_str,
                last_successful_sync=self._last_successful_sync_utc,
                message=f"Active tropical cyclone '{storm_name}' detected in North Indian Ocean basin.",
            )

            # Build normalized GeoJSON FeatureCollection
            all_features = [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "feature_type": "storm_center",
                        "event_id": event_id,
                        "storm_name": storm_name,
                        "wind_speed_kts": wind_kts,
                        "wind_speed_kmh": wind_kmh,
                        "alert_level": props.get("alertlevel"),
                        "source": "GDACS",
                    },
                }
            ]
            all_features.extend(track_features)
            all_features.extend(hazard_features)

            self._cached_status = status
            self._cached_geojson = {
                "type": "FeatureCollection",
                "properties": {
                    "status": "ACTIVE",
                    "storm_name": storm_name,
                    "event_id": event_id,
                    "source": "GDACS (UN OCHA / EC JRC)",
                    "retrieved_at": now_str,
                },
                "features": all_features,
            }

            return status

        except Exception as exc:
            logger.error("Failed to fetch GDACS live cyclone data: %s", exc)
            self._last_fetch_utc = now
            # Graceful degradation: Report UNAVAILABLE, never pretend the basin is calm
            return LiveCycloneStatusResponse(
                source="GDACS",
                data_mode="LIVE",
                live_status="UNAVAILABLE",
                active_cyclone=None,
                cyclone=None,
                fetched_at=now_str,
                last_successful_sync=self._last_successful_sync_utc,
                message=f"GDACS real-time cyclone feed currently unreachable: {str(exc)}",
            )

    async def get_live_track_geojson(self) -> Dict[str, Any]:
        """Return normalized GeoJSON for currently active NIO cyclone."""
        # Ensure fresh or cached status has been evaluated
        status = await self.get_live_cyclone_status()

        if status.live_status == "ACTIVE" and self._cached_geojson:
            return self._cached_geojson

        if status.live_status == "CALM":
            return {
                "type": "FeatureCollection",
                "properties": {
                    "status": "CALM",
                    "source": "GDACS (UN OCHA / EC JRC)",
                    "retrieved_at": status.fetched_at,
                    "message": "No active tropical cyclone in North Indian Ocean.",
                },
                "features": [],
            }

        # UNAVAILABLE state
        return {
            "type": "FeatureCollection",
            "properties": {
                "status": "UNAVAILABLE",
                "source": "GDACS",
                "retrieved_at": status.fetched_at,
                "last_successful_sync": status.last_successful_sync,
                "message": status.message,
            },
            "features": [],
        }
