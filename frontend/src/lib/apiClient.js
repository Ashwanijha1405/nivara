/**
 * Centralized API Client for Backend Services.
 *
 * All HTTP fetch calls to the FastAPI backend MUST be isolated in this file.
 * Frontend React components must never call fetch() directly.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Generic helper for handling HTTP errors and JSON parsing.
 */
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
        errorBody.detail || `Request to ${endpoint} failed with HTTP status ${response.status}`
      );
    }

    return await response.json();
  } catch (error) {
    console.error(`[API Client Error] ${options.method || 'GET'} ${endpoint}:`, error);
    throw error;
  }
}

/**
 * Fetch catalog of available historical cyclone tracks.
 * @returns {Promise<Array<{storm_id: string, name: string, year: number, basin: string}>>}
 */
export async function fetchStormCatalog() {
  return request('/api/storms');
}

/**
 * Fetch full storm track GeoJSON sequence (trajectory and center positions).
 * @param {string} stormId
 * @returns {Promise<GeoJSON.FeatureCollection>}
 */
export async function fetchStormTrack(stormId) {
  return request(`/api/storms/${encodeURIComponent(stormId)}/track`);
}

/**
 * Fetch infrastructure risk points GeoJSON for a specific timestep.
 * @param {string} stormId
 * @param {number} stepIndex
 * @returns {Promise<GeoJSON.FeatureCollection>}
 */
export async function fetchTimestepRisk(stormId, stepIndex) {
  return request(`/api/storms/${encodeURIComponent(stormId)}/timesteps/${stepIndex}/risk`);
}

/**
 * Fetch Gemini-generated district advisory text and mocked dispatches for a timestep.
 * @param {string} stormId
 * @param {number} stepIndex
 * @returns {Promise<Object>}
 */
export async function fetchTimestepAdvisory(stormId, stepIndex) {
  return request(`/api/storms/${encodeURIComponent(stormId)}/timesteps/${stepIndex}/advisory`);
}
