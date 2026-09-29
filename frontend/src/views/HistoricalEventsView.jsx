import React, { useEffect, useState } from 'react';
import OpenSource3DMap from '../components/OpenSource3DMap';
import DataSourceBadge from '../components/DataSourceBadge';
import { fetchStormCatalog, fetchStormTrack, fetchStormRisk } from '../lib/apiClient';

/**
 * Historical Events Replay View.
 * Verified historical tropical cyclone sequences from NOAA IBTrACS archive.
 */
export default function HistoricalEventsView({ onSelectAsset, selectedAsset }) {
  const [storms, setStorms] = useState([]);
  const [selectedStormId, setSelectedStormId] = useState('2020136N10088');
  const [trackData, setTrackData] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [stepIndex, setStepIndex] = useState(12);

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
        setStepIndex(pts.length > 5 ? Math.floor(pts.length * 0.6) : 0);
      })
      .catch(console.error);
  }, [selectedStormId]);

  useEffect(() => {
    if (!selectedStormId) return;
    fetchStormRisk(selectedStormId, stepIndex)
      .then(setRiskData)
      .catch(console.error);
  }, [selectedStormId, stepIndex]);

  const waypoints = trackData?.features?.filter((f) => f.properties?.feature_type === 'storm_center') || [];
  const currentPoint = waypoints[stepIndex]?.properties || {};
  const stormInfo = storms.find((s) => s.storm_id === selectedStormId) || { name: 'AMPHAN' };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', height: '100%', overflow: 'hidden' }}>
      {/* Left Column: Historical Storms Archive */}
      <div style={{ backgroundColor: '#0b111e', borderRight: '1px solid #1e293b', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ padding: '16px 18px', borderBottom: '1px solid #1e293b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              HISTORICAL CYCLONE ARCHIVE
            </span>
            <DataSourceBadge source="NOAA IBTrACS" status="HISTORICAL" />
          </div>

          <div style={{ fontSize: 14, fontWeight: 800, color: '#f1f5f9' }}>
            Verified Bay of Bengal Landfalls
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            Official post-season re-analysis tracks from World Data Center for Meteorology.
          </div>
        </div>

        {/* Storm Selector Cards */}
        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {storms.map((s) => {
            const isSelected = selectedStormId === s.storm_id;
            return (
              <div
                key={s.storm_id}
                onClick={() => setSelectedStormId(s.storm_id)}
                style={{
                  padding: '12px 14px',
                  backgroundColor: isSelected ? '#1e293b' : '#111827',
                  border: isSelected ? '1px solid #38bdf8' : '1px solid #1e293b',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9' }}>
                    CYCLONE {s.name} ({s.season || s.year})
                  </div>
                  <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#38bdf8', fontWeight: 600 }}>
                    {s.peak_intensity || 'Cyclonic Storm'}
                  </span>
                </div>

                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  Peak: {s.peak_winds_knots || '—'} kts · Landfall: {s.landfall_area || 'Odisha / Bengal'}
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Storm Historical Telemetry */}
        <div style={{ padding: '16px 18px', borderTop: '1px solid #1e293b', backgroundColor: '#0d1527', flex: 1, overflowY: 'auto' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#cbd5e1', marginBottom: 8 }}>
            HISTORICAL TIMESTEP REPLAY
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 14px', fontSize: 11, fontFamily: 'monospace', marginBottom: 14 }}>
            <div>
              <span style={{ color: '#64748b' }}>DATE / TIME (UTC):</span>
              <div style={{ color: '#f1f5f9', fontWeight: 600, marginTop: 2 }}>{currentPoint.timestamp || '—'}</div>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>WIND VELOCITY:</span>
              <div style={{ color: '#f1f5f9', fontWeight: 700, marginTop: 2 }}>{currentPoint.wind_speed_knots || '—'} kts</div>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>CENTRAL PRESSURE:</span>
              <div style={{ color: '#f1f5f9', fontWeight: 700, marginTop: 2 }}>{currentPoint.pressure_mb || '—'} mb</div>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>LANDFALL STATUS:</span>
              <div style={{ color: currentPoint.is_landfall_point ? '#ef4444' : '#22c55e', fontWeight: 700, marginTop: 2 }}>
                {currentPoint.is_landfall_point ? 'LANDFALL ACTIVE' : 'OPEN WATER'}
              </div>
            </div>
          </div>

          {/* Scrubber */}
          <div style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'monospace', color: '#64748b', marginBottom: 4 }}>
              <span>TIMESTEP POSITION</span>
              <span>{stepIndex + 1} / {waypoints.length || 1}</span>
            </div>
            <input
              type="range"
              min={0}
              max={Math.max(0, waypoints.length - 1)}
              value={stepIndex}
              onChange={(e) => setStepIndex(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
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
            lat: currentPoint.lat ? currentPoint.lat + 0.4 : 22.0,
            lon: currentPoint.lon ? currentPoint.lon + 0.4 : 88.0,
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
