"""Unit and integration tests for Phase 5, Phase 6, and Phase 7.

Phase 5: Google Earth Engine (GEE) & Sentinel-1 SAR Integration
- GEE connectivity status and offline graceful degradation
- Dynamic World 10m land cover classification & physical surface multipliers
- Sentinel-1 SAR C-band microwave flood backscatter detection (< -3.0 dB drop)
- API endpoints: /api/satellite/gee/status, /api/satellite/gee/layers, /api/satellite/sar-flood, /api/satellite/land-cover

Phase 6: Automated Early-Warning Advisory Dispatch Engine
- OASIS Common Alerting Protocol (CAP v1.2 XML) generation
- Authoritative recipient directory (District Magistrates, SEOC)
- Multi-channel dispatch execution (CAP, Webhook, SMS, SitRep)
- Cryptographic SHA-256 dispatch audit log
- API endpoints: /api/advisory/recipients, /api/advisory/cap.xml, /api/advisory/dispatch, /api/advisory/dispatch/log

Phase 7: Gemini 3.7 Flash Multimodal Visual Reasoning & Parametric Liquidity Triggers
- Gemini 3.7 Flash multimodal visual reasoning over map/satellite canvas
- Parametric insurance index gates (wind speed, surge inundation, road impassability)
- Guaranteed pre-landfall liquidity payout disbursement in INR Crores
- Cryptographic SHA-256 payout audit certificates
- API endpoints: /api/advisory/multimodal-analyze, /api/parametric/policies, /api/parametric/evaluate, /api/parametric/certificates
"""

import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient

from app.data_sources.gee.gee_adapter import GEEAdapter
from app.main import app
from app.services.advisory_engine import AdvisoryEngineService
from app.services.dispatch_engine import DispatchEngineService
from app.services.parametric_engine import ParametricEngineService

client = TestClient(app)


# ==============================================================================
# PHASE 5 TESTS: GEE SATELLITE FEEDS & AUTHENTIC ENVIRONMENTAL LAYERS
# ==============================================================================

def test_gee_adapter_status_and_layers():
    """Verify GEE adapter reports operational status and authentic datasets."""
    adapter = GEEAdapter()
    status = adapter.get_status()

    assert status.datasets_available is not None
    assert len(status.datasets_available) >= 3
    assert any("SRTM" in ds for ds in status.datasets_available)
    assert any("DYNAMICWORLD" in ds for ds in status.datasets_available)
    assert any("S1_GRD" in ds or "Sentinel-1" in ds for ds in status.datasets_available)

    layers = adapter.get_tile_layers()
    assert len(layers) == 3
    layer_ids = [l["layer_id"] for l in layers]
    assert "sentinel1_sar_water" in layer_ids
    assert "dynamic_world_landcover" in layer_ids
    assert "srtm_elevation" in layer_ids


def test_dynamic_world_land_cover_multipliers():
    """Verify authentic surface roughness / friction multipliers for Bengal delta geography."""
    adapter = GEEAdapter()

    # Sundarbans mangrove estuary (21.8N, 88.6E) -> flooded_vegetation (friction buffer 0.55)
    mangrove = adapter.get_land_cover_at_point(lat=21.8, lon=88.6)
    assert mangrove.label == "flooded_vegetation"
    assert mangrove.surface_roughness_multiplier == 0.55

    # Digha coastal sand / beach (21.62N, 87.51E) -> bare sand (0.95)
    coastal_sand = adapter.get_land_cover_at_point(lat=21.62, lon=87.51)
    assert coastal_sand.label == "bare"
    assert coastal_sand.surface_roughness_multiplier == 0.95

    # Haldia industrial port (22.05N, 88.08E) -> built (impervious 1.00)
    urban_port = adapter.get_land_cover_at_point(lat=22.05, lon=88.08)
    assert urban_port.label == "built"
    assert urban_port.surface_roughness_multiplier == 1.00


def test_sentinel1_sar_flood_water_detection():
    """Verify Sentinel-1 SAR C-band water anomaly polygon extraction."""
    adapter = GEEAdapter()
    sar_data = adapter.get_sar_flood_raster()

    assert sar_data.total_inundated_area_sqkm > 50.0
    assert len(sar_data.features) >= 3
    for f in sar_data.features:
        assert f["type"] == "Feature"
        assert f["geometry"]["type"] == "Polygon"
        assert f["properties"]["polarization"] == "VV"
        assert f["properties"]["backscatter_drop_db"] < -3.0


def test_satellite_api_endpoints():
    """Verify GET endpoints for satellite GEE status, layers, SAR flooding, and point land cover."""
    res_status = client.get("/api/satellite/gee/status")
    assert res_status.status_code == 200
    assert "datasets_available" in res_status.json()

    res_layers = client.get("/api/satellite/gee/layers")
    assert res_layers.status_code == 200
    assert len(res_layers.json()) >= 3

    res_sar = client.get("/api/satellite/sar-flood")
    assert res_sar.status_code == 200
    assert res_sar.json()["total_inundated_area_sqkm"] > 0

    res_lc = client.get("/api/satellite/land-cover?lat=21.8&lon=88.6")
    assert res_lc.status_code == 200
    assert res_lc.json()["label"] == "flooded_vegetation"
    assert res_lc.json()["surface_roughness_multiplier"] == 0.55


# ==============================================================================
# PHASE 6 TESTS: AUTOMATED EARLY-WARNING ADVISORY DISPATCH ENGINE
# ==============================================================================

def test_oasis_cap_xml_generation():
    """Verify generated CAP XML strictly conforms to OASIS CAP v1.2 standard schema."""
    engine = DispatchEngineService()
    xml_str = engine.generate_cap_xml(
        storm_name="AMPHAN_EXERCISE",
        alert_level="Red",
        wind_speed_kmh=185.0,
        heading_deg=35.0,
        peak_surge_m=4.5,
        affected_districts=["Purba Medinipur", "South 24 Parganas"],
    )

    # Must be valid XML
    root = ET.fromstring(xml_str)
    assert "alert" in root.tag
    assert root.find("{urn:oasis:names:tc:emergency:cap:1.2}status").text == "Actual"
    assert root.find("{urn:oasis:names:tc:emergency:cap:1.2}msgType").text == "Alert"

    info = root.find("{urn:oasis:names:tc:emergency:cap:1.2}info")
    assert info is not None
    assert info.find("{urn:oasis:names:tc:emergency:cap:1.2}urgency").text == "Immediate"
    assert info.find("{urn:oasis:names:tc:emergency:cap:1.2}severity").text == "Extreme"
    assert "AMPHAN_EXERCISE" in info.find("{urn:oasis:names:tc:emergency:cap:1.2}headline").text


def test_dispatch_execution_and_cryptographic_receipt():
    """Verify multi-channel dispatch execution and SHA-256 cryptographic audit logging."""
    engine = DispatchEngineService()
    record = engine.dispatch_advisories(
        storm_name="TEST_CYCLONE",
        alert_level="Orange",
        wind_speed_kmh=115.0,
        heading_deg=40.0,
        peak_surge_m=2.8,
        affected_districts=["Purba Medinipur", "Balasore"],
        channels=["CAP_XML", "WEBHOOK", "SMS", "SITREP"],
    )

    assert record.delivery_status == "DELIVERED"
    assert record.recipients_count >= 4
    assert len(record.verification_hash_sha256) == 64  # valid SHA-256 hex string
    assert record.dispatch_id.startswith("DISPATCH-")

    # Verify presence in dispatch audit log
    log = engine.get_dispatch_log()
    assert len(log) >= 1
    assert log[0].dispatch_id == record.dispatch_id


def test_advisory_dispatch_api_endpoints():
    """Verify HTTP API endpoints for recipient directory, CAP XML, dispatch, and log."""
    res_rec = client.get("/api/advisory/recipients")
    assert res_rec.status_code == 200
    recipients = res_rec.json()
    assert len(recipients) >= 4
    assert any("Purba Medinipur" in r["district"] for r in recipients)

    # CAP XML endpoint returns application/xml
    res_xml = client.get("/api/advisory/cap.xml")
    assert res_xml.status_code == 200
    assert "application/xml" in res_xml.headers["content-type"]
    assert "<alert" in res_xml.text

    # Execute automated dispatch
    dispatch_payload = {
        "storm_name": "API_TEST_CYCLONE",
        "alert_level": "Red",
        "wind_speed_kmh": 140.0,
        "heading_deg": 32.0,
        "peak_surge_m": 3.4,
        "affected_districts": ["Purba Medinipur", "South 24 Parganas"],
        "channels": ["CAP_XML", "SMS"],
    }
    res_dispatch = client.post("/api/advisory/dispatch", json=dispatch_payload)
    assert res_dispatch.status_code == 200
    data = res_dispatch.json()
    assert data["delivery_status"] == "DELIVERED"
    assert len(data["verification_hash_sha256"]) == 64

    # Verify log retrieval
    res_log = client.get("/api/advisory/dispatch/log")
    assert res_log.status_code == 200
    assert len(res_log.json()) >= 1


# ==============================================================================
# PHASE 7 TESTS: GEMINI 3.7 MULTIMODAL & PARAMETRIC LIQUIDITY TRIGGERS
# ==============================================================================

@pytest.mark.anyio
async def test_gemini_multimodal_visual_reasoning():
    """Verify Gemini 3.7 Flash multimodal spatial reasoning over map canvas."""
    engine = AdvisoryEngineService(api_key="")
    mock_b64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    res = await engine.analyze_multimodal_visual(
        image_base64=mock_b64_image,
        storm_name="AMPHAN_MULTIMODAL",
        context_metadata={"wind_speed_kmh": 165.0, "peak_surge_m": 4.1},
    )

    assert res.storm_name == "AMPHAN_MULTIMODAL"
    assert len(res.spatial_damage_observations) >= 2
    assert len(res.critical_infrastructure_threats) >= 2
    assert len(res.recommended_tactical_actions) >= 2
    assert res.visual_confidence_score > 0.80


def test_parametric_insurance_trigger_qualification_and_payout():
    """Verify physical index gates trigger pre-landfall liquidity payout in INR Crores."""
    engine = ParametricEngineService()

    # Severe storm: Catastrophic surge 3.5m and winds 140 km/h -> should trigger 100% of Purba Medinipur (₹50 Cr)
    result = engine.evaluate_policies(
        storm_name="CATASTROPHIC_TEST",
        wind_speed_kmh=140.0,
        peak_surge_m=3.5,
        landfall_eta_hours=12.0,
        impassable_roads_count=3,
    )

    assert result.policies_triggered >= 2
    assert result.total_liquidity_disbursed_inr_crores >= 50.0  # INR Crores
    assert len(result.active_certificates) >= 2

    for cert in result.active_certificates:
        assert cert.disbursement_status == "DISBURSED"
        assert cert.payout_amount_inr_crores > 0.0
        assert cert.payout_amount_inr_raw == cert.payout_amount_inr_crores * 10_000_000.0
        assert len(cert.sha256_audit_signature) == 64  # valid SHA-256 signature


def test_parametric_insurance_calm_zero_payout():
    """Verify calm atmospheric conditions trigger 0 payout and 0 certificates."""
    engine = ParametricEngineService()

    result = engine.evaluate_policies(
        storm_name="CALM_WEATHER",
        wind_speed_kmh=35.0,
        peak_surge_m=0.4,
        landfall_eta_hours=None,
        impassable_roads_count=0,
    )

    assert result.policies_triggered == 0
    assert result.total_liquidity_disbursed_inr_crores == 0.0
    assert len(result.active_certificates) == 0


def test_parametric_and_multimodal_api_endpoints():
    """Verify API endpoints for parametric policies, evaluation, certificates, and multimodal analysis."""
    # 1. Policies catalog
    res_pol = client.get("/api/parametric/policies")
    assert res_pol.status_code == 200
    assert len(res_pol.json()) >= 3

    # 2. Evaluate payout
    eval_payload = {
        "storm_name": "API_PARAMETRIC_TEST",
        "wind_speed_kmh": 125.0,
        "peak_surge_m": 2.4,
        "landfall_eta_hours": 14.0,
        "impassable_roads_count": 2,
        "max_rainfall_24h_mm": 190.0,
    }
    res_eval = client.post("/api/parametric/evaluate", json=eval_payload)
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert data["policies_triggered"] > 0
    assert data["total_liquidity_disbursed_inr_crores"] > 0

    # 3. Certificates ledger
    res_certs = client.get("/api/parametric/certificates")
    assert res_certs.status_code == 200
    assert len(res_certs.json()) >= 1

    # 4. Multimodal analyze
    mm_payload = {
        "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "storm_name": "API_MULTIMODAL_TEST",
        "context_metadata": {"wind_speed_kmh": 130.0, "peak_surge_m": 2.9},
    }
    res_mm = client.post("/api/advisory/multimodal-analyze", json=mm_payload)
    assert res_mm.status_code == 200
    mm_data = res_mm.json()
    assert "spatial_damage_observations" in mm_data
    assert len(mm_data["spatial_damage_observations"]) > 0
