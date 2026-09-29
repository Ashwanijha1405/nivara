import React, { useEffect, useRef } from 'react';
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
export default function OpenSource3DMap({
  trackData = null,
  infrastructure = [],
  onSelectAsset = null,
  selectedAsset = null,
  activeLayers = { track: true, infrastructure: true, hazards: true },
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const popupRef = useRef(null);
  const isLoadedRef = useRef(false);

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

      // Track line (visible on satellite)
      map.addLayer({
        id: 'track-line',
        type: 'line',
        source: 'storm-track',
        filter: ['==', ['get', 'feature_type'], 'track_path'],
        paint: {
          'line-color': '#f8fafc',
          'line-width': 2.5,
          'line-dasharray': [2, 1.5],
        },
      });

      // Track waypoints
      map.addLayer({
        id: 'track-waypoints',
        type: 'circle',
        source: 'storm-track',
        filter: ['==', ['get', 'feature_type'], 'storm_center'],
        paint: {
          'circle-radius': 4.5,
          'circle-color': '#f59e0b',
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#0f172a',
        },
      });

      // ── 2. Infrastructure Source ──
      const infraGeoJson = {
        type: 'FeatureCollection',
        features: infrastructure.map((a) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [a.lon, a.lat] },
          properties: a,
        })),
      };

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
            '#38bdf8',
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
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      isLoadedRef.current = false;
    };
  }, []);

  // Update track data
  useEffect(() => {
    if (!mapRef.current || !isLoadedRef.current || !trackData) return;
    mapRef.current.getSource('storm-track')?.setData(trackData);
  }, [trackData]);

  // Update infrastructure data
  useEffect(() => {
    if (!mapRef.current || !isLoadedRef.current || !infrastructure) return;
    const fc = {
      type: 'FeatureCollection',
      features: infrastructure.map((a) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [a.lon, a.lat] },
        properties: a,
      })),
    };
    mapRef.current.getSource('infra-source')?.setData(fc);
  }, [infrastructure]);

  // Fly to asset on selection
  useEffect(() => {
    if (selectedAsset && mapRef.current && isLoadedRef.current) {
      mapRef.current.flyTo({
        center: [selectedAsset.lon, selectedAsset.lat],
        zoom: 10.5,
        pitch: 50,
        essential: true,
      });
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
            border: '1px solid #1e293b',
            borderRadius: 4,
            padding: '4px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            backdropFilter: 'blur(6px)',
          }}
        >
          <span style={{ fontSize: 10, fontWeight: 700, color: '#38bdf8', letterSpacing: '0.8px' }}>
            OPEN-SOURCE SATELLITE 3D GIS
          </span>
          <span style={{ color: '#64748b' }}>·</span>
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#94a3b8' }}>
            ESRI WORLD IMAGERY · WEBGL 3D
          </span>
        </div>
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
          <span style={{ width: 14, height: 2, backgroundColor: '#f8fafc' }} />
          <span>Storm Trajectory</span>
        </div>
      </div>
    </div>
  );
}
