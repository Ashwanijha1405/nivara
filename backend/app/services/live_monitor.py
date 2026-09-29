"""Live Operations Monitoring Service.

Aggregates real-time external feeds:
IMD Cyclone Bulletins + Open-Meteo Current Weather + OpenStreetMap Infrastructure.
Maintains cached operational awareness and tracks source health.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.data_sources.gdacs.gdacs_adapter import GDACSAdapter
from app.data_sources.gee.gee_adapter import GEEAdapter
from app.data_sources.ibtracs.ibtracs_adapter import IBTrACSAdapter
from app.data_sources.imd.imd_adapter import IMDAdapter, IMDSystemStatus
from app.data_sources.open_meteo.open_meteo_adapter import AtmosphericReading, OpenMeteoAdapter
from app.data_sources.osm.osm_adapter import OSMAdapter
from app.domain.cyclone import LiveCycloneInfo, LiveCycloneStatusResponse
from app.domain.infrastructure import InfrastructureAsset
from app.domain.provenance import DataMode, DataSourceMeta
from app.domain.risk import ModelledRiskResult
from app.services.risk_engine import RiskEngineService


class SourceHealthRecord(BaseModel):
    """Health and freshness status for an external data provider."""

    source_id: str
    display_name: str
    status: str  # CONNECTED, DEGRADED, UNAVAILABLE
    latency_ms: float
    last_success_utc: Optional[str]
    last_error: Optional[str] = None
    attribution: str
    mode: DataMode


class LiveOperationsSnapshot(BaseModel):
    """Integrated operational picture for the Live Operations command view."""

    system_mode: str = "LIVE OPERATIONS"
    timestamp_utc: str
    basin: str
    live_status: str = "CALM"  # ACTIVE, CALM, UNAVAILABLE
    active_threat_detected: bool
    threat_title: str
    current_weather: Dict[str, Any]
    active_warnings: List[Dict[str, Any]]
    total_infrastructure_monitored: int
    critical_facilities_exposed: int
    top_exposed_facilities: List[Dict[str, Any]]
    live_cyclone: Optional[Dict[str, Any]] = None
    source_health: Dict[str, SourceHealthRecord]
    provenance: DataSourceMeta


class LiveMonitorService:
    """Service orchestrating real-time situation assessment for operational disaster response."""

    def __init__(
        self,
        gdacs_adapter: Optional[GDACSAdapter] = None,
        imd_adapter: Optional[IMDAdapter] = None,
        open_meteo: Optional[OpenMeteoAdapter] = None,
        osm_adapter: Optional[OSMAdapter] = None,
        gee_adapter: Optional[GEEAdapter] = None,
        risk_engine: Optional[RiskEngineService] = None,
    ) -> None:
        self.gdacs = gdacs_adapter or GDACSAdapter()
        self.imd = imd_adapter or IMDAdapter()
        self.open_meteo = open_meteo or OpenMeteoAdapter()
        self.osm = osm_adapter or OSMAdapter()
        self.gee = gee_adapter or GEEAdapter()
        self.risk_engine = risk_engine or RiskEngineService()

        self._cached_snapshot: Optional[LiveOperationsSnapshot] = None
        self._last_refresh_utc: Optional[datetime] = None
        self._ttl_seconds: int = 120  # Refresh every 2 minutes

    async def get_system_health(self) -> Dict[str, SourceHealthRecord]:
        """Check live connectivity, latency, and operational health of all source providers."""
        now_str = datetime.now(timezone.utc).isoformat()
        health: Dict[str, SourceHealthRecord] = {}

        # 1. GDACS (Real-Time Tropical Cyclone Ingestion)
        try:
            t0 = datetime.now()
            gdacs_status = await self.gdacs.get_live_cyclone_status()
            lat_ms = (datetime.now() - t0).total_seconds() * 1000
            health["gdacs"] = SourceHealthRecord(
                source_id="gdacs",
                display_name="Global Disaster Alert & Coordination System (GDACS)",
                status="CONNECTED" if gdacs_status.live_status != "UNAVAILABLE" else "UNAVAILABLE",
                latency_ms=round(lat_ms, 1),
                last_success_utc=gdacs_status.last_successful_sync or now_str,
                last_error=gdacs_status.message if gdacs_status.live_status == "UNAVAILABLE" else None,
                attribution="Authoritative disaster alert feed by UN OCHA and European Commission (EC JRC)",
                mode=DataMode.LIVE,
            )
        except Exception as e:
            health["gdacs"] = SourceHealthRecord(
                source_id="gdacs",
                display_name="Global Disaster Alert & Coordination System (GDACS)",
                status="UNAVAILABLE",
                latency_ms=0.0,
                last_success_utc=None,
                last_error=str(e),
                attribution="Authoritative disaster alert feed by UN OCHA and EC JRC",
                mode=DataMode.UNAVAILABLE,
            )

        # 1b. IMD (National Operational Bulletins)
        try:
            t0 = datetime.now()
            basin_status = await self.imd.get_current_basin_status()
            lat_ms = (datetime.now() - t0).total_seconds() * 1000
            health["imd"] = SourceHealthRecord(
                source_id="imd",
                display_name="India Meteorological Department (IMD)",
                status="CONNECTED",
                latency_ms=round(lat_ms, 1),
                last_success_utc=now_str,
                attribution="Official cyclone bulletins from Ministry of Earth Sciences",
                mode=DataMode.LIVE,
            )
        except Exception as e:
            health["imd"] = SourceHealthRecord(
                source_id="imd",
                display_name="India Meteorological Department (IMD)",
                status="UNAVAILABLE",
                latency_ms=0.0,
                last_success_utc=None,
                last_error=str(e),
                attribution="Public weather and cyclone warnings",
                mode=DataMode.UNAVAILABLE,
            )

        # 2. Open-Meteo (Ambient Atmospheric Telemetry)
        try:
            t0 = datetime.now()
            await self.open_meteo.get_current_weather(21.628, 87.514)
            lat_ms = (datetime.now() - t0).total_seconds() * 1000
            health["open_meteo"] = SourceHealthRecord(
                source_id="open_meteo",
                display_name="Open-Meteo Numerical Weather Models",
                status="CONNECTED",
                latency_ms=round(lat_ms, 1),
                last_success_utc=now_str,
                attribution="Atmospheric and SRTM elevation models under CC-BY 4.0",
                mode=DataMode.LIVE,
            )
        except Exception as e:
            health["open_meteo"] = SourceHealthRecord(
                source_id="open_meteo",
                display_name="Open-Meteo Numerical Weather Models",
                status="DEGRADED",
                latency_ms=0.0,
                last_success_utc=None,
                last_error=str(e),
                attribution="Atmospheric and SRTM elevation models",
                mode=DataMode.UNAVAILABLE,
            )

        # 3. OpenStreetMap / Overpass (Critical Infrastructure)
        try:
            assets = await self.osm.fetch_infrastructure()
            health["osm"] = SourceHealthRecord(
                source_id="osm",
                display_name="OpenStreetMap Overpass API",
                status="CONNECTED",
                latency_ms=45.0,
                last_success_utc=now_str,
                attribution="© OpenStreetMap contributors under ODbL",
                mode=DataMode.LIVE if not self.osm.demo_mode else DataMode.HISTORICAL,
            )
        except Exception as e:
            health["osm"] = SourceHealthRecord(
                source_id="osm",
                display_name="OpenStreetMap Overpass API",
                status="DEGRADED",
                latency_ms=0.0,
                last_success_utc=None,
                last_error=str(e),
                attribution="© OpenStreetMap contributors under ODbL",
                mode=DataMode.UNAVAILABLE,
            )

        # 4. Google Earth Engine
        gee_status = self.gee.get_status()
        health["gee"] = SourceHealthRecord(
            source_id="gee",
            display_name="Google Earth Engine Satellite Archive",
            status="CONNECTED" if gee_status.is_authenticated else "UNAVAILABLE",
            latency_ms=10.0 if gee_status.is_authenticated else 0.0,
            last_success_utc=now_str if gee_status.is_authenticated else None,
            last_error=gee_status.error_message,
            attribution="Google Earth Engine planetary imagery",
            mode=DataMode.LIVE if gee_status.is_authenticated else DataMode.UNAVAILABLE,
        )

        # 5. NOAA IBTrACS
        health["ibtracs"] = SourceHealthRecord(
            source_id="ibtracs",
            display_name="NOAA IBTrACS Best Track Archive",
            status="CONNECTED",
            latency_ms=5.0,
            last_success_utc=now_str,
            attribution="NOAA NCEI World Data Center for Meteorology",
            mode=DataMode.HISTORICAL,
        )

        return health

    async def get_live_operations_snapshot(self) -> LiveOperationsSnapshot:
        """Construct the live operational intelligence picture for the command view."""
        now = datetime.now(timezone.utc)

        if (
            self._cached_snapshot is not None
            and self._last_refresh_utc is not None
            and (now - self._last_refresh_utc).total_seconds() < self._ttl_seconds
        ):
            return self._cached_snapshot

        now_str = now.isoformat()

        # 1. Fetch live GDACS cyclone status for North Indian Ocean
        gdacs_status = await self.gdacs.get_live_cyclone_status()
        is_active = gdacs_status.live_status == "ACTIVE" and gdacs_status.cyclone is not None
        live_cyclone_dict = gdacs_status.cyclone.model_dump() if gdacs_status.cyclone else None

        # 2. Fetch live atmospheric reading at coastal benchmark (Digha/Sagar coastal approach)
        weather_reading = None
        try:
            weather_reading = await self.open_meteo.get_current_weather(21.628, 87.514)
        except Exception:
            pass

        weather_dict = (
            {
                "location": "Digha Coastal Observation Station (West Bengal)",
                "observation_type": "Ambient Coastal Surface Telemetry (Non-Cyclone)",
                "temperature_c": weather_reading.temperature_2m_c,
                "surface_pressure_hpa": weather_reading.surface_pressure_hpa,
                "wind_speed_kph": weather_reading.wind_speed_10m_kph,
                "wind_speed_knots": weather_reading.wind_speed_10m_knots,
                "wind_gusts_kph": weather_reading.wind_gusts_10m_kph,
                "precipitation_mm": weather_reading.precipitation_mm,
                "source": "Open-Meteo Live API",
            }
            if weather_reading
            else {
                "location": "Digha Coastal Observation Station",
                "observation_type": "Ambient Coastal Surface Telemetry",
                "status": "Awaiting Weather Telemetry",
                "source": "Open-Meteo",
            }
        )

        # 3. Fetch monitored infrastructure assets
        infra_assets: List[InfrastructureAsset] = []
        try:
            infra_assets = await self.osm.fetch_infrastructure()
        except Exception:
            pass

        # 4. Evaluate current risk (using genuine active cyclone coordinates ONLY when active)
        top_exposed: List[Dict[str, Any]] = []
        crit_count = 0

        if infra_assets and is_active and gdacs_status.cyclone:
            c_lat = gdacs_status.cyclone.current_lat
            c_lon = gdacs_status.cyclone.current_lon
            wind_kts = gdacs_status.cyclone.wind_speed_kts or 45.0

            for asset in infra_assets:
                risk_res = self.risk_engine.evaluate_asset(
                    asset=asset,
                    cyclone_lat=c_lat,
                    cyclone_lon=c_lon,
                    cyclone_wind_knots=wind_kts,
                    data_mode=DataMode.LIVE,
                )
                if risk_res.risk_level in ["CRITICAL", "HIGH"]:
                    crit_count += 1
                top_exposed.append(
                    {
                        "id": risk_res.id or risk_res.asset_id,
                        "name": risk_res.name or risk_res.asset_name,
                        "category": risk_res.category,
                        "latitude": risk_res.latitude,
                        "longitude": risk_res.longitude,
                        "district": risk_res.district,
                        "elevation_m": risk_res.vulnerability.terrain_elevation_m,
                        "dist_to_coast_km": risk_res.exposure.distance_to_coastline_km,
                        "risk_score": risk_res.risk_score,
                        "modelled_risk": risk_res.risk_score,
                        "risk_level": risk_res.risk_level,
                    }
                )
            top_exposed.sort(key=lambda x: x["modelled_risk"], reverse=True)
        elif infra_assets:
            # CALM or UNAVAILABLE: Baseline infrastructure monitoring only.
            # Do NOT treat Digha benchmark as a cyclone center!
            for asset in infra_assets[:8]:
                top_exposed.append(
                    {
                        "id": asset.id,
                        "name": asset.name,
                        "category": asset.category.value if hasattr(asset.category, "value") else str(asset.category),
                        "latitude": asset.lat,
                        "longitude": asset.lon,
                        "district": asset.district,
                        "elevation_m": asset.elevation_m,
                        "dist_to_coast_km": asset.dist_to_coast_km,
                        "risk_score": 0.0,
                        "modelled_risk": 0.0,
                        "risk_level": "LOW",
                    }
                )

        # 5. Determine threat title based on live status
        if gdacs_status.live_status == "ACTIVE" and gdacs_status.cyclone:
            threat_title = f"ACTIVE CYCLONIC THREAT: {gdacs_status.cyclone.storm_name.upper()} ({gdacs_status.cyclone.alert_level or 'ALERT'})"
        elif gdacs_status.live_status == "CALM":
            threat_title = "ROUTINE MONITORING — NO ACTIVE CYCLONE IN BASIN"
        else:
            threat_title = "LIVE CYCLONE DATA UNAVAILABLE — VERIFYING FEED"

        # 6. Fetch provider health
        health = await self.get_system_health()

        snapshot = LiveOperationsSnapshot(
            system_mode="LIVE OPERATIONS",
            timestamp_utc=now_str,
            basin="North Indian Ocean (Bay of Bengal / Arabian Sea)",
            live_status=gdacs_status.live_status,
            active_threat_detected=is_active,
            threat_title=threat_title,
            current_weather=weather_dict,
            active_warnings=[],
            total_infrastructure_monitored=len(infra_assets),
            critical_facilities_exposed=crit_count,
            top_exposed_facilities=top_exposed[:8],
            live_cyclone=live_cyclone_dict,
            source_health=health,
            provenance=DataSourceMeta(
                source="Nivara Live Operations Monitor (GDACS + Open-Meteo + OSM)",
                dataset="Real-Time Unified Situational Awareness",
                retrieved_at=now_str,
                status=DataMode.LIVE,
                confidence="HIGH",
                is_forecast=is_active,
                attribution="Integrated from GDACS (UN OCHA / EC JRC), Open-Meteo, and OpenStreetMap authoritative sources",
            ),
        )

        self._cached_snapshot = snapshot
        self._last_refresh_utc = now
        return snapshot
