import React, { useState } from 'react';
import { MapStyleId, MAP_PROVIDERS } from '../../services/mapProviders';

interface MapLayerSwitcherProps {
  currentStyle: MapStyleId;
  onStyleChange: (styleId: MapStyleId) => void;
  className?: string;
}

export const MapLayerSwitcher: React.FC<MapLayerSwitcherProps> = ({
  currentStyle,
  onStyleChange,
  className = ''
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  const styleIcons: Record<MapStyleId, string> = {
    street: 'map',
    satellite: 'satellite_alt',
    hybrid: 'layers',
    terrain: 'terrain',
    dark: 'dark_mode'
  };

  const styleLabels: Record<MapStyleId, string> = {
    street: 'Street',
    satellite: 'Satellite',
    hybrid: 'Hybrid',
    terrain: 'Terrain',
    dark: 'Dark'
  };

  return (
    <div className={`relative z-20 ${className}`}>
      {/* Floating Toggle Pill / Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/95 backdrop-blur-md shadow-md border border-[#e4e1e6] hover:bg-[#f0edf1] transition-all cursor-pointer text-[#1b1b1e]"
        title="Change Map Style (Street, Satellite, Hybrid, Terrain, Dark)"
      >
        <span className="material-symbols-outlined text-[18px] text-[#0051d5]">
          {styleIcons[currentStyle]}
        </span>
        <span className="text-xs font-semibold">{styleLabels[currentStyle]}</span>
        <span className="material-symbols-outlined text-[16px] text-[#76777d]">
          {isOpen ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {/* Expanded Map Style Grid Modal / Popover */}
      {isOpen && (
        <div className="absolute right-0 top-11 w-64 bg-white/95 backdrop-blur-lg rounded-2xl shadow-xl border border-[#eae7eb] p-2.5 z-50 animate-in fade-in zoom-in-95 flex flex-col gap-2">
          <div className="flex items-center justify-between px-1 pb-1 border-b border-[#f0edf1]">
            <span className="text-[10px] font-mono uppercase text-[#76777d] font-bold tracking-wider">
              Map Basemap Style
            </span>
            <span className="text-[10px] font-mono text-[#0051d5] font-semibold">
              Live Tile Feeds
            </span>
          </div>

          <div className="grid grid-cols-1 gap-1.5">
            {(Object.keys(MAP_PROVIDERS) as MapStyleId[]).map((styleId) => {
              const cfg = MAP_PROVIDERS[styleId];
              const isSelected = currentStyle === styleId;

              return (
                <button
                  key={styleId}
                  onClick={() => {
                    onStyleChange(styleId);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left p-2 rounded-xl flex items-center justify-between transition-all cursor-pointer border ${
                    isSelected
                      ? 'bg-[#eef4ff] border-[#b4c5ff] text-[#0051d5] shadow-xs'
                      : 'hover:bg-[#f8fafc] border-transparent text-[#1b1b1e]'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className={`material-symbols-outlined text-[20px] flex-shrink-0 ${
                        isSelected ? 'text-[#0051d5]' : 'text-[#76777d]'
                      }`}
                    >
                      {styleIcons[styleId]}
                    </span>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold truncate">{cfg.name}</span>
                        {isSelected && (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#0051d5] flex-shrink-0"></span>
                        )}
                      </div>
                      <span className="text-[10px] text-[#76777d] truncate">
                        {cfg.description}
                      </span>
                    </div>
                  </div>

                  {isSelected && (
                    <span className="material-symbols-outlined text-[18px] text-[#0051d5] flex-shrink-0">
                      check
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="p-1.5 rounded-lg bg-[#f8fafc] border border-[#e2e8f0] text-[10px] text-[#64748b] leading-tight">
            High-res satellite and street imagery provided via OpenStreetMap, Esri, and CARTO raster tiles.
          </div>
        </div>
      )}
    </div>
  );
};
