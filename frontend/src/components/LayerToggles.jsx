import React from 'react';
import { Layers, Activity, Zap, Navigation, Flame } from 'lucide-react';

/**
 * LayerToggles Component.
 *
 * Controls visibility of MapLibre map layers and displays risk legend.
 */
export default function LayerToggles({
  activeLayers = {
    heatmap: true,
    hospitals: true,
    power: true,
    roads: true,
  },
  onToggleLayer,
}) {
  const layers = [
    { id: 'heatmap', label: 'Surge Risk Heatmap', color: '#f97316', icon: Flame },
    { id: 'hospitals', label: 'Hospitals & Medical', color: '#ef4444', icon: Activity },
    { id: 'power', label: 'Power Grid Substations', color: '#eab308', icon: Zap },
    { id: 'roads', label: 'Arterial Evacuation Routes', color: '#38bdf8', icon: Navigation },
  ];

  return (
    <div
      style={{
        position: 'absolute',
        top: 24,
        right: 24,
        backgroundColor: 'rgba(15, 23, 42, 0.92)',
        backdropFilter: 'blur(12px)',
        padding: '16px',
        borderRadius: '12px',
        border: '1px solid #334155',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
        zIndex: 20,
        minWidth: '230px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
        <Layers size={16} color="#38bdf8" />
        <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
          Map Layers
        </h3>
      </div>

      {/* Layer checkboxes */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {layers.map((layer) => {
          const Icon = layer.icon;
          return (
            <label
              key={layer.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '0.8rem',
                color: '#cbd5e1',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <input
                type="checkbox"
                checked={Boolean(activeLayers[layer.id])}
                onChange={() => onToggleLayer && onToggleLayer(layer.id)}
                style={{ accentColor: layer.color, cursor: 'pointer' }}
              />
              <Icon size={14} color={layer.color} />
              <span>{layer.label}</span>
            </label>
          );
        })}
      </div>

      {/* Risk Legend */}
      <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #334155' }}>
        <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
          Risk Classification
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.725rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }} />
            <span style={{ color: '#fca5a5' }}>Critical (&ge; 0.80)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#f97316' }} />
            <span style={{ color: '#fdba74' }}>High (0.60 – 0.79)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#eab308' }} />
            <span style={{ color: '#fde047' }}>Medium (0.35 – 0.59)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
            <span style={{ color: '#86efac' }}>Low (&lt; 0.35)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
