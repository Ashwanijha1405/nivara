import React, { useEffect, useState } from 'react';
import OpenSource3DMap from '../components/OpenSource3DMap';
import DataSourceBadge from '../components/DataSourceBadge';
import { fetchLiveSnapshot, fetchInfrastructure } from '../lib/apiClient';

/**
 * Live Operations Command Center View (Default Application Route).
 * Displays active basin threats, current weather, 3D map, and exposed lifelines.
 */
export default function LiveOperationsView({ onSelectAsset, selectedAsset }) {
  const [snapshot, setSnapshot] = useState(null);
  const [infrastructure, setInfrastructure] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const [snapData, infraData] = await Promise.all([
          fetchLiveSnapshot(),
          fetchInfrastructure(),
        ]);
        if (mounted) {
          setSnapshot(snapData);
          setInfrastructure(infraData || []);
          setIsLoading(false);
        }
      } catch (err) {
        console.error('Failed to load live operations snapshot:', err);
        if (mounted) setIsLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 60000); // 1-minute refresh
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const weather = snapshot?.current_weather || {};
  const warnings = snapshot?.active_warnings || [];
  const exposed = snapshot?.top_exposed_facilities || [];

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', position: 'relative' }}>
      {/* Centerpiece: Photorealistic 3D Map */}
      <div style={{ flex: 1, height: '100%', position: 'relative' }}>
        <OpenSource3DMap
          infrastructure={infrastructure}
          onSelectAsset={onSelectAsset}
          selectedAsset={selectedAsset}
          activeLayers={{ track: false, infrastructure: true, hazards: true }}
        />
      </div>

      {/* Floating Operational Cards Panel */}
      <div
        style={{
          position: 'absolute',
          top: 16,
          left: 16,
          width: 380,
          maxHeight: 'calc(100% - 32px)',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          pointerEvents: 'none',
          zIndex: 30,
        }}
      >
        {/* Threat Status Card */}
        <div
          style={{
            backgroundColor: 'rgba(11, 17, 30, 0.94)',
            border: '1px solid #1e293b',
            borderRadius: 6,
            padding: '14px 16px',
            backdropFilter: 'blur(8px)',
            pointerEvents: 'auto',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              OPERATIONAL BASIN STATUS
            </span>
            <DataSourceBadge source="IMD" status="LIVE" />
          </div>

          <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', lineHeight: 1.3 }}>
            {snapshot?.threat_title || 'MONITORING NORTH INDIAN OCEAN'}
          </div>

          <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
            {snapshot?.active_threat_detected
              ? 'Active cyclonic disturbance monitored in coastal approach sector.'
              : 'No active tropical cyclone or severe depression detected by IMD bulletins.'}
          </div>
        </div>

        {/* Live Weather Telemetry */}
        <div
          style={{
            backgroundColor: 'rgba(11, 17, 30, 0.94)',
            border: '1px solid #1e293b',
            borderRadius: 6,
            padding: '14px 16px',
            backdropFilter: 'blur(8px)',
            pointerEvents: 'auto',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              COASTAL ATMOSPHERIC TELEMETRY
            </span>
            <DataSourceBadge source="Open-Meteo" status="LIVE" />
          </div>

          <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>
            {weather.location || 'Coastal Observation Station'}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', fontSize: 11, fontFamily: 'monospace' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>WIND SPEED:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.wind_speed_kph || '—'} km/h</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>GUSTS:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.wind_gusts_kph || '—'} km/h</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>PRESSURE:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.surface_pressure_hpa || '—'} hPa</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>PRECIP:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.precipitation_mm || '0.0'} mm</span>
            </div>
          </div>
        </div>

        {/* Monitored Lifelines Summary */}
        <div
          style={{
            backgroundColor: 'rgba(11, 17, 30, 0.94)',
            border: '1px solid #1e293b',
            borderRadius: 6,
            padding: '14px 16px',
            backdropFilter: 'blur(8px)',
            pointerEvents: 'auto',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              EXPOSED INFRASTRUCTURE LIFELINES
            </span>
            <DataSourceBadge source="OpenStreetMap" status="LIVE" />
          </div>

          <div style={{ fontSize: 12, color: '#cbd5e1', marginBottom: 10 }}>
            {snapshot?.total_infrastructure_monitored || infrastructure.length} critical facilities evaluated across coastal districts.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
            {exposed.slice(0, 5).map((f) => (
              <div
                key={f.id}
                onClick={() => onSelectAsset?.(f)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  backgroundColor: '#151e2e',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontSize: 11,
                }}
              >
                <div style={{ minWidth: 0, flex: 1, paddingRight: 8 }}>
                  <div style={{ color: '#f1f5f9', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {f.name}
                  </div>
                  <div style={{ color: '#64748b', fontSize: 10 }}>
                    {f.district} · {f.category}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <span
                    style={{
                      fontFamily: 'monospace',
                      fontWeight: 700,
                      color: f.risk_level === 'CRITICAL' ? '#ef4444' : f.risk_level === 'HIGH' ? '#f59e0b' : '#22c55e',
                    }}
                  >
                    {Number(f.modelled_risk).toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
