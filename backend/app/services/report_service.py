"""Operational Report Generation Service.

Builds structured, exportable disaster response documents:
1. Operational Situation Report (SitRep)
2. Critical Infrastructure Exposure Report
3. District Vulnerability Briefing
4. Scenario Simulation Assessment Report
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.domain.provenance import DataMode, DataSourceMeta


class OperationalReport(BaseModel):
    """Structured executive report for disaster management authorities."""

    report_id: str
    report_title: str
    report_type: str  # SITUATION_REPORT, INFRASTRUCTURE_RISK, DISTRICT_BRIEFING, SCENARIO_SIMULATION
    generated_at_utc: str
    issuing_authority: str
    classification: str  # OFFICIAL / SENSITIVE
    executive_summary: str
    data_sources_provenance: List[DataSourceMeta]
    observed_metrics: Dict[str, Any]
    forecast_metrics: Dict[str, Any]
    modelled_risk_findings: Dict[str, Any]
    limitations_and_uncertainty: str
    recommended_immediate_actions: List[str]
    markdown_content: str


class ReportService:
    """Service generating standardized disaster management reports."""

    def generate_situation_report(
        self,
        snapshot: Dict[str, Any],
        ai_advisory: Optional[Dict[str, Any]] = None,
    ) -> OperationalReport:
        """Generate official Situation Report (SitRep) from current operational snapshot."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        report_id = f"SITREP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"

        weather = snapshot.get("current_weather", {})
        warnings = snapshot.get("active_warnings", [])
        exposed = snapshot.get("top_exposed_facilities", [])

        md_lines = [
            f"# NIVARA DISASTER INTELLIGENCE PLATFORM",
            f"## OPERATIONAL SITUATION REPORT (SITREP) — {report_id}",
            f"**Generated:** {now_str} | **Classification:** FOR OFFICIAL DISASTER PREPAREDNESS USE",
            "",
            "---",
            "### 1. EXECUTIVE SITUATIONAL SUMMARY",
            f"- **Basin Status:** {snapshot.get('threat_title', 'Routine Monitoring')}",
            f"- **Coastal Benchmark Weather:** {weather.get('location', 'Bay of Bengal Coast')}",
            f"  - Surface Wind: {weather.get('wind_speed_kph', 0)} km/h ({weather.get('wind_speed_knots', 0)} kts)",
            f"  - Surface Pressure: {weather.get('surface_pressure_hpa', 1010)} hPa",
            f"  - Active Precipitation: {weather.get('precipitation_mm', 0)} mm",
            f"- **Total Infrastructure Lifelines Monitored:** {snapshot.get('total_infrastructure_monitored', 0)} facilities",
            f"- **Facilities in High/Critical Risk Tiers:** {snapshot.get('critical_facilities_exposed', 0)} facilities",
            "",
            "### 2. OFFICIAL IMD WARNING STATUS",
        ]

        if warnings:
            for w in warnings:
                md_lines.append(f"- **{w.get('title', 'Warning')}:** {w.get('wind_warning', 'Standard conditions')}")
        else:
            md_lines.append("- No active tropical cyclone warning flags active from IMD.")

        md_lines.extend([
            "",
            "### 3. EXPOSED CRITICAL INFRASTRUCTURE (TOP TIER)",
            "| Facility Name | Category | District | Elevation | Shore Dist | Modelled Risk |",
            "|---|---|---|---|---|---|",
        ])

        for item in exposed[:6]:
            md_lines.append(
                f"| {item.get('name')} | {item.get('category')} | {item.get('district')} | "
                f"{item.get('elevation_m')}m | {item.get('dist_to_coast_km')}km | {item.get('modelled_risk')} ({item.get('risk_level')}) |"
            )

        md_lines.extend([
            "",
            "### 4. DATA SOURCES & SCIENTIFIC LIMITATIONS",
            "- **Meteorology:** Real-time numerical weather telemetry via Open-Meteo ECMWF/GFS surface model.",
            "- **Cyclone Trajectory:** Official operational bulletins from India Meteorological Department (IMD).",
            "- **Infrastructure:** Real-time spatial query from OpenStreetMap Overpass API.",
            "- **Digital Elevation:** Authentic NASA/USGS SRTM 90m digital elevation model.",
            "- **Limitation Notice:** Modelled Risk indices are deterministic syntheses indicating relative physical vulnerability. They do not constitute deterministic structural collapse guarantees.",
            "",
            "---",
            "*Report certified by Nivara Operational Automated Reporting Engine.*",
        ])

        markdown_doc = "\n".join(md_lines)

        return OperationalReport(
            report_id=report_id,
            report_title=f"Operational Cyclone Preparedness Situation Report ({report_id})",
            report_type="SITUATION_REPORT",
            generated_at_utc=now_str,
            issuing_authority="Nivara Disaster Intelligence System",
            classification="OFFICIAL USE",
            executive_summary=(
                f"Operational SitRep as of {now_str}. "
                f"Total {snapshot.get('total_infrastructure_monitored', 0)} lifelines monitored. "
                f"Active Threat: {snapshot.get('threat_title', 'None')}."
            ),
            data_sources_provenance=[
                DataSourceMeta(
                    source="IMD / Open-Meteo / OpenStreetMap",
                    dataset="Operational SitRep Data Integration",
                    status=DataMode.LIVE,
                    confidence="HIGH",
                    is_forecast=False,
                )
            ],
            observed_metrics=weather,
            forecast_metrics={},
            modelled_risk_findings={
                "total_monitored": snapshot.get("total_infrastructure_monitored", 0),
                "critical_exposed": snapshot.get("critical_facilities_exposed", 0),
            },
            limitations_and_uncertainty=(
                "Risk indices represent simulated vulnerability and spatial exposure. "
                "Local building structural integrity variations require ground verification."
            ),
            recommended_immediate_actions=[
                "Maintain continuous telemetry polling across coastal automated weather stations.",
                "Review auxiliary diesel fuel supply for secondary general hospitals in low-lying sectors.",
                "Verify operational readiness of dedicated cyclone shelters in Purba Medinipur and South 24 Parganas.",
            ],
            markdown_content=markdown_doc,
        )
