import React from 'react';

interface MapLegendProps {
  heatmapOpacity: number;
  onOpacityChange: (val: number) => void;
  showHeatmap: boolean;
  onToggleHeatmap: () => void;
  showZones: boolean;
  onToggleZones: () => void;
  isSupportedRegion: boolean;
  className?: string;
}

export const MapLegend: React.FC<MapLegendProps> = ({
  heatmapOpacity,
  onOpacityChange,
  showHeatmap,
  onToggleHeatmap,
  showZones,
  onToggleZones,
  isSupportedRegion,
  className = ''
}) => {
  return (
    <div className={`flex flex-col gap-1.5 z-20 ${className}`}>
      {/* Legend & Layer Control HUD */}
      <div className="px-3 py-2 rounded-xl bg-white/95 backdrop-blur-md shadow-md border border-[#e4e1e6] flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Risk Level Badges */}
        <div className="flex items-center gap-3 overflow-x-auto text-nowrap">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#16a34a] flex-shrink-0"></span>
            <span className="font-semibold text-[#1b1b1e]">Lower (&lt;30)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#d97706] flex-shrink-0"></span>
            <span className="font-semibold text-[#1b1b1e]">Moderate (31-65)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#ba1a1a] flex-shrink-0"></span>
            <span className="font-semibold text-[#1b1b1e]">Higher (&gt;65)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#76777d] flex-shrink-0"></span>
            <span className="text-[#45464d]">Sparse</span>
          </div>
          {!isSupportedRegion && (
            <div className="flex items-center gap-1.5 pl-1.5 border-l border-[#e4e1e6]">
              <span className="w-2.5 h-2.5 rounded-full bg-[#94a3b8] flex-shrink-0"></span>
              <span className="text-[#64748b] italic">Unavailable (Not 0)</span>
            </div>
          )}
        </div>

        {/* Quick Overlay Toggles & Opacity */}
        {isSupportedRegion && (
          <div className="flex items-center gap-3 flex-shrink-0 text-[11px] font-mono text-[#45464d]">
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={showHeatmap}
                onChange={onToggleHeatmap}
                className="rounded accent-[#0051d5]"
              />
              <span>Heatmap</span>
            </label>
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={showZones}
                onChange={onToggleZones}
                className="rounded accent-[#0051d5]"
              />
              <span>Zones</span>
            </label>

            {/* Opacity Slider */}
            {showHeatmap && (
              <div className="flex items-center gap-1.5 pl-1 border-l border-[#e4e1e6]">
                <span>Opacity:</span>
                <input
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  value={heatmapOpacity}
                  onChange={(e) => onOpacityChange(parseFloat(e.target.value))}
                  className="w-16 h-1 bg-[#e4e1e6] rounded-lg appearance-none cursor-pointer accent-[#0051d5]"
                  title={`Heatmap Opacity: ${Math.round(heatmapOpacity * 100)}%`}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
