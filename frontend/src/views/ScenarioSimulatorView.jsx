import React, { useState } from 'react';
import OpenSource3DMap from '../components/OpenSource3DMap';
import DataSourceBadge from '../components/DataSourceBadge';
import { runScenarioSimulation } from '../lib/apiClient';

/**
 * Scenario Simulator View.
 * Isolated product module for testing hypothetical cyclone impact scenarios.
 * Prominently displays: SCENARIO / MODELLED — NOT AN OFFICIAL FORECAST.
 */
export default function ScenarioSimulatorView({ onSelectAsset, selectedAsset }) {
  const [params, setParams] = useState({
    scenario_name: 'Digha-Sagar High Surge Scenario',
    landfall_lat: 21.65,
    landfall_lon: 87.85,
    max_wind_speed_knots: 110.0,
    central_pressure_mb: 935.0,
    surge_height_meters: 5.5,
    track_heading_deg: 35.0,
  });

  const [result, setResult] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState(null);

  const handleRun = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setError(null);
    // Clear previous geometry while new scenario runs to avoid displaying stale data
    setResult(null);

    try {
      const data = await runScenarioSimulation(params);
      setResult(data);
    } catch (err) {
      console.error('Simulation failed:', err);
      setError(err?.response?.data?.detail || err?.message || 'Simulation execution failed. Please check inputs and retry.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '440px 1fr', height: '100%', overflow: 'hidden' }}>
      {/* Left Parameters & Results Panel */}
      <div
        style={{
          backgroundColor: '#0b111e',
          borderRight: '1px solid #1e293b',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflowY: 'auto',
        }}
      >
        {/* Module Header */}
        <div style={{ padding: '18px 20px', borderBottom: '1px solid #1e293b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              SCENARIO SIMULATOR
            </span>
            <DataSourceBadge source="Simulation Engine" status="SCENARIO" />
          </div>

          <div style={{ fontSize: 15, fontWeight: 800, color: '#f1f5f9' }}>
            Hypothetical Impact Modeler
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 3 }}>
            Explore hypothetical cyclone landfall scenarios and evaluate asset vulnerability.
          </div>
        </div>

        {/* Input Parameters Form */}
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 4 }}>
              SCENARIO TITLE
            </label>
            <input
              type="text"
              value={params.scenario_name}
              onChange={(e) => setParams({ ...params, scenario_name: e.target.value })}
              style={{
                width: '100%',
                padding: '6px 10px',
                backgroundColor: '#151e2e',
                border: '1px solid #334155',
                borderRadius: 4,
                color: '#f1f5f9',
                fontSize: 12,
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8' }}>
                  LANDFALL LAT (°N)
                </label>
                <span style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>15.0 - 25.0</span>
              </div>
              <input
                type="number"
                step="0.05"
                min="15.0"
                max="25.0"
                value={params.landfall_lat}
                onChange={(e) => setParams({ ...params, landfall_lat: parseFloat(e.target.value) || 0 })}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  backgroundColor: '#151e2e',
                  border: '1px solid #334155',
                  borderRadius: 4,
                  color: '#f1f5f9',
                  fontSize: 12,
                  fontFamily: 'monospace',
                }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8' }}>
                  LANDFALL LON (°E)
                </label>
                <span style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>80.0 - 92.0</span>
              </div>
              <input
                type="number"
                step="0.05"
                min="80.0"
                max="92.0"
                value={params.landfall_lon}
                onChange={(e) => setParams({ ...params, landfall_lon: parseFloat(e.target.value) || 0 })}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  backgroundColor: '#151e2e',
                  border: '1px solid #334155',
                  borderRadius: 4,
                  color: '#f1f5f9',
                  fontSize: 12,
                  fontFamily: 'monospace',
                }}
              />
            </div>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
              <span>MAX SUSTAINED WINDS</span>
              <span style={{ color: '#f1f5f9', fontFamily: 'monospace', fontWeight: 700 }}>
                {params.max_wind_speed_knots} kts
              </span>
            </div>
            <input
              type="range"
              min={40}
              max={150}
              value={params.max_wind_speed_knots}
              onChange={(e) => setParams({ ...params, max_wind_speed_knots: parseFloat(e.target.value) })}
              style={{ width: '100%', accentColor: '#ea580c' }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
              <span>PEAK STORM SURGE HEIGHT</span>
              <span style={{ color: '#ef4444', fontFamily: 'monospace', fontWeight: 700 }}>
                {params.surge_height_meters} meters
              </span>
            </div>
            <input
              type="range"
              min={1.0}
              max={10.0}
              step={0.5}
              value={params.surge_height_meters}
              onChange={(e) => setParams({ ...params, surge_height_meters: parseFloat(e.target.value) })}
              style={{ width: '100%', accentColor: '#ef4444' }}
            />
          </div>

          <button
            onClick={handleRun}
            disabled={isRunning}
            style={{
              marginTop: 6,
              padding: '10px 16px',
              backgroundColor: isRunning ? '#334155' : '#ea580c',
              border: 'none',
              borderRadius: 4,
              color: '#ffffff',
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: '0.8px',
              cursor: isRunning ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
            }}
          >
            {isRunning && <span>🌀</span>}
            {isRunning ? 'RUNNING SIMULATION...' : 'RUN SCENARIO'}
          </button>
        </div>

        {/* Error Banner */}
        {error && (
          <div
            style={{
              margin: '0 20px 14px',
              padding: '10px 14px',
              backgroundColor: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: 4,
              fontSize: 11,
              color: '#f87171',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Results & Evaluated Assets Section */}
        {result && (
          <div style={{ padding: '0 20px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Prominent Warning Callout */}
            <div
              style={{
                backgroundColor: 'rgba(234, 88, 12, 0.12)',
                border: '1px solid rgba(234, 88, 12, 0.4)',
                borderRadius: 4,
                padding: '10px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span style={{ fontSize: 13, color: '#fb923c' }}>⚠️</span>
              <span style={{ fontSize: 10, color: '#fb923c', fontWeight: 700, letterSpacing: '0.5px', lineHeight: 1.3 }}>
                {result.disclaimer || 'SCENARIO / MODELLED — NOT AN OFFICIAL FORECAST'}
              </span>
            </div>

            {/* Impact Metric Summary Cards (2x2 Grid) */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div style={{ backgroundColor: '#151e2e', border: '1px solid #1e293b', borderRadius: 4, padding: '10px 12px' }}>
                <div style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>TOTAL AT RISK</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: '#f1f5f9', marginTop: 2 }}>
                  {result.summary.total_assets_at_risk} facilities
                </div>
              </div>

              <div style={{ backgroundColor: '#151e2e', border: '1px solid #1e293b', borderRadius: 4, padding: '10px 12px' }}>
                <div style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>CRITICAL TIER</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: '#ef4444', marginTop: 2 }}>
                  {result.summary.critical_facilities_count}
                </div>
              </div>

              <div style={{ backgroundColor: '#151e2e', border: '1px solid #1e293b', borderRadius: 4, padding: '10px 12px' }}>
                <div style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>SURGE INUNDATION</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: '#38bdf8', marginTop: 2 }}>
                  {result.summary.simulated_surge_corridor_km} km
                </div>
              </div>

              <div style={{ backgroundColor: '#151e2e', border: '1px solid #1e293b', borderRadius: 4, padding: '10px 12px' }}>
                <div style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>WORST HIT DISTRICT</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {result.summary.worst_hit_district}
                </div>
              </div>
            </div>

            {/* Evaluated Assets Table */}
            <div style={{ backgroundColor: '#101726', border: '1px solid #1e293b', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.8px' }}>
                  SIMULATED ASSET EXPOSURE
                </div>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>
                  TOP {Math.min(8, result.evaluated_assets?.length || 0)}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {result.evaluated_assets?.slice(0, 8).map((asset) => {
                  const isSelected = selectedAsset && (selectedAsset.id === asset.id || selectedAsset.asset_id === asset.asset_id);
                  const riskLevel = asset.risk_level || 'LOW';
                  const riskScore = asset.modelled_risk_score ?? asset.risk_score ?? 0;
                  const name = asset.name || asset.asset_name;
                  const elev = asset.vulnerability?.terrain_elevation_m;

                  const badgeColor =
                    riskLevel === 'CRITICAL' ? '#ef4444' :
                    riskLevel === 'HIGH' ? '#f97316' :
                    riskLevel === 'MODERATE' ? '#eab308' : '#22c55e';

                  return (
                    <div
                      key={asset.id || asset.asset_id || name}
                      onClick={() => onSelectAsset?.(asset)}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '7px 9px',
                        backgroundColor: isSelected ? 'rgba(234, 88, 12, 0.2)' : '#151e2e',
                        border: isSelected ? '1px solid #ea580c' : '1px solid transparent',
                        borderRadius: 4,
                        fontSize: 11,
                        cursor: 'pointer',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      <div style={{ minWidth: 0, flex: 1, marginRight: 8 }}>
                        <div style={{ color: '#f1f5f9', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {name}
                        </div>
                        <div style={{ color: '#64748b', fontSize: 10, fontFamily: 'monospace', marginTop: 1 }}>
                          {asset.district} · {asset.category}
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                        {elev != null && (
                          <span style={{ color: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}>
                            {elev}m
                          </span>
                        )}
                        <span
                          style={{
                            fontFamily: 'monospace',
                            fontWeight: 700,
                            fontSize: 10,
                            color: badgeColor,
                            backgroundColor: `${badgeColor}18`,
                            padding: '2px 5px',
                            borderRadius: 3,
                            border: `1px solid ${badgeColor}40`,
                          }}
                        >
                          {riskScore.toFixed(2)} {riskLevel}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Disclaimer Footer Banner */}
        <div style={{ marginTop: 'auto', padding: '14px 18px', backgroundColor: '#0d1527', borderTop: '1px solid #1e293b' }}>
          <div style={{ fontSize: 10, color: '#fb923c', fontWeight: 700, letterSpacing: '0.6px', marginBottom: 2 }}>
            SCENARIO / MODELLED
          </div>
          <div style={{ fontSize: 10, color: '#94a3b8', lineHeight: 1.3 }}>
            NOT AN OFFICIAL FORECAST. Hypothetical modeling strictly for disaster management preparedness exercises.
          </div>
        </div>
      </div>

      {/* Right Column: 3D Map Canvas */}
      <div style={{ position: 'relative', height: '100%', width: '100%', overflow: 'hidden', backgroundColor: '#070c18' }}>
        <OpenSource3DMap
          simulationData={result}
          infrastructure={result?.evaluated_assets || []}
          isScenario={true}
          onSelectAsset={onSelectAsset}
          selectedAsset={selectedAsset}
          activeLayers={{ track: true, infrastructure: true, hazards: true }}
        />

        {/* Empty State Overlay */}
        {!result && !isRunning && (
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              backgroundColor: 'rgba(11, 17, 30, 0.92)',
              border: '1px dashed #334155',
              borderRadius: 8,
              padding: '26px 34px',
              textAlign: 'center',
              maxWidth: 440,
              backdropFilter: 'blur(8px)',
              pointerEvents: 'none',
              boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
              zIndex: 10,
            }}
          >
            <div style={{ fontSize: 26, marginBottom: 8 }}>🌀</div>
            <div style={{ fontSize: 12, fontWeight: 800, color: '#f1f5f9', letterSpacing: '0.8px', marginBottom: 6 }}>
              RUN A SCENARIO TO VIEW SIMULATED TRACK & HAZARD FOOTPRINT
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.45 }}>
              Configure landfall coordinates, sustained winds, and peak surge on the left panel, then click{' '}
              <strong style={{ color: '#fb923c' }}>RUN SCENARIO</strong> to project spatial storm track lines, hazard surge footprints, and impacted infrastructure assets.
            </div>
          </div>
        )}

        {/* Running Simulation Overlay */}
        {isRunning && (
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              backgroundColor: 'rgba(11, 17, 30, 0.94)',
              border: '1px solid #ea580c',
              borderRadius: 8,
              padding: '22px 30px',
              textAlign: 'center',
              backdropFilter: 'blur(8px)',
              pointerEvents: 'none',
              boxShadow: '0 0 28px rgba(234, 88, 12, 0.35)',
              zIndex: 10,
            }}
          >
            <div style={{ fontSize: 24, marginBottom: 8, display: 'inline-block' }}>🌀</div>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#fb923c', letterSpacing: '0.8px' }}>
              RUNNING SIMULATION...
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
              Projecting trajectory, surge flood polygon, and asset risk exposure...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
