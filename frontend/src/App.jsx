import React, { useState, useEffect } from 'react';
import LiveOperationsView from './views/LiveOperationsView';
import StormIntelligenceView from './views/StormIntelligenceView';
import RiskExposureView from './views/RiskExposureView';
import InfrastructureView from './views/InfrastructureView';
import ScenarioSimulatorView from './views/ScenarioSimulatorView';
import HistoricalEventsView from './views/HistoricalEventsView';
import ReportsView from './views/ReportsView';
import DataSourcesView from './views/DataSourcesView';
import DataSourceBadge from './components/DataSourceBadge';
import { fetchSystemStatus } from './lib/apiClient';

const NAV_TABS = [
  { id: 'live', label: 'LIVE OPERATIONS' },
  { id: 'storms', label: 'STORM INTELLIGENCE' },
  { id: 'risk', label: 'RISK & EXPOSURE' },
  { id: 'infrastructure', label: 'INFRASTRUCTURE' },
  { id: 'simulation', label: 'SCENARIO SIMULATOR' },
  { id: 'history', label: 'HISTORICAL EVENTS' },
  { id: 'reports', label: 'REPORTS' },
  { id: 'data', label: 'DATA & SOURCES' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('live');
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [currentTimeUTC, setCurrentTimeUTC] = useState('');

  // Clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTimeUTC(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // System status polling
  useEffect(() => {
    fetchSystemStatus()
      .then(setSystemStatus)
      .catch(console.error);
  }, []);

  return (
    <div className="app-container">
      {/* ── TOP OPERATIONAL COMMAND BAR ── */}
      <header className="app-topbar">
        {/* Brand & Subtitle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 900, letterSpacing: '1.8px', color: '#f8fafc' }}>
              NIVARA
            </span>
            <span style={{ fontSize: 10, color: '#38bdf8', fontWeight: 700, letterSpacing: '0.8px' }}>
              DISASTER INTELLIGENCE
            </span>
          </div>

          <span style={{ width: 1, height: 18, background: '#1e293b' }} />

          {/* Operational Status Pill */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '2px 8px',
              borderRadius: 3,
              backgroundColor: 'rgba(22, 163, 74, 0.15)',
              border: '1px solid rgba(22, 163, 74, 0.4)',
              color: '#86efac',
              fontSize: 10,
              fontFamily: 'monospace',
              fontWeight: 700,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                backgroundColor: '#22c55e',
                boxShadow: '0 0 8px #22c55e',
              }}
            />
            LIVE OPERATIONS ACTIVE
          </div>
        </div>

        {/* Primary Navigation Tabs */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {NAV_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`nav-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Telemetry & Time */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontFamily: 'monospace', fontSize: 11 }}>
          <span style={{ color: '#94a3b8' }}>{currentTimeUTC}</span>
          <DataSourceBadge source="IMD" status="LIVE" />
        </div>
      </header>

      {/* ── MAIN PRODUCT CONTENT VIEWPORT ── */}
      <main style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {activeTab === 'live' && (
          <LiveOperationsView onSelectAsset={setSelectedAsset} selectedAsset={selectedAsset} />
        )}
        {activeTab === 'storms' && (
          <StormIntelligenceView onSelectAsset={setSelectedAsset} selectedAsset={selectedAsset} />
        )}
        {activeTab === 'risk' && (
          <RiskExposureView onSelectAsset={setSelectedAsset} selectedAsset={selectedAsset} />
        )}
        {activeTab === 'infrastructure' && (
          <InfrastructureView onSelectAsset={setSelectedAsset} selectedAsset={selectedAsset} />
        )}
        {activeTab === 'simulation' && (
          <ScenarioSimulatorView onSelectAsset={setSelectedAsset} />
        )}
        {activeTab === 'history' && (
          <HistoricalEventsView onSelectAsset={setSelectedAsset} selectedAsset={selectedAsset} />
        )}
        {activeTab === 'reports' && <ReportsView />}
        {activeTab === 'data' && <DataSourcesView />}

        {/* Global Asset Detail Modal/Drawer */}
        {selectedAsset && (
          <div
            style={{
              position: 'absolute',
              top: 16,
              right: 16,
              width: 360,
              backgroundColor: '#0b111e',
              border: '1px solid #1e293b',
              borderRadius: 6,
              padding: '16px 18px',
              boxShadow: '0 12px 36px rgba(0, 0, 0, 0.7)',
              zIndex: 60,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
              <div>
                <span style={{ fontSize: 10, fontWeight: 700, color: '#38bdf8', letterSpacing: '0.8px' }}>
                  FACILITY INSPECTOR
                </span>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>
                  {selectedAsset.name}
                </div>
              </div>
              <button
                onClick={() => setSelectedAsset(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  fontSize: 14,
                  cursor: 'pointer',
                  padding: '2px 6px',
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11, fontFamily: 'monospace', marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>CATEGORY:</span>
                <span style={{ color: '#f1f5f9' }}>{selectedAsset.category?.toUpperCase() || 'INFRASTRUCTURE'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>DISTRICT:</span>
                <span style={{ color: '#f1f5f9' }}>{selectedAsset.district || 'Coastal Zone'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>SRTM ELEVATION:</span>
                <span style={{ color: '#38bdf8' }}>{selectedAsset.elevation_m || 5.0}m</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>SHORE DISTANCE:</span>
                <span style={{ color: '#f1f5f9' }}>{selectedAsset.dist_to_coast_km || '—'}km</span>
              </div>
              {selectedAsset.modelled_risk !== undefined && (
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 6, borderTop: '1px solid #1e293b' }}>
                  <span style={{ color: '#64748b' }}>MODELLED RISK:</span>
                  <span style={{ color: '#ef4444', fontWeight: 800 }}>{Number(selectedAsset.modelled_risk).toFixed(2)}</span>
                </div>
              )}
            </div>

            <div style={{ fontSize: 10, color: '#64748b', borderTop: '1px solid #162032', paddingTop: 8 }}>
              Source: OpenStreetMap Contributors (ODbL) · SRTM 90m DEM
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
