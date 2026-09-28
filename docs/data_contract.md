# Data Contract: Backend ↔ Frontend GeoJSON Specification

This document defines the strict GeoJSON and JSON payload contracts exchanged between the FastAPI backend and the MapLibre GL JS frontend. Both frontend and backend engineers should develop against these exact schemas.

---

## 1. REST Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/storms` | Lists available historical storm tracks for replay |
| `GET` | `/api/storms/{storm_id}/track` | Returns complete storm trajectory (points & path) |
| `GET` | `/api/storms/{storm_id}/timesteps/{step_index}/risk` | Returns GeoJSON FeatureCollection of infrastructure & risk points at that timestep |
| `GET` | `/api/storms/{storm_id}/timesteps/{step_index}/advisory` | Returns Gemini 3.7 Flash district early-warning text & mocked dispatch payload |

---

## 2. Storm Track Schema (`/api/storms/{storm_id}/track`)

### Response Format: `GeoJSON FeatureCollection`
Contains:
1. One `LineString` feature representing the full historical storm path.
2. An array of `Point` features representing storm eye centers across sequential timesteps.

```json
{
  "type": "FeatureCollection",
  "properties": {
    "storm_id": "2020139N09086",
    "name": "AMPHAN",
    "basin": "NI",
    "total_timesteps": 12,
    "start_time": "2020-05-18T00:00:00Z",
    "end_time": "2020-05-21T06:00:00Z"
  },
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [86.4, 13.2],
          [86.7, 15.5],
          [87.1, 18.2],
          [88.3, 21.6]
        ]
      },
      "properties": {
        "feature_type": "track_path",
        "storm_id": "2020139N09086"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [88.3, 21.6]
      },
      "properties": {
        "feature_type": "storm_center",
        "step_index": 3,
        "timestamp": "2020-05-20T06:00:00Z",
        "wind_speed_knots": 85.0,
        "wind_speed_kph": 157.4,
        "pressure_mb": 950.0,
        "cyclone_category": "Extremely Severe Cyclonic Storm",
        "is_landfall_point": true
      }
    }
  ]
}
```

---

## 3. Per-Timestep Risk GeoJSON (`/api/storms/{storm_id}/timesteps/{step_index}/risk`)

### Response Format: `GeoJSON FeatureCollection`
Emitted by the risk engine for the selected timestep.
- Point features represent critical infrastructure points evaluated for risk.
- Polygon features (optional) represent district boundary aggregates.

```json
{
  "type": "FeatureCollection",
  "properties": {
    "storm_id": "2020139N09086",
    "step_index": 3,
    "timestamp": "2020-05-20T06:00:00Z",
    "storm_center": [88.3, 21.6],
    "storm_wind_knots": 85.0,
    "total_assets_evaluated": 142
  },
  "features": [
    {
      "type": "Feature",
      "id": "osm_node_49201923",
      "geometry": {
        "type": "Point",
        "coordinates": [88.12, 21.68]
      },
      "properties": {
        "id": "osm_node_49201923",
        "name": "Digha Sub-Divisional Hospital",
        "infra_type": "hospital",
        "district": "Purba Medinipur",
        "state": "West Bengal",
        "elevation_m": 4.2,
        "dist_to_track_km": 18.5,
        "dist_to_coast_km": 1.2,
        "land_cover_class": "urban",
        "risk_score": 0.88,
        "risk_level": "CRITICAL",
        "risk_breakdown": {
          "proximity_factor": 0.92,
          "wind_intensity_factor": 0.85,
          "elevation_vulnerability": 0.90,
          "coastal_exposure": 0.95,
          "land_cover_multiplier": 0.80
        }
      }
    },
    {
      "type": "Feature",
      "id": "osm_node_98312011",
      "geometry": {
        "type": "Point",
        "coordinates": [88.24, 21.90]
      },
      "properties": {
        "id": "osm_node_98312011",
        "name": "Ramnagar 132kV Substation",
        "infra_type": "power_substation",
        "district": "Purba Medinipur",
        "state": "West Bengal",
        "elevation_m": 5.8,
        "dist_to_track_km": 24.1,
        "dist_to_coast_km": 4.8,
        "land_cover_class": "cropland",
        "risk_score": 0.74,
        "risk_level": "HIGH",
        "risk_breakdown": {
          "proximity_factor": 0.81,
          "wind_intensity_factor": 0.85,
          "elevation_vulnerability": 0.82,
          "coastal_exposure": 0.70,
          "land_cover_multiplier": 0.60
        }
      }
    }
  ]
}
```

### Risk Level Ranges
| `risk_level` | Score Range | Map Marker Color | Heatmap Weight |
|---|---|---|---|
| `LOW` | `0.00` – `0.34` | `#22c55e` (Green) | `0.2` |
| `MEDIUM` | `0.35` – `0.59` | `#eab308` (Yellow) | `0.5` |
| `HIGH` | `0.60` – `0.79` | `#f97316` (Orange) | `0.8` |
| `CRITICAL` | `0.80` – `1.00` | `#ef4444` (Red) | `1.0` |

### Infrastructure Types (`infra_type`)
- `hospital` (Hospitals, clinics, primary health centres)
- `power_station` (Power generation facilities)
- `power_substation` (Electrical distribution substations)
- `road_arterial` (Highways, primary arterial bridges & road junctions)
- `shelter` (Designated cyclone relief shelters)

---

## 4. Timestep Advisory Schema (`/api/storms/{storm_id}/timesteps/{step_index}/advisory`)

### Response Format: `application/json`
Output generated by Gemini 3.7 Flash synthesizing high-risk districts for this timestep.

```json
{
  "storm_id": "2020139N09086",
  "storm_name": "AMPHAN",
  "step_index": 3,
  "timestamp": "2020-05-20T06:00:00Z",
  "summary": {
    "worst_hit_district": "Purba Medinipur",
    "highest_risk_score": 0.88,
    "total_critical_assets": 14
  },
  "district_advisories": [
    {
      "district": "Purba Medinipur",
      "state": "West Bengal",
      "risk_level": "CRITICAL",
      "headline": "Critical Storm-Surge Inundation Imminent Along Digha Coastal Corridor",
      "key_risks": [
        "18.5km proximity to eye wall with sustained 85kt winds",
        "Sub-5m elevation with 1.2km coastal exposure creates extreme storm surge vulnerability",
        "2 major sub-divisional hospitals within projected inundation zone"
      ],
      "recommended_actions": [
        "Enforce mandatory evacuation of all settlements within 3km of coastline by 10:00 IST",
        "Cut electrical feeds to flood-prone 132kV substations to prevent cascading transformer fires",
        "Pre-position inflatable rescue craft at Contai bypass"
      ],
      "mocked_dispatch": {
        "sms_preview": "[IMD/NDMA ALERT] Cyclone AMPHAN landfall near Purba Medinipur within 6 hours. Move to cyclone shelters now. Avoid coastal roads.",
        "email_preview": "Subject: OPERATIONAL DIRECTIVE: Landfall Pre-Positioning - Purba Medinipur\nTo: District Magistrate, Purba Medinipur\n\nHigh risk score (0.88) computed for coastal belt. Immediate transition to emergency power protocols at Digha Sub-Divisional Hospital recommended."
      }
    }
  ]
}
```
