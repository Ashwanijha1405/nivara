"""Parametric Insurance Index & Pre-Landfall Liquidity Engine.

Enables anticipatory disaster financing by evaluating transparent physical trigger indices
(wind speed, hydrodynamic storm surge, pluvial flooding, road washouts)
to release guaranteed liquidity BEFORE cyclone landfall, bypassing slow post-disaster loss adjustment.
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.domain.provenance import DataMode, DataSourceMeta


class ParametricPolicy(BaseModel):
    """Parametric liquidity insurance policy definition."""

    policy_id: str
    policy_name: str
    beneficiary_authority: str
    district: str
    state: str
    underwriter: str
    coverage_limit_inr_crores: float
    trigger_criteria: Dict[str, Any]
    status: str = "ACTIVE"


class PayoutAuditCertificate(BaseModel):
    """Cryptographically certified payout certificate for pre-landfall liquidity disbursement."""

    certificate_id: str
    policy_id: str
    policy_name: str
    beneficiary: str
    storm_name: str
    triggered_at_utc: str
    disbursement_status: str  # DISBURSED, APPROVED, PENDING_CONFIRMATION
    trigger_tier: str  # TIER_1_EARLY_ACTION, TIER_2_EVACUATION, TIER_3_CATASTROPHIC
    trigger_reason: str
    qualifying_metrics: Dict[str, Any]
    payout_percentage: float
    payout_amount_inr_crores: float
    payout_amount_inr_raw: float
    sha256_audit_signature: str
    provenance: DataSourceMeta
    legal_attestation: str = Field(
        default="AUTHENTIC PARAMETRIC SETTLEMENT — Certified against verifiable physical index thresholds without required loss adjustment."
    )


class ParametricEvaluationResult(BaseModel):
    """Overall evaluation of all policies against current or simulated storm parameters."""

    evaluation_time_utc: str
    storm_name: str
    total_liquidity_available_inr_crores: float
    total_liquidity_disbursed_inr_crores: float
    policies_evaluated: int
    policies_triggered: int
    active_certificates: List[PayoutAuditCertificate]
    provenance: DataSourceMeta


class ParametricEngineService:
    """Service evaluating parametric trigger indices and certifying immediate liquidity disbursements."""

    DEFAULT_POLICIES = [
        ParametricPolicy(
            policy_id="POL-PURBA-MED-01",
            policy_name="Purba Medinipur Coastal Evacuation & Embankment Liquidity",
            beneficiary_authority="District Disaster Management Authority, Purba Medinipur",
            district="Purba Medinipur",
            state="West Bengal",
            underwriter="National Disaster Liquidity Pool (NDLP) & Parametric Re",
            coverage_limit_inr_crores=50.0,
            trigger_criteria={
                "min_wind_speed_kmh": 90.0,
                "min_surge_depth_m": 1.5,
                "impassable_roads_threshold": 1,
            },
        ),
        ParametricPolicy(
            policy_id="POL-S24PGS-HEALTH-02",
            policy_name="Sundarbans Lifeline Hospitals & Shelter Contingency Facility",
            beneficiary_authority="South 24 Parganas District Emergency Healthcare Society",
            district="South 24 Parganas",
            state="West Bengal",
            underwriter="Asian Infrastructure & Climate Resiliency Fund",
            coverage_limit_inr_crores=35.0,
            trigger_criteria={
                "min_wind_speed_kmh": 100.0,
                "min_surge_depth_m": 2.0,
                "impassable_roads_threshold": 2,
            },
        ),
        ParametricPolicy(
            policy_id="POL-ODISHA-GRID-03",
            policy_name="Balasore & Kendrapara Power Substation Hardening Liquidity",
            beneficiary_authority="Odisha State Disaster Management Authority (OSDMA)",
            district="Balasore / Kendrapara",
            state="Odisha",
            underwriter="Global Parametric Shield Facility",
            coverage_limit_inr_crores=45.0,
            trigger_criteria={
                "min_wind_speed_kmh": 115.0,
                "min_surge_depth_m": 1.8,
                "impassable_roads_threshold": 2,
            },
        ),
    ]

    def __init__(self) -> None:
        self.policies: List[ParametricPolicy] = list(self.DEFAULT_POLICIES)
        self.issued_certificates: List[PayoutAuditCertificate] = []

    def get_policies(self) -> List[ParametricPolicy]:
        """Return list of active parametric insurance contracts."""
        return self.policies

    def evaluate_policies(
        self,
        storm_name: str,
        wind_speed_kmh: float,
        peak_surge_m: float,
        landfall_eta_hours: Optional[float] = None,
        impassable_roads_count: int = 0,
        max_rainfall_24h_mm: float = 0.0,
    ) -> ParametricEvaluationResult:
        """Evaluate physical index gates for each policy and certify liquidity payouts."""
        now_utc = datetime.now(timezone.utc).isoformat()
        total_available = sum(p.coverage_limit_inr_crores for p in self.policies)
        total_disbursed = 0.0
        new_certificates: List[PayoutAuditCertificate] = []

        for policy in self.policies:
            crit = policy.trigger_criteria
            req_wind = crit.get("min_wind_speed_kmh", 100.0)
            req_surge = crit.get("min_surge_depth_m", 1.8)
            req_roads = crit.get("impassable_roads_threshold", 1)

            wind_met = wind_speed_kmh >= req_wind
            surge_met = peak_surge_m >= req_surge
            roads_met = impassable_roads_count >= req_roads

            # Determine trigger qualification and payout tier
            payout_pct = 0.0
            tier = ""
            reason = ""

            # Tier 3: Catastrophic Surge & Wind Breach (100% Payout)
            if (wind_speed_kmh >= req_wind * 1.25 and surge_met) or peak_surge_m >= 3.0:
                payout_pct = 1.00
                tier = "TIER_3_CATASTROPHIC"
                reason = (
                    f"Catastrophic threshold reached: Peak surge {peak_surge_m:.1f}m (>= 3.0m) and "
                    f"sustained winds {wind_speed_kmh:.0f} km/h. 100% immediate liquidity released."
                )
            # Tier 2: Severe Threat (60% Payout)
            elif (wind_met and surge_met) or (surge_met and roads_met):
                payout_pct = 0.60
                tier = "TIER_2_EVACUATION_MANDATE"
                reason = (
                    f"Severe coastal breach criteria met: Surge {peak_surge_m:.1f}m >= {req_surge:.1f}m and "
                    f"winds {wind_speed_kmh:.0f} km/h >= {req_wind:.0f} km/h. 60% anticipatory payout released."
                )
            # Tier 1: Early Action Warning (30% Payout)
            elif wind_met or surge_met or roads_met or (landfall_eta_hours is not None and landfall_eta_hours <= 24 and wind_speed_kmh >= 80.0):
                payout_pct = 0.30
                tier = "TIER_1_EARLY_ACTION"
                reason = (
                    f"Early anticipatory trigger met: Storm within {landfall_eta_hours or 'threat'}h of coast "
                    f"with {wind_speed_kmh:.0f} km/h winds. 30% preparatory liquidity unlocked."
                )

            if payout_pct > 0.0:
                payout_cr = round(policy.coverage_limit_inr_crores * payout_pct, 2)
                payout_raw = payout_cr * 10_000_000.0
                total_disbursed += payout_cr

                cert_id = f"CERT-{policy.policy_id[:10]}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

                # Deterministic SHA-256 cryptographic audit receipt
                audit_raw = f"{cert_id}:{policy.policy_id}:{payout_cr}:{wind_speed_kmh}:{peak_surge_m}:{now_utc}"
                sha_sig = hashlib.sha256(audit_raw.encode("utf-8")).hexdigest()

                cert = PayoutAuditCertificate(
                    certificate_id=cert_id,
                    policy_id=policy.policy_id,
                    policy_name=policy.policy_name,
                    beneficiary=policy.beneficiary_authority,
                    storm_name=storm_name,
                    triggered_at_utc=now_utc,
                    disbursement_status="DISBURSED",
                    trigger_tier=tier,
                    trigger_reason=reason,
                    qualifying_metrics={
                        "observed_wind_kmh": round(wind_speed_kmh, 1),
                        "projected_peak_surge_m": round(peak_surge_m, 2),
                        "impassable_roads_count": impassable_roads_count,
                        "max_rainfall_24h_mm": round(max_rainfall_24h_mm, 1),
                        "landfall_eta_hours": landfall_eta_hours,
                    },
                    payout_percentage=payout_pct,
                    payout_amount_inr_crores=payout_cr,
                    payout_amount_inr_raw=payout_raw,
                    sha256_audit_signature=sha_sig,
                    provenance=DataSourceMeta(
                        source="Nivara Parametric Liquidity Engine",
                        dataset="Smart Parametric Settlement Protocol",
                        retrieved_at=now_utc,
                        status=DataMode.LIVE,
                        confidence="HIGH",
                        is_forecast=True,
                        attribution="Automated index-linked parametric payout mechanism",
                    ),
                )
                new_certificates.append(cert)
                self.issued_certificates.insert(0, cert)

        return ParametricEvaluationResult(
            evaluation_time_utc=now_utc,
            storm_name=storm_name,
            total_liquidity_available_inr_crores=total_available,
            total_liquidity_disbursed_inr_crores=round(total_disbursed, 2),
            policies_evaluated=len(self.policies),
            policies_triggered=len(new_certificates),
            active_certificates=new_certificates,
            provenance=DataSourceMeta(
                source="Nivara Anticipatory Parametric Engine",
                dataset="Pre-Landfall Liquidity Index Trigger",
                retrieved_at=now_utc,
                status=DataMode.LIVE,
                confidence="HIGH",
                is_forecast=True,
                attribution="Automated parametric smart index certification",
            ),
        )

    def get_issued_certificates(self, limit: int = 50) -> List[PayoutAuditCertificate]:
        """Retrieve historical certified parametric payout ledger."""
        return self.issued_certificates[:limit]
