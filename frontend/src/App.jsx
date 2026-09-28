import React, { useState, useEffect, useRef } from 'react';
import gsap from 'gsap';
import ParticleBackground from './components/ParticleBackground';
import MapView from './components/MapView';
import AdvisoryPanel from './components/AdvisoryPanel';
import RiskSummaryPanel from './components/RiskSummaryPanel';
import TimelineStrip from './components/TimelineStrip';
import {
  fetchStormCatalog,
  fetchStormTrack,
  fetchTimestepRisk,
  fetchTimestepAdvisory,
} from './lib/apiClient';

export default function App() {
  const [storms, setStorms] = useState([]);
  const [selectedStormId, setSelectedStormId] = useState('2020139N09086');
  const [trackData, setTrackData] = useState(null);
  const [timesteps, setTimesteps] = useState([]);
  const [currentStepIndex, setCurrentStepIndex] = useState(5);
  const [riskData, setRiskData] = useState(null);
  const [advisoryData, setAdvisoryData] = useState(null);
  const [isLoadingAdvisory, setIsLoadingAdvisory] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [activeLayers, setActiveLayers] = useState({
    heatmap: true, hospitals: true, power: true, roads: true,
  });

  const timerRef = useRef(null);
  const headerRef = useRef(null);

  // GSAP entrance
  useEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(headerRef.current,
        { opacity: 0, y: -10 },
        { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out' }
      );
    }
  }, []);

  // Load storm catalog
  useEffect(() => {
    fetchStormCatalog()
      .then((data) => { if (data?.length) setStorms(data); })
      .catch(() => {
        setStorms([{ storm_id: '2020139N09086', name: 'AMPHAN', year: 2020, basin: 'NI' }]);
      });
  }, []);

  // Load track
  useEffect(() => {
    if (!selectedStormId) return;
    fetchStormTrack(selectedStormId)
      .then((data) => {
        setTrackData(data);
        const pts = data?.features?.filter((f) => f.properties?.feature_type === 'storm_center') || [];
        setTimesteps(pts.map((p) => p.properties));
      })
      .catch(console.error);
  }, [selectedStormId]);

  // Load risk + advisory on step change
  useEffect(() => {
    if (!selectedStormId) return;

    fetchTimestepRisk(selectedStormId, currentStepIndex)
      .then(setRiskData)
      .catch(console.error);

    setIsLoadingAdvisory(true);
    fetchTimestepAdvisory(selectedStormId, currentStepIndex)
      .then(setAdvisoryData)
      .catch(console.error)
      .finally(() => setIsLoadingAdvisory(false));
  }, [selectedStormId, currentStepIndex]);

  // Auto-play
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = setInterval(() => {
        setCurrentStepIndex((prev) => {
          if (prev >= timesteps.length - 1) { setIsPlaying(false); return prev; }
          return prev + 1;
        });
      }, 2200);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isPlaying, timesteps.length]);

  const handleTogglePlay = () => {
    if (currentStepIndex >= timesteps.length - 1) setCurrentStepIndex(0);
    setIsPlaying((p) => !p);
  };

  const currentStep = timesteps[currentStepIndex] || {};

  return (
    <>
      <ParticleBackground />

      <div className="dashboard-grid">
        {/* ── HEADER ── */}
        <header ref={headerRef} className="dashboard-header" style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 20px',
        }}>
          {/* Left: Brand */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{
              fontSize: 14, fontWeight: 800, color: 'var(--text-primary)',
              letterSpacing: '1.5px',
            }}>
              NIVARA
            </span>
            <span style={{ width: 1, height: 16, background: 'var(--border-subtle)' }} />
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500 }}>
              Cyclone Impact & Infrastructure Vulnerability Forecaster
            </span>
          </div>

          {/* Center: Live Storm Context */}
          <div className="mono" style={{
            display: 'flex', alignItems: 'center', gap: 10,
            fontSize: 11, color: 'var(--text-secondary)',
          }}>
            <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
              {storms.find((s) => s.storm_id === selectedStormId)?.name || 'AMPHAN'}
            </span>
            <span style={{ color: 'var(--text-dim)' }}>·</span>
            <span>NI BASIN</span>
            <span style={{ color: 'var(--text-dim)' }}>·</span>
            <span>{currentStep.cyclone_category || 'ESCS'}</span>
            <span style={{ color: 'var(--text-dim)' }}>·</span>
            <span>{currentStep.wind_speed_knots || '—'} kt</span>
            <span style={{ color: 'var(--text-dim)' }}>·</span>
            <span>{currentStep.pressure_mb || '—'} mb</span>
          </div>

          {/* Right: Storm selector */}
          <select
            value={selectedStormId}
            onChange={(e) => setSelectedStormId(e.target.value)}
            className="mono"
            style={{
              padding: '4px 8px',
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 2,
              fontSize: 10,
              cursor: 'pointer',
            }}
          >
            {storms.map((s) => (
              <option key={s.storm_id} value={s.storm_id}>
                {s.name} ({s.year})
              </option>
            ))}
          </select>
        </header>

        {/* ── LEFT PANEL: Advisory ── */}
        <div className="dashboard-left">
          <AdvisoryPanel advisoryData={advisoryData} isLoading={isLoadingAdvisory} />
        </div>

        {/* ── CENTER: Map ── */}
        <div className="dashboard-map">
          <MapView
            trackData={trackData}
            riskData={riskData}
            currentStepIndex={currentStepIndex}
            activeLayers={activeLayers}
            onSelectAsset={setSelectedAsset}
          />
        </div>

        {/* ── RIGHT PANEL: Risk Summary ── */}
        <div className="dashboard-right">
          <RiskSummaryPanel
            riskData={riskData}
            activeLayers={activeLayers}
            onToggleLayer={(id) => setActiveLayers((p) => ({ ...p, [id]: !p[id] }))}
            selectedAsset={selectedAsset}
            onClearAsset={() => setSelectedAsset(null)}
          />
        </div>

        {/* ── BOTTOM: Timeline ── */}
        <div className="dashboard-timeline">
          <TimelineStrip
            timesteps={timesteps}
            currentIndex={currentStepIndex}
            onChangeIndex={setCurrentStepIndex}
            isPlaying={isPlaying}
            onTogglePlay={handleTogglePlay}
          />
        </div>
      </div>
    </>
  );
}
