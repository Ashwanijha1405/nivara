import React, { useEffect, useState, useCallback } from 'react';
import OpenSource3DMap from '../components/OpenSource3DMap';
import DataSourceBadge from '../components/DataSourceBadge';
import {
  fetchLiveSnapshot,
  fetchInfrastructure,
  fetchLiveCycloneStatus,
  fetchLiveCycloneTrack,
  fetchLiveCycloneRisk,
} from '../lib/apiClient';

/**
 * Live Operations Command Center View (Default Application Route).
 * Displays active basin threats, current weather, 3D map, and exposed lifelines.
 * Fully integrates GDACS real-time cyclone ingestion across ACTIVE, CALM, and UNAVAILABLE states.
 */
export default function LiveOperationsView({ onSelectAsset, selectedAsset }) {
  const [snapshot, setSnapshot] = useState(null);
  const [cycloneStatus, setCycloneStatus] = useState(null);
  const [cycloneTrack, setCycloneTrack] = useState(null);
  const [cycloneRisk, setCycloneRisk] = useState(null);
  const [infrastructure, setInfrastructure] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);

  const loadLiveData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setIsRefreshing(true);
    try {
      const [snapRes, statusRes, trackRes, riskRes, infraRes] = await Promise.allSettled([
        fetchLiveSnapshot(),
        fetchLiveCycloneStatus(),
        fetchLiveCycloneTrack(),
        fetchLiveCycloneRisk(),
        fetchInfrastructure(),
      ]);

      if (snapRes.status === 'fulfilled' && snapRes.value) {
        setSnapshot(snapRes.value);
      }
      if (statusRes.status === 'fulfilled' && statusRes.value) {
        setCycloneStatus(statusRes.value);
      }
      if (trackRes.status === 'fulfilled' && trackRes.value) {
        setCycloneTrack(trackRes.value);
      }
      if (riskRes.status === 'fulfilled' && riskRes.value) {
        setCycloneRisk(riskRes.value);
      }
      if (infraRes.status === 'fulfilled' && infraRes.value) {
        setInfrastructure(infraRes.value);
      }

      setLastRefreshedAt(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Error refreshing Live Operations data:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadLiveData();
    const interval = setInterval(() => {
      loadLiveData();
    }, 60000); // 60-second polling interval (respects 90s backend cache)
    return () => clearInterval(interval);
  }, [loadLiveData]);

  // Determine operational state
  const liveStatus = cycloneStatus?.live_status || snapshot?.live_status || 'CALM';
  const isActive = liveStatus === 'ACTIVE' && Boolean(cycloneStatus?.cyclone);
  const isUnavailable = liveStatus === 'UNAVAILABLE';
  const isCalm = liveStatus === 'CALM' || (!isActive && !isUnavailable);

  const cyclone = cycloneStatus?.cyclone;
  const weather = snapshot?.current_weather || {};

  // Determine infrastructure list and exposed facilities
  const displayedAssets = (() => {
    if (isActive && cycloneRisk?.assets && cycloneRisk.assets.length > 0) {
      return cycloneRisk.assets;
    }
    if (snapshot?.top_exposed_facilities && snapshot.top_exposed_facilities.length > 0) {
      return snapshot.top_exposed_facilities;
    }
    return infrastructure;
  })();

  const topFacilities = displayedAssets.slice(0, 6);

  // Map track data: strictly null or empty when not ACTIVE to prevent any fabricated storm geometry
  const mapTrackData = isActive ? cycloneTrack : null;

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', position: 'relative' }}>
      {/* Centerpiece: Photorealistic 3D Map */}
      <div style={{ flex: 1, height: '100%', position: 'relative' }}>
        <OpenSource3DMap
          trackData={mapTrackData}
          infrastructure={displayedAssets}
          onSelectAsset={onSelectAsset}
          selectedAsset={selectedAsset}
          activeLayers={{
            track: isActive,
            infrastructure: true,
            hazards: isActive,
          }}
        />
      </div>

      {/* Top Right Refresh Bar */}
      <div
        style={{
          position: 'absolute',
          top: 14,
          right: 210,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          zIndex: 30,
        }}
      >
        <button
          onClick={() => loadLiveData(true)}
          disabled={isRefreshing}
          style={{
            padding: '5px 12px',
            backgroundColor: 'rgba(15, 23, 42, 0.92)',
            border: '1px solid #334155',
            borderRadius: 4,
            color: isRefreshing ? '#94a3b8' : '#f1f5f9',
            fontSize: 11,
            fontWeight: 600,
            cursor: isRefreshing ? 'wait' : 'pointer',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span style={{ display: 'inline-block', transform: isRefreshing ? 'rotate(180deg)' : 'none', transition: 'transform 0.4s ease' }}>
            🔄
          </span>
          {isRefreshing ? 'REFRESHING...' : 'SYNC GDACS'}
        </button>
        {lastRefreshedAt && (
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#64748b' }}>
            {lastRefreshedAt}
          </span>
        )}
      </div>

      {/* Floating Operational Cards Panel */}
      <div
        style={{
          position: 'absolute',
          top: 16,
          left: 16,
          width: 400,
          maxHeight: 'calc(100% - 32px)',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          pointerEvents: 'none',
          zIndex: 30,
        }}
      >
        {/* ── CARD 1: OPERATIONAL BASIN & CYCLONE THREAT STATUS ── */}
        <div
          style={{
            backgroundColor: 'rgba(11, 17, 30, 0.94)',
            border: isActive
              ? '1px solid #ef4444'
              : isUnavailable
              ? '1px solid #f59e0b'
              : '1px solid #1e293b',
            borderRadius: 6,
            padding: '14px 16px',
            backdropFilter: 'blur(8px)',
            pointerEvents: 'auto',
            boxShadow: isActive
              ? '0 8px 24px rgba(239, 68, 68, 0.25)'
              : '0 8px 24px rgba(0, 0, 0, 0.5)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              OPERATIONAL BASIN STATUS
            </span>
            <DataSourceBadge
              source="GDACS"
              status={isActive ? 'LIVE' : isUnavailable ? 'UNAVAILABLE' : 'LIVE'}
            />
          </div>

          {/* ACTIVE STATE */}
          {isActive && cyclone && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: '#ef4444',
                    boxShadow: '0 0 10px #ef4444',
                    display: 'inline-block',
                  }}
                />
                <div style={{ fontSize: 15, fontWeight: 800, color: '#f8fafc', letterSpacing: '0.4px' }}>
                  {cyclone.storm_name.toUpperCase()}
                </div>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: 3,
                    backgroundColor:
                      cyclone.alert_level === 'Red'
                        ? 'rgba(239, 68, 68, 0.25)'
                        : cyclone.alert_level === 'Orange'
                        ? 'rgba(249, 115, 22, 0.25)'
                        : 'rgba(234, 179, 8, 0.25)',
                    color:
                      cyclone.alert_level === 'Red'
                        ? '#fca5a5'
                        : cyclone.alert_level === 'Orange'
                        ? '#fdba74'
                        : '#fef08a',
                    border: '1px solid currentColor',
                  }}
                >
                  {cyclone.alert_level?.toUpperCase() || 'ALERT'}
                </span>
              </div>

              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 10 }}>
                {cyclone.intensity_text || 'Active Tropical Cyclone'} in North Indian Ocean basin (0°–32°N, 50°–100°E).
              </div>

              {/* Storm Telemetry Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '6px 12px',
                  fontSize: 11,
                  fontFamily: 'monospace',
                  backgroundColor: 'rgba(15, 23, 42, 0.7)',
                  padding: '8px 10px',
                  borderRadius: 4,
                  border: '1px solid #1e293b',
                  marginBottom: 10,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b' }}>CENTER:</span>
                  <span style={{ color: '#f8fafc', fontWeight: 600 }}>
                    {cyclone.current_lat.toFixed(2)}°N, {cyclone.current_lon.toFixed(2)}°E
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b' }}>WIND:</span>
                  <span style={{ color: '#ef4444', fontWeight: 700 }}>
                    {cyclone.wind_speed_kmh != null ? `${cyclone.wind_speed_kmh} km/h` : '—'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b' }}>WIND (KTS):</span>
                  <span style={{ color: '#f8fafc', fontWeight: 600 }}>
                    {cyclone.wind_speed_kts != null ? `${cyclone.wind_speed_kts} kts` : '—'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b' }}>PRESSURE:</span>
                  <span style={{ color: cyclone.central_pressure_mb ? '#f8fafc' : '#64748b', fontWeight: 600 }}>
                    {cyclone.central_pressure_mb ? `${cyclone.central_pressure_mb} hPa` : 'N/A'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b' }}>HEADING:</span>
                  <span style={{ color: cyclone.heading_deg != null ? '#38bdf8' : '#64748b', fontWeight: 600 }}>
                    {cyclone.heading_deg != null ? `${Math.round(cyclone.heading_deg)}°` : 'Computing'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748b' }}>SCORE:</span>
                  <span style={{ color: '#f59e0b', fontWeight: 600 }}>
                    {cyclone.alert_score ? cyclone.alert_score.toFixed(1) : '—'}
                  </span>
                </div>
              </div>

              {cyclone.affected_countries && cyclone.affected_countries.length > 0 && (
                <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>Affected Basins / Countries: </span>
                  <span style={{ color: '#cbd5e1' }}>{cyclone.affected_countries.join(', ')}</span>
                </div>
              )}

              <div style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>
                SYNCED: {cycloneStatus.fetched_at || 'LIVE'} · UN OCHA / EC JRC
              </div>
            </div>
          )}

          {/* CALM STATE */}
          {isCalm && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: '#22c55e',
                    boxShadow: '0 0 8px #22c55e',
                    display: 'inline-block',
                  }}
                />
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9' }}>
                  ROUTINE MONITORING — BASIN CALM
                </div>
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4, marginTop: 4 }}>
                No active tropical cyclone detected in the North Indian Ocean basin (Bay of Bengal / Arabian Sea).
              </div>
              <div
                style={{
                  marginTop: 8,
                  padding: '6px 8px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: 4,
                  fontSize: 10,
                  fontFamily: 'monospace',
                  color: '#64748b',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>FILTER: 0°N–32°N, 50°E–100°E</span>
                <span style={{ color: '#22c55e' }}>CALM VERIFIED</span>
              </div>
            </div>
          )}

          {/* UNAVAILABLE STATE */}
          {isUnavailable && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: '#f59e0b',
                    boxShadow: '0 0 8px #f59e0b',
                    display: 'inline-block',
                  }}
                />
                <div style={{ fontSize: 13, fontWeight: 700, color: '#fbbf24' }}>
                  LIVE CYCLONE DATA UNAVAILABLE
                </div>
              </div>
              <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.4, marginTop: 4 }}>
                GDACS real-time feed currently unreachable. Basin cannot be confirmed calm. Automated retries active.
              </div>
              <div
                style={{
                  marginTop: 8,
                  padding: '6px 8px',
                  backgroundColor: 'rgba(245, 158, 11, 0.12)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  borderRadius: 4,
                  fontSize: 10,
                  fontFamily: 'monospace',
                  color: '#fde68a',
                }}
              >
                <div>LAST SYNC: {cycloneStatus?.last_successful_sync || 'NO PRIOR SYNC IN SESSION'}</div>
                <div style={{ color: '#94a3b8', fontSize: 9, marginTop: 2 }}>
                  {cycloneStatus?.message || 'Upstream connection timeout.'}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── CARD 2: AMBIENT COASTAL SURFACE TELEMETRY (OPEN-METEO) ── */}
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
              AMBIENT COASTAL SURFACE TELEMETRY
            </span>
            <DataSourceBadge source="Open-Meteo" status="LIVE" />
          </div>

          <div style={{ fontSize: 11, fontWeight: 600, color: '#e2e8f0', marginBottom: 2 }}>
            {weather.location || 'Digha Coastal Station (21.63°N, 87.51°E)'}
          </div>
          <div style={{ fontSize: 9, color: '#64748b', marginBottom: 8 }}>
            Non-cyclone baseline coastal telemetry · Observation benchmark
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', fontSize: 11, fontFamily: 'monospace' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>WIND SPEED:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.wind_speed_kph ?? '—'} km/h</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>GUSTS:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.wind_gusts_kph ?? '—'} km/h</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>PRESSURE:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.surface_pressure_hpa ?? '—'} hPa</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>PRECIP:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{weather.precipitation_mm ?? '0.0'} mm</span>
            </div>
          </div>
        </div>

        {/* ── CARD 3: CRITICAL INFRASTRUCTURE LIFELINES & RISK ── */}
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
              CRITICAL INFRASTRUCTURE MONITORING
            </span>
            <DataSourceBadge source="OpenStreetMap" status="LIVE" />
          </div>

          <div style={{ fontSize: 12, color: '#cbd5e1', marginBottom: 4 }}>
            {snapshot?.total_infrastructure_monitored || displayedAssets.length} critical facilities evaluated across coastal districts.
          </div>

          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 8 }}>
            {isActive
              ? 'Multi-factor risk modelled against active storm center and GDACS wind hazard field.'
              : isUnavailable
              ? 'Risk evaluation paused due to unreachable cyclone feed; baseline facilities shown.'
              : 'Zero active cyclonic hazard; all facilities operating at baseline low risk.'}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 200, overflowY: 'auto' }}>
            {topFacilities.map((f) => {
              const riskVal = Number(f.modelled_risk ?? f.risk_score ?? 0);
              const riskLvl = f.risk_level || (isUnavailable ? 'UNAVAILABLE' : 'LOW');
              const isCrit = riskLvl === 'CRITICAL';
              const isHigh = riskLvl === 'HIGH';
              const isMod = riskLvl === 'MODERATE';

              return (
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
                    border: '1px solid transparent',
                    transition: 'border-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#38bdf8')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'transparent')}
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
                    {isUnavailable ? (
                      <span
                        style={{
                          fontSize: 9,
                          fontFamily: 'monospace',
                          fontWeight: 700,
                          padding: '2px 5px',
                          borderRadius: 3,
                          backgroundColor: 'rgba(245, 158, 11, 0.2)',
                          color: '#fbbf24',
                        }}
                      >
                        UNAVAILABLE
                      </span>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span
                          style={{
                            fontSize: 9,
                            fontFamily: 'monospace',
                            fontWeight: 700,
                            padding: '1px 4px',
                            borderRadius: 2,
                            backgroundColor: isCrit
                              ? 'rgba(239, 68, 68, 0.2)'
                              : isHigh
                              ? 'rgba(249, 115, 22, 0.2)'
                              : isMod
                              ? 'rgba(234, 179, 8, 0.2)'
                              : 'rgba(34, 197, 94, 0.15)',
                            color: isCrit
                              ? '#ef4444'
                              : isHigh
                              ? '#f97316'
                              : isMod
                              ? '#eab308'
                              : '#22c55e',
                          }}
                        >
                          {riskLvl}
                        </span>
                        <span
                          style={{
                            fontFamily: 'monospace',
                            fontWeight: 700,
                            color: isCrit ? '#ef4444' : isHigh ? '#f59e0b' : '#22c55e',
                          }}
                        >
                          {riskVal.toFixed(2)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
