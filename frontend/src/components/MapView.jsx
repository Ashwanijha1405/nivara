import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';

/**
 * MapView — Clean ops-grade map canvas.
 * Muted track line, subtle heatmap, compact infrastructure markers, monospace popups.
 */
export default function MapView({
  trackData,
  riskData,
  currentStepIndex,
  activeLayers,
  onSelectAsset,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const popupRef = useRef(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json',
      center: [88.0, 21.5],
      zoom: 6.8,
      minZoom: 4,
      maxZoom: 14,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    popupRef.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 10,
      maxWidth: '220px',
    });

    map.on('load', () => {
      loadedRef.current = true;

      // ── Storm Track Source ──
      map.addSource('storm-track', {
        type: 'geojson',
        data: trackData || { type: 'FeatureCollection', features: [] },
      });

      // Track line — muted, thin, solid
      map.addLayer({
        id: 'track-line',
        type: 'line',
        source: 'storm-track',
        filter: ['==', ['get', 'feature_type'], 'track_path'],
        paint: {
          'line-color': '#334155',
          'line-width': 2,
          'line-opacity': 0.7,
        },
      });

      // Historical track dots — very small
      map.addLayer({
        id: 'track-dots',
        type: 'circle',
        source: 'storm-track',
        filter: ['==', ['get', 'feature_type'], 'storm_center'],
        paint: {
          'circle-radius': 3,
          'circle-color': '#475569',
          'circle-stroke-width': 1,
          'circle-stroke-color': '#1e293b',
        },
      });

      // ── Current Eye Position ──
      map.addSource('current-eye', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      // Outer pulse ring
      map.addLayer({
        id: 'eye-pulse',
        type: 'circle',
        source: 'current-eye',
        paint: {
          'circle-radius': 18,
          'circle-color': 'transparent',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#dc2626',
          'circle-stroke-opacity': 0.4,
        },
      });

      // Inner eye dot
      map.addLayer({
        id: 'eye-center',
        type: 'circle',
        source: 'current-eye',
        paint: {
          'circle-radius': 6,
          'circle-color': '#dc2626',
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#fca5a5',
        },
      });

      // ── Risk Infrastructure Source ──
      map.addSource('risk-infra', {
        type: 'geojson',
        data: riskData || { type: 'FeatureCollection', features: [] },
      });

      // Heatmap — very subtle thermal underlay
      map.addLayer({
        id: 'lyr-heatmap',
        type: 'heatmap',
        source: 'risk-infra',
        maxzoom: 12,
        paint: {
          'heatmap-weight': ['get', 'risk_score'],
          'heatmap-intensity': 0.7,
          'heatmap-color': [
            'interpolate', ['linear'], ['heatmap-density'],
            0,   'rgba(0,0,0,0)',
            0.2, 'rgba(22,101,52,0.2)',
            0.5, 'rgba(133,77,14,0.35)',
            0.8, 'rgba(153,27,27,0.5)',
            1.0, 'rgba(220,38,38,0.65)',
          ],
          'heatmap-radius': 28,
          'heatmap-opacity': 0.6,
        },
      });

      // Risk-colored function
      const riskColor = [
        'case',
        ['>=', ['get', 'risk_score'], 0.75], '#dc2626',
        ['>=', ['get', 'risk_score'], 0.55], '#d97706',
        ['>=', ['get', 'risk_score'], 0.30], '#ca8a04',
        '#16a34a',
      ];

      const riskRadius = [
        'interpolate', ['linear'], ['get', 'risk_score'],
        0.0, 4,  0.5, 6,  1.0, 9,
      ];

      // Hospitals
      map.addLayer({
        id: 'lyr-hospitals',
        type: 'circle',
        source: 'risk-infra',
        filter: ['==', ['get', 'infra_type'], 'hospital'],
        paint: {
          'circle-radius': riskRadius,
          'circle-color': riskColor,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#1e293b',
        },
      });

      // Power
      map.addLayer({
        id: 'lyr-power',
        type: 'circle',
        source: 'risk-infra',
        filter: ['any',
          ['==', ['get', 'infra_type'], 'power_substation'],
          ['==', ['get', 'infra_type'], 'power_station'],
        ],
        paint: {
          'circle-radius': riskRadius,
          'circle-color': riskColor,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#1e293b',
        },
      });

      // Roads & Shelters
      map.addLayer({
        id: 'lyr-roads',
        type: 'circle',
        source: 'risk-infra',
        filter: ['any',
          ['==', ['get', 'infra_type'], 'road_arterial'],
          ['==', ['get', 'infra_type'], 'shelter'],
        ],
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['get', 'risk_score'], 0.0, 4, 1.0, 7],
          'circle-color': riskColor,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#1e293b',
        },
      });

      // Tooltip interaction
      ['lyr-hospitals', 'lyr-power', 'lyr-roads'].forEach((id) => {
        map.on('mouseenter', id, (e) => {
          map.getCanvas().style.cursor = 'pointer';
          const f = e.features?.[0];
          if (!f) return;
          const p = f.properties;
          const coords = f.geometry.coordinates.slice();

          popupRef.current
            .setLngLat(coords)
            .setHTML(`
              <div style="line-height:1.4">
                <div style="font-weight:700;font-size:12px;color:#e5e7eb;margin-bottom:3px">${p.name}</div>
                <div style="color:#6b7280;font-size:10px;margin-bottom:6px">${p.district || ''} · ${p.infra_type}</div>
                <div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid #1e293b;padding-top:4px">
                  <span>RISK ${Number(p.risk_score).toFixed(2)}</span>
                  <span style="color:${p.risk_level === 'CRITICAL' ? '#fca5a5' : p.risk_level === 'HIGH' ? '#fcd34d' : '#86efac'}">${p.risk_level}</span>
                </div>
                <div style="color:#4b5563;font-size:10px;margin-top:3px">
                  ELV ${p.elevation_m}m · TRK ${p.dist_to_track_km}km · CST ${p.dist_to_coast_km}km
                </div>
              </div>
            `)
            .addTo(map);
        });

        map.on('mouseleave', id, () => {
          map.getCanvas().style.cursor = '';
          popupRef.current.remove();
        });

        map.on('click', id, (e) => {
          if (e.features?.[0] && onSelectAsset) onSelectAsset(e.features[0].properties);
        });
      });
    });

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; loadedRef.current = false; };
  }, []);

  // Update track data
  useEffect(() => {
    if (!mapRef.current || !loadedRef.current || !trackData) return;
    mapRef.current.getSource('storm-track')?.setData(trackData);
  }, [trackData]);

  // Update eye position
  useEffect(() => {
    if (!mapRef.current || !loadedRef.current || !trackData) return;
    const pts = trackData.features?.filter((f) => f.properties?.feature_type === 'storm_center') || [];
    const target = pts.find((p) => p.properties.step_index === currentStepIndex) || pts[0];
    if (target) {
      mapRef.current.getSource('current-eye')?.setData({
        type: 'FeatureCollection', features: [target],
      });
    }
  }, [trackData, currentStepIndex]);

  // Update risk data
  useEffect(() => {
    if (!mapRef.current || !loadedRef.current || !riskData) return;
    mapRef.current.getSource('risk-infra')?.setData(riskData);
  }, [riskData]);

  // Layer visibility
  useEffect(() => {
    if (!mapRef.current || !loadedRef.current) return;
    const m = mapRef.current;
    const mapping = { heatmap: 'lyr-heatmap', hospitals: 'lyr-hospitals', power: 'lyr-power', roads: 'lyr-roads' };
    Object.entries(mapping).forEach(([key, layerId]) => {
      if (m.getLayer(layerId)) {
        m.setLayoutProperty(layerId, 'visibility', activeLayers[key] ? 'visible' : 'none');
      }
    });
  }, [activeLayers]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
