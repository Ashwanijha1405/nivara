import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';

/**
 * AdvisoryPanel — Full left column. Always visible. No collapse. No tabs.
 * Advisory, SMS dispatch, and email directive stacked vertically.
 */
export default function AdvisoryPanel({ advisoryData, isLoading = false }) {
  const panelRef = useRef(null);
  const prevDataRef = useRef(null);

  const advisories = advisoryData?.district_advisories || [];
  const primary = advisories[0] || null;
  const secondary = advisories[1] || null;

  // GSAP entrance animation when advisory data changes
  useEffect(() => {
    if (!primary || !panelRef.current) return;
    if (prevDataRef.current === advisoryData) return;
    prevDataRef.current = advisoryData;

    const items = panelRef.current.querySelectorAll('.adv-animate');
    gsap.fromTo(items,
      { opacity: 0, y: 8 },
      { opacity: 1, y: 0, duration: 0.4, stagger: 0.06, ease: 'power2.out' }
    );
  }, [advisoryData, primary]);

  const chipClass = (level) => {
    const l = (level || '').toUpperCase();
    if (l === 'CRITICAL') return 'risk-chip risk-chip--critical';
    if (l === 'HIGH') return 'risk-chip risk-chip--high';
    if (l === 'MEDIUM') return 'risk-chip risk-chip--medium';
    return 'risk-chip risk-chip--low';
  };

  const borderColor = (level) => {
    const l = (level || '').toUpperCase();
    if (l === 'CRITICAL') return '#dc2626';
    if (l === 'HIGH') return '#d97706';
    return '#ca8a04';
  };

  const renderDistrict = (adv, idx) => {
    if (!adv) return null;
    return (
      <div key={idx} ref={idx === 0 ? panelRef : undefined}>
        {/* District Header */}
        <div className="panel-section adv-animate" style={{ paddingBottom: 10 }}>
          <div className="section-label">
            {idx === 0 ? 'PRIMARY THREAT SECTOR' : 'SECONDARY SECTOR'}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              {adv.district}
            </div>
            <span className={chipClass(adv.risk_level)}>{adv.risk_level}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {adv.state}
          </div>
        </div>

        {/* Headline */}
        <div className="panel-section adv-animate" style={{ paddingTop: 0 }}>
          <div style={{
            padding: '10px 12px',
            backgroundColor: 'var(--bg-inset)',
            borderLeft: `3px solid ${borderColor(adv.risk_level)}`,
            borderRadius: '0 3px 3px 0',
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text-primary)',
            lineHeight: 1.45,
          }}>
            {adv.headline}
          </div>
        </div>

        {/* Hazards */}
        <div className="panel-section adv-animate">
          <div className="section-label" style={{ color: '#991b1b' }}>IDENTIFIED HAZARDS</div>
          <ol style={{
            paddingLeft: 18,
            fontSize: 12,
            color: 'var(--text-secondary)',
            lineHeight: 1.55,
            listStyleType: 'decimal',
          }}>
            {(adv.key_risks || []).map((r, i) => (
              <li key={i} className="adv-animate" style={{ marginBottom: 5 }}>{r}</li>
            ))}
          </ol>
        </div>

        {/* Actions */}
        <div className="panel-section adv-animate">
          <div className="section-label" style={{ color: '#1d4ed8' }}>ANTICIPATORY DIRECTIVES</div>
          <ol style={{
            paddingLeft: 18,
            fontSize: 12,
            color: 'var(--text-secondary)',
            lineHeight: 1.55,
            listStyleType: 'decimal',
          }}>
            {(adv.recommended_actions || []).map((a, i) => (
              <li key={i} className="adv-animate" style={{ marginBottom: 5 }}>{a}</li>
            ))}
          </ol>
        </div>

        {/* SMS Dispatch */}
        {adv.mocked_dispatch?.sms_preview && (
          <div className="panel-section adv-animate">
            <div className="section-label">SMS BROADCAST SIMULATION</div>
            <div style={{
              backgroundColor: 'var(--bg-inset)',
              border: '1px solid var(--border-muted)',
              borderRadius: 3,
              padding: '10px 12px',
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                marginBottom: 6, fontSize: 9, fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.8px',
                color: '#dc2626',
              }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#dc2626' }} />
                NATIONAL EMERGENCY BROADCAST
              </div>
              <p className="mono" style={{
                color: 'var(--text-primary)', lineHeight: 1.45, margin: 0, fontSize: 11,
              }}>
                {adv.mocked_dispatch.sms_preview}
              </p>
              <div className="mono" style={{
                textAlign: 'right', fontSize: 10, color: 'var(--text-dim)', marginTop: 6,
              }}>
                {adv.mocked_dispatch.sms_preview.length}/160
              </div>
            </div>
          </div>
        )}

        {/* Email Directive */}
        {adv.mocked_dispatch?.email_preview && (
          <div className="panel-section adv-animate">
            <div className="section-label">SDMA OPERATIONAL MEMO</div>
            <pre className="mono" style={{
              backgroundColor: 'var(--bg-inset)',
              border: '1px solid var(--border-muted)',
              borderRadius: 3,
              padding: '10px 12px',
              fontSize: 10.5,
              color: 'var(--text-secondary)',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.5,
              maxHeight: 160,
              overflowY: 'auto',
              margin: 0,
            }}>
              {adv.mocked_dispatch.email_preview}
            </pre>
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Panel Title */}
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid var(--border-muted)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            Anticipatory Action Advisory
          </div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 1 }}>
            GEMINI 3.7 FLASH · STRUCTURED OUTPUT
          </div>
        </div>
        {isLoading && (
          <span className="mono" style={{
            fontSize: 10, color: '#d97706',
            padding: '2px 6px',
            border: '1px solid #92400e',
            borderRadius: 2,
          }}>
            ANALYZING
          </span>
        )}
      </div>

      {/* Scrollable Content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {!primary ? (
          <div className="panel-section">
            <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0' }}>
              Awaiting risk analysis for current timestep.
            </p>
          </div>
        ) : (
          <>
            {renderDistrict(primary, 0)}
            {secondary && (
              <div style={{ borderTop: '2px solid var(--border-subtle)' }}>
                {renderDistrict(secondary, 1)}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
