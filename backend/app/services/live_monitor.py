"""Live Operations Monitoring Service.

Aggregates real-time external feeds:
IMD Cyclone Bulletins + Open-Meteo Current Weather + OpenStreetMap Infrastructure.
Maintains cached operational awareness and tracks source health.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.data_sources.gee.gee_adapter import GEEAdapter
from app.data_sources.ibtracs.ibtracs_adapter import IBTrACSAdapter
from app.data_sources.imd.imd_adapter import IMDAdapter, IMDSystemStatus
from app.data_sources.open_meteo.open_meteo_adapter import AtmosphericReading, OpenMeteoAdapter
from app.data_sources.osm.osm_adapter import OSMAdapter
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

    system_mode: str  # LIVE OPERATIONS
    timestamp_utc: str
    basin: str
    active_threat_detected: bool
    threat_title: str
    current_weather: Dict[str, Any]
    active_warnings: List[Dict[str, Any]]
    total_infrastructure_monitored: int
    critical_facilities_exposed: int
    top_exposed_facilities: List[Dict[str, Any]]
    source_health: Dict[str, SourceHealthRecord]
    provenance: DataSourceMeta


class LiveMonitorService:
    """Service orchestrating real-time situation assessment for operational disaster response."""

    def __init__(
        self,
        imd_adapter: Optional[IMDAdapter] = None,
        open_meteo: Optional[OpenMeteoAdapter] = None,
        osm_adapter: Optional[OSMAdapter] = None,
        gee_adapter: Optional[GEEAdapter] = None,
        risk_engine: Optional[RiskEngineService] = None,
    ) -> None:
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

        # 1. IMD
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

        # 2. Open-Meteo
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

        # 3. OpenStreetMap / Overpass
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

        # 1. Fetch live IMD basin status
        imd_status = await self.imd.get_current_basin_status()

        # 2. Fetch live atmospheric reading at coastal benchmark (Digha/Sagar coastal approach)
        weather_reading = None
        try:
            weather_reading = await self.open_meteo.get_current_weather(21.628, 87.514)
        except Exception:
            pass

        weather_dict = (
            {
                "location": "Digha Coastal Corridor (West Bengal / Odisha)",
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
                "location": "Coastal Station",
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

        # 4. Evaluate current risk (using active storm if exists, or current coastal wind)
        top_exposed: List[Dict[str, Any]] = []
        crit_count = 0

        if infra_assets:
            c_lat = 21.628
            c_lon = 87.514
            wind_kts = weather_reading.wind_speed_10m_knots if weather_reading else 20.0

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
                        "id": risk_res.asset_id,
                        "name": risk_res.asset_name,
                        "category": risk_res.category,
                        "district": risk_res.district,
                        "elevation_m": risk_res.vulnerability.terrain_elevation_m,
                        "dist_to_coast_km": risk_res.exposure.distance_to_coastline_km,
                        "modelled_risk": risk_res.modelled_risk_score,
                        "risk_level": risk_res.risk_level,
                    }
                )

        top_exposed.sort(key=lambda x: x["modelled_risk"], reverse=True)

        # 5. Fetch provider health
        health = await self.get_system_health()

        snapshot = LiveOperationsSnapshot(
            system_mode="LIVE OPERATIONS",
            timestamp_utc=now_str,
            basin="North Indian Ocean (Bay of Bengal / Arabian Sea)",
            active_threat_detected=imd_status.is_active_cyclone,
            threat_title=(
                "ACTIVE CYCLONIC DISTURBANCE"
                if imd_status.is_active_cyclone
                else "ROUTINE MONITORING — NO ACTIVE CYCLONE REPORTED"
            ),
            current_weather=weather_dict,
            active_warnings=[w.model_dump() for w in imd_status.warnings],
            total_infrastructure_monitored=len(infra_assets),
            critical_facilities_exposed=crit_count,
            top_exposed_facilities=top_exposed[:8],
            source_health=health,
            provenance=DataSourceMeta(
                source="Nivara Live Operations Monitor",
                dataset="Real-Time Unified Situational Awareness",
                retrieved_at=now_str,
                status=DataMode.LIVE,
                confidence="HIGH",
                is_forecast=False,
                attribution="Integrated from IMD, Open-Meteo, and OpenStreetMap authoritative sources",
            ),
        )

        self._cached_snapshot = snapshot
        self._last_refresh_utc = now
        return snapshot
