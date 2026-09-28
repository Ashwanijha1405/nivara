# Nivara: Track-Based Cyclone Impact & Infrastructure Vulnerability Forecaster

A geospatial risk modeling pipeline (NOT a RAG system) that fuses historical cyclone track data, elevation/land cover, and critical infrastructure locations into a per-timestep risk score, then uses Google Gemini 3.7 Flash to generate district-level advisories with an interactive MapLibre GL JS timeline map.

---

## 🛠️ Architecture & Tech Stack

- **Backend**: Python 3.10+, FastAPI, Pydantic v2
- **Data Ingestion**:
  - **IBTrACS**: Historical cyclone track sequences (lat, lon, wind speed, pressure, timestamp)
  - **Open-Meteo**: Region meteorological data
  - **Google Earth Engine (GEE)**: SRTM elevation & Dynamic World / Copernicus land cover
  - **OSM Overpass API**: Critical infrastructure points (hospitals, power facilities, arterial roads)
- **Risk Scoring Engine**:
  - Deterministic, defensible weighted formula: proximity to track + wind intensity + elevation vulnerability + coastal exposure + land cover multiplier.
- **LLM Reasoning Layer**:
  - Google Gemini 3.7 Flash via Google AI Studio (`google-genai` / REST).
  - Summarizes top-N impacted districts into actionable evacuation & hardening advisories.
- **Frontend**:
  - Vite + React + MapLibre GL JS
  - Interactive timeline slider, layer toggles, risk heatmap, and advisory preview drawer.
- **Data Persistence**:
  - File-based GeoJSON store for MVP (no database required).

---

## 📁 Repository Structure

```text
repo-root/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI entrypoint & router registration
│   │   ├── config.py              # Pydantic Settings for environment variables
│   │   ├── ingestion/
│   │   │   ├── track_loader.py    # IBTrACS storm track parser & normalizer
│   │   │   ├── weather_client.py  # Open-Meteo meteorological API client
│   │   │   ├── gee_client.py      # Google Earth Engine client (elevation & land cover)
│   │   │   └── infra_client.py    # OSM Overpass client for roads, hospitals, power
│   │   ├── risk_engine/
│   │   │   ├── scoring.py         # Pure risk scoring functions (unit testable)
│   │   │   └── schema.py          # Pydantic models for GeoJSON contracts
│   │   ├── advisory/
│   │   │   ├── gemini_client.py   # Gemini 3.7 Flash API client wrapper
│   │   │   └── prompts.py         # Advisory system and user prompt templates
│   │   ├── api/
│   │   │   └── routes.py          # FastAPI HTTP endpoints
│   │   └── __init__.py
│   ├── tests/
│   │   └── test_scoring.py        # Unit tests for risk formula
│   ├── requirements.txt           # Python dependencies
│   └── .env.example               # Backend environment variables
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MapView.jsx        # MapLibre GL JS map container & layers
│   │   │   ├── TimelineSlider.jsx # Timestep scrubber control
│   │   │   ├── LayerToggles.jsx   # Heatmap & infra visibility toggles
│   │   │   └── AdvisoryPanel.jsx  # District early warning & mocked dispatch UI
│   │   ├── lib/
│   │   │   └── apiClient.js       # Centralized API fetch wrapper
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
├── data/
│   └── sample_track/              # Sample storm tracks (e.g. Cyclone Amphan 2020)
├── docs/
│   ├── data_contract.md           # Agreed GeoJSON schema between backend & frontend
│   └── docs_nivara/               # Hackathon architecture and task split PDFs
├── .gitignore
└── README.md
```

---

## 🚀 Quickstart Guide

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and GEE credentials if applicable
```

#### Run Backend Server:
```bash
uvicorn app.main:app --reload --port 8000
```
Swagger UI will be available at: `http://localhost:8000/docs`

#### Run Tests:
```bash
pytest tests/
```

---

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install Node dependencies
npm install

# Configure environment variables
cp .env.example .env
# Default points VITE_API_BASE_URL to http://localhost:8000

# Start Vite dev server
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 📑 Data Contract

Frontend and backend communicate via standardized GeoJSON FeatureCollections defined in [`docs/data_contract.md`](docs/data_contract.md). Both teams can develop concurrently using mock payloads conforming to this schema.
