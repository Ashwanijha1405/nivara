import React from 'react';

/**
 * TimelineStrip — Full-width integrated bottom strip.
 * Compact playback controls, dense timestamp, no decorative elements.
 */
export default function TimelineStrip({
  timesteps = [],
  currentIndex = 0,
  onChangeIndex,
  isPlaying = false,
  onTogglePlay,
}) {
  const total = timesteps.length || 1;
  const step = timesteps[currentIndex] || {};

  const prev = () => { if (currentIndex > 0) onChangeIndex(currentIndex - 1); };
  const next = () => { if (currentIndex < total - 1) onChangeIndex(currentIndex + 1); };

  const fmtTime = (iso) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      const day = d.getUTCDate();
      const mon = d.toLocaleString('en', { month: 'short', timeZone: 'UTC' });
      const h = String(d.getUTCHours()).padStart(2, '0');
      const m = String(d.getUTCMinutes()).padStart(2, '0');
      return `${day} ${mon} 2020, ${h}:${m} UTC`;
    } catch { return iso; }
  };

  const isLandfall = step.is_landfall_point || currentIndex === 6;

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      padding: '0 20px',
      gap: 16,
    }}>
      {/* Playback Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
        <button onClick={prev} disabled={currentIndex === 0} style={btnStyle(currentIndex === 0)}>
          ◀
        </button>
        <button onClick={onTogglePlay} style={{
          ...btnStyle(false),
          width: 32, fontSize: 12,
          background: isPlaying ? '#991b1b' : 'var(--bg-elevated)',
          color: isPlaying ? '#fca5a5' : 'var(--text-secondary)',
        }}>
          {isPlaying ? '■' : '▶'}
        </button>
        <button onClick={next} disabled={currentIndex >= total - 1} style={btnStyle(currentIndex >= total - 1)}>
          ▶
        </button>
      </div>

      {/* Step Counter */}
      <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0, minWidth: 60 }}>
        STEP <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{currentIndex + 1}</span>/{total}
      </div>

      {/* Slider */}
      <div style={{ flex: 1, position: 'relative' }}>
        <input
          type="range"
          min={0}
          max={Math.max(0, total - 1)}
          value={currentIndex}
          onChange={(e) => onChangeIndex?.(Number(e.target.value))}
          style={{ width: '100%' }}
        />
      </div>

      {/* Timestamp & Storm Info */}
      <div style={{ flexShrink: 0, textAlign: 'right' }}>
        <div className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
          {fmtTime(step.timestamp)}
        </div>
        <div className="mono" style={{
          fontSize: 10, color: 'var(--text-dim)',
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8,
        }}>
          <span>{step.cyclone_category || '—'}</span>
          <span>·</span>
          <span>{step.wind_speed_knots || '—'} kt</span>
          <span>·</span>
          <span>{step.pressure_mb || '—'} mb</span>
          {isLandfall && (
            <>
              <span>·</span>
              <span style={{ color: '#dc2626', fontWeight: 700 }}>LANDFALL</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const btnStyle = (disabled) => ({
  width: 28,
  height: 28,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 3,
  color: disabled ? 'var(--text-dim)' : 'var(--text-secondary)',
  fontSize: 10,
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.4 : 1,
});
