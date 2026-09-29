import React from 'react';

/**
 * Reusable Data Provenance Badge.
 * Transparently answers: WHERE DID THIS DATA COME FROM? WHAT IS ITS STATUS?
 */
export default function DataSourceBadge({
  source = 'IMD',
  status = 'LIVE',
  retrievedAt = null,
  isForecast = false,
  className = '',
}) {
  const statusColors = {
    LIVE: {
      bg: 'rgba(22, 163, 74, 0.15)',
      border: 'rgba(22, 163, 74, 0.4)',
      text: '#4ade80',
      dot: '#22c55e',
    },
    FORECAST: {
      bg: 'rgba(59, 130, 246, 0.15)',
      border: 'rgba(59, 130, 246, 0.4)',
      text: '#60a5fa',
      dot: '#3b82f6',
    },
    HISTORICAL: {
      bg: 'rgba(148, 163, 184, 0.12)',
      border: 'rgba(148, 163, 184, 0.3)',
      text: '#cbd5e1',
      dot: '#94a3b8',
    },
    MODELLED: {
      bg: 'rgba(168, 85, 247, 0.15)',
      border: 'rgba(168, 85, 247, 0.4)',
      text: '#c084fc',
      dot: '#a855f7',
    },
    SCENARIO: {
      bg: 'rgba(234, 88, 12, 0.15)',
      border: 'rgba(234, 88, 12, 0.4)',
      text: '#fb923c',
      dot: '#ea580c',
    },
    UNAVAILABLE: {
      bg: 'rgba(220, 38, 38, 0.15)',
      border: 'rgba(220, 38, 38, 0.4)',
      text: '#f87171',
      dot: '#dc2626',
    },
  };

  const style = statusColors[status.toUpperCase()] || statusColors.MODELLED;

  return (
    <div
      title={retrievedAt ? `Retrieved at: ${retrievedAt}` : undefined}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono tracking-wider font-semibold ${className}`}
      style={{
        backgroundColor: style.bg,
        border: `1px solid ${style.border}`,
        color: style.text,
      }}
    >
      <span
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          backgroundColor: style.dot,
          display: 'inline-block',
        }}
      />
      <span>
        {status} • {source.toUpperCase()}
      </span>
      {isForecast && <span className="opacity-80 font-normal">[FCST]</span>}
    </div>
  );
}
