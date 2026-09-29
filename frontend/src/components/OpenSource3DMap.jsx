import React, { useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import DataSourceBadge from './DataSourceBadge';

/**
 * OpenSource3DMap — High-Resolution Open-Source Satellite GIS Canvas.
 *
 * 100% Open-Source, Free, Zero-Payment, No API Key Required.
 * Uses authentic ESRI World Imagery global satellite tiles with MapLibre GL WebGL engine.
 * Full 3D camera tilt/pitch, interactive markers, track line, and real-time asset inspector.
 */
/**
 * Validates geographic coordinate bounds.
 * Longitude: [-180, 180], Latitude: [-90, 90]
 */
export function isValidCoordinate(lon, lat) {
  return (
    typeof lon === 'number' &&
    typeof lat === 'number' &&
    Number.isFinite(lon) &&
    Number.isFinite(lat) &&
    lon >= -180 &&
    lon <= 180 &&
    lat >= -90 &&
    lat <= 90
  );
}

/**
 * Extracts validated [longitude, latitude] from an asset or GeoJSON feature.
 */
export function extractAssetCoordinates(asset) {
  if (!asset) return null;
  if (asset.geometry?.type === 'Point' && Array.isArray(asset.geometry?.coordinates)) {
    const [lon, lat] = asset.geometry.coordinates;
    if (isValidCoordinate(lon, lat)) return [lon, lat];
  }
  const rawLon = asset.longitude !== undefined ? asset.longitude : asset.lon;
  const rawLat = asset.latitude !== undefined ? asset.latitude : asset.lat;
  const lon = typeof rawLon === 'string' ? parseFloat(rawLon) : Number(rawLon);
  const lat = typeof rawLat === 'string' ? parseFloat(rawLat) : Number(rawLat);

  if (isValidCoordinate(lon, lat)) {
    return [lon, lat];
  }
  return null;
}

/**
 * Builds a validated GeoJSON FeatureCollection from backend infrastructure items.
 */
export function buildInfraFeatureCollection(infrastructure) {
  if (!infrastructure) return { type: 'FeatureCollection', features: [] };
  if (infrastructure.type === 'FeatureCollection' && Array.isArray(infrastructure.features)) {
    return {
      type: 'FeatureCollection',
      features: infrastructure.features.filter((f) => {
        const coords = f?.geometry?.coordinates;
        return Array.isArray(coords) && coords.length >= 2 && isValidCoordinate(coords[0], coords[1]);
      }),
    };
  }

  const list = Array.isArray(infrastructure) ? infrastructure : [];
  const features = [];
  for (const item of list) {
    const coords = extractAssetCoordinates(item);
    if (!coords) continue; // Drop invalid or fabricated coordinates
    const props = item.properties || item;
    features.push({
      type: 'Feature',
      id: props.id || props.asset_id,
      geometry: { type: 'Point', coordinates: coords },
      properties: {
        ...props,
        longitude: coords[0],
        latitude: coords[1],
        lon: coords[0],
        lat: coords[1],
        risk_score: props.risk_score ?? props.modelled_risk_score ?? 0,
        risk_level: props.risk_level || 'LOW',
      },
    });
  }
  return { type: 'FeatureCollection', features };
}

/**
 * Extracts the single storm waypoint feature corresponding to the current step index.
 * Matches by properties.step_index or falls back to array index.
 */
export function extractCurrentStormFeature(trackData, stepIndex) {
  if (!trackData?.features) {
    return null;
  }
  const points = trackData.features.filter(
    (f) => f?.geometry?.type === 'Point' && f?.properties?.feature_type === 'storm_center'
  );
  if (points.length === 0) return null;

  if (stepIndex !== null && stepIndex !== undefined && stepIndex >= 0) {
    let match = points.find((f) => f.properties?.step_index === stepIndex);
    if (!match) {
      const idx = Math.min(Math.max(0, stepIndex), points.length - 1);
      match = points[idx];
    }
    return match || null;
  }

  return points[0] || null;
}

/**
 * Builds GeoJSON FeatureCollection for simulated track waypoints and path.
 */
export function buildSimulatedTrackGeoJson(simulatedTrack) {
  if (!Array.isArray(simulatedTrack) || simulatedTrack.length === 0) {
    return { type: 'FeatureCollection', features: [] };
  }

  const coords = simulatedTrack
    .filter((w) => isValidCoordinate(w.lon, w.lat))
    .map((w) => [w.lon, w.lat]);

  const features = [];

  if (coords.length >= 2) {
    features.push({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: coords },
      properties: {
        feature_type: 'simulated_track_path',
        title: 'Simulated Cyclone Path',
      },
    });
  }

  for (const w of simulatedTrack) {
    if (isValidCoordinate(w.lon, w.lat)) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [w.lon, w.lat] },
        properties: {
          ...w,
          feature_type: 'simulated_waypoint',
        },
      });
    }
  }

  return { type: 'FeatureCollection', features };
}

/**
 * Builds GeoJSON FeatureCollection for simulated hazard / surge footprint polygon and depth zones.
 */
export function buildSimulatedHazardPolygonGeoJson(polygonCoords, depthZones = []) {
  const features = [];

  // Multi-band surge depth zones if available
  if (Array.isArray(depthZones) && depthZones.length > 0) {
    for (const zone of depthZones) {
      const ring = zone.polygon;
      if (Array.isArray(ring) && ring.length >= 3) {
        const valid = ring.filter(
          (pt) => Array.isArray(pt) && pt.length >= 2 && isValidCoordinate(pt[0], pt[1])
        );
        if (valid.length >= 3) {
          const first = valid[0];
          const last = valid[valid.length - 1];
          if (first[0] !== last[0] || first[1] !== last[1]) {
            valid.push([first[0], first[1]]);
          }
          features.push({
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [valid] },
            properties: {
              feature_type: 'surge_depth_zone',
              title: zone.zone_label,
              depth_range_m: zone.depth_range_m,
              fill_color: zone.fill_color || '#ea580c',
            },
          });
        }
      }
    }
  }

  // Fallback / outer footprint polygon
  if (features.length === 0 && Array.isArray(polygonCoords) && polygonCoords.length >= 3) {
    const validRing = polygonCoords.filter(
      (pt) => Array.isArray(pt) && pt.length >= 2 && isValidCoordinate(pt[0], pt[1])
    );
    if (validRing.length >= 3) {
      const first = validRing[0];
      const last = validRing[validRing.length - 1];
      if (first[0] !== last[0] || first[1] !== last[1]) {
        validRing.push([first[0], first[1]]);
      }
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [validRing] },
        properties: {
          feature_type: 'hazard_footprint_polygon',
          title: 'Simulated Hazard & Surge Footprint',
          fill_color: '#ea580c',
        },
      });
    }
  }

  return { type: 'FeatureCollection', features };
}

export default function OpenSource3DMap({
  trackData = null,
  currentStepIndex = null,
  simulationData = null,
  isScenario = false,
  infrastructure = [],
  onSelectAsset = null,
  selectedAsset = null,
  activeLayers = { track: true, infrastructure: true, hazards: true },
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const popupRef = useRef(null);
  const currentStormMarkerRef = useRef(null);
  const simulatedLandfallMarkerRef = useRef(null);
  const isLoadedRef = useRef(false);

  const updateCurrentStorm = useCallback(() => {
    if (!mapRef.current || !isLoadedRef.current) return;

    const feature = extractCurrentStormFeature(trackData, currentStepIndex);
    const source = mapRef.current.getSource('current-storm');

    if (feature && feature.geometry?.coordinates) {
      if (source) {
        source.setData({
          type: 'FeatureCollection',
          features: [feature],
        });
      }

      const coords = feature.geometry.coordinates; // [longitude, latitude]
      const name = feature.properties?.storm_name;
      const category = feature.properties?.cyclone_category || feature.properties?.alert_level;
      const windKts = feature.properties?.wind_speed_knots ?? feature.properties?.wind_speed_kts;
      const windKmh = feature.properties?.wind_speed_kmh;

      if (!currentStormMarkerRef.current) {
        const el = document.createElement('div');
        el.className = 'current-storm-badge';
        el.style.cssText = `
          background: rgba(15, 23, 42, 0.94);
          border: 1.5px solid #ef4444;
          color: #fca5a5;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          font-size: 10px;
          font-weight: 700;
          padding: 2px 7px;
          border-radius: 4px;
          white-space: nowrap;
          pointer-events: none;
          transform: translate(0, -20px);
          box-shadow: 0 0 12px rgba(239, 68, 68, 0.55);
          display: flex;
          align-items: center;
          gap: 4px;
        `;
        currentStormMarkerRef.current = new maplibregl.Marker({
          element: el,
          anchor: 'bottom',
        });
      }

      const el = currentStormMarkerRef.current.getElement();
      if (el) {
        const stormLabel = name ? `🌀 ${name}` : '🌀 CURRENT STORM';
        const catLabel = category ? ` · ${category}` : '';
        const windLabel = windKts ? ` (${windKts} kts${windKmh ? ` / ${windKmh} km/h` : ''})` : '';
        el.innerHTML = `${stormLabel}${catLabel}${windLabel}`;
      }

      currentStormMarkerRef.current.setLngLat(coords).addTo(mapRef.current);
    } else {
      if (source) {
        source.setData({
          type: 'FeatureCollection',
          features: [],
        });
      }
      if (currentStormMarkerRef.current) {
        currentStormMarkerRef.current.remove();
      }
    }
  }, [trackData, currentStepIndex]);

  const updateCurrentStormRef = useRef(updateCurrentStorm);
  updateCurrentStormRef.current = updateCurrentStorm;

  const updateSimulation = useCallback(() => {
    if (!mapRef.current || !isLoadedRef.current) return;

    const trackSource = mapRef.current.getSource('simulation-track');
    const hazardSource = mapRef.current.getSource('simulation-hazard');

    if (!simulationData) {
      trackSource?.setData({ type: 'FeatureCollection', features: [] });
      hazardSource?.setData({ type: 'FeatureCollection', features: [] });
      if (simulatedLandfallMarkerRef.current) {
        simulatedLandfallMarkerRef.current.remove();
      }
      return;
    }

    const trackFc = buildSimulatedTrackGeoJson(simulationData.simulated_track);
    const hazardFc = buildSimulatedHazardPolygonGeoJson(
      simulationData.hazard_footprint_polygon,
      simulationData.surge_depth_zones
    );

    trackSource?.setData(trackFc);
    hazardSource?.setData(hazardFc);

    // Auto-fit camera around simulation geometry
    const bounds = new maplibregl.LngLatBounds();
    let hasCoords = false;

    if (Array.isArray(simulationData.simulated_track)) {
      simulationData.simulated_track.forEach((w) => {
        if (isValidCoordinate(w.lon, w.lat)) {
          bounds.extend([w.lon, w.lat]);
          hasCoords = true;
        }
      });
    }

    if (Array.isArray(simulationData.hazard_footprint_polygon)) {
      simulationData.hazard_footprint_polygon.forEach((pt) => {
        if (Array.isArray(pt) && pt.length >= 2 && isValidCoordinate(pt[0], pt[1])) {
          bounds.extend(pt);
          hasCoords = true;
        }
      });
    }

    if (hasCoords) {
      mapRef.current.fitBounds(bounds, {
        padding: 55,
        maxZoom: 9.5,
        pitch: 36,
        essential: true,
      });
    }

    // Landfall HTML Marker / Badge
    const landfallPt =
      simulationData.simulated_track?.find((w) => w.is_landfall_point) ||
      simulationData.simulated_track?.[4];

    if (landfallPt && isValidCoordinate(landfallPt.lon, landfallPt.lat)) {
      if (!simulatedLandfallMarkerRef.current) {
        const el = document.createElement('div');
        el.className = 'simulated-landfall-badge';
        el.style.cssText = `
          background: rgba(15, 23, 42, 0.94);
          border: 1.5px solid #ea580c;
          color: #fb923c;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          font-size: 10px;
          font-weight: 700;
          padding: 2px 7px;
          border-radius: 4px;
          white-space: nowrap;
          pointer-events: none;
          transform: translate(0, -20px);
          box-shadow: 0 0 12px rgba(234, 88, 12, 0.55);
          display: flex;
          align-items: center;
          gap: 4px;
        `;
        simulatedLandfallMarkerRef.current = new maplibregl.Marker({
          element: el,
          anchor: 'bottom',
        });
      }

      const el = simulatedLandfallMarkerRef.current.getElement();
      if (el) {
        el.innerHTML = `⚠️ SIMULATED LANDFALL (${landfallPt.wind_speed_knots || 0} kts)`;
      }

      simulatedLandfallMarkerRef.current
        .setLngLat([landfallPt.lon, landfallPt.lat])
        .addTo(mapRef.current);
    } else if (simulatedLandfallMarkerRef.current) {
      simulatedLandfallMarkerRef.current.remove();
    }
  }, [simulationData]);

  const updateSimulationRef = useRef(updateSimulation);
  updateSimulationRef.current = updateSimulation;

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    // High-resolution authentic satellite style using open ESRI satellite imagery
    const satelliteStyle = {
      version: 8,
      sources: {
        'esri-satellite': {
          type: 'raster',
          tiles: [
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          ],
          tileSize: 256,
          attribution: 'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, GIS Community',
        },
      },
      layers: [
        {
          id: 'satellite-layer',
          type: 'raster',
          source: 'esri-satellite',
          minzoom: 0,
          maxzoom: 19,
        },
      ],
    };

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: satelliteStyle,
      center: [88.0, 21.4],
      zoom: 6.8,
      pitch: 42, // 3D tilted camera perspective
      bearing: -8, // Slight perspective rotation
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(
      new maplibregl.AttributionControl({ compact: true, customAttribution: 'ESRI World Imagery · OpenStreetMap' }),
      'bottom-right'
    );

    popupRef.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 12,
      maxWidth: '240px',
    });

    map.on('load', () => {
      isLoadedRef.current = true;

      // ── 1. Storm Track Source ──
      map.addSource('storm-track', {
        type: 'geojson',
        data: trackData || { type: 'FeatureCollection', features: [] },
      });

      // 1a. Uncertainty Cone Fill & Outline (GDACS Poly_Cones)
      map.addLayer({
        id: 'hazard-cone-fill',
        type: 'fill',
        source: 'storm-track',
        filter: ['==', ['get', 'feature_type'], 'uncertainty_cone'],
        paint: {
          'fill-color': '#38bdf8',
          'fill-opacity': 0.18,
        },
      });

      map.addLayer({
        id: 'hazard-cone-outline',
        type: 'line',
        source: 'storm-track',
        filter: ['==', ['get', 'feature_type'], 'uncertainty_cone'],
        paint: {
          'line-color': '#38bdf8',
          'line-width': 1.5,
          'line-dasharray': [3, 2],
          'line-opacity': 0.75,
        },
      });

      // 1b. Wind Hazard Polygons (GDACS WindRadii / PointRadii)
      map.addLayer({
        id: 'hazard-polygon-fill',
        type: 'fill',
        source: 'storm-track',
        filter: ['in', ['get', 'feature_type'], ['literal', ['wind_hazard_polygon', 'hazard_polygon']]],
        paint: {
          'fill-color': [
            'case',
            ['==', ['get', 'alertlevel'], 'Red'],
            '#ef4444',
            ['==', ['get', 'alertlevel'], 'Orange'],
            '#f97316',
            '#eab308',
          ],
          'fill-opacity': 0.22,
        },
      });

      map.addLayer({
        id: 'hazard-polygon-outline',
        type: 'line',
        source: 'storm-track',
        filter: ['in', ['get', 'feature_type'], ['literal', ['wind_hazard_polygon', 'hazard_polygon']]],
        paint: {
          'line-color': '#f97316',
          'line-width': 1.5,
          'line-opacity': 0.85,
        },
      });

      // 1c. Observed & Historical Track Line (solid white)
      map.addLayer({
        id: 'track-line',
        type: 'line',
        source: 'storm-track',
        filter: ['in', ['get', 'feature_type'], ['literal', ['track_path', 'observed_track']]],
        paint: {
          'line-color': '#f8fafc',
          'line-width': 2.5,
          'line-dasharray': [2, 1.5],
        },
      });

      // 1d. Forecast Track Line (dashed blue)
      map.addLayer({
        id: 'forecast-track-line',
        type: 'line',
        source: 'storm-track',
        filter: ['==', ['get', 'feature_type'], 'forecast_track'],
        paint: {
          'line-color': '#60a5fa',
          'line-width': 2.5,
          'line-dasharray': [3, 2],
        },
      });

      // 1e. Track waypoints
      map.addLayer({
        id: 'track-waypoints',
        type: 'circle',
        source: 'storm-track',
        filter: ['in', ['get', 'feature_type'], ['literal', ['storm_center', 'waypoint']]],
        paint: {
          'circle-radius': 4.5,
          'circle-color': '#f59e0b',
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#0f172a',
        },
      });

      // ── 1b. Current Storm Position (Selected Timestep) ──
      map.addSource('current-storm', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      // Outer radar pulse / glow ring
      map.addLayer({
        id: 'current-storm-halo',
        type: 'circle',
        source: 'current-storm',
        paint: {
          'circle-radius': 18,
          'circle-color': '#ef4444',
          'circle-opacity': 0.22,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ef4444',
          'circle-stroke-opacity': 0.8,
        },
      });

      // Prominent current-storm core marker (high contrast white border, larger than waypoints)
      map.addLayer({
        id: 'current-storm-core',
        type: 'circle',
        source: 'current-storm',
        paint: {
          'circle-radius': 9,
          'circle-color': '#dc2626',
          'circle-stroke-width': 2.5,
          'circle-stroke-color': '#ffffff',
        },
      });

      // Inner eye center pin
      map.addLayer({
        id: 'current-storm-eye',
        type: 'circle',
        source: 'current-storm',
        paint: {
          'circle-radius': 3,
          'circle-color': '#ffffff',
        },
      });

      // ── 1c. Simulation Footprint & Track Sources & Layers ──
      map.addSource('simulation-hazard', {
        type: 'geojson',
        data: buildSimulatedHazardPolygonGeoJson(
          simulationData?.hazard_footprint_polygon,
          simulationData?.surge_depth_zones
        ),
      });

      // Simulation Hazard Fill (supports multi-band depth coloring or fallback amber)
      map.addLayer({
        id: 'simulation-hazard-fill',
        type: 'fill',
        source: 'simulation-hazard',
        paint: {
          'fill-color': ['coalesce', ['get', 'fill_color'], '#ea580c'],
          'fill-opacity': ['coalesce', ['get', 'fill_opacity'], 0.25],
        },
      });

      // Simulation Hazard Outline (dashed boundary)
      map.addLayer({
        id: 'simulation-hazard-outline',
        type: 'line',
        source: 'simulation-hazard',
        paint: {
          'line-color': ['coalesce', ['get', 'stroke_color'], '#f97316'],
          'line-width': 2.0,
          'line-dasharray': [3, 2],
          'line-opacity': 0.85,
        },
      });

      // Simulation Track Source
      map.addSource('simulation-track', {
        type: 'geojson',
        data: buildSimulatedTrackGeoJson(simulationData?.simulated_track),
      });

      // Simulation Track Line
      map.addLayer({
        id: 'simulation-track-line',
        type: 'line',
        source: 'simulation-track',
        filter: ['==', ['get', 'feature_type'], 'simulated_track_path'],
        paint: {
          'line-color': '#fb923c',
          'line-width': 3,
          'line-dasharray': [2, 1.5],
        },
      });

      // Simulation Track Waypoints
      map.addLayer({
        id: 'simulation-track-waypoints',
        type: 'circle',
        source: 'simulation-track',
        filter: ['==', ['get', 'feature_type'], 'simulated_waypoint'],
        paint: {
          'circle-radius': [
            'case',
            ['==', ['get', 'is_landfall_point'], true],
            8,
            4.5,
          ],
          'circle-color': [
            'case',
            ['==', ['get', 'is_landfall_point'], true],
            '#ef4444',
            '#fb923c',
          ],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      });

      // ── 2. Infrastructure Source ──
      const infraGeoJson = buildInfraFeatureCollection(infrastructure);

      map.addSource('infra-source', {
        type: 'geojson',
        data: infraGeoJson,
      });

      // Heatmap of vulnerable infrastructure
      map.addLayer({
        id: 'infra-heatmap',
        type: 'heatmap',
        source: 'infra-source',
        maxzoom: 11,
        paint: {
          'heatmap-weight': ['coalesce', ['get', 'modelled_risk'], 0.5],
          'heatmap-intensity': 0.8,
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,
            'rgba(0,0,0,0)',
            0.2,
            'rgba(34,197,94,0.3)',
            0.5,
            'rgba(245,158,11,0.45)',
            0.8,
            'rgba(239,68,68,0.65)',
            1.0,
            'rgba(220,38,38,0.85)',
          ],
          'heatmap-radius': 24,
          'heatmap-opacity': 0.65,
        },
      });

      // Infrastructure markers with sector coloring
      map.addLayer({
        id: 'infra-markers',
        type: 'circle',
        source: 'infra-source',
        paint: {
          'circle-radius': [
            'case',
            ['==', ['get', 'category'], 'hospital'],
            7,
            ['==', ['get', 'category'], 'power_grid'],
            6.5,
            5.5,
          ],
          'circle-color': [
            'case',
            ['==', ['get', 'category'], 'hospital'],
            '#ef4444',
            ['==', ['get', 'category'], 'power_grid'],
            '#f59e0b',
            ['==', ['get', 'category'], 'shelter'],
            '#10b981',
            ['==', ['get', 'category'], 'bridge'],
            '#a855f7',
            ['==', ['get', 'category'], 'road'],
            '#38bdf8',
            '#06b6d4',
          ],
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#0b111e',
        },
      });

      // Interactions
      map.on('mouseenter', 'infra-markers', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties;
        const coords = f.geometry.coordinates.slice();

        popupRef.current
          .setLngLat(coords)
          .setHTML(`
            <div style="font-family:Inter,sans-serif;line-height:1.4;padding:2px">
              <div style="font-weight:700;font-size:12px;color:#f8fafc;margin-bottom:3px">${p.name}</div>
              <div style="color:#94a3b8;font-size:10px;margin-bottom:6px">${p.district || ''} · ${p.category?.toUpperCase() || ''}</div>
              <div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid #334155;padding-top:4px;font-family:monospace;font-size:10px">
                <span style="color:#38bdf8">${p.elevation_m}m ASL</span>
                <span style="color:#f59e0b">${p.dist_to_coast_km}km shore</span>
              </div>
              ${p.inundation_depth_m > 0 ? `
              <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;padding-top:4px;border-top:1px solid #334155;font-size:10px">
                <span style="color:#38bdf8">Surge Inundation:</span>
                <span style="font-weight:700;color:${p.inundation_depth_m >= 1.5 ? '#ef4444' : '#f59e0b'}">${Number(p.inundation_depth_m).toFixed(2)}m</span>
              </div>` : ''}
              ${p.rainfall_accum_24h_mm > 0 ? `
              <div style="display:flex;justify-content:space-between;align-items:center;margin-top:2px;font-size:10px">
                <span style="color:#94a3b8">24h Rainfall:</span>
                <span style="font-weight:600;color:#60a5fa">${Number(p.rainfall_accum_24h_mm).toFixed(0)} mm</span>
              </div>` : ''}
              ${p.access_status ? `
              <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;padding-top:4px;border-top:1px solid #334155;font-size:10px">
                <span style="color:#94a3b8">Access:</span>
                <span style="font-weight:700;color:${p.access_status === 'IMPASSABLE' ? '#ef4444' : p.access_status === 'VULNERABLE' ? '#f59e0b' : '#10b981'}">${p.access_status}</span>
              </div>` : ''}
            </div>
          `)
          .addTo(map);
      });

      map.on('mouseleave', 'infra-markers', () => {
        map.getCanvas().style.cursor = '';
        popupRef.current.remove();
      });

      map.on('click', 'infra-markers', (e) => {
        if (e.features?.[0] && onSelectAsset) {
          onSelectAsset(e.features[0].properties);
        }
      });

      // Initial synchronization of current storm position
      updateCurrentStormRef.current?.();
      updateSimulationRef.current?.();
    });

    mapRef.current = map;

    return () => {
      if (currentStormMarkerRef.current) {
        currentStormMarkerRef.current.remove();
        currentStormMarkerRef.current = null;
      }
      if (simulatedLandfallMarkerRef.current) {
        simulatedLandfallMarkerRef.current.remove();
        simulatedLandfallMarkerRef.current = null;
      }
      map.remove();
      mapRef.current = null;
      isLoadedRef.current = false;
    };
  }, []);

  // Update current storm marker reactively whenever trackData or currentStepIndex changes
  useEffect(() => {
    updateCurrentStorm();
  }, [updateCurrentStorm]);

  // Update simulation data & auto-fit bounds reactively
  useEffect(() => {
    updateSimulation();
  }, [updateSimulation]);

  // Update track data reactively (clears when empty or null)
  useEffect(() => {
    if (!mapRef.current || !isLoadedRef.current) return;
    const data = trackData || { type: 'FeatureCollection', features: [] };
    mapRef.current.getSource('storm-track')?.setData(data);
  }, [trackData]);

  // Update infrastructure data
  useEffect(() => {
    if (!mapRef.current || !isLoadedRef.current || !infrastructure) return;
    const fc = buildInfraFeatureCollection(infrastructure);
    mapRef.current.getSource('infra-source')?.setData(fc);
  }, [infrastructure]);

  // Reactive layer visibility control
  useEffect(() => {
    if (!mapRef.current || !isLoadedRef.current) return;
    const map = mapRef.current;
    const setVisibility = (layerId, visible) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
      }
    };

    const trackVisible = activeLayers?.track !== false;
    setVisibility('track-line', trackVisible);
    setVisibility('forecast-track-line', trackVisible);
    setVisibility('track-waypoints', trackVisible);
    setVisibility('current-storm-halo', trackVisible);
    setVisibility('current-storm-core', trackVisible);
    setVisibility('current-storm-eye', trackVisible);
    if (currentStormMarkerRef.current) {
      currentStormMarkerRef.current.getElement().style.display = trackVisible ? 'flex' : 'none';
    }

    const hazardVisible = activeLayers?.hazards !== false;
    setVisibility('hazard-cone-fill', hazardVisible);
    setVisibility('hazard-cone-outline', hazardVisible);
    setVisibility('hazard-polygon-fill', hazardVisible);
    setVisibility('hazard-polygon-outline', hazardVisible);
    setVisibility('simulation-hazard-fill', hazardVisible);
    setVisibility('simulation-hazard-outline', hazardVisible);

    const infraVisible = activeLayers?.infrastructure !== false;
    setVisibility('infra-heatmap', infraVisible);
    setVisibility('infra-markers', infraVisible);
  }, [activeLayers]);

  // Auto-pan towards active cyclone when trackData has a valid NIO storm center
  useEffect(() => {
    if (!mapRef.current || !isLoadedRef.current || isScenario || !trackData) return;
    const center = extractCurrentStormFeature(trackData, currentStepIndex);
    if (center?.geometry?.coordinates) {
      const [lon, lat] = center.geometry.coordinates;
      if (lon >= 50 && lon <= 100 && lat >= 0 && lat <= 32) {
        mapRef.current.flyTo({
          center: [lon, lat],
          zoom: 6.5,
          pitch: 35,
          essential: false,
        });
      }
    }
  }, [trackData, isScenario]);

  // Fly to asset on selection
  useEffect(() => {
    if (selectedAsset && mapRef.current && isLoadedRef.current) {
      const coords = extractAssetCoordinates(selectedAsset);
      if (coords) {
        mapRef.current.flyTo({
          center: coords,
          zoom: 10.5,
          pitch: 50,
          essential: true,
        });
      }
    }
  }, [selectedAsset]);

  const resetCamera = () => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [88.0, 21.4],
        zoom: 6.8,
        pitch: 42,
        bearing: -8,
        essential: true,
      });
    }
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Top Map Operational Badges */}
      <div
        style={{
          position: 'absolute',
          top: 14,
          left: 14,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          zIndex: 30,
        }}
      >
        <div
          style={{
            backgroundColor: 'rgba(11, 17, 30, 0.90)',
            border: isScenario ? '1px solid rgba(234, 88, 12, 0.5)' : '1px solid #1e293b',
            borderRadius: 4,
            padding: '4px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            backdropFilter: 'blur(6px)',
          }}
        >
          <span style={{ fontSize: 10, fontWeight: 700, color: isScenario ? '#fb923c' : '#38bdf8', letterSpacing: '0.8px' }}>
            {isScenario ? 'SCENARIO SIMULATOR GIS' : 'OPEN-SOURCE SATELLITE 3D GIS'}
          </span>
          <span style={{ color: '#64748b' }}>·</span>
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#94a3b8' }}>
            {isScenario
              ? simulationData
                ? 'HYPOTHETICAL HAZARD FOOTPRINT & TRACK'
                : 'AWAITING SIMULATION EXECUTION'
              : 'ESRI WORLD IMAGERY · WEBGL 3D'}
          </span>
        </div>
        {isScenario && simulationData && (
          <DataSourceBadge source="Scenario Simulator" status="SCENARIO" />
        )}
      </div>

      <div
        style={{
          position: 'absolute',
          top: 14,
          right: 60,
          zIndex: 30,
        }}
      >
        <button
          onClick={resetCamera}
          style={{
            padding: '5px 12px',
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            border: '1px solid #334155',
            borderRadius: 4,
            color: '#f1f5f9',
            fontSize: 11,
            fontWeight: 600,
            cursor: 'pointer',
            backdropFilter: 'blur(6px)',
          }}
        >
          RESET 3D PERSPECTIVE
        </button>
      </div>

      {/* Bottom Map Legend */}
      <div
        style={{
          position: 'absolute',
          bottom: 14,
          left: 14,
          backgroundColor: 'rgba(11, 17, 30, 0.92)',
          border: '1px solid #1e293b',
          borderRadius: 4,
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          fontSize: 11,
          fontFamily: 'monospace',
          color: '#cbd5e1',
          zIndex: 30,
          backdropFilter: 'blur(6px)',
        }}
      >
        {isScenario ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 14, height: 2, backgroundColor: '#fb923c', borderTop: '2px dashed #fb923c' }} />
              <span>Simulated Path</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, backgroundColor: 'rgba(239, 68, 68, 0.45)', border: '1px solid #ef4444', display: 'inline-block' }} />
              <span>Surge &gt;3.0m</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, backgroundColor: 'rgba(249, 115, 22, 0.35)', border: '1px solid #f97316', display: 'inline-block' }} />
              <span>Surge 1.5–3.0m</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, backgroundColor: 'rgba(6, 182, 212, 0.25)', border: '1px solid #06b6d4', display: 'inline-block' }} />
              <span>Surge &lt;1.5m</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#ef4444', border: '2px solid #ffffff', display: 'inline-block' }} />
              <span>Simulated Landfall</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#ef4444' }} />
              <span>Critical Facility</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#f59e0b' }} />
              <span>Moderate Risk</span>
            </div>
          </>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#ef4444' }} />
              <span>Hospitals</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#f59e0b' }} />
              <span>Power Grid</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#10b981' }} />
              <span>Shelters</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#a855f7' }} />
              <span>Bridges</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#38bdf8' }} />
              <span>Arterial Roads</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 14, height: 2, backgroundColor: '#f8fafc' }} />
              <span>Observed Track</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 14, height: 2, backgroundColor: '#60a5fa', borderTop: '2px dashed #60a5fa' }} />
              <span>Forecast Track</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, backgroundColor: 'rgba(56, 189, 248, 0.25)', border: '1px dashed #38bdf8', display: 'inline-block' }} />
              <span>Uncertainty Cone</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, backgroundColor: 'rgba(249, 115, 22, 0.25)', border: '1px solid #f97316', display: 'inline-block' }} />
              <span>Hazard Radii</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#dc2626', border: '2px solid #ffffff', display: 'inline-block' }} />
              <span>Storm Center</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
