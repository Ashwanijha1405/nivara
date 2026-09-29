import React, { useEffect, useState, useRef } from 'react';
import OpenSource3DMap from '../components/OpenSource3DMap';
import DataSourceBadge from '../components/DataSourceBadge';
import {
  fetchStormCatalog,
  fetchStormTrack,
  fetchStormRisk,
  fetchStormAdvisory,
} from '../lib/apiClient';

/**
 * Storm Intelligence View.
 * In-depth track analysis, category trends, waypoint scrubber, and grounded Gemini advisory.
 */
export default function StormIntelligenceView({ onSelectAsset, selectedAsset }) {
  const [storms, setStorms] = useState([]);
  const [selectedStormId, setSelectedStormId] = useState('2020136N10088');
  const [trackData, setTrackData] = useState(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(12);
  const [riskData, setRiskData] = useState(null);
  const [advisoryData, setAdvisoryData] = useState(null);
  const [isLoadingAdvisory, setIsLoadingAdvisory] = useState(false);

  useEffect(() => {
    fetchStormCatalog()
      .then((data) => {
        if (data?.length) {
          setStorms(data);
          setSelectedStormId(data[0].storm_id);
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedStormId) return;
    fetchStormTrack(selectedStormId)
      .then((track) => {
        setTrackData(track);
        const pts = track.features?.filter((f) => f.properties?.feature_type === 'storm_center') || [];
        const defaultStep = pts.length > 5 ? Math.floor(pts.length * 0.6) : 0;
        setCurrentStepIndex(defaultStep);
      })
      .catch(console.error);
  }, [selectedStormId]);

  useEffect(() => {
    if (!selectedStormId) return;
    fetchStormRisk(selectedStormId, currentStepIndex)
      .then(setRiskData)
      .catch(console.error);

    setIsLoadingAdvisory(true);
    fetchStormAdvisory(selectedStormId, currentStepIndex)
      .then(setAdvisoryData)
      .catch(console.error)
      .finally(() => setIsLoadingAdvisory(false));
  }, [selectedStormId, currentStepIndex]);

  const waypoints = trackData?.features?.filter((f) => f.properties?.feature_type === 'storm_center') || [];
  const currentPoint = waypoints[currentStepIndex]?.properties || {};
  const currentStorm = storms.find((s) => s.storm_id === selectedStormId) || { name: 'AMPHAN' };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', height: '100%', overflow: 'hidden' }}>
      {/* Left Sidebar: Storm Details & Advisory */}
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
        {/* Storm Selector Header */}
        <div style={{ padding: '16px 18px', borderBottom: '1px solid #1e293b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              STORM INTELLIGENCE ARCHIVE
            </span>
            <DataSourceBadge source="NOAA IBTrACS" status="HISTORICAL" />
          </div>

          <select
            value={selectedStormId}
            onChange={(e) => setSelectedStormId(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 10px',
              backgroundColor: '#151e2e',
              border: '1px solid #334155',
              borderRadius: 4,
              color: '#f1f5f9',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {storms.map((s) => (
              <option key={s.storm_id} value={s.storm_id}>
                {s.name} ({s.season || s.year}) · {s.peak_intensity || 'Cyclonic Storm'}
              </option>
            ))}
          </select>
        </div>

        {/* Current Timestep Telemetry */}
        <div style={{ padding: '14px 18px', borderBottom: '1px solid #1e293b', backgroundColor: '#0d1527' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', marginBottom: 4 }}>
            {currentPoint.cyclone_category || 'Super Cyclonic Storm'}
          </div>
          <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#94a3b8', marginBottom: 8 }}>
            {currentPoint.timestamp || 'Valid Time Horizon'}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', fontSize: 11, fontFamily: 'monospace' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>WIND:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 700 }}>{currentPoint.wind_speed_knots || '—'} kts</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>PRESSURE:</span>
              <span style={{ color: '#f1f5f9', fontWeight: 700 }}>{currentPoint.pressure_mb || '—'} mb</span>
            </div>
          </div>
        </div>

        {/* Grounded Gemini Advisory */}
        <div style={{ flex: 1, padding: '16px 18px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              GROUNDED OPERATIONAL ADVISORY
            </span>
            <DataSourceBadge source="Gemini 3.7 Flash" status="MODELLED" />
          </div>

          {isLoadingAdvisory ? (
            <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace', padding: '20px 0', textAlign: 'center' }}>
              Synthesizing grounded district advisory...
            </div>
          ) : advisoryData?.advisories?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {advisoryData.advisories.map((adv, i) => (
                <div key={i} style={{ backgroundColor: '#151e2e', borderRadius: 4, padding: '12px 14px', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#38bdf8', marginBottom: 2 }}>
                    {adv.district}, {adv.state}
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#f1f5f9', marginBottom: 6 }}>
                    {adv.headline}
                  </div>
                  <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 6, lineHeight: 1.4 }}>
                    {adv.grounded_hazards?.[0]}
                  </div>
                  <div style={{ fontSize: 10, color: '#4ade80', lineHeight: 1.4 }}>
                    • {adv.actionable_directives?.[0]}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 11, color: '#64748b' }}>No advisory directives available for this timestep.</div>
          )}
        </div>

        {/* Temporal Scrubber Control */}
        <div style={{ padding: '14px 18px', borderTop: '1px solid #1e293b', backgroundColor: '#0d1527' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'monospace', marginBottom: 6 }}>
            <span style={{ color: '#64748b' }}>TIMESTEP SCRUBBER</span>
            <span style={{ color: '#f1f5f9', fontWeight: 700 }}>
              {currentStepIndex + 1} / {waypoints.length || 1}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={Math.max(0, waypoints.length - 1)}
            value={currentStepIndex}
            onChange={(e) => setCurrentStepIndex(Number(e.target.value))}
            style={{ width: '100%', cursor: 'pointer' }}
          />
        </div>
      </div>

      {/* Right Map Canvas */}
      <div style={{ height: '100%', position: 'relative' }}>
        <OpenSource3DMap
          trackData={trackData}
          infrastructure={riskData?.assets?.map((a) => ({
            id: a.asset_id,
            name: a.asset_name,
            category: a.category,
            lat: currentPoint.lat ? currentPoint.lat + 0.5 : 22.0,
            lon: currentPoint.lon ? currentPoint.lon + 0.5 : 88.0,
            elevation_m: a.vulnerability.terrain_elevation_m,
            modelled_risk: a.modelled_risk_score,
          })) || []}
          onSelectAsset={onSelectAsset}
          selectedAsset={selectedAsset}
          activeLayers={{ track: true, infrastructure: true, hazards: true }}
        />
      </div>
    </div>
  );
}
