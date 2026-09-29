import React, { useEffect, useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { fetchSystemStatus } from '../lib/apiClient';

/**
 * Authoritative Data Sources & Provenance Health Matrix.
 * Displays live connectivity, latency, datasets, and attribution for all external providers.
 */
export default function DataSourcesView() {
  const [statusData, setStatusData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchSystemStatus()
      .then((data) => {
        setStatusData(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load system status:', err);
        setIsLoading(false);
      });
  }, []);

  const sources = statusData?.sources || {};

  return (
    <div style={{ padding: '24px 32px', height: '100%', overflowY: 'auto', backgroundColor: '#070c18' }}>
      <div style={{ maxWidth: 960, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '1px' }}>
            SYSTEM HEALTH & DATA PROVENANCE
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: '#f1f5f9', marginTop: 2 }}>
            Authoritative Geospatial & Meteorological Providers
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
            Strict Data Integrity Policy: Nivara never fabricates or silently substitutes synthetic data for live operations.
          </div>
        </div>

        {/* Source Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {Object.entries(sources).map(([key, item]) => {
            const isConnected = item.status === 'CONNECTED';
            return (
              <div
                key={key}
                style={{
                  backgroundColor: '#0b111e',
                  border: isConnected ? '1px solid #1e293b' : '1px solid #991b1b',
                  borderRadius: 6,
                  padding: '18px 20px',
                  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>
                    {item.display_name}
                  </div>
                  <DataSourceBadge source={key.toUpperCase()} status={item.mode || item.status} />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11, fontFamily: 'monospace', marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>INTEGRATION STATUS:</span>
                    <span style={{ color: isConnected ? '#4ade80' : '#f87171', fontWeight: 700 }}>
                      ● {item.status}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>ROUND-TRIP LATENCY:</span>
                    <span style={{ color: '#e2e8f0' }}>{item.latency_ms} ms</span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>LAST SUCCESS (UTC):</span>
                    <span style={{ color: '#94a3b8' }}>{item.last_success_utc || 'Pending'}</span>
                  </div>

                  {item.last_error && (
                    <div style={{ color: '#f87171', fontSize: 10, marginTop: 4 }}>
                      Diagnostic: {item.last_error}
                    </div>
                  )}
                </div>

                <div style={{ borderTop: '1px solid #162032', paddingTop: 10, fontSize: 10, color: '#64748b', lineHeight: 1.4 }}>
                  {item.attribution}
                </div>
              </div>
            );
          })}
        </div>

        {/* Global Data Integrity Statement */}
        <div
          style={{
            marginTop: 28,
            backgroundColor: '#0d1527',
            border: '1px solid #1e293b',
            borderRadius: 6,
            padding: '16px 20px',
            fontSize: 12,
            color: '#94a3b8',
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8', letterSpacing: '0.8px', marginBottom: 4 }}>
            OFFICIAL ATTRIBUTION & LICENSING COMPLIANCE
          </div>
          All meteorological warnings are derived from the India Meteorological Department (IMD), Ministry of Earth Sciences.
          Historical cyclone best-track sequences originate from NOAA NCEI IBTrACS v04.
          Physical infrastructure data is provided by © OpenStreetMap contributors under the Open Database License (ODbL).
          Digital elevation data is derived from NASA/USGS Shuttle Radar Topography Mission (SRTM 90m DEM).
        </div>
      </div>
    </div>
  );
}
