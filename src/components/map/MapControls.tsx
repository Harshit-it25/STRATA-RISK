import React from 'react';

interface MapControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onRecenter: () => void;
  onLocateMe: () => void;
  onToggleFullscreen: () => void;
  onOpenLayersModal?: () => void;
  isFullscreen: boolean;
  isLocating?: boolean;
  className?: string;
}

export const MapControls: React.FC<MapControlsProps> = ({
  onZoomIn,
  onZoomOut,
  onRecenter,
  onLocateMe,
  onToggleFullscreen,
  onOpenLayersModal,
  isFullscreen,
  isLocating = false,
  className = ''
}) => {
  return (
    <div className={`flex flex-col gap-1.5 z-20 ${className}`}>
      {/* Risk Layers Modal Trigger */}
      {onOpenLayersModal && (
        <button
          onClick={onOpenLayersModal}
          className="w-9 h-9 rounded-xl bg-white/95 backdrop-blur-md text-[#1b1b1e] flex items-center justify-center shadow-md hover:bg-[#f0edf1] active:bg-[#e4e1e6] transition-all cursor-pointer border border-[#e4e1e6]"
          title="Toggle Risk Layers Modal"
        >
          <span className="material-symbols-outlined text-[18px]">tune</span>
        </button>
      )}

      {/* Fullscreen Toggle */}
      <button
        onClick={onToggleFullscreen}
        className="w-9 h-9 rounded-xl bg-white/95 backdrop-blur-md text-[#1b1b1e] flex items-center justify-center shadow-md hover:bg-[#f0edf1] active:bg-[#e4e1e6] transition-all cursor-pointer border border-[#e4e1e6]"
        title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Map'}
      >
        <span className="material-symbols-outlined text-[18px]">
          {isFullscreen ? 'fullscreen_exit' : 'fullscreen'}
        </span>
      </button>

      {/* Locate Me (GPS) */}
      <button
        onClick={onLocateMe}
        disabled={isLocating}
        className="w-9 h-9 rounded-xl bg-white/95 backdrop-blur-md text-[#0051d5] flex items-center justify-center shadow-md hover:bg-[#f0edf1] active:bg-[#e4e1e6] transition-all cursor-pointer border border-[#e4e1e6] disabled:opacity-50"
        title="Find My Location"
      >
        <span className={`material-symbols-outlined text-[18px] ${isLocating ? 'animate-spin' : ''}`}>
          {isLocating ? 'sync' : 'my_location'}
        </span>
      </button>

      {/* Recenter / Fit View */}
      <button
        onClick={onRecenter}
        className="w-9 h-9 rounded-xl bg-white/95 backdrop-blur-md text-[#1b1b1e] flex items-center justify-center shadow-md hover:bg-[#f0edf1] active:bg-[#e4e1e6] transition-all cursor-pointer border border-[#e4e1e6]"
        title="Recenter Map View"
      >
        <span className="material-symbols-outlined text-[18px]">center_focus_strong</span>
      </button>

      {/* Zoom In & Out Stack */}
      <div className="flex flex-col rounded-xl overflow-hidden shadow-md border border-[#e4e1e6] bg-white/95 backdrop-blur-md">
        <button
          onClick={onZoomIn}
          className="w-9 h-9 flex items-center justify-center text-[#1b1b1e] hover:bg-[#f0edf1] active:bg-[#e4e1e6] transition-colors cursor-pointer border-b border-[#f0edf1]"
          title="Zoom In"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
        </button>
        <button
          onClick={onZoomOut}
          className="w-9 h-9 flex items-center justify-center text-[#1b1b1e] hover:bg-[#f0edf1] active:bg-[#e4e1e6] transition-colors cursor-pointer"
          title="Zoom Out"
        >
          <span className="material-symbols-outlined text-[18px]">remove</span>
        </button>
      </div>
    </div>
  );
};
