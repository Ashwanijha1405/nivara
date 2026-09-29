"""GDACS (Global Disaster Alert and Coordination System) Adapter.

Authoritative free real-time tropical cyclone data source operated by the
United Nations OCHA and European Commission Joint Research Centre (EC JRC).
Provides live active cyclone detection, tracks, and wind hazard buffer polygons.

Design Principles:
1. No API keys, no registration, public UN/EC feed.
2. Defensible North Indian Ocean geographic filtering (0°N-32°N, 50°E-100°E).
3. Anti-fabrication guarantees:
   - central_pressure_mb is strictly null if not provided by GDACS. Never estimated or derived.
   - heading_deg is null unless directly available or safely derived from consecutive track coordinates.
   - Never replace actual GDACS geometry with synthetic trajectories.
   - Never use arbitrary coastal benchmark points (like Digha) as cyclone centers.
4. Tri-state status model: ACTIVE, CALM, UNAVAILABLE.
   - Network failure or timeout yields UNAVAILABLE, never falsely claiming CALM.
5. In-memory caching with configurable TTL (60-120s) and timeout (2-5s).
"""

from datetime import datetime, timezone
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.domain.cyclone import LiveCycloneInfo, LiveCycloneStatusResponse
from app.domain.provenance import DataMode, DataSourceMeta

logger = logging.getLogger(__name__)

# ==============================================================================
# NORTH INDIAN OCEAN (NIO) BASIN DEFINITION
# ==============================================================================
# The North Indian Ocean operational tropical cyclone basin, as defined by
# WMO and RSMC New Delhi (IMD), encompasses the Bay of Bengal, the Arabian Sea,
# the Andaman Sea, and adjacent northern Indian Ocean maritime approaches.
#
# Geographic Bounding Box:
#   Latitude:  0.0°N (Equator) to 32.0°N (Northern landfall corridors / Bay head)
#   Longitude: 50.0°E (Arabian Peninsula / Gulf of Aden) to 100.0°E (Malay Peninsula)
#
# South of 0°N is the South Indian Ocean basin (RSMC La Réunion).
# East of 100°E is the Western North Pacific / South China Sea basin (RSMC Tokyo / JTWC).
# ==============================================================================
NIO_MIN_LAT = 0.0
NIO_MAX_LAT = 32.0
NIO_MIN_LON = 50.0
NIO_MAX_LON = 100.0

# Authoritative ISO3 country codes bordering or within the North Indian Ocean basin
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


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[float]:
    """Calculate forward geodesic azimuth / bearing from (lat1, lon1) to (lat2, lon2) in degrees [0, 360).

    Returns None if coordinates are identical or invalid.
    """
    if lat1 == lat2 and lon1 == lon2:
        return None
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.degrees(math.atan2(y, x))
    return round((bearing + 360.0) % 360.0, 1)


class GDACSAdapter:
    """Adapter for querying operational cyclone information from GDACS."""

    def __init__(
        self,
        base_url: str = "https://www.gdacs.org/gdacsapi/api",
        timeout_seconds: float = 4.0,
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

        Uses defensible two-tier verification:
        1. Coordinate bounds (0°N - 32°N, 50°E - 100°E):
           If coordinates are provided, the storm center MUST fall within this bounding box.
           Any storm outside (e.g. Mexico, Caribbean, Western Pacific, Southern Indian Ocean)
           is strictly rejected.
        2. Affected country fallback:
           Only if coordinates are absent or (0.0, 0.0), verify against authoritative
           coastal member states (India, Bangladesh, Myanmar, Sri Lanka, Oman, etc.).
        """
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates")
        props = feature.get("properties") or {}

        # 1. Primary spatial verification if coordinates exist
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                lon, lat = float(coords[0]), float(coords[1])
                # Check for non-zero coordinates
                if not (abs(lon) < 1e-4 and abs(lat) < 1e-4):
                    return (
                        NIO_MIN_LAT <= lat <= NIO_MAX_LAT
                        and NIO_MIN_LON <= lon <= NIO_MAX_LON
                    )
            except (ValueError, TypeError):
                pass

        # 2. Check bounding box if provided
        bbox = feature.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            try:
                min_lon, min_lat, max_lon, max_lat = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                # Intersect with NIO domain
                if not (max_lon < NIO_MIN_LON or min_lon > NIO_MAX_LON or max_lat < NIO_MIN_LAT or min_lat > NIO_MAX_LAT):
                    return True
            except (ValueError, TypeError):
                pass

        # 3. Fallback verification using affected country ISO3 codes
        country_iso3 = props.get("iso3")
        if country_iso3 and country_iso3.upper() in NIO_AFFECTED_ISO3:
            return True

        for c in props.get("affectedcountries", []):
            if isinstance(c, dict) and c.get("iso3", "").upper() in NIO_AFFECTED_ISO3:
                return True

        return False

    async def fetch_active_tropical_cyclones(self) -> List[Dict[str, Any]]:
        """Query GDACS active TC search endpoint with strict timeout and error handling."""
        url = f"{self.base_url}/events/geteventlist/SEARCH?eventtype=TC"
        headers = {
            "User-Agent": "Nivara-Disaster-Intelligence/1.0 (Public Research; Disaster Management)",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.get(url, headers=headers)
                if res.status_code != 200:
                    raise RuntimeError(f"GDACS API returned HTTP {res.status_code}: {res.text[:120]}")
                data = res.json()
                features = data.get("features", [])
                if not isinstance(features, list):
                    logger.warning("GDACS search response features is not a list")
                    return []
                return features
        except httpx.TimeoutException as exc:
            logger.warning("GDACS active TC query timed out after %s seconds", self.timeout_seconds)
            raise TimeoutError(f"GDACS API request timed out after {self.timeout_seconds}s") from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("GDACS active TC query failed: %s", exc)
            raise RuntimeError(f"GDACS API communication failure: {str(exc)}") from exc

    async def fetch_detailed_geometry(self, event_id: Any, episode_id: Any) -> Dict[str, Any]:
        """Fetch detailed event GeoJSON including track lines, forecast segments, and wind buffer polygons."""
        url = f"{self.base_url}/polygons/getgeometry?eventtype=TC&eventid={event_id}&episodeid={episode_id}"
        headers = {
            "User-Agent": "Nivara-Disaster-Intelligence/1.0 (Public Research; Disaster Management)",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.get(url, headers=headers)
                if res.status_code != 200:
                    logger.warning("Failed to fetch GDACS geometry for event %s: HTTP %s", event_id, res.status_code)
                    return {"type": "FeatureCollection", "features": []}
                return res.json()
        except Exception as exc:
            logger.warning("Failed to fetch detailed geometry for TC event %s: %s", event_id, exc)
            return {"type": "FeatureCollection", "features": []}

    async def get_live_cyclone_status(self) -> LiveCycloneStatusResponse:
        """Fetch normalized live cyclone status from GDACS with in-memory caching.

        Returns one of three states:
        - ACTIVE: Verified active cyclone exists in North Indian Ocean basin.
        - CALM: Verified that GDACS responded successfully and no active NIO cyclone exists.
        - UNAVAILABLE: GDACS could not be reached or returned an error; active_cyclone is null.
        """
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        # 1. Return cached response if within TTL
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

            # 2. Filter for current active TC events
            current_events = [
                f for f in features
                if str(f.get("properties", {}).get("iscurrent", "")).lower() == "true"
                and f.get("properties", {}).get("eventtype") == "TC"
            ]

            # 3. Apply North Indian Ocean geographic filter (Bay of Bengal / Arabian Sea)
            nio_events = [f for f in current_events if self.is_north_indian_ocean(f)]

            # 4. CALM STATE: No active NIO cyclone detected
            if not nio_events:
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
                    "properties": {
                        "status": "CALM",
                        "live_status": "CALM",
                        "source": "GDACS",
                        "data_mode": "LIVE",
                        "retrieved_at": now_str,
                        "last_successful_sync": self._last_successful_sync_utc,
                        "message": "No active tropical cyclone in North Indian Ocean basin (Bay of Bengal / Arabian Sea).",
                    },
                    "features": [],
                }
                return status

            # 5. ACTIVE STATE: Select primary active NIO event (highest alert score)
            selected_feature = sorted(
                nio_events,
                key=lambda f: float(f.get("properties", {}).get("alertscore", 0.0)),
                reverse=True,
            )[0]

            props = selected_feature.get("properties") or {}
            geom = selected_feature.get("geometry") or {}
            coords = geom.get("coordinates", [0.0, 0.0])

            lon = float(coords[0]) if len(coords) >= 2 else 0.0
            lat = float(coords[1]) if len(coords) >= 2 else 0.0

            event_id = str(props.get("eventid", ""))
            episode_id = str(props.get("episodeid", ""))
            storm_name = props.get("eventname") or props.get("name") or f"TC-{event_id}"

            sev_data = props.get("severitydata") or {}
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

            # Safely classify features into observed, forecast, uncertainty cones, and wind buffers
            track_features = []
            hazard_features = []
            observed_coords: List[Tuple[float, float]] = []

            for gf in geo_features:
                g_type = gf.get("geometry", {}).get("type", "")
                gf_props = gf.get("properties") or {}

                if "Line" in g_type:
                    # Distinguish observed track from forecast/projected track
                    is_forecast = (
                        gf_props.get("forecast") is True
                        or "forecast" in str(gf_props.get("Class", "")).lower()
                        or "fcst" in str(gf_props.get("polygonlabel", "")).lower()
                    )
                    gf_props["feature_type"] = "forecast_track" if is_forecast else "observed_track"
                    gf["properties"] = gf_props
                    track_features.append(gf)

                    if not is_forecast:
                        line_coords = gf.get("geometry", {}).get("coordinates", [])
                        for pt in line_coords:
                            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                                observed_coords.append((float(pt[1]), float(pt[0])))  # (lat, lon)

                elif "Polygon" in g_type:
                    p_class = str(gf_props.get("Class", ""))
                    p_label = str(gf_props.get("polygonlabel", "")).lower()
                    p_ftype = str(gf_props.get("featuretype", ""))

                    if p_class == "Poly_Cones" or "cone" in p_label:
                        gf_props["feature_type"] = "uncertainty_cone"
                    elif p_ftype in ["WindRadii", "PointRadii"] or "poly_" in p_class.lower() or "km/h" in p_label:
                        gf_props["feature_type"] = "wind_hazard_polygon"
                    else:
                        gf_props["feature_type"] = "hazard_polygon"
                    gf["properties"] = gf_props
                    hazard_features.append(gf)

            # Safely derive heading from consecutive observed coordinates if available
            derived_heading = None
            if len(observed_coords) >= 2:
                lat1, lon1 = observed_coords[-2]
                lat2, lon2 = observed_coords[-1]
                derived_heading = calculate_bearing(lat1, lon1, lat2, lon2)

            # Check for central pressure in GDACS (strictly null if not provided; never fabricated)
            pressure_raw = props.get("pressure") or props.get("centralpressure")
            central_pressure = float(pressure_raw) if pressure_raw is not None else None

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
                central_pressure_mb=central_pressure,  # Strictly nullable, never fabricated
                heading_deg=derived_heading,           # Safely derived from consecutive track points or null
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

            # Build normalized GeoJSON FeatureCollection with [lon, lat] coordinates
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
                        "data_mode": "LIVE",
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
                    "live_status": "ACTIVE",
                    "storm_name": storm_name,
                    "event_id": event_id,
                    "source": "GDACS (UN OCHA / EC JRC)",
                    "data_mode": "LIVE",
                    "retrieved_at": now_str,
                    "last_successful_sync": self._last_successful_sync_utc,
                },
                "features": all_features,
            }

            return status

        except Exception as exc:
            logger.error("Failed to fetch GDACS live cyclone data: %s", exc)
            self._last_fetch_utc = now
            # UNAVAILABLE STATE: Never convert a network/parse failure into CALM
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
        """Return normalized GeoJSON for currently active NIO cyclone.

        Returns:
        - When ACTIVE: GeoJSON FeatureCollection with storm_center, observed_track, forecast_track, uncertainty_cone, and wind_hazard_polygon features.
        - When CALM: Valid empty GeoJSON FeatureCollection with status='CALM'.
        - When UNAVAILABLE: Valid GeoJSON FeatureCollection with status='UNAVAILABLE' indicating feed unreachable.
        """
        status = await self.get_live_cyclone_status()

        if status.live_status == "ACTIVE" and self._cached_geojson:
            return self._cached_geojson

        if status.live_status == "CALM":
            return {
                "type": "FeatureCollection",
                "properties": {
                    "status": "CALM",
                    "live_status": "CALM",
                    "source": "GDACS",
                    "data_mode": "LIVE",
                    "retrieved_at": status.fetched_at,
                    "last_successful_sync": status.last_successful_sync,
                    "message": "No active tropical cyclone in North Indian Ocean basin (Bay of Bengal / Arabian Sea).",
                },
                "features": [],
            }

        # UNAVAILABLE state
        return {
            "type": "FeatureCollection",
            "properties": {
                "status": "UNAVAILABLE",
                "live_status": "UNAVAILABLE",
                "source": "GDACS",
                "data_mode": "LIVE",
                "retrieved_at": status.fetched_at,
                "last_successful_sync": status.last_successful_sync,
                "message": status.message,
            },
            "features": [],
        }
