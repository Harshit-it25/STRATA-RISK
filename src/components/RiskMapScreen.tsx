import React, { useState, useEffect, useRef } from 'react';
import { OverlayLayers, SectorOption } from '../types';
import { useBackend } from '../context/BackendContext';
import { UniversalLocationPicker } from './UniversalLocationPicker';
import { InteractiveRiskMap } from './map/InteractiveRiskMap';

interface RiskMapScreenProps {
  selectedSector: SectorOption;
  onOpenSectorPicker: () => void;
  onOpenLayersModal: () => void;
  layers: OverlayLayers;
  initialZoneKey?: string;
}

export const RiskMapScreen: React.FC<RiskMapScreenProps> = ({
  selectedSector,
  onOpenSectorPicker,
  onOpenLayersModal,
  layers,
  initialZoneKey = 'market'
}) => {
  const {
    selectedTime,
    setSelectedTime,
    selectedDate,
    setSelectedDate,
    activeTimeStep,
    timeline,
    isForecastLoading,
    isBackendOnline,
    selectedLocation,
    locationForecast,
    selectLocation,
    selectCoordinates
  } = useBackend();

  const [activeZoneKey, setActiveZoneKey] = useState<'market' | 'central' | 'riverside' | 'east'>(
    (initialZoneKey as 'market' | 'central' | 'riverside' | 'east') || 'market'
  );
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(true);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [showDatePicker, setShowDatePicker] = useState<boolean>(false);

  const playbackRef = useRef<NodeJS.Timeout | null>(null);

  const activeTimeIndex = Math.max(0, timeline.findIndex((t) => t.hour === selectedTime));
  const currentTimeData = activeTimeStep;
  const currentZoneData = currentTimeData.zones[activeZoneKey] || currentTimeData.zones.market;

  // Auto-play timelapse
  useEffect(() => {
    if (isPlaying) {
      playbackRef.current = setInterval(() => {
        const nextIdx = (activeTimeIndex + 1) % timeline.length;
        if (timeline[nextIdx]) {
          setSelectedTime(timeline[nextIdx].hour);
        }
      }, 1900);
    } else {
      if (playbackRef.current) clearInterval(playbackRef.current);
    }
    return () => {
      if (playbackRef.current) clearInterval(playbackRef.current);
    };
  }, [isPlaying, activeTimeIndex, timeline, setSelectedTime]);

  const togglePlayback = () => {
    setIsPlaying(!isPlaying);
  };

  const handleSelectTimeStep = (hour: string) => {
    setIsPlaying(false);
    setSelectedTime(hour);
  };

  const handleZoneClick = (key: 'market' | 'central' | 'riverside' | 'east') => {
    setActiveZoneKey(key);
    setIsDrawerOpen(true);
  };


  return (
    <div className="flex flex-col w-full max-w-lg mx-auto pb-24 relative select-none">
      {/* Top Command & Spatial Context Filters */}
      <div className="px-4 pt-2 pb-2 flex flex-col gap-2 z-20">
        {/* Universal Location Selector */}
        <UniversalLocationPicker />

        <div className="flex items-center justify-between gap-2">
          {/* Sector Dropdown Pill */}
          <button
            onClick={onOpenSectorPicker}
            className="flex-1 min-w-0 flex items-center justify-between px-3 py-2 rounded-xl bg-[#f0edf1] hover:bg-[#e4e1e6] transition-colors shadow-xs border border-[#e4e1e6]/60 cursor-pointer text-left"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="material-symbols-outlined text-[18px] text-[#0051d5] flex-shrink-0">
                near_me
              </span>
              <div className="flex flex-col text-left min-w-0">
                <span className="text-[10px] font-mono uppercase text-[#45464d] tracking-wider leading-none">
                  Chicago Sector Lattice
                </span>
                <span className="text-xs font-semibold text-[#1b1b1e] truncate mt-0.5">
                  {selectedSector.name}
                </span>
              </div>
            </div>
            <span className="material-symbols-outlined text-[20px] text-[#45464d]">
              arrow_drop_down
            </span>
          </button>

          {/* Date Filter Pill */}
          <div className="relative">
            <button
              onClick={() => setShowDatePicker(!showDatePicker)}
              className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-[#f0edf1] hover:bg-[#e4e1e6] transition-colors shadow-xs border border-[#e4e1e6]/60 flex-shrink-0 cursor-pointer"
            >
              <span className="material-symbols-outlined text-[16px] text-[#45464d]">
                calendar_today
              </span>
              <span className="text-xs font-semibold text-[#1b1b1e]">
                {selectedDate}
              </span>
            </button>

            {showDatePicker && (
              <div className="absolute right-0 top-12 w-48 bg-white rounded-xl shadow-lg border border-[#e4e1e6] p-2 z-40 animate-in fade-in zoom-in-95">
                <div className="text-[11px] font-semibold text-[#45464d] px-2 py-1 uppercase tracking-wider font-mono">
                  Scenario Date
                </div>
                {['Mon, Oct 24', 'Tue, Oct 25', 'Wed, Oct 26', 'Synthetic Baseline'].map((d) => (
                  <button
                    key={d}
                    onClick={() => {
                      setSelectedDate(d);
                      setShowDatePicker(false);
                    }}
                    className={`w-full text-left px-2 py-1.5 text-xs rounded-lg transition-colors ${
                      selectedDate === d
                        ? 'bg-[#0051d5] text-white font-semibold'
                        : 'text-[#1b1b1e] hover:bg-[#f0edf1]'
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Geographic Coverage & Model Provenance Sub-strip */}
        <div className="flex items-center justify-between px-1 text-[#45464d]">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                selectedLocation.coverageStatus === 'SUPPORTED'
                  ? 'bg-[#16a34a]'
                  : selectedLocation.coverageStatus === 'PARTIAL_COVERAGE'
                  ? 'bg-[#d97706]'
                  : 'bg-[#64748b]'
              }`}
            ></span>
            <span className="text-xs font-mono text-[#45464d] truncate">
              {selectedLocation.coverageStatus === 'SUPPORTED'
                ? `CPD Validated • ${selectedLocation.timezone || 'America/Chicago'}`
                : selectedLocation.coverageStatus === 'PARTIAL_COVERAGE'
                ? `Buffer Fringe (Degraded) • ${selectedLocation.timezone || 'UTC'}`
                : `Unsupported: ${selectedLocation.displayName.slice(0, 24)}...`}
            </span>
          </div>
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
              selectedLocation.coverageStatus === 'SUPPORTED'
                ? 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0]'
                : selectedLocation.coverageStatus === 'PARTIAL_COVERAGE'
                ? 'bg-[#fef3c7] text-[#92400e] border-[#fde68a]'
                : 'bg-[#f1f5f9] text-[#475569] border-[#e2e8f0]'
            }`}
          >
            {selectedLocation.coverageStatus}
          </span>
        </div>
      </div>

      {/* Real Interactive Leaflet Geographic Map Viewport */}
      <div className="relative w-full h-[520px] bg-[#e4e1e6] border-y border-[#dcd9dd] select-none">
        <InteractiveRiskMap
          onSelectZone={handleZoneClick}
          activeZoneKey={activeZoneKey}
          layers={layers}
          onOpenLayersModal={onOpenLayersModal}
        />
      </div>

      {/* Defining Feature: Temporal Horizon Scrubber Strip */}
      <div className="px-4 py-3 bg-[#f6f2f7] shadow-xs border-b border-[#eae7eb] z-20">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2.5">
            {/* Play / Pause Simulation Control */}
            <button
              onClick={togglePlayback}
              aria-label={isPlaying ? 'Pause forecast simulation' : 'Play forecast simulation'}
              className="w-8 h-8 rounded-full bg-[#000000] text-white flex items-center justify-center shadow hover:bg-[#303033] transition-transform active:scale-90 cursor-pointer"
            >
              <span className="material-symbols-outlined text-[20px]">
                {isPlaying ? 'pause' : 'play_arrow'}
              </span>
            </button>
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-[#1b1b1e] flex items-center gap-1.5">
                Temporal Simulation
                <span className="w-1.5 h-1.5 rounded-full bg-[#0051d5]"></span>
              </span>
              <span className="text-[11px] text-[#45464d] leading-tight">
                Drag or tap points to project spatial density
              </span>
            </div>
          </div>

          {/* Selected Active Timestamp Badge */}
          <div className="px-2.5 py-1 rounded-full bg-[#131b2e] text-[#fefcff] font-mono text-xs font-semibold flex items-center gap-1 shadow-xs">
            <span className="material-symbols-outlined text-[13px] text-[#b4c5ff]">
              schedule
            </span>
            <span>{currentTimeData.label}</span>
          </div>
        </div>

        {/* Stepped Horizontal Time Axis Rail */}
        <div className="relative w-full pt-2 pb-1">
          <div className="h-1.5 w-full bg-[#e4e1e6] rounded-full relative overflow-hidden">
            <div
              className="h-full bg-[#0051d5] rounded-full transition-all duration-300"
              style={{ width: currentTimeData.fillPct }}
            ></div>
          </div>

          {/* Interactive Time Checkpoint Indicators */}
          <div className="flex justify-between items-center mt-2.5">
            {timeline.map((step, idx) => {
              const isSelected = step.hour === selectedTime;
              return (
                <button
                  key={step.hour}
                  onClick={() => handleSelectTimeStep(step.hour)}
                  className="flex flex-col items-center group focus:outline-none cursor-pointer"
                >
                  <div
                    className={`transition-all mb-1 ${
                      isSelected
                        ? 'w-4 h-4 rounded-full bg-[#0051d5] ring-4 ring-[#b4c5ff] scale-110 shadow-xs'
                        : 'w-3.5 h-3.5 rounded-full bg-[#e4e1e6] group-hover:bg-[#0051d5]/60'
                    }`}
                  ></div>
                  <span
                    className={`font-mono text-xs ${
                      isSelected
                        ? 'text-[#0051d5] font-bold'
                        : 'text-[#45464d] font-medium'
                    }`}
                  >
                    {step.hour}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Contextual Risk Details Inspection Panel (Interactive Bottom Drawer) */}
      {isDrawerOpen && (
        <div className="mx-4 mt-3 mb-2 p-4 rounded-2xl bg-[#ffffff] shadow-md border border-[#eae7eb] transition-all duration-300 animate-in fade-in slide-in-from-bottom-2">
          {/* Header with Location and Dismiss action */}
          <div className="flex items-start justify-between pb-3 border-b border-[#f0edf1]">
            <div className="min-w-0 pr-2">
              <div className="flex items-center gap-1.5 mb-0.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    selectedLocation.coverageStatus === 'SUPPORTED'
                      ? 'bg-[#16a34a]'
                      : selectedLocation.coverageStatus === 'PARTIAL_COVERAGE'
                      ? 'bg-[#d97706]'
                      : 'bg-[#64748b]'
                  }`}
                ></span>
                <span className="font-mono text-xs uppercase text-[#45464d] tracking-wider truncate">
                  {selectedLocation.coverageStatus === 'SUPPORTED' || selectedLocation.coverageStatus === 'PARTIAL_COVERAGE'
                    ? currentZoneData.tag
                    : `COVERAGE: ${selectedLocation.coverageStatus}`}
                </span>
              </div>
              <h2 className="text-xl font-bold text-[#1b1b1e] truncate font-headline">
                {selectedLocation.coverageStatus === 'SUPPORTED' || selectedLocation.coverageStatus === 'PARTIAL_COVERAGE'
                  ? currentZoneData.name
                  : selectedLocation.displayName}
              </h2>
              <p className="text-xs text-[#45464d] mt-0.5 font-mono">
                {selectedLocation.latitude.toFixed(4)}°N, {Math.abs(selectedLocation.longitude).toFixed(4)}°
                {selectedLocation.longitude < 0 ? 'W' : 'E'} • {selectedLocation.timezone || 'UTC'}
              </p>
            </div>

            <button
              onClick={() => setIsDrawerOpen(false)}
              aria-label="Dismiss inspector panel"
              className="w-8 h-8 rounded-full bg-[#f0edf1] hover:bg-[#e4e1e6] flex items-center justify-center text-[#45464d] transition-colors flex-shrink-0 cursor-pointer"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>

          {/* Conditional: Honest Unsupported Card vs Full Supported Forecast Inspector */}
          {selectedLocation.coverageStatus !== 'SUPPORTED' && selectedLocation.coverageStatus !== 'PARTIAL_COVERAGE' ? (
            <div className="my-3 flex flex-col gap-3">
              <div className="p-3.5 rounded-xl bg-[#f8fafc] border border-[#cbd5e1] flex flex-col gap-2.5">
                <div className="flex items-center gap-2 text-[#334155]">
                  <span className="material-symbols-outlined text-[20px] text-[#475569]">
                    policy
                  </span>
                  <span className="text-xs font-bold font-headline">
                    Forecast Deactivated: Area Not Supported by Validated Model
                  </span>
                </div>

                <p className="text-xs text-[#475569] leading-relaxed">
                  We identified this location, but no verified municipal crime incident dataset is integrated,
                  and the active CatBoost engine is calibrated exclusively on Chicago spatio-temporal dynamics.
                </p>

                <div className="p-2.5 rounded-lg bg-white border border-[#e2e8f0] flex flex-col gap-1.5 text-[11px] font-mono text-[#475569]">
                  <div className="flex items-start gap-1.5">
                    <span className="text-[#dc2626] font-bold">!</span>
                    <span>Cross-regional model transfer without local historical training is prohibited.</span>
                  </div>
                  <div className="flex items-start gap-1.5">
                    <span className="text-[#dc2626] font-bold">!</span>
                    <span>Risk scores are not fabricated or rendered as zero to prevent misleading low-risk assumptions.</span>
                  </div>
                </div>

                <div className="pt-2 flex items-center justify-between border-t border-[#e2e8f0]">
                  <span className="text-xs font-semibold text-[#1b1b1e]">
                    Jump to Validated Benchmark:
                  </span>
                  <button
                    onClick={() => {
                      selectLocation({
                        displayName: 'Downtown Metro / Loop (District 001)',
                        latitude: 41.8719,
                        longitude: -87.6283,
                        regionId: 'chicago',
                        regionName: 'Chicago Metropolitan Area',
                        coverageStatus: 'SUPPORTED',
                        timezone: 'America/Chicago',
                        resolvedSectorId: 'zone-04',
                        resolvedZoneKey: 'market',
                        sourceType: 'preset'
                      });
                    }}
                    className="px-3 py-1.5 rounded-xl bg-[#0051d5] text-white text-xs font-semibold hover:bg-[#003ea8] transition-colors cursor-pointer"
                  >
                    View Chicago Forecast
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* Core Score, Trend & Evidence Meta Stats */}
              <div className="grid grid-cols-2 gap-2.5 my-3.5">
                {/* Metric 1: Forecast Gauge */}
                <div className="p-3 rounded-xl bg-[#f6f2f7] flex flex-col justify-between border border-[#e4e1e6]/60">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-[#45464d]">
                      Forecast Score
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                        currentZoneData.level === 'Higher'
                          ? 'bg-[#ffdad6] text-[#93000a]'
                          : currentZoneData.level === 'Moderate'
                          ? 'bg-[#fef3c7] text-[#b45309]'
                          : currentZoneData.level === 'Lower'
                          ? 'bg-[#dcfce7] text-[#15803d]'
                          : 'bg-[#eae7eb] text-[#45464d]'
                      }`}
                    >
                      {currentZoneData.level}
                    </span>
                  </div>

                  <div className="flex items-baseline gap-1 my-1">
                    <span className="text-3xl font-bold text-[#1b1b1e] font-headline">
                      {currentZoneData.score}
                    </span>
                    <span className="font-mono text-xs text-[#45464d]">/100</span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-1.5 bg-[#e4e1e6] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        currentZoneData.level === 'Higher'
                          ? 'bg-[#ba1a1a]'
                          : currentZoneData.level === 'Moderate'
                          ? 'bg-[#d97706]'
                          : currentZoneData.level === 'Lower'
                          ? 'bg-[#16a34a]'
                          : 'bg-[#76777d]'
                      }`}
                      style={{
                        width:
                          typeof currentZoneData.score === 'number'
                            ? `${currentZoneData.score}%`
                            : '0%'
                      }}
                    ></div>
                  </div>
                </div>

                {/* Metric 2: Temporal Trajectory & Evidence */}
                <div className="p-3 rounded-xl bg-[#f6f2f7] flex flex-col justify-between border border-[#e4e1e6]/60">
                  <div>
                    <span className="text-xs font-medium text-[#45464d]">
                      Temporal Delta
                    </span>
                    <div
                      className={`flex items-center gap-1 mt-1 font-bold text-sm ${
                        currentZoneData.level === 'Higher'
                          ? 'text-[#ba1a1a]'
                          : currentZoneData.level === 'Moderate'
                          ? 'text-[#b45309]'
                          : currentZoneData.level === 'Lower'
                          ? 'text-[#16a34a]'
                          : 'text-[#45464d]'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[18px]">
                        {currentZoneData.trend}
                      </span>
                      <span>{currentZoneData.trendLabel}</span>
                    </div>
                  </div>

                  <div className="pt-2">
                    <span className="text-xs font-medium text-[#45464d] block mb-1">
                      Evidence Depth
                    </span>
                    <span className="inline-flex items-center gap-1 font-mono text-[11px] text-[#1b1b1e] bg-[#eae7eb] px-2 py-0.5 rounded border border-[#c6c6cd]/50">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#0051d5]"></span>
                      {currentZoneData.observations} observations
                    </span>
                  </div>
                </div>
              </div>

              {/* Explainability Section: Why this forecast? */}
              <div className="mb-3.5 p-3.5 rounded-xl bg-[#f6f2f7] border border-[#e4e1e6]/60">
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="material-symbols-outlined text-[16px] text-[#0051d5]">
                    psychology
                  </span>
                  <h3 className="text-xs font-semibold text-[#1b1b1e]">
                    Why this forecast?
                  </h3>
                </div>

                <ul className="space-y-2 text-[#1b1b1e]">
                  {currentZoneData.reasons.map((reason, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="material-symbols-outlined text-[15px] text-[#45464d] mt-0.5 flex-shrink-0">
                        check_circle
                      </span>
                      <span className="text-xs text-[#45464d] leading-snug">
                        {reason}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Responsible AI & Uncertainty Disclosure */}
              <div className="p-3 rounded-xl bg-[#f0edf1] flex items-start gap-2 text-[#45464d] border border-[#e4e1e6]/50">
                <span className="material-symbols-outlined text-[16px] text-[#0051d5] flex-shrink-0 mt-0.5">
                  policy
                </span>
                <p className="text-[11px] leading-relaxed">
                  <strong className="font-semibold text-[#1b1b1e]">
                    Uncertainty band: ±7.2 pts.
                  </strong>{' '}
                  Strata forecasts estimate incident concentration density for resource positioning. Not an indictment or predictor of individual behavior.
                </p>
              </div>
            </>
          )}
        </div>
      )}

      {/* Reopen Drawer Trigger if dismissed */}
      {!isDrawerOpen && (
        <div className="px-4 mt-3">
          <button
            onClick={() => setIsDrawerOpen(true)}
            className="w-full py-2.5 px-3 bg-white rounded-xl shadow-xs border border-[#eae7eb] flex items-center justify-between text-xs font-semibold text-[#1b1b1e] hover:bg-[#f0edf1] cursor-pointer"
          >
            <div className="flex items-center gap-2 truncate">
              <span className="material-symbols-outlined text-[16px] text-[#0051d5]">
                info
              </span>
              <span className="truncate">
                Open Location Inspector (
                {selectedLocation.coverageStatus === 'SUPPORTED' || selectedLocation.coverageStatus === 'PARTIAL_COVERAGE'
                  ? currentZoneData.name
                  : selectedLocation.displayName}
                )
              </span>
            </div>
            <span className="material-symbols-outlined text-[18px]">expand_less</span>
          </button>
        </div>
      )}
    </div>
  );
};
