import React, { useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { runScenarioSimulation } from '../lib/apiClient';

/**
 * Scenario Simulator View.
 * Isolated product module for testing hypothetical cyclone impact scenarios.
 * Prominently displays: SCENARIO / MODELLED — NOT AN OFFICIAL FORECAST.
 */
export default function ScenarioSimulatorView({ onSelectAsset }) {
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

  const handleRun = async () => {
    setIsRunning(true);
    try {
      const data = await runScenarioSimulation(params);
      setResult(data);
    } catch (err) {
      console.error('Simulation failed:', err);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', height: '100%', overflow: 'hidden' }}>
      {/* Left Parameters Panel */}
      <div style={{ backgroundColor: '#0b111e', borderRight: '1px solid #1e293b', display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
        <div style={{ padding: '20px 22px', borderBottom: '1px solid #1e293b' }}>
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
        <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
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
              <label style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                LANDFALL LAT
              </label>
              <input
                type="number"
                step="0.05"
                value={params.landfall_lat}
                onChange={(e) => setParams({ ...params, landfall_lat: parseFloat(e.target.value) })}
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
              <label style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                LANDFALL LON
              </label>
              <input
                type="number"
                step="0.05"
                value={params.landfall_lon}
                onChange={(e) => setParams({ ...params, landfall_lon: parseFloat(e.target.value) })}
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
              <span style={{ color: '#f1f5f9', fontFamily: 'monospace', fontWeight: 700 }}>{params.max_wind_speed_knots} kts</span>
            </div>
            <input
              type="range"
              min={40}
              max={150}
              value={params.max_wind_speed_knots}
              onChange={(e) => setParams({ ...params, max_wind_speed_knots: parseFloat(e.target.value) })}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
              <span>PEAK STORM SURGE HEIGHT</span>
              <span style={{ color: '#ef4444', fontFamily: 'monospace', fontWeight: 700 }}>{params.surge_height_meters} meters</span>
            </div>
            <input
              type="range"
              min={1.0}
              max={10.0}
              step={0.5}
              value={params.surge_height_meters}
              onChange={(e) => setParams({ ...params, surge_height_meters: parseFloat(e.target.value) })}
              style={{ width: '100%' }}
            />
          </div>

          <button
            onClick={handleRun}
            disabled={isRunning}
            style={{
              marginTop: 10,
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
            }}
          >
            {isRunning ? 'RUNNING SIMULATION...' : 'RUN SCENARIO'}
          </button>
        </div>

        {/* Disclaimer Banner */}
        <div style={{ padding: '14px 18px', backgroundColor: '#0d1527', borderTop: '1px solid #1e293b' }}>
          <div style={{ fontSize: 10, color: '#fb923c', fontWeight: 700, letterSpacing: '0.6px', marginBottom: 2 }}>
            SCENARIO / MODELLED
          </div>
          <div style={{ fontSize: 10, color: '#94a3b8', lineHeight: 1.3 }}>
            NOT AN OFFICIAL FORECAST. Hypothetical modeling strictly for disaster management preparedness exercises.
          </div>
        </div>
      </div>

      {/* Right Output Panel */}
      <div style={{ padding: '24px 28px', overflowY: 'auto', backgroundColor: '#070c18' }}>
        {result ? (
          <div style={{ maxWidth: 880 }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: '#f1f5f9' }}>
                  {result.parameters.scenario_name}
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace', marginTop: 3 }}>
                  Landfall Target: {result.parameters.landfall_lat}°N, {result.parameters.landfall_lon}°E · Peak Winds: {result.parameters.max_wind_speed_knots} kts
                </div>
              </div>

              <DataSourceBadge source="Scenario Simulator" status="SCENARIO" />
            </div>

            {/* Prominent Warning Callout */}
            <div
              style={{
                backgroundColor: 'rgba(234, 88, 12, 0.12)',
                border: '1px solid rgba(234, 88, 12, 0.4)',
                borderRadius: 4,
                padding: '10px 14px',
                marginBottom: 20,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <span style={{ fontSize: 14, color: '#fb923c' }}>⚠️</span>
              <span style={{ fontSize: 11, color: '#fb923c', fontWeight: 700, letterSpacing: '0.6px' }}>
                {result.disclaimer}
              </span>
            </div>

            {/* Impact Metric Summary Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>TOTAL AT RISK</div>
                <div style={{ fontSize: 18, fontWeight: 800, color: '#f1f5f9', marginTop: 2 }}>
                  {result.summary.total_assets_at_risk} facilities
                </div>
              </div>

              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>CRITICAL TIER</div>
                <div style={{ fontSize: 18, fontWeight: 800, color: '#ef4444', marginTop: 2 }}>
                  {result.summary.critical_facilities_count}
                </div>
              </div>

              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>SURGE INUNDATION</div>
                <div style={{ fontSize: 18, fontWeight: 800, color: '#38bdf8', marginTop: 2 }}>
                  {result.summary.simulated_surge_corridor_km} km inland
                </div>
              </div>

              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>WORST HIT DISTRICT</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', marginTop: 4 }}>
                  {result.summary.worst_hit_district}
                </div>
              </div>
            </div>

            {/* Evaluated Assets Table */}
            <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 6, padding: '16px 18px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.8px', marginBottom: 12 }}>
                SIMULATED ASSET EXPOSURE (TOP TIER)
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {result.evaluated_assets.slice(0, 8).map((asset, i) => (
                  <div
                    key={asset.asset_id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 10px',
                      backgroundColor: '#151e2e',
                      borderRadius: 4,
                      fontSize: 11,
                    }}
                  >
                    <div>
                      <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{asset.asset_name}</span>
                      <span style={{ color: '#64748b', marginLeft: 8, fontFamily: 'monospace' }}>
                        {asset.district} · {asset.category}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>
                        {asset.vulnerability.terrain_elevation_m}m ASL
                      </span>
                      <span
                        style={{
                          fontFamily: 'monospace',
                          fontWeight: 700,
                          color: asset.risk_level === 'CRITICAL' ? '#ef4444' : '#f59e0b',
                        }}
                      >
                        {asset.modelled_risk_score.toFixed(2)} ({asset.risk_level})
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b' }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#94a3b8', marginBottom: 6 }}>
              Scenario Simulator Ready
            </div>
            <div style={{ fontSize: 12, maxWidth: 440, margin: '0 auto' }}>
              Adjust hypothetical landfall coordinates, intensity, and storm surge height on the left, then click <strong>RUN SCENARIO</strong> to project asset vulnerability.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
