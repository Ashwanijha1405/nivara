import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';

/**
 * RiskSummaryPanel — Right column.
 * Risk distribution, top-5 impacted table, layer controls, asset inspector.
 */
export default function RiskSummaryPanel({
  riskData,
  activeLayers,
  onToggleLayer,
  selectedAsset,
  onClearAsset,
}) {
  const panelRef = useRef(null);
  const prevFeaturesRef = useRef(null);

  const features = riskData?.features || [];
  const props = riskData?.properties || {};

  // Count by risk level
  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  const typeCounts = { hospital: 0, power_substation: 0, power_station: 0, road_arterial: 0, shelter: 0 };
  features.forEach((f) => {
    const p = f.properties;
    const lvl = p.risk_level;
    if (counts[lvl] !== undefined) counts[lvl]++;
    if (typeCounts[p.infra_type] !== undefined) typeCounts[p.infra_type]++;
  });

  const total = features.length;
  const top5 = features.slice(0, 5);

  // GSAP animation on data change
  useEffect(() => {
    if (!panelRef.current || features.length === 0) return;
    if (prevFeaturesRef.current === features) return;
    prevFeaturesRef.current = features;

    const items = panelRef.current.querySelectorAll('.rs-animate');
    gsap.fromTo(items,
      { opacity: 0, x: 6 },
      { opacity: 1, x: 0, duration: 0.35, stagger: 0.04, ease: 'power2.out' }
    );
  }, [features]);

  const barWidth = (count) => {
    if (total === 0) return '0%';
    return `${Math.max(4, (count / total) * 100)}%`;
  };

  const riskColors = {
    CRITICAL: { bar: '#dc2626', text: '#fca5a5' },
    HIGH: { bar: '#d97706', text: '#fcd34d' },
    MEDIUM: { bar: '#ca8a04', text: '#fde68a' },
    LOW: { bar: '#16a34a', text: '#86efac' },
  };

  const chipClass = (level) => {
    const l = (level || '').toUpperCase();
    return `risk-chip risk-chip--${l.toLowerCase()}`;
  };

  return (
    <div ref={panelRef} style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Panel Header */}
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid var(--border-muted)',
        flexShrink: 0,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
          Situation Intelligence
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 1 }}>
          {total} ASSETS EVALUATED · STEP {props.step_index ?? '—'}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {/* Risk Distribution */}
        <div className="panel-section rs-animate">
          <div className="section-label">RISK DISTRIBUTION</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(counts).map(([level, count]) => (
              <div key={level} className="rs-animate" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="mono" style={{
                  width: 60, fontSize: 10, color: riskColors[level].text, fontWeight: 600,
                }}>
                  {level}
                </span>
                <div style={{
                  flex: 1, height: 6, backgroundColor: 'var(--bg-inset)', borderRadius: 1,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    width: barWidth(count),
                    height: '100%',
                    backgroundColor: riskColors[level].bar,
                    borderRadius: 1,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
                <span className="mono" style={{
                  width: 28, textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600,
                }}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Top 5 Impacted */}
        <div className="panel-section rs-animate">
          <div className="section-label">HIGHEST RISK ASSETS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {top5.map((f, i) => {
              const p = f.properties;
              return (
                <div
                  key={p.id}
                  className="rs-animate"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '6px 8px',
                    backgroundColor: i % 2 === 0 ? 'var(--bg-inset)' : 'transparent',
                    borderRadius: 2,
                    cursor: 'pointer',
                  }}
                  onClick={() => onClearAsset?.()} // Could highlight on map
                >
                  <span className="mono" style={{
                    fontSize: 10, color: 'var(--text-dim)', width: 14, flexShrink: 0,
                  }}>
                    {i + 1}.
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 11, fontWeight: 600, color: 'var(--text-primary)',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                      {p.name}
                    </div>
                    <div className="mono" style={{ fontSize: 9, color: 'var(--text-dim)' }}>
                      {p.district} · {p.infra_type}
                    </div>
                  </div>
                  <span className="mono" style={{
                    fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', flexShrink: 0,
                  }}>
                    {Number(p.risk_score).toFixed(2)}
                  </span>
                  <span className={chipClass(p.risk_level)} style={{ flexShrink: 0 }}>
                    {p.risk_level}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Layer Controls */}
        <div className="panel-section rs-animate">
          <div className="section-label">LAYER CONTROLS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[
              { id: 'heatmap', label: 'Surge Risk Heatmap', count: null },
              { id: 'hospitals', label: 'Hospitals & Medical', count: typeCounts.hospital },
              { id: 'power', label: 'Power Grid', count: typeCounts.power_substation + typeCounts.power_station },
              { id: 'roads', label: 'Arterial Routes & Shelters', count: typeCounts.road_arterial + typeCounts.shelter },
            ].map((layer) => (
              <label
                key={layer.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  fontSize: 11, color: 'var(--text-secondary)', cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={Boolean(activeLayers[layer.id])}
                  onChange={() => onToggleLayer?.(layer.id)}
                  style={{ accentColor: '#6b7280', width: 13, height: 13, cursor: 'pointer' }}
                />
                <span style={{ flex: 1 }}>{layer.label}</span>
                {layer.count !== null && (
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                    {layer.count}
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>

        {/* Asset Inspector */}
        {selectedAsset && (
          <div className="panel-section rs-animate" style={{
            borderTop: '2px solid var(--border-subtle)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="section-label" style={{ marginBottom: 0 }}>ASSET DETAIL</div>
              <button
                onClick={() => onClearAsset?.()}
                style={{
                  background: 'none', border: 'none', color: 'var(--text-dim)',
                  fontSize: 10, cursor: 'pointer', padding: '2px 6px',
                }}
              >
                CLOSE
              </button>
            </div>

            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                {selectedAsset.name}
              </div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>
                {selectedAsset.district} · {selectedAsset.state} · {selectedAsset.infra_type}
              </div>
            </div>

            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border-muted)',
            }}>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Composite Risk:</span>
              <span className="mono" style={{
                fontSize: 14, fontWeight: 800,
                color: Number(selectedAsset.risk_score) >= 0.75 ? '#dc2626' : '#d97706',
              }}>
                {Number(selectedAsset.risk_score).toFixed(2)}
              </span>
            </div>

            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px',
              marginTop: 8, fontSize: 10,
            }}>
              {[
                ['Elevation', `${selectedAsset.elevation_m}m`],
                ['Coast Dist', `${selectedAsset.dist_to_coast_km}km`],
                ['Track Dist', `${selectedAsset.dist_to_track_km}km`],
                ['Land Cover', selectedAsset.land_cover_class],
              ].map(([label, val]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-dim)' }}>{label}</span>
                  <span className="mono" style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{val}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
