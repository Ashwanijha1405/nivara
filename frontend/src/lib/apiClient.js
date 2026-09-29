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
      throw new Error(
        errorBody.detail || `Request to ${endpoint} failed with HTTP ${response.status}`
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

export async function fetchStormRisk(stormId, stepIndex = 0) {
  return request(`/api/storms/${encodeURIComponent(stormId)}/risk?step_index=${stepIndex}`);
}

export async function fetchStormAdvisory(stormId, stepIndex = 0) {
  return request(`/api/storms/${encodeURIComponent(stormId)}/advisory?step_index=${stepIndex}`);
}

// ── Critical Infrastructure Lifelines ──

export async function fetchInfrastructure(category = null, district = null) {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  if (district) params.append('district', district);
  const q = params.toString() ? `?${params.toString()}` : '';
  return request(`/api/infrastructure${q}`);
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
