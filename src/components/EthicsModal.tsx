import React from 'react';

interface EthicsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const EthicsModal: React.FC<EthicsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in">
      <div className="bg-[#ffffff] w-full max-w-md rounded-2xl shadow-xl border border-[#eae7eb] overflow-hidden flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="p-4 bg-[#fbf8fc] border-b border-[#f0edf1] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[#0051d5] text-[22px]">
              shield
            </span>
            <div className="flex flex-col">
              <h2 className="text-base font-bold text-[#1b1b1e] font-headline">
                Ethical Governance & Model Limits
              </h2>
              <span className="text-xs text-[#45464d] font-mono">
                Strata Public Safety Protocol v2.4
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

        {/* Modal Content */}
        <div className="p-4 overflow-y-auto space-y-3.5 text-xs text-[#45464d] leading-relaxed">
          <div className="p-3 bg-[#f6f2f7] rounded-xl border border-[#e4e1e6]/60">
            <h3 className="font-bold text-[#1b1b1e] mb-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#0051d5]"></span>
              Logistical Density, Not Individual Prediction
            </h3>
            <p>
              Strata forecasts estimate municipal aggregated incident density across spatial grid units (250m cells). They do <strong>not</strong> predict individual human behavior, likelihood of delinquency, or personal intent.
            </p>
          </div>

          <div className="p-3 bg-[#f6f2f7] rounded-xl border border-[#e4e1e6]/60">
            <h3 className="font-bold text-[#1b1b1e] mb-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#16a34a]"></span>
              Mandatory Human-in-the-Loop Oversight
            </h3>
            <p>
              Statistical projections are operational recommendations designed to optimize dispatch coverage, lighting logistics, and transit staffing. Projections never trigger automated enforcement actions or displace sworn commander discretion.
            </p>
          </div>

          <div className="p-3 bg-[#f6f2f7] rounded-xl border border-[#e4e1e6]/60">
            <h3 className="font-bold text-[#1b1b1e] mb-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#ba1a1a]"></span>
              Explicit Data Exclusions
            </h3>
            <p>
              The ingestion engine enforces hard cryptographic filters. The model has zero access to:
            </p>
            <ul className="list-disc pl-4 mt-1 space-y-0.5">
              <li>Biometric, facial recognition, or license plate telemetry</li>
              <li>Demographic, racial, religious, or socioeconomic indicators</li>
              <li>Individual criminal histories or juvenile records</li>
            </ul>
          </div>

          <div className="p-3 bg-[#f0edf1] rounded-xl border border-[#e4e1e6]/50">
            <h3 className="font-bold text-[#1b1b1e] mb-1">
              Independent Oversight
            </h3>
            <p>
              Audited quarterly by the Civil Computing Governance Committee. Last certified: October 2026.
            </p>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-3 bg-[#fbf8fc] border-t border-[#f0edf1] flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#000000] text-white rounded-lg text-xs font-semibold hover:bg-[#303033] transition-colors cursor-pointer"
          >
            Acknowledge & Close
          </button>
        </div>
      </div>
    </div>
  );
};
