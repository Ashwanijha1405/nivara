import React, { useEffect, useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { fetchInfrastructure } from '../lib/apiClient';

/**
 * Critical Infrastructure Lifeline Explorer View.
 * Filter by sector, inspect verified OpenStreetMap entities, elevation, and coastal buffers.
 */
export default function InfrastructureView({ onSelectAsset, selectedAsset }) {
  const [assets, setAssets] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeAsset, setActiveAsset] = useState(null);

  useEffect(() => {
    fetchInfrastructure(selectedCategory || null)
      .then((data) => {
        setAssets(data || []);
        if (data?.length && !activeAsset) setActiveAsset(data[0]);
      })
      .catch(console.error);
  }, [selectedCategory]);

  const filtered = assets.filter((a) =>
    a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.district.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '460px 1fr', height: '100%', overflow: 'hidden' }}>
      {/* Left List & Filters */}
      <div style={{ backgroundColor: '#0b111e', borderRight: '1px solid #1e293b', display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Filters */}
        <div style={{ padding: '16px 18px', borderBottom: '1px solid #1e293b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', color: '#94a3b8' }}>
              CRITICAL INFRASTRUCTURE ASSETS
            </span>
            <DataSourceBadge source="OpenStreetMap" status="LIVE" />
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <input
              type="text"
              placeholder="Search facility name or district..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                padding: '6px 10px',
                backgroundColor: '#151e2e',
                border: '1px solid #334155',
                borderRadius: 4,
                color: '#f1f5f9',
                fontSize: 12,
              }}
            />
          </div>

          {/* Sector Chips */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {['', 'hospital', 'power_grid', 'shelter', 'road', 'airport'].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  padding: '3px 8px',
                  borderRadius: 3,
                  fontSize: 10,
                  fontFamily: 'monospace',
                  fontWeight: 600,
                  border: selectedCategory === cat ? '1px solid #38bdf8' : '1px solid #1e293b',
                  backgroundColor: selectedCategory === cat ? '#1e293b' : '#0d1527',
                  color: selectedCategory === cat ? '#38bdf8' : '#94a3b8',
                  cursor: 'pointer',
                }}
              >
                {cat ? cat.toUpperCase().replace('_', ' ') : 'ALL SECTORS'}
              </button>
            ))}
          </div>
        </div>

        {/* Assets List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {filtered.map((item) => {
            const isSelected = activeAsset?.id === item.id;
            return (
              <div
                key={item.id}
                onClick={() => {
                  setActiveAsset(item);
                  onSelectAsset?.(item);
                }}
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
                <div style={{ minWidth: 0, flex: 1, paddingRight: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.name}
                  </div>
                  <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace', marginTop: 2 }}>
                    {item.district} · {item.category.toUpperCase()}
                  </div>
                </div>

                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#38bdf8', fontWeight: 600 }}>
                    {item.elevation_m}m ASL
                  </div>
                  <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#64748b' }}>
                    {item.dist_to_coast_km}km shore
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Asset Dossier */}
      <div style={{ padding: '24px 28px', overflowY: 'auto', backgroundColor: '#070c18' }}>
        {activeAsset ? (
          <div style={{ maxWidth: 800 }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#f1f5f9' }}>
                  {activeAsset.name}
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace', marginTop: 4 }}>
                  {activeAsset.district}, {activeAsset.state} · OSM ID: {activeAsset.id}
                </div>
              </div>

              <DataSourceBadge source="OpenStreetMap" status="LIVE" />
            </div>

            {/* Quick Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>SECTOR</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>
                  {activeAsset.category.toUpperCase()}
                </div>
              </div>

              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>SRTM ELEVATION</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#38bdf8', marginTop: 2 }}>
                  {activeAsset.elevation_m} meters
                </div>
              </div>

              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>COAST DISTANCE</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>
                  {activeAsset.dist_to_coast_km} km
                </div>
              </div>

              <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 4, padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>COORDINATES</div>
                <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#94a3b8', marginTop: 4 }}>
                  {activeAsset.lat.toFixed(4)}, {activeAsset.lon.toFixed(4)}
                </div>
              </div>
            </div>

            {/* Raw OpenStreetMap Tags */}
            <div style={{ backgroundColor: '#0b111e', border: '1px solid #1e293b', borderRadius: 6, padding: '16px 18px', marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.8px', marginBottom: 12 }}>
                VERIFIED OPENSTREETMAP TAGS & ATTRIBUTES
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 14px', fontSize: 11, fontFamily: 'monospace' }}>
                {Object.entries(activeAsset.raw_tags || {}).slice(0, 12).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #162032', paddingBottom: 4 }}>
                    <span style={{ color: '#64748b' }}>{k}:</span>
                    <span style={{ color: '#e2e8f0', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Attribution Note */}
            <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.4 }}>
              Data sourced directly from OpenStreetMap contributors under Open Database License (ODbL). Elevation derived from NASA/USGS SRTM 90m DEM.
            </div>
          </div>
        ) : (
          <div style={{ color: '#64748b', fontSize: 13 }}>Select an infrastructure entity to view details.</div>
        )}
      </div>
    </div>
  );
}
