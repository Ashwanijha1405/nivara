import React, { useEffect, useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { fetchStormRisk } from '../lib/apiClient';

/**
 * Risk & Exposure Analytical View.
 * Displays decomposed risk: Hazard -> Exposure -> Vulnerability -> Impact.
 * Explains "Why is this location high risk?" based on structured model inputs.
 */
export default function RiskExposureView({ selectedAsset, onSelectAsset }) {
  const [riskData, setRiskData] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);

  useEffect(() => {
    fetchStormRisk('2020136N10088', 12)
      .then((data) => {
        setRiskData(data);
        if (data?.assets?.length) {
          setSelectedResult(data.assets[0]);
        }
      })
      .catch(console.error);
  }, []);

  const assets = riskData?.assets || [];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', height: '100%', overflow: 'hidden' }}>
      {/* Left Column: Asset Risk Table */}
      <div
        style={{
          backgroundColor: '#0b111e',
          borderRight: '1px solid #1e293b',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
        }}
      >
        <div style={{ padding: '16px 18px', borderBottom: '1px solid #1e293b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              CRITICAL LIFELINE RISK EVALUATION
            </span>
            <DataSourceBadge source="Nivara Model" status="MODELLED" />
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9' }}>
            {assets.length} Physical Facilities Evaluated
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            Ranked by Modelled Risk index under storm circulation.
          </div>
        </div>

        {/* Scrollable Asset List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {assets.map((item) => {
            const isSelected = selectedResult?.asset_id === item.asset_id;
            const score = item.modelled_risk_score;
            const color = score >= 0.75 ? '#ef4444' : score >= 0.5 ? '#f59e0b' : '#22c55e';

            return (
              <div
                key={item.asset_id}
                onClick={() => setSelectedResult(item)}
                style={{
                  padding: '10px 12px',
                  backgroundColor: isSelected ? '#1e293b' : '#111827',
                  border: isSelected ? '1px solid #38bdf8' : '1px solid #1e293b',
                  borderRadius: 4,
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div style={{ minWidth: 0, flex: 1, paddingRight: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.asset_name}
                  </div>
                  <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace', marginTop: 2 }}>
                    {item.district} · {item.category.toUpperCase()} · {item.vulnerability.terrain_elevation_m}m ASL
                  </div>
                </div>

                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 800, fontFamily: 'monospace', color }}>
                    {score.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 9, fontWeight: 700, fontFamily: 'monospace', color }}>
                    {item.risk_level}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Column: "Why is this location high risk?" Deconstruction */}
      <div style={{ padding: '24px 28px', overflowY: 'auto', backgroundColor: '#070c18' }}>
        {selectedResult ? (
          <div style={{ maxWidth: 860 }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: '#f1f5f9' }}>
                  {selectedResult.asset_name}
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace', marginTop: 3 }}>
                  {selectedResult.district}, {selectedResult.state} · Sector: {selectedResult.category.toUpperCase()}
                </div>
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 24, fontWeight: 900, fontFamily: 'monospace', color: selectedResult.modelled_risk_score >= 0.75 ? '#ef4444' : '#f59e0b' }}>
                  {selectedResult.modelled_risk_score.toFixed(2)}
                </div>
                <div style={{ fontSize: 11, fontWeight: 700, fontFamily: 'monospace', color: '#94a3b8' }}>
                  MODELLED RISK INDEX ({selectedResult.risk_level})
                </div>
              </div>
            </div>

            {/* Explanation Callout */}
            <div
              style={{
                backgroundColor: '#0f172a',
                borderLeft: '4px solid #38bdf8',
                padding: '14px 18px',
                borderRadius: '0 4px 4px 0',
                marginBottom: 24,
                fontSize: 13,
                color: '#e2e8f0',
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8', letterSpacing: '0.8px', marginBottom: 4 }}>
                WHY IS THIS LOCATION AT RISK?
              </div>
              {selectedResult.explanation}
            </div>

            {/* Decomposed Components Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
              {/* 1. Hazard */}
              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 6, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#ef4444', letterSpacing: '0.8px', marginBottom: 12 }}>
                  1. ENVIRONMENTAL HAZARD (40% WEIGHT)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12, fontFamily: 'monospace' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Sustained Wind:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{selectedResult.hazard.wind_speed_knots} kts</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Peak Wind Gusts:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{selectedResult.hazard.wind_gusts_kph} km/h</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Eyewall Distance:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{selectedResult.hazard.cyclone_proximity_km} km</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Surge Hazard Index:</span>
                    <span style={{ color: '#ef4444', fontWeight: 700 }}>{selectedResult.hazard.storm_surge_risk_score}</span>
                  </div>
                </div>
              </div>

              {/* 2. Exposure */}
              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 6, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', letterSpacing: '0.8px', marginBottom: 12 }}>
                  2. SPATIAL EXPOSURE (30% WEIGHT)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12, fontFamily: 'monospace' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Shoreline Distance:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{selectedResult.exposure.distance_to_coastline_km} km</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Coastal Exposure Score:</span>
                    <span style={{ color: '#f59e0b', fontWeight: 700 }}>{selectedResult.exposure.coastal_exposure_score}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Projected Path Intersect:</span>
                    <span style={{ color: selectedResult.exposure.in_projected_path ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                      {selectedResult.exposure.in_projected_path ? 'YES' : 'NO'}
                    </span>
                  </div>
                </div>
              </div>

              {/* 3. Vulnerability */}
              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 6, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#a855f7', letterSpacing: '0.8px', marginBottom: 12 }}>
                  3. SECTORAL VULNERABILITY (30% WEIGHT)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12, fontFamily: 'monospace' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>SRTM Ground Elevation:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{selectedResult.vulnerability.terrain_elevation_m} m</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Elevation Vulnerability:</span>
                    <span style={{ color: '#a855f7', fontWeight: 700 }}>{selectedResult.vulnerability.elevation_vulnerability_score}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Facility Criticality:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{selectedResult.vulnerability.asset_criticality_score}</span>
                  </div>
                </div>
              </div>

              {/* 4. Potential Impact */}
              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 6, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8', letterSpacing: '0.8px', marginBottom: 12 }}>
                  4. PROJECTED OPERATIONAL IMPACT
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12, fontFamily: 'monospace' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Disruption Probability:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 700 }}>{(selectedResult.impact.service_disruption_probability * 100).toFixed(0)}%</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Isolation Risk:</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{selectedResult.impact.estimated_isolation_risk}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Evacuation Priority:</span>
                    <span style={{ color: '#38bdf8', fontWeight: 700 }}>{selectedResult.impact.evacuation_priority}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Impact Narrative */}
            <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 6, padding: '16px 18px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.8px', marginBottom: 6 }}>
                OPERATIONAL IMPACT SUMMARY
              </div>
              <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.5 }}>
                {selectedResult.impact.consequence_summary}
              </div>
            </div>
          </div>
        ) : (
          <div style={{ color: '#64748b', fontSize: 13 }}>Select an infrastructure asset to inspect its risk drivers.</div>
        )}
      </div>
    </div>
  );
}
