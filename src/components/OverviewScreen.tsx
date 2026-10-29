import React, { useState } from 'react';
import { ScreenType } from '../types';
import { useBackend } from '../context/BackendContext';
import { UniversalLocationPicker } from './UniversalLocationPicker';
import { LocationForecastCard } from './LocationForecastCard';

interface OverviewScreenProps {
  onNavigateToRiskMap: (zoneKey?: string) => void;
  onOpenEthics: () => void;
}

export const OverviewScreen: React.FC<OverviewScreenProps> = ({
  onNavigateToRiskMap,
  onOpenEthics
}) => {
  const {
    forecast,
    activeTimeStep,
    modelHealth,
    isForecastLoading,
    isBackendOnline,
    backendUrl
  } = useBackend();

  const [selectedPreviewSector, setSelectedPreviewSector] = useState<'market' | 'riverside' | 'sector4'>('market');
  const [tooltipFlash, setTooltipFlash] = useState(false);

  const handleSelectSector = (sector: 'market' | 'riverside' | 'sector4') => {
    setSelectedPreviewSector(sector);
    setTooltipFlash(true);
    setTimeout(() => setTooltipFlash(false), 800);
  };

  const statusOverview = forecast?.status_overview;
  const currentStatus = statusOverview?.status || 'Calm Baseline';
  const statusWindow = statusOverview?.window || 'Today, 18:00 – 22:00';
  const statusRiskPct = statusOverview?.risk_percentage ?? 28;
  const refreshedAt = statusOverview?.refreshed_at || (isBackendOnline ? 'Live via FastAPI' : 'Refreshed 8m ago');
  const feedIntegrity = modelHealth?.feed_integrity || '99.4%';
  const precinctCount = modelHealth?.active_precinct_logs ?? 14;

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pb-24 pt-3 gap-4">
      {/* Header Context Area */}
      <div className="flex flex-col gap-1.5 mt-1">
        <div className="flex flex-wrap items-center gap-1.5 self-start">
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#f0edf1] text-[#45464d] text-xs font-mono">
            <span className={`w-1.5 h-1.5 rounded-full ${isBackendOnline ? 'bg-[#16a34a]' : 'bg-[#0051d5]'}`}></span>
            <span>
              {isBackendOnline
                ? 'FastAPI Connected • CatBoost v4.2.1'
                : 'Demo Mode • Simulated Pattern Engine'}
            </span>
          </div>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-[#eef4ff] text-[#0051d5] text-[11px] font-mono border border-[#d0e1fd]">
            Chicago Crime Data — Proxy Dataset (H=4h Horizon)
          </span>
        </div>
        <div className="flex flex-col gap-1 mt-1">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold tracking-tight text-[#1b1b1e] font-headline">
              Risk Overview
            </h1>
            {isForecastLoading && (
              <span className="text-xs font-mono text-[#0051d5] flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px] animate-spin">sync</span>
                <span>Updating</span>
              </span>
            )}
          </div>
          <p className="text-sm text-[#45464d] leading-relaxed">
            Understand how recorded incident patterns change by location and time.
          </p>
        </div>
      </div>

      {/* Universal Location Selector */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between px-0.5">
          <span className="text-[11px] font-mono uppercase text-[#45464d] tracking-wider font-semibold">
            Universal Location Explorer
          </span>
          <span className="text-[10px] font-mono text-[#0051d5]">
            Global Coordinates • Cities • GPS
          </span>
        </div>
        <UniversalLocationPicker />
      </div>

      {/* Location-Aware Forecast & Honest Provenance */}
      <LocationForecastCard />

      {/* Three Essential Summaries Grid */}
      <div className="flex flex-col gap-2.5">
        {/* 1. Forecast Status */}
        <div className="bg-[#ffffff] p-4 rounded-xl shadow-xs border border-[#eae7eb] flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#45464d] uppercase tracking-wider">
              Current Forecast Status
            </span>
            <span className="text-xs font-mono text-[#45464d]">
              {refreshedAt}
            </span>
          </div>

          <div className="flex items-baseline justify-between mt-1">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#0051d5] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#0051d5]"></span>
              </span>
              <span className="text-lg font-semibold text-[#1b1b1e] font-headline">
                {currentStatus}
              </span>
            </div>
            <span className="inline-flex items-center px-2 py-0.5 rounded bg-[#f0edf1] text-[#45464d] text-xs font-mono font-medium">
              {statusWindow}
            </span>
          </div>

          <div className="w-full bg-[#f0edf1] rounded-full h-1.5 mt-2.5 overflow-hidden flex">
            <div
              className="bg-[#0051d5] h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(statusRiskPct, 100)}%` }}
            ></div>
          </div>
        </div>

        {/* 2. Areas with Elevated Predicted Risk */}
        <div className="bg-[#ffffff] p-4 rounded-xl shadow-xs border border-[#eae7eb] flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#45464d] uppercase tracking-wider">
              Elevated Predicted Risk
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#ffdad6] text-[#93000a] text-xs font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#ba1a1a]"></span>
              {statusOverview?.monitored_sectors_count ?? 2} Sectors Monitored
            </span>
          </div>

          <p className="text-sm font-medium text-[#1b1b1e] mt-1">
            Market Road Corridor & Central Transit Loop during peak hours.
          </p>

          <div className="flex flex-wrap items-center gap-2 mt-1.5">
            <span
              onClick={() => onNavigateToRiskMap('market')}
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-[#f6f2f7] text-[#1b1b1e] text-xs font-mono border border-[#e4e1e6]/60 cursor-pointer hover:bg-[#eae7eb] transition-colors"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#ba1a1a]"></span>
              <span>Market Rd: +34% variance</span>
            </span>
            <span
              onClick={() => onNavigateToRiskMap('central')}
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-[#f6f2f7] text-[#1b1b1e] text-xs font-mono border border-[#e4e1e6]/60 cursor-pointer hover:bg-[#eae7eb] transition-colors"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#0051d5]"></span>
              <span>Loop: Moderate density</span>
            </span>
          </div>
        </div>

        {/* 3. Feed Integrity & Ingestion */}
        <div className="bg-[#ffffff] p-4 rounded-xl shadow-xs border border-[#eae7eb] flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#45464d] uppercase tracking-wider">
              Feed Integrity & Ingestion
            </span>
            <span className="text-xs font-mono text-[#1b1b1e] font-bold">
              {feedIntegrity}
            </span>
          </div>

          <div className="flex items-center gap-2 mt-1">
            <span className="material-symbols-outlined text-[19px] text-[#0051d5]">
              sync_saved_locally
            </span>
            <span className="text-xs text-[#45464d]">
              Updated from {precinctCount} precinct logs {isBackendOnline ? 'via live feed' : 'up to 17:30 today'}
            </span>
          </div>
        </div>
      </div>

      {/* Large Interactive Map Preview Card */}
      <div className="bg-[#ffffff] rounded-xl shadow-sm border border-[#eae7eb] overflow-hidden flex flex-col">
        {/* Header inside Map Card */}
        <div className="p-4 bg-[#ffffff] flex items-center justify-between border-b border-[#f0edf1]">
          <div className="flex flex-col">
            <span className="text-base font-bold text-[#1b1b1e] font-headline">
              Spatial Distribution
            </span>
            <span className="text-xs text-[#45464d]">
              Probabilistic grid projection
            </span>
          </div>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#f0edf1] text-xs font-mono text-[#1b1b1e] font-medium">
            <span className="material-symbols-outlined text-[14px] text-[#0051d5]">
              schedule
            </span>
            20:00 Peak Projection
          </span>
        </div>

        {/* Map Canvas Representation */}
        <div className="relative w-full h-64 bg-[#f0edf1] overflow-hidden flex items-center justify-center select-none">
          {/* Subtle real-world map layer baseline pattern */}
          <div
            className="absolute inset-0 w-full h-full bg-cover bg-center opacity-30 mix-blend-multiply"
            style={{
              backgroundImage:
                "radial-gradient(#76777d 1px, transparent 1px), radial-gradient(#76777d 1px, #f0edf1 1px)",
              backgroundSize: "24px 24px"
            }}
          />

          {/* Vector Stylized Geo-Grid Overlay */}
          <svg
            className="absolute inset-0 w-full h-full cursor-pointer"
            preserveAspectRatio="none"
            viewBox="0 0 360 256"
          >
            <defs>
              <pattern
                id="preview-grid"
                width="30"
                height="30"
                patternUnits="userSpaceOnUse"
              >
                <path
                  d="M 30 0 L 0 0 0 30"
                  fill="none"
                  stroke="#76777d"
                  strokeOpacity="0.22"
                  strokeWidth="0.5"
                />
              </pattern>
            </defs>

            <rect width="100%" height="100%" fill="url(#preview-grid)" />

            {/* Stylized River Corridor */}
            <path
              d="M -20 120 C 60 100, 140 180, 220 220 C 280 250, 360 260, 400 270"
              fill="none"
              stroke="#b4c5ff"
              strokeWidth="24"
              opacity="0.35"
            />

            {/* Sector: Riverside (Calm / Low Risk - Green tone) */}
            <g
              onClick={() => handleSelectSector('riverside')}
              className="cursor-pointer transition-opacity hover:opacity-90"
            >
              <polygon
                points="20,130 90,110 110,180 30,210"
                fill="#22c55e"
                fillOpacity={selectedPreviewSector === 'riverside' ? 0.35 : 0.2}
                stroke="#16a34a"
                strokeWidth={selectedPreviewSector === 'riverside' ? '2.5' : '1.5'}
                strokeDasharray="3 3"
              />
              <circle cx="60" cy="150" r="4" fill="#16a34a" />
              <text
                x="68"
                y="153"
                fill="#1b1b1e"
                fontFamily="JetBrains Mono"
                fontSize="8"
                fontWeight="500"
              >
                Riverside (Low)
              </text>
            </g>

            {/* Sector: Market Road Corridor (Elevated Risk - Amber/Red tone) */}
            <g
              onClick={() => handleSelectSector('market')}
              className="cursor-pointer transition-opacity hover:opacity-95"
            >
              <polygon
                id="market-poly"
                points="160,50 270,40 290,130 180,140"
                fill="#ef4444"
                fillOpacity={selectedPreviewSector === 'market' ? 0.42 : 0.3}
                stroke="#ba1a1a"
                strokeWidth={selectedPreviewSector === 'market' ? '2.5' : '1.5'}
              />
              <circle cx="225" cy="85" r="5" fill="#ba1a1a">
                <animate
                  attributeName="r"
                  values="4;7;4"
                  dur="2s"
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="opacity"
                  values="1;0.6;1"
                  dur="2s"
                  repeatCount="indefinite"
                />
              </circle>
              <text
                x="235"
                y="88"
                fill="#1b1b1e"
                fontFamily="JetBrains Mono"
                fontSize="8"
                fontWeight="600"
              >
                Market Rd (High)
              </text>
            </g>

            {/* Sector 4: Insufficient Evidence / Calm Baseline (Gray tone) */}
            <g
              onClick={() => handleSelectSector('sector4')}
              className="cursor-pointer transition-opacity hover:opacity-90"
            >
              <polygon
                points="240,160 330,150 340,220 250,230"
                fill="#76777d"
                fillOpacity={selectedPreviewSector === 'sector4' ? 0.3 : 0.15}
                stroke="#76777d"
                strokeWidth={selectedPreviewSector === 'sector4' ? '2' : '1'}
                strokeDasharray="2 2"
              />
              <circle cx="285" cy="190" r="3.5" fill="#76777d" />
              <text
                x="293"
                y="193"
                fill="#45464d"
                fontFamily="JetBrains Mono"
                fontSize="8"
              >
                Sector 4 (Null/Low)
              </text>
            </g>
          </svg>

          {/* Floating Map Legend Pill */}
          <div className="absolute top-3 left-3 bg-[#ffffff]/90 backdrop-blur-md px-2.5 py-1.5 rounded-lg shadow-sm border border-[#e4e1e6]/70 flex items-center gap-3">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#ba1a1a]"></span>
              <span className="text-xs font-mono text-[#1b1b1e]">Elevated</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#0051d5]"></span>
              <span className="text-xs font-mono text-[#1b1b1e]">Moderate</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#76777d]"></span>
              <span className="text-xs font-mono text-[#45464d]">Neutral</span>
            </div>
          </div>

          {/* Quick Interactive Sector Tooltip */}
          <div
            className={`absolute bottom-3 right-3 backdrop-blur-md px-3 py-2 rounded-lg shadow-md max-w-[210px] transition-all duration-300 border ${
              tooltipFlash
                ? 'bg-[#ffdad6] border-[#ba1a1a]'
                : 'bg-[#ffffff]/95 border-[#e4e1e6]'
            }`}
          >
            {(() => {
              const zoneKey = selectedPreviewSector === 'sector4' ? 'east' : selectedPreviewSector;
              const zoneData = activeTimeStep?.zones?.[zoneKey as 'market' | 'riverside' | 'east'] || activeTimeStep?.zones?.market;
              const rawScore = zoneData?.score;
              const probNum = typeof rawScore === 'number' ? (rawScore / 100).toFixed(2) : '--';
              const isHigh = zoneData?.level === 'Higher';
              const isMod = zoneData?.level === 'Moderate';

              return (
                <>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-[#1b1b1e] truncate">
                      {zoneData?.name || 'Sector Zone'}
                    </span>
                    <span className={`text-xs font-mono font-semibold ${
                      isHigh ? 'text-[#ba1a1a]' : isMod ? 'text-[#d97706]' : 'text-[#16a34a]'
                    }`}>
                      {rawScore !== '--' ? `Score: ${rawScore}` : 'Sparse'} (p={probNum})
                    </span>
                  </div>
                  <span className="text-[11px] text-[#45464d] block mt-0.5 leading-tight truncate">
                    {zoneData?.reasons?.[0] || `${zoneData?.tag} • ${zoneData?.level}`}
                  </span>
                </>
              );
            })()}
          </div>
        </div>

        {/* Map Action Footer */}
        <div className="p-4 bg-[#ffffff] flex flex-col gap-3">
          <div className="flex items-center justify-between text-[#45464d] text-xs">
            <span className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-[#45464d]">
                layers
              </span>
              3 Active Overlay Layers
            </span>
            <span className="font-mono text-xs">Cell resolution: 250m</span>
          </div>

          <button
            onClick={() => onNavigateToRiskMap()}
            className="w-full h-11 bg-[#000000] hover:bg-[#303033] text-white rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-all active:scale-[0.99] cursor-pointer shadow-sm"
          >
            <span>Explore Risk Map</span>
            <span className="material-symbols-outlined text-[18px]">
              arrow_forward
            </span>
          </button>
        </div>
      </div>

      {/* Responsible Use Micro-Notice */}
      <div className="bg-[#f6f2f7] p-4 rounded-xl border border-[#e4e1e6]/60 flex items-start gap-3">
        <span className="material-symbols-outlined text-[#45464d] text-[20px] flex-shrink-0 mt-0.5">
          shield
        </span>
        <div className="flex flex-col gap-1">
          <p className="text-xs text-[#45464d] leading-relaxed">
            Forecasts estimate recorded incident density to support public safety logistics. Does not predict individual behavior or replace human oversight.
          </p>
          <button
            onClick={onOpenEthics}
            className="text-xs text-[#0051d5] hover:underline self-start flex items-center gap-0.5 font-medium cursor-pointer"
          >
            <span>Read ethical governance</span>
            <span className="material-symbols-outlined text-[14px]">
              open_in_new
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};
