/**
 * Centralized API Client for Nivara Disaster Intelligence Services.
 *
 * All HTTP fetch calls to the FastAPI backend are strictly centralized here.
 * Components must never call fetch() directly.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      let detailMsg = errorBody.detail;
      if (Array.isArray(detailMsg)) {
        detailMsg = detailMsg.map((err) => `${err.loc?.slice(-1)[0] || 'Field'}: ${err.msg}`).join(' | ');
      } else if (typeof detailMsg === 'object' && detailMsg !== null) {
        detailMsg = JSON.stringify(detailMsg);
      }
      throw new Error(
        detailMsg || `Request to ${endpoint} failed with HTTP ${response.status}`
      );
    }

    return await response.json();
  } catch (error) {
    console.error(`[API Client Error] ${options.method || 'GET'} ${endpoint}:`, error);
    throw error;
  }
}

// ── Live Operations & System Status ──

export async function fetchLiveSnapshot() {
  return request('/api/live/snapshot');
}

export async function fetchSystemStatus() {
  return request('/api/system/status');
}

// ── Storm Intelligence & Historical Events ──

export async function fetchStormCatalog() {
  return request('/api/storms');
}

export async function fetchStormDetails(stormId) {
  return request(`/api/storms/${encodeURIComponent(stormId)}`);
}

export async function fetchStormTrack(stormId) {
  return request(`/api/storms/${encodeURIComponent(stormId)}/track`);
}

/**
 * Normalizes an infrastructure risk item to the canonical shared structure:
 * {
 *   id, name, category, latitude, longitude,
 *   risk_score, risk_level, hazard, exposure, vulnerability
 * }
 */
export function normalizeRiskItem(item) {
  if (!item) return null;

  const rawLat = item.latitude !== undefined ? item.latitude : item.lat;
  const rawLon = item.longitude !== undefined ? item.longitude : item.lon;
  const latitude = typeof rawLat === 'string' ? parseFloat(rawLat) : Number(rawLat);
  const longitude = typeof rawLon === 'string' ? parseFloat(rawLon) : Number(rawLon);

  let riskLevel = (item.risk_level || 'LOW').toUpperCase();
  if (riskLevel === 'MEDIUM') riskLevel = 'MODERATE';
  if (!['LOW', 'MODERATE', 'HIGH', 'CRITICAL', 'UNAVAILABLE'].includes(riskLevel)) {
    riskLevel = 'LOW';
  }

  const rawScore =
    item.risk_score !== undefined
      ? item.risk_score
      : item.modelled_risk_score !== undefined
      ? item.modelled_risk_score
      : item.modelled_risk !== undefined
      ? item.modelled_risk
      : 0.0;
  const riskScore = typeof rawScore === 'string' ? parseFloat(rawScore) : Number(rawScore || 0);

  const id = String(item.id || item.asset_id || '');
  const name = String(item.name || item.asset_name || 'Infrastructure Facility');
  const category = String(item.category || item.infra_type || 'facility');

  return {
    ...item,
    id,
    name,
    category,
    latitude,
    longitude,
    lat: latitude,
    lon: longitude,
    risk_score: riskScore,
    modelled_risk_score: riskScore,
    modelled_risk: riskScore,
    risk_level: riskLevel,
    hazard: item.hazard || {},
    exposure: item.exposure || {},
    vulnerability: item.vulnerability || {},
    asset_id: id,
    asset_name: name,
  };
}

// Client-side memory cache keyed by `${stormId}_${stepIndex}`
const riskCache = new Map();
const advisoryCache = new Map();
const inFlightRisk = new Map();
const inFlightAdvisory = new Map();

export async function fetchStormRisk(stormId, stepIndex = 0) {
  const cacheKey = `${stormId}_${stepIndex}`;
  if (riskCache.has(cacheKey)) {
    return riskCache.get(cacheKey);
  }
  if (inFlightRisk.has(cacheKey)) {
    return inFlightRisk.get(cacheKey);
  }

  const promise = (async () => {
    try {
      const data = await request(`/api/storms/${encodeURIComponent(stormId)}/risk?step_index=${stepIndex}`);

      const rawAssets = Array.isArray(data?.assets)
        ? data.assets
        : Array.isArray(data?.features)
        ? data.features.map((f) => ({
            ...f.properties,
            longitude: f.geometry?.coordinates?.[0],
            latitude: f.geometry?.coordinates?.[1],
          }))
        : [];

      const normalizedAssets = rawAssets.map(normalizeRiskItem).filter(Boolean);

      const features = normalizedAssets.map((asset) => ({
        type: 'Feature',
        id: asset.id,
        geometry: {
          type: 'Point',
          coordinates: [asset.longitude, asset.latitude],
        },
        properties: asset,
      }));

      const result = {
        ...data,
        type: 'FeatureCollection',
        assets: normalizedAssets,
        features,
      };

      riskCache.set(cacheKey, result);
      return result;
    } finally {
      inFlightRisk.delete(cacheKey);
    }
  })();

  inFlightRisk.set(cacheKey, promise);
  return promise;
}

export async function fetchStormAdvisory(stormId, stepIndex = 0) {
  const cacheKey = `${stormId}_${stepIndex}`;
  if (advisoryCache.has(cacheKey)) {
    return advisoryCache.get(cacheKey);
  }
  if (inFlightAdvisory.has(cacheKey)) {
    return inFlightAdvisory.get(cacheKey);
  }

  const promise = (async () => {
    try {
      const data = await request(`/api/storms/${encodeURIComponent(stormId)}/advisory?step_index=${stepIndex}`);
      advisoryCache.set(cacheKey, data);
      return data;
    } finally {
      inFlightAdvisory.delete(cacheKey);
    }
  })();

  inFlightAdvisory.set(cacheKey, promise);
  return promise;
}

// ── Critical Infrastructure Lifelines ──

export async function fetchInfrastructure(category = null, district = null) {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  if (district) params.append('district', district);
  const q = params.toString() ? `?${params.toString()}` : '';
  const data = await request(`/api/infrastructure${q}`);

  if (Array.isArray(data)) {
    return data.map((item) => {
      const rawLat = item.latitude !== undefined ? item.latitude : item.lat;
      const rawLon = item.longitude !== undefined ? item.longitude : item.lon;
      const lat = typeof rawLat === 'string' ? parseFloat(rawLat) : Number(rawLat);
      const lon = typeof rawLon === 'string' ? parseFloat(rawLon) : Number(rawLon);
      return {
        ...item,
        latitude: lat,
        longitude: lon,
        lat,
        lon,
      };
    });
  }
  return data;
}

export async function fetchInfrastructureDetail(assetId) {
  return request(`/api/infrastructure/${encodeURIComponent(assetId)}`);
}

// ── Scenario Simulator ──

export async function runScenarioSimulation(params) {
  return request('/api/simulation/run', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ── Automated Operational Reports ──

export async function fetchSituationReport() {
  return request('/api/reports/situation');
}
