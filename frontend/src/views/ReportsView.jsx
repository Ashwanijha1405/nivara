import React, { useEffect, useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { fetchSituationReport } from '../lib/apiClient';

/**
 * Operational Reports View.
 * Generates official Situation Reports (SitRep), Infrastructure Risk Briefings,
 * and exportable documentation for disaster management officers.
 */
export default function ReportsView() {
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchSituationReport()
      .then((data) => {
        setReport(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load report:', err);
        setIsLoading(false);
      });
  }, []);

  const handleCopy = () => {
    if (report?.markdown_content) {
      navigator.clipboard.writeText(report.markdown_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div style={{ padding: '24px 32px', height: '100%', overflowY: 'auto', backgroundColor: '#070c18' }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        {/* Header Actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '1px' }}>
              OFFICIAL DISASTER MANAGEMENT BRIEFINGS
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#f1f5f9', marginTop: 2 }}>
              Automated Situation Report (SitRep)
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={handleCopy}
              style={{
                padding: '6px 14px',
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 4,
                color: '#f1f5f9',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {copied ? 'COPIED TO CLIPBOARD' : 'COPY MARKDOWN'}
            </button>
            <button
              onClick={() => window.print()}
              style={{
                padding: '6px 14px',
                backgroundColor: '#0284c7',
                border: 'none',
                borderRadius: 4,
                color: '#ffffff',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              PRINT SITREP
            </button>
          </div>
        </div>

        {/* Report Paper Container */}
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b' }}>
            Compiling operational SitRep from live sources...
          </div>
        ) : report ? (
          <div
            style={{
              backgroundColor: '#0b111e',
              border: '1px solid #1e293b',
              borderRadius: 6,
              padding: '28px 32px',
              boxShadow: '0 12px 36px rgba(0, 0, 0, 0.6)',
            }}
          >
            {/* Report Header Metadata */}
            <div style={{ borderBottom: '2px solid #1e293b', paddingBottom: 16, marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: '#f1f5f9' }}>
                  {report.report_title}
                </span>
                <DataSourceBadge source="Nivara SitRep Engine" status="LIVE" />
              </div>
              <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#94a3b8', marginTop: 4 }}>
                Report ID: {report.report_id} · Generated: {report.generated_at_utc} · Classification: {report.classification}
              </div>
            </div>

            {/* Markdown Body Rendered */}
            <div style={{ color: '#cbd5e1', fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap', fontFamily: 'Inter, sans-serif' }}>
              {report.markdown_content}
            </div>

            {/* Immediate Action Checklist */}
            <div style={{ marginTop: 24, paddingTop: 18, borderTop: '1px solid #1e293b' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', letterSpacing: '0.8px', marginBottom: 10 }}>
                IMMEDIATE ANTICIPATORY ACTIONS (SDMA CHECKLIST)
              </div>
              <ul style={{ paddingLeft: 18, fontSize: 12, color: '#e2e8f0', lineHeight: 1.6 }}>
                {report.recommended_immediate_actions.map((act, i) => (
                  <li key={i}>{act}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div style={{ color: '#ef4444' }}>Failed to generate report.</div>
        )}
      </div>
    </div>
  );
}
