import React from 'react';
import { Play, Pause, ChevronLeft, ChevronRight, Wind, AlertCircle } from 'lucide-react';

/**
 * TimelineSlider Component.
 *
 * Scrubber and animation control driving which storm timestep is actively rendered.
 */
export default function TimelineSlider({
  timesteps = [],
  currentIndex = 0,
  onChangeIndex,
  isPlaying = false,
  onTogglePlay,
}) {
  const currentStep = timesteps[currentIndex] || {};
  const total = timesteps.length || 1;
  const isLandfall = currentStep.is_landfall_point || currentIndex === 6;

  const handleStepPrev = () => {
    if (currentIndex > 0) onChangeIndex(currentIndex - 1);
  };

  const handleStepNext = () => {
    if (currentIndex < total - 1) onChangeIndex(currentIndex + 1);
  };

  // Format date if valid ISO
  const formatTime = (isoString) => {
    if (!isoString) return '2020-05-20 06:00 UTC';
    try {
      const d = new Date(isoString);
      return d.toUTCString().replace('GMT', 'UTC');
    } catch {
      return isoString;
    }
  };

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 24,
        left: '50%',
        transform: 'translateX(-50%)',
        width: 'min(92%, 840px)',
        backgroundColor: 'rgba(15, 23, 42, 0.94)',
        backdropFilter: 'blur(12px)',
        padding: '16px 24px',
        borderRadius: '14px',
        boxShadow: '0 20px 35px -5px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.08)',
        zIndex: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      {/* Top row: Controls, Timestep info, Storm metrics */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {/* Playback Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={onTogglePlay}
            title={isPlaying ? 'Pause Replay' : 'Play Timeline'}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '38px',
              height: '38px',
              backgroundColor: isPlaying ? '#ef4444' : '#38bdf8',
              color: '#0f172a',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {isPlaying ? <Pause size={18} fill="#0f172a" /> : <Play size={18} fill="#0f172a" />}
          </button>

          <button
            type="button"
            onClick={handleStepPrev}
            disabled={currentIndex === 0}
            title="Previous Timestep"
            style={{
              padding: '6px 10px',
              backgroundColor: '#1e293b',
              color: currentIndex === 0 ? '#475569' : '#cbd5e1',
              border: '1px solid #334155',
              borderRadius: '6px',
              cursor: currentIndex === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            <ChevronLeft size={16} />
          </button>

          <button
            type="button"
            onClick={handleStepNext}
            disabled={currentIndex >= total - 1}
            title="Next Timestep"
            style={{
              padding: '6px 10px',
              backgroundColor: '#1e293b',
              color: currentIndex >= total - 1 ? '#475569' : '#cbd5e1',
              border: '1px solid #334155',
              borderRadius: '6px',
              cursor: currentIndex >= total - 1 ? 'not-allowed' : 'pointer',
            }}
          >
            <ChevronRight size={16} />
          </button>

          <span style={{ fontSize: '0.825rem', color: '#94a3b8', marginLeft: '6px' }}>
            Timestep <strong style={{ color: '#f8fafc' }}>{currentIndex + 1}</strong> / {total}
          </span>
        </div>

        {/* Center: Landfall indicator */}
        {isLandfall && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid #ef4444',
              borderRadius: '6px',
              color: '#fca5a5',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            <AlertCircle size={14} color="#ef4444" />
            LANDFALL ZONE (SUNDARBANS)
          </div>
        )}

        {/* Right: Timestamp and Wind */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
            {formatTime(currentStep.timestamp)}
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '4px',
              fontSize: '0.75rem',
              color: '#38bdf8',
            }}
          >
            <Wind size={12} />
            <span>
              {currentStep.cyclone_category || 'Super Cyclone'} · {currentStep.wind_speed_knots || 85} kts ({currentStep.wind_speed_kph || 157} km/h)
            </span>
          </div>
        </div>
      </div>

      {/* Slider Bar */}
      <div style={{ position: 'relative', width: '100%', display: 'flex', alignItems: 'center' }}>
        <input
          type="range"
          min={0}
          max={Math.max(0, total - 1)}
          value={currentIndex}
          onChange={(e) => onChangeIndex && onChangeIndex(Number(e.target.value))}
          style={{
            width: '100%',
            height: '6px',
            borderRadius: '4px',
            backgroundColor: '#334155',
            accentColor: '#38bdf8',
            cursor: 'pointer',
            outline: 'none',
          }}
        />
      </div>

      {/* Step notch labels */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.7rem',
          color: '#64748b',
          marginTop: '-4px',
        }}
      >
        <span>t0 (Open Sea)</span>
        <span>t4 (Landfall Approach)</span>
        <span style={{ color: isLandfall ? '#ef4444' : '#64748b', fontWeight: isLandfall ? 700 : 400 }}>
          t6 (Landfall)
        </span>
        <span>t8 (Inland Dissipation)</span>
      </div>
    </div>
  );
}
