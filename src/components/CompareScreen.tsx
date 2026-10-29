import React, { useState } from 'react';
import { useBackend } from '../context/BackendContext';

export const CompareScreen: React.FC = () => {
  const { timeline, isBackendOnline } = useBackend();
  const [timeAIdx, setTimeAIdx] = useState<number>(1); // 12:00 Midday
  const [timeBIdx, setTimeBIdx] = useState<number>(3); // 20:00 Peak

  const safeTimeAIdx = Math.min(timeAIdx, timeline.length - 1);
  const safeTimeBIdx = Math.min(timeBIdx, timeline.length - 1);

  const timeA = timeline[safeTimeAIdx] || timeline[0];
  const timeB = timeline[safeTimeBIdx] || timeline[0];

  const zoneKeys: ('market' | 'central' | 'riverside' | 'east')[] = [
    'market',
    'central',
    'riverside',
    'east'
  ];

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pb-24 pt-3 gap-4">
      {/* Header Context Area */}
      <div className="flex flex-col gap-1.5 mt-1">
        <div className="inline-flex items-center gap-1.5 self-start px-2 py-0.5 rounded-full bg-[#f0edf1] text-[#45464d] text-xs font-mono">
          <span className={`w-1.5 h-1.5 rounded-full ${isBackendOnline ? 'bg-[#16a34a]' : 'bg-[#0051d5]'}`}></span>
          <span>
            {isBackendOnline ? 'Live API Temporal Comparison' : 'Temporal & Cross-Sector Comparison'}
          </span>
        </div>
        <div className="flex flex-col gap-1 mt-1">
          <h1 className="text-2xl font-bold tracking-tight text-[#1b1b1e] font-headline">
            Variance Compare
          </h1>
          <p className="text-sm text-[#45464d] leading-relaxed">
            Evaluate delta shifts between operational shifts and historical temporal baselines.
          </p>
        </div>
      </div>

      {/* Interval Selector Cards */}
      <div className="grid grid-cols-2 gap-2.5">
        {/* Interval A */}
        <div className="bg-[#ffffff] p-3 rounded-xl border border-[#eae7eb] shadow-xs flex flex-col gap-2">
          <span className="text-[10px] font-mono text-[#45464d] uppercase font-semibold">
            Baseline Window (A)
          </span>
          <select
            value={safeTimeAIdx}
            onChange={(e) => setTimeAIdx(Number(e.target.value))}
            className="w-full text-xs font-semibold text-[#1b1b1e] bg-[#f0edf1] p-2 rounded-lg border border-[#e4e1e6] focus:outline-none focus:ring-1 focus:ring-[#0051d5]"
          >
            {timeline.map((t, idx) => (
              <option key={t.hour} value={idx}>
                {t.hour} - {t.sublabel}
              </option>
            ))}
          </select>
          <span className="text-[11px] text-[#45464d] font-mono">
            {timeA?.label}
          </span>
        </div>

        {/* Interval B */}
        <div className="bg-[#ffffff] p-3 rounded-xl border border-[#eae7eb] shadow-xs flex flex-col gap-2">
          <span className="text-[10px] font-mono text-[#0051d5] uppercase font-semibold">
            Comparison Window (B)
          </span>
          <select
            value={safeTimeBIdx}
            onChange={(e) => setTimeBIdx(Number(e.target.value))}
            className="w-full text-xs font-semibold text-[#1b1b1e] bg-[#f0edf1] p-2 rounded-lg border border-[#e4e1e6] focus:outline-none focus:ring-1 focus:ring-[#0051d5]"
          >
            {timeline.map((t, idx) => (
              <option key={t.hour} value={idx}>
                {t.hour} - {t.sublabel}
              </option>
            ))}
          </select>
          <span className="text-[11px] text-[#0051d5] font-mono font-medium">
            {timeB?.label}
          </span>
        </div>
      </div>

      {/* Cross-Sector Delta Table */}
      <div className="bg-[#ffffff] rounded-xl border border-[#eae7eb] shadow-xs overflow-hidden">
        <div className="p-3.5 border-b border-[#f0edf1] flex items-center justify-between">
          <h2 className="text-sm font-bold text-[#1b1b1e] font-headline">
            Sector Variance Matrix
          </h2>
          <span className="text-xs font-mono text-[#45464d]">
            Δ Shift Score
          </span>
        </div>

        <div className="divide-y divide-[#f0edf1]">
          {zoneKeys.map((key) => {
            const zA = timeA?.zones?.[key] || { name: key, code: key.toUpperCase(), level: 'Moderate' as const, score: '--' };
            const zB = timeB?.zones?.[key] || { name: key, code: key.toUpperCase(), level: 'Moderate' as const, score: '--' };
            const scoreA = typeof zA.score === 'number' ? zA.score : null;
            const scoreB = typeof zB.score === 'number' ? zB.score : null;
            const diff = scoreA !== null && scoreB !== null ? scoreB - scoreA : null;

            return (
              <div key={key} className="p-3.5 flex items-center justify-between gap-3 hover:bg-[#fbf8fc] transition-colors">
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-bold text-[#1b1b1e] truncate">
                    {zB.name}
                  </span>
                  <span className="text-[11px] font-mono text-[#45464d]">
                    {zB.code} • {zB.level}
                  </span>
                </div>

                <div className="flex items-center gap-4 flex-shrink-0">
                  {/* Window A score */}
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] text-[#45464d]">Win A</span>
                    <span className="font-mono text-xs font-semibold text-[#45464d]">
                      {zA.score}
                    </span>
                  </div>

                  <span className="text-xs text-[#c6c6cd]">→</span>

                  {/* Window B score */}
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] text-[#45464d]">Win B</span>
                    <span className="font-mono text-xs font-bold text-[#1b1b1e]">
                      {zB.score}
                    </span>
                  </div>

                  {/* Delta Badge */}
                  <div className="w-16 flex justify-end">
                    {diff !== null ? (
                      <span
                        className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-xs font-mono font-bold ${
                          diff > 0
                            ? 'bg-[#ffdad6] text-[#ba1a1a]'
                            : diff < 0
                            ? 'bg-[#dcfce7] text-[#15803d]'
                            : 'bg-[#f0edf1] text-[#45464d]'
                        }`}
                      >
                        {diff > 0 ? `+${diff}` : diff}
                      </span>
                    ) : (
                      <span className="text-xs font-mono text-[#76777d]">N/A</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Logistical Strategy Insights */}
      <div className="bg-[#ffffff] p-4 rounded-xl border border-[#eae7eb] shadow-xs flex flex-col gap-2.5">
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[18px] text-[#0051d5]">
            insights
          </span>
          <h2 className="text-sm font-bold text-[#1b1b1e] font-headline">
            Temporal Logistics Insights
          </h2>
        </div>

        <div className="space-y-2 text-xs text-[#45464d]">
          <div className="p-2.5 rounded-lg bg-[#f6f2f7] border border-[#e4e1e6]/60 flex items-start gap-2">
            <span className="material-symbols-outlined text-[16px] text-[#ba1a1a] mt-0.5">
              priority_high
            </span>
            <div className="flex flex-col">
              <span className="font-semibold text-[#1b1b1e]">
                Primary Divergence Focus
              </span>
              <span>
                Market Road Corridor accelerates +28 points between 12:00 and 20:00. Prioritize safety unit positioning near transit junction prior to 18:30.
              </span>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-[#f6f2f7] border border-[#e4e1e6]/60 flex items-start gap-2">
            <span className="material-symbols-outlined text-[16px] text-[#16a34a] mt-0.5">
              check_circle
            </span>
            <div className="flex flex-col">
              <span className="font-semibold text-[#1b1b1e]">
                Riverside Esplanade Stability
              </span>
              <span>
                Remains stable with delta variance ≤ 4. Standard routine patrol cycle sufficient; no supplementary staging required.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
