"""Advisory Prompt Templates Module.

Keeps system instructions and prompt formatting isolated from API client code.
Formats structured district metrics into NDMA/IMD operational early-warning format.
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class DistrictRiskSummaryInput(BaseModel):
    """Structured data payload fed into Gemini for a single district summary."""

    storm_name: str
    step_index: int
    timestamp: str
    district: str
    state: str
    max_risk_score: float
    avg_risk_score: float
    critical_infra_count: int
    impacted_assets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top high-risk infrastructure points in this district",
    )


class MockedDispatch(BaseModel):
    """Simulated emergency notification text for preview panel."""

    sms_preview: str = Field(..., description="Short SMS broadcast under 160 chars")
    email_preview: str = Field(..., description="Detailed operational briefing email")


class DistrictAdvisoryResult(BaseModel):
    """Structured advisory response generated for one district."""

    district: str
    state: str
    risk_level: str
    headline: str
    key_risks: List[str]
    recommended_actions: List[str]
    mocked_dispatch: MockedDispatch


SYSTEM_PROMPT_TEMPLATE = """You are an expert Chief Disaster Response Officer advising Indian state and district disaster management authorities (NDMA/SDMA) on pre-landfall cyclone emergency operations.
You receive structured geospatial risk scores, coastal exposure, and critical infrastructure exposure data for an administrative district.
Your task:
1. Provide an authoritative emergency headline indicating the threat level and critical impact zone.
2. Detail exactly 3 specific key hazards/vulnerabilities based directly on the provided infrastructure (e.g. named hospitals, power substations, highways).
3. Specify exactly 3 actionable anticipatory actions for local authorities (e.g. mandatory evacuation buffers, power grid de-energization, medical shelter reinforcement).
4. Provide a mocked emergency dispatch preview:
   - sms_preview: Under 160 characters, urgent, actionable public alert.
   - email_preview: Formal operational directive to the District Magistrate.

Respond STRICTLY with valid JSON matching this schema:
{
  "district": "string",
  "state": "string",
  "risk_level": "CRITICAL" | "HIGH" | "MODERATE" | "LOW",
  "headline": "string",
  "key_risks": ["hazard 1", "hazard 2", "hazard 3"],
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "mocked_dispatch": {
    "sms_preview": "string (<= 160 chars)",
    "email_preview": "string"
  }
}
Do not include markdown fences or other text. Return raw JSON only.
"""


def format_district_advisory_prompt(data: DistrictRiskSummaryInput) -> str:
    """Format the user prompt for Gemini with structured district risk metrics."""
    assets_summary = []
    for a in data.impacted_assets[:5]:
        assets_summary.append(
            f"- {a.get('name')} ({a.get('infra_type')}): Risk Score {a.get('risk_score', 'N/A')}, "
            f"Elev: {a.get('elevation_m', 'N/A')}m, Dist to Track: {a.get('dist_to_track_km', 'N/A')}km, "
            f"Coast Dist: {a.get('dist_to_coast_km', 'N/A')}km"
        )
    assets_text = "\n".join(assets_summary) if assets_summary else "- General coastal infrastructure assets"

    return f"""Cyclone Name: {data.storm_name}
Timestep: {data.step_index} ({data.timestamp})
Target District: {data.district}, State: {data.state}
Max Computed Risk Score: {data.max_risk_score:.2f} / 1.00
Average Risk Score across facilities: {data.avg_risk_score:.2f}
Total High-Risk Assets in Sector: {data.critical_infra_count}

Top Impacted Infrastructure Assets:
{assets_text}

Generate the early-warning advisory JSON now."""


def build_fallback_advisory(data: DistrictRiskSummaryInput) -> DistrictAdvisoryResult:
    """Deterministic fallback advisory if Gemini API is unavailable or rate-limited."""
    level = "CRITICAL" if data.max_risk_score >= 0.80 else "HIGH" if data.max_risk_score >= 0.60 else "MODERATE"
    
    headline = f"Urgent Pre-Landfall Cyclone Warning for {data.district}"
    if level == "CRITICAL":
        headline = f"CRITICAL: Extreme Surge & Wind Impact Imminent in {data.district}"
    elif level == "HIGH":
        headline = f"HIGH ALERT: Destructive Gale Winds Approaching {data.district}"

    hazards = [
        f"Maximum composite infrastructure risk reached {data.max_risk_score:.2f} near coastal corridor.",
        f"Severe threat to {data.critical_infra_count} evaluated healthcare, power, and road facilities.",
        f"Sub-5m low elevation terrain vulnerable to storm-surge saltwater inundation.",
    ]

    actions = [
        f"Enforce immediate evacuation within 3km of {data.district} coastal belt.",
        "Switch high-voltage coastal power substations to emergency shutdown to avert transformer fire.",
        "Pre-stage emergency diesel generators and clean water supplies at designated base hospitals.",
    ]

    sms = f"[DISASTER ALERT] Cyclone {data.storm_name} approaching {data.district}. Extreme wind/surge risk ({data.max_risk_score:.2f}). Move to cyclone shelter immediately."
    if len(sms) > 160:
        sms = sms[:157] + "..."

    email = (
        f"SUBJECT: OPERATIONAL DIRECTIVE: Landfall Pre-Positioning - {data.district}\n"
        f"TO: District Magistrate & Emergency Response Officer, {data.district}\n\n"
        f"Predictive modeling indicates peak risk score of {data.max_risk_score:.2f} at {data.timestamp}.\n"
        f"Priority 1: Secure {data.critical_infra_count} critical healthcare & power nodes.\n"
        f"Priority 2: Clear arterial evacuation corridors.\n"
        f"Authorized by State Disaster Management Authority."
    )

    return DistrictAdvisoryResult(
        district=data.district,
        state=data.state,
        risk_level=level,
        headline=headline,
        key_risks=hazards,
        recommended_actions=actions,
        mocked_dispatch=MockedDispatch(
            sms_preview=sms,
            email_preview=email,
        ),
    )
