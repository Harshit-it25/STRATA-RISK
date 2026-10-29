import React from 'react';
import { OverlayLayers } from '../types';

interface LayersModalProps {
  isOpen: boolean;
  layers: OverlayLayers;
  onToggleLayer: (layerKey: keyof OverlayLayers) => void;
  onClose: () => void;
}

export const LayersModal: React.FC<LayersModalProps> = ({
  isOpen,
  layers,
  onToggleLayer,
  onClose
}) => {
  if (!isOpen) return null;

  const layerItems: { key: keyof OverlayLayers; label: string; desc: string; icon: string }[] = [
    {
      key: 'densityHeatmap',
      label: 'Density Heatmap Dispersion',
      desc: 'Gaussian kernel spatial probability density contours',
      icon: 'blur_on'
    },
    {
      key: 'transitArteries',
      label: 'Primary Arterial Avenues',
      desc: 'Major thoroughfares, street label anchors, and rapid transit lines',
      icon: 'alt_route'
    },
    {
      key: 'sensorNodes',
      label: 'Precinct Telemetry Nodes',
      desc: 'Fixed acoustic, optical, and turnstile telemetry beacons',
      icon: 'sensors'
    },
    {
      key: 'confidenceBands',
      label: '95% Bayesian Confidence Intervals',
      desc: 'Visual bounding polygon error margins (±9 CI)',
      icon: 'all_inclusive'
    },
    {
      key: 'topographicGrid',
      label: '250m Spatial Carto Grid',
      desc: 'Cartographic reference coordinate intersections',
      icon: 'grid_4x4'
    }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in">
      <div className="bg-[#ffffff] w-full max-w-md rounded-2xl shadow-xl border border-[#eae7eb] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 bg-[#fbf8fc] border-b border-[#f0edf1] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[#0051d5] text-[20px]">
              layers
            </span>
            <h2 className="text-sm font-bold text-[#1b1b1e] font-headline">
              Active Map Overlay Layers
            </h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-[#f0edf1] hover:bg-[#e4e1e6] flex items-center justify-center text-[#45464d] transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Layer Toggles */}
        <div className="p-3 divide-y divide-[#f0edf1] max-h-80 overflow-y-auto">
          {layerItems.map((item) => {
            const isEnabled = layers[item.key];
            return (
              <div
                key={item.key}
                onClick={() => onToggleLayer(item.key)}
                className="py-3 px-2 flex items-center justify-between gap-3 hover:bg-[#fbf8fc] rounded-lg cursor-pointer transition-colors"
              >
                <div className="flex items-start gap-2.5 min-w-0">
                  <span className="material-symbols-outlined text-[20px] text-[#45464d] mt-0.5 flex-shrink-0">
                    {item.icon}
                  </span>
                  <div className="flex flex-col">
                    <span className="text-xs font-semibold text-[#1b1b1e]">
                      {item.label}
                    </span>
                    <span className="text-[11px] text-[#45464d] leading-snug">
                      {item.desc}
                    </span>
                  </div>
                </div>

                {/* Switch indicator */}
                <div
                  className={`w-10 h-6 flex items-center rounded-full p-1 transition-colors flex-shrink-0 ${
                    isEnabled ? 'bg-[#0051d5]' : 'bg-[#c6c6cd]'
                  }`}
                >
                  <div
                    className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
                      isEnabled ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-3 bg-[#fbf8fc] border-t border-[#f0edf1] flex items-center justify-between">
          <span className="text-[11px] text-[#45464d] font-mono">
            {Object.values(layers).filter(Boolean).length} layers active
          </span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 bg-[#000000] text-white rounded-lg text-xs font-semibold hover:bg-[#303033] transition-colors cursor-pointer"
          >
            Apply & View
          </button>
        </div>
      </div>
    </div>
  );
};
