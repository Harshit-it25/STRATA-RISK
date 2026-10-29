import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useBackend } from '../context/BackendContext';
import { ApiService } from '../services/api';
import { LocationSearchResult, SelectedLocation, GeographicCoverageStatus } from '../types';

interface UniversalLocationPickerProps {
  onLocationChange?: (location: SelectedLocation) => void;
  className?: string;
  showCardWhenSelected?: boolean;
}

export const UniversalLocationPicker: React.FC<UniversalLocationPickerProps> = ({
  onLocationChange,
  className = '',
  showCardWhenSelected = false
}) => {
  const {
    selectedLocation,
    selectLocation,
    selectCoordinates,
    recentSearches,
    clearRecentSearches,
    isLocationForecastLoading
  } = useBackend();

  const [query, setQuery] = useState<string>('');
  const [suggestions, setSuggestions] = useState<LocationSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState<boolean>(false);

  // Manual Coordinate Input Modal State
  const [isCoordModalOpen, setIsCoordModalOpen] = useState<boolean>(false);
  const [inputLat, setInputLat] = useState<string>('');
  const [inputLon, setInputLon] = useState<string>('');
  const [coordError, setCoordError] = useState<string | null>(null);

  // Geolocation State
  const [isGeolocating, setIsGeolocating] = useState<boolean>(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Debounced Place Search
  const handleQueryChange = (val: string) => {
    setQuery(val);
    setSearchError(null);

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (val.trim().length < 2) {
      setSuggestions([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    setIsDropdownOpen(true);

    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const res = await ApiService.searchLocations(val, 6);
        if (res.ok && res.data) {
          setSuggestions(res.data);
          setSearchError(null);
        } else {
          setSuggestions([]);
          setSearchError(res.error || 'Failed to search locations');
        }
      } catch (err: any) {
        setSuggestions([]);
        setSearchError(err.message || 'Error communicating with geocoding service');
      } finally {
        setIsSearching(false);
      }
    }, 300);
  };

  // Select place from suggestions
  const handleSelectSuggestion = (item: LocationSearchResult) => {
    const newLoc: SelectedLocation = {
      displayName: item.display_name,
      latitude: item.latitude,
      longitude: item.longitude,
      regionId: item.region_id,
      coverageStatus: item.coverage_status,
      timezone: item.timezone || 'UTC',
      sourceType: 'search'
    };
    selectLocation(newLoc);
    if (onLocationChange) onLocationChange(newLoc);
    setIsDropdownOpen(false);
    setQuery('');
  };

  // Select place from recent searches
  const handleSelectRecent = (item: SelectedLocation) => {
    selectLocation(item);
    if (onLocationChange) onLocationChange(item);
    setIsDropdownOpen(false);
  };

  // Handle Browser Geolocation
  const handleCurrentLocation = () => {
    setGeoError(null);
    if (!navigator.geolocation) {
      setGeoError('Geolocation is not supported by your browser.');
      return;
    }

    setIsGeolocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          // Check coverage and reverse geocode via backend
          const covRes = await ApiService.checkCoverage(latitude, longitude);
          const covStatus = covRes.ok && covRes.data ? covRes.data.status : 'UNSUPPORTED';
          const regId = covRes.ok && covRes.data ? covRes.data.region_id : null;
          const regName = covRes.ok && covRes.data ? covRes.data.region_name : null;

          const newLoc: SelectedLocation = {
            displayName: `Current Location (${latitude.toFixed(4)}°, ${longitude.toFixed(4)}°)`,
            latitude,
            longitude,
            regionId: regId,
            regionName: regName,
            coverageStatus: covStatus,
            sourceType: 'current_location'
          };

          await selectLocation(newLoc);
          if (onLocationChange) onLocationChange(newLoc);
          setIsDropdownOpen(false);
        } catch (err: any) {
          setGeoError('Failed to verify coverage for your location.');
        } finally {
          setIsGeolocating(false);
        }
      },
      (err) => {
        setIsGeolocating(false);
        switch (err.code) {
          case err.PERMISSION_DENIED:
            setGeoError('Location permission denied by browser. You can still search for any city or enter coordinates.');
            break;
          case err.POSITION_UNAVAILABLE:
            setGeoError('Location information is currently unavailable.');
            break;
          case err.TIMEOUT:
            setGeoError('Location request timed out. Please try again.');
            break;
          default:
            setGeoError('An unknown error occurred while requesting location.');
        }
      },
      { timeout: 9000, enableHighAccuracy: false, maximumAge: 60000 }
    );
  };

  // Handle Manual Coordinates Submission
  const handleCoordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCoordError(null);

    const lat = parseFloat(inputLat.trim());
    const lon = parseFloat(inputLon.trim());

    if (isNaN(lat) || isNaN(lon)) {
      setCoordError('Please enter valid numeric latitude and longitude values.');
      return;
    }

    if (lat < -90 || lat > 90) {
      setCoordError('Latitude must be between -90.0 and +90.0 degrees.');
      return;
    }

    if (lon < -180 || lon > 180) {
      setCoordError('Longitude must be between -180.0 and +180.0 degrees.');
      return;
    }

    selectCoordinates(lat, lon, `Custom Coordinates (${lat.toFixed(4)}°, ${lon.toFixed(4)}°)`);
    setIsCoordModalOpen(false);
    setInputLat('');
    setInputLon('');
  };

  // Quick preset jump
  const handleJumpToChicago = () => {
    const chiLoc: SelectedLocation = {
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
    };
    selectLocation(chiLoc);
    if (onLocationChange) onLocationChange(chiLoc);
    setIsDropdownOpen(false);
  };

  const getCoverageBadge = (status: GeographicCoverageStatus) => {
    switch (status) {
      case 'SUPPORTED':
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#dcfce7] text-[#166534] border border-[#bbf7d0]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a]"></span>
            <span>SUPPORTED</span>
          </span>
        );
      case 'PARTIAL_COVERAGE':
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#d97706]"></span>
            <span>PARTIAL</span>
          </span>
        );
      case 'INSUFFICIENT_DATA':
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#e0e7ff] text-[#3730a3] border border-[#c7d2fe]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#4f46e5]"></span>
            <span>INSUFFICIENT DATA</span>
          </span>
        );
      case 'UNSUPPORTED':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#f1f5f9] text-[#475569] border border-[#e2e8f0]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#64748b]"></span>
            <span>UNSUPPORTED</span>
          </span>
        );
    }
  };

  return (
    <div ref={containerRef} className={`relative flex flex-col w-full ${className}`}>
      {/* Search Input Bar */}
      <div className="flex items-center gap-2 w-full">
        <div className="relative flex-1 flex items-center">
          <span className="material-symbols-outlined text-[18px] text-[#45464d] absolute left-3 pointer-events-none">
            search
          </span>
          <input
            type="text"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onFocus={() => setIsDropdownOpen(true)}
            placeholder="Search any city or place (e.g. Chicago, Mumbai, London)..."
            className="w-full pl-9 pr-8 py-2 rounded-xl bg-white hover:bg-[#faf8fb] focus:bg-white text-xs text-[#1b1b1e] border border-[#eae7eb] focus:border-[#0051d5] focus:outline-none transition-all shadow-2xs placeholder:text-[#76777d]"
          />
          {isSearching ? (
            <span className="material-symbols-outlined text-[16px] text-[#0051d5] animate-spin absolute right-2.5">
              sync
            </span>
          ) : query ? (
            <button
              onClick={() => {
                setQuery('');
                setSuggestions([]);
              }}
              className="absolute right-2.5 text-[#76777d] hover:text-[#1b1b1e] cursor-pointer"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          ) : null}
        </div>

        {/* Current Location GPS Button */}
        <button
          onClick={handleCurrentLocation}
          disabled={isGeolocating}
          title="Use my current location"
          className="flex items-center gap-1 px-2.5 py-2 rounded-xl bg-white hover:bg-[#f0edf1] border border-[#eae7eb] text-[#0051d5] text-xs font-semibold shadow-2xs transition-colors cursor-pointer disabled:opacity-50 flex-shrink-0"
        >
          <span className={`material-symbols-outlined text-[16px] ${isGeolocating ? 'animate-spin' : ''}`}>
            {isGeolocating ? 'sync' : 'my_location'}
          </span>
          <span className="hidden sm:inline">Current</span>
        </button>

        {/* Coordinate Input Trigger */}
        <button
          onClick={() => setIsCoordModalOpen(true)}
          title="Enter geographic coordinates manually"
          className="flex items-center gap-1 px-2.5 py-2 rounded-xl bg-white hover:bg-[#f0edf1] border border-[#eae7eb] text-[#45464d] text-xs font-semibold shadow-2xs transition-colors cursor-pointer flex-shrink-0"
        >
          <span className="material-symbols-outlined text-[16px]">pin_drop</span>
          <span className="hidden sm:inline">Coords</span>
        </button>
      </div>

      {/* Geolocation Error Alert */}
      {geoError && (
        <div className="mt-2 p-2 rounded-lg bg-[#fff1f2] border border-[#fecdd3] text-[11px] text-[#9f1239] flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="material-symbols-outlined text-[15px] flex-shrink-0">info</span>
            <span className="truncate">{geoError}</span>
          </div>
          <button
            onClick={() => setGeoError(null)}
            className="text-[#9f1239] hover:text-[#4c0519] ml-2 flex-shrink-0 font-bold"
          >
            ×
          </button>
        </div>
      )}

      {/* Suggestions / History Dropdown */}
      {isDropdownOpen && (
        <div className="absolute top-11 left-0 right-0 bg-white rounded-2xl shadow-xl border border-[#eae7eb] p-2 z-50 animate-in fade-in zoom-in-95 max-h-88 overflow-y-auto">
          {/* Active Search Results */}
          {suggestions.length > 0 && (
            <div className="flex flex-col gap-1 pb-2">
              <div className="text-[10px] font-bold text-[#76777d] uppercase tracking-wider px-2 py-1 font-mono">
                Matching Places & Cities
              </div>
              {suggestions.map((sug, idx) => (
                <button
                  key={`${sug.latitude}-${sug.longitude}-${idx}`}
                  onClick={() => handleSelectSuggestion(sug)}
                  className="w-full text-left p-2 rounded-xl hover:bg-[#f0edf1] transition-colors flex items-center justify-between gap-2 cursor-pointer group"
                >
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="material-symbols-outlined text-[16px] text-[#0051d5] mt-0.5 flex-shrink-0">
                      location_city
                    </span>
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-semibold text-[#1b1b1e] truncate group-hover:text-[#0051d5]">
                        {sug.city ? `${sug.city}, ${sug.country || ''}` : sug.display_name}
                      </span>
                      <span className="text-[10px] text-[#76777d] truncate font-mono">
                        {sug.latitude.toFixed(4)}°, {sug.longitude.toFixed(4)}° • {sug.timezone || 'UTC'}
                      </span>
                    </div>
                  </div>
                  <div className="flex-shrink-0">{getCoverageBadge(sug.coverage_status)}</div>
                </button>
              ))}
            </div>
          )}

          {/* Search Empty / Not Found */}
          {query.trim().length >= 2 && !isSearching && suggestions.length === 0 && (
            <div className="p-3 text-center text-xs text-[#76777d]">
              No places found for "{query}". Try checking city spelling or enter raw coordinates.
            </div>
          )}

          {/* Quick Presets Strip */}
          <div className="pt-2 border-t border-[#f0edf1]">
            <div className="text-[10px] font-bold text-[#76777d] uppercase tracking-wider px-2 py-1 font-mono flex items-center justify-between">
              <span>Benchmark Scenarios</span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 px-1 py-1">
              <button
                onClick={handleJumpToChicago}
                className="p-2 rounded-xl bg-[#f0f9ff] hover:bg-[#e0f2fe] border border-[#bae6fd] text-left cursor-pointer transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#0369a1]">Chicago (Loop)</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a]"></span>
                </div>
                <div className="text-[10px] text-[#0284c7] font-mono mt-0.5">Validated CPD Model</div>
              </button>

              <button
                onClick={() => {
                  const mumLoc: SelectedLocation = {
                    displayName: 'Mumbai, Maharashtra, India',
                    latitude: 19.0760,
                    longitude: 72.8777,
                    regionId: 'mumbai',
                    regionName: 'Greater Mumbai',
                    coverageStatus: 'UNSUPPORTED',
                    timezone: 'Asia/Kolkata',
                    sourceType: 'preset'
                  };
                  selectLocation(mumLoc);
                  if (onLocationChange) onLocationChange(mumLoc);
                  setIsDropdownOpen(false);
                }}
                className="p-2 rounded-xl bg-[#f8fafc] hover:bg-[#f1f5f9] border border-[#e2e8f0] text-left cursor-pointer transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#334155]">Mumbai</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-[#64748b]"></span>
                </div>
                <div className="text-[10px] text-[#64748b] font-mono mt-0.5">Uncalibrated (Honest)</div>
              </button>
            </div>
          </div>

          {/* Recent Searches */}
          {recentSearches.length > 0 && (
            <div className="pt-2 mt-1 border-t border-[#f0edf1]">
              <div className="flex items-center justify-between px-2 py-1 text-[10px] font-bold text-[#76777d] uppercase tracking-wider font-mono">
                <span>Recent Searches</span>
                <button
                  onClick={clearRecentSearches}
                  className="text-[#93000a] hover:underline cursor-pointer font-normal"
                >
                  Clear
                </button>
              </div>
              <div className="flex flex-col gap-1">
                {recentSearches.map((rec, i) => (
                  <button
                    key={`${rec.latitude}-${rec.longitude}-${i}`}
                    onClick={() => handleSelectRecent(rec)}
                    className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-[#f0edf1] text-xs flex items-center justify-between gap-2 text-[#1b1b1e] cursor-pointer"
                  >
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="material-symbols-outlined text-[14px] text-[#76777d]">
                        history
                      </span>
                      <span className="truncate">{rec.displayName}</span>
                    </div>
                    {getCoverageBadge(rec.coverageStatus)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Manual Coordinate Input Modal */}
      {isCoordModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white w-full max-w-sm rounded-2xl shadow-2xl border border-[#eae7eb] p-5 flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-[#f0edf1] pb-2">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[20px] text-[#0051d5]">
                  pin_drop
                </span>
                <h3 className="text-sm font-bold text-[#1b1b1e]">Enter Geographic Coordinates</h3>
              </div>
              <button
                onClick={() => setIsCoordModalOpen(false)}
                className="text-[#76777d] hover:text-[#1b1b1e] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>

            <p className="text-xs text-[#76777d] leading-relaxed">
              Accepts standard decimal coordinates. Strata Risk evaluates coverage dynamically for any valid point on Earth.
            </p>

            <form onSubmit={handleCoordSubmit} className="flex flex-col gap-3">
              <div>
                <label className="block text-[11px] font-bold text-[#45464d] uppercase tracking-wider mb-1 font-mono">
                  Latitude (-90.0 to +90.0)
                </label>
                <input
                  type="text"
                  placeholder="e.g. 41.8781 or 19.0760"
                  value={inputLat}
                  onChange={(e) => setInputLat(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#eae7eb] focus:border-[#0051d5] focus:outline-none text-xs font-mono"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-[#45464d] uppercase tracking-wider mb-1 font-mono">
                  Longitude (-180.0 to +180.0)
                </label>
                <input
                  type="text"
                  placeholder="e.g. -87.6298 or 72.8777"
                  value={inputLon}
                  onChange={(e) => setInputLon(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#eae7eb] focus:border-[#0051d5] focus:outline-none text-xs font-mono"
                />
              </div>

              {coordError && (
                <div className="p-2 rounded-lg bg-[#fff1f2] border border-[#fecdd3] text-[11px] text-[#9f1239]">
                  {coordError}
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCoordModalOpen(false)}
                  className="px-3 py-1.5 rounded-xl border border-[#eae7eb] text-xs text-[#45464d] hover:bg-[#f0edf1] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-xl bg-[#0051d5] hover:bg-[#003ea8] text-white text-xs font-semibold shadow-xs cursor-pointer transition-colors"
                >
                  Evaluate Location
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
