import React from 'react';
import { SECTOR_OPTIONS } from '../data/mockData';
import { SectorOption } from '../types';

interface SectorSelectorModalProps {
  isOpen: boolean;
  selectedSector: SectorOption;
  onSelectSector: (sector: SectorOption) => void;
  onClose: () => void;
}

export const SectorSelectorModal: React.FC<SectorSelectorModalProps> = ({
  isOpen,
  selectedSector,
  onSelectSector,
  onClose
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in">
      <div className="bg-[#ffffff] w-full max-w-md rounded-2xl shadow-xl border border-[#eae7eb] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 bg-[#fbf8fc] border-b border-[#f0edf1] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[#0051d5] text-[20px]">
              near_me
            </span>
            <h2 className="text-sm font-bold text-[#1b1b1e] font-headline">
              Select Operational Sector
            </h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-[#f0edf1] hover:bg-[#e4e1e6] flex items-center justify-center text-[#45464d] transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Sectors list */}
        <div className="p-3 divide-y divide-[#f0edf1] max-h-80 overflow-y-auto">
          {SECTOR_OPTIONS.map((sec) => {
            const isSelected = sec.id === selectedSector.id;
            return (
              <button
                key={sec.id}
                onClick={() => {
                  onSelectSector(sec);
                  onClose();
                }}
                className={`w-full p-3 text-left rounded-xl flex items-center justify-between transition-colors cursor-pointer ${
                  isSelected ? 'bg-[#f0edf1]' : 'hover:bg-[#fbf8fc]'
                }`}
              >
                <div className="flex flex-col min-w-0 pr-2">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-xs text-[#1b1b1e]">
                      {sec.name}
                    </span>
                    <span className="font-mono text-[10px] text-[#45464d] bg-[#e4e1e6] px-1.5 py-0.2 rounded">
                      {sec.code}
                    </span>
                  </div>
                  <span className="text-[11px] text-[#45464d] mt-0.5">
                    {sec.status}
                  </span>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-[11px] font-mono font-medium text-[#0051d5]">
                    {sec.incidentTrend}
                  </span>
                  {isSelected && (
                    <span className="material-symbols-outlined text-[#0051d5] text-[18px]">
                      check
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        <div className="p-3 bg-[#fbf8fc] border-t border-[#f0edf1] text-center text-xs text-[#45464d]">
          Switching sectors reconfigures active GIS grid projections.
        </div>
      </div>
    </div>
  );
};
