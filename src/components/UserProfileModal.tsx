import React from 'react';

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  isOpen,
  onClose
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in">
      <div className="bg-[#ffffff] w-full max-w-md rounded-2xl shadow-xl border border-[#eae7eb] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 bg-[#fbf8fc] border-b border-[#f0edf1] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-[#000000] flex items-center justify-center text-white">
              <span className="material-symbols-outlined text-[18px]">person</span>
            </div>
            <div className="flex flex-col">
              <h2 className="text-sm font-bold text-[#1b1b1e] font-headline">
                Operational Dispatcher Session
              </h2>
              <span className="text-[11px] text-[#45464d] font-mono">
                precinct-id: 14-METRO-CMD
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-[#f0edf1] hover:bg-[#e4e1e6] flex items-center justify-center text-[#45464d] transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-3.5 text-xs">
          <div className="p-3 bg-[#f6f2f7] rounded-xl border border-[#e4e1e6]/60 flex items-center justify-between">
            <div>
              <span className="font-semibold text-[#1b1b1e] block">
                Simulation Engine Mode
              </span>
              <span className="text-[#45464d] text-[11px]">
                Synthetic Bayesian Pattern Engine v1.2
              </span>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-[#dcfce7] text-[#15803d] font-mono font-bold text-[10px]">
              ONLINE
            </span>
          </div>

          <div className="space-y-2 text-[#45464d]">
            <div className="flex items-center justify-between py-1.5 border-b border-[#f0edf1]">
              <span>Active Role</span>
              <span className="font-semibold text-[#1b1b1e]">
                Senior Spatial Analyst
              </span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-[#f0edf1]">
              <span>Access Level</span>
              <span className="font-mono text-[#0051d5] font-semibold">
                Tier-3 Civil Logistics
              </span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-[#f0edf1]">
              <span>Telemetry Feed Sync</span>
              <span className="font-mono text-[#16a34a]">
                Live Ingestion (14 nodes)
              </span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span>Uncertainty Confidence Threshold</span>
              <span className="font-mono text-[#1b1b1e]">95% (p &lt; 0.05)</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 bg-[#fbf8fc] border-t border-[#f0edf1] flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#000000] text-white rounded-lg text-xs font-semibold hover:bg-[#303033] transition-colors cursor-pointer"
          >
            Close Session Info
          </button>
        </div>
      </div>
    </div>
  );
};
