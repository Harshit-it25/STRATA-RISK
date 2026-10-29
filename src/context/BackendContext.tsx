import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { ApiService, ApiResult } from '../services/api';
import {
  ForecastResponse,
  MapResponse,
  ModelHealthResponse,
  ValidationResponse,
  SectorOption,
  TimeStep,
  SelectedLocation,
  LocationForecastResponse,
  GeographicCoverageStatus
} from '../types';
import { FORECAST_TIMELINE, SECTOR_OPTIONS } from '../data/mockData';

const DEFAULT_LOCATION: SelectedLocation = {
  displayName: 'Downtown Metro / Loop (District 001)',
  latitude: 41.8719,
  longitude: -87.6283,
  regionId: 'chicago',
  regionName: 'Chicago Metropolitan Area, Illinois, USA',
  coverageStatus: 'SUPPORTED',
  timezone: 'America/Chicago',
  resolvedSectorId: 'zone-04',
  resolvedZoneKey: 'market',
  sourceType: 'preset'
};

interface BackendContextType {
  backendUrl: string;
  isBackendOnline: boolean;
  isConnecting: boolean;
  backendError: string | null;
  retryConnection: () => Promise<void>;
  updateBackendUrl: (newUrl: string) => void;

  // Forecast state (Legacy sector compatibility)
  selectedSector: SectorOption;
  setSelectedSector: (sector: SectorOption) => void;
  selectedTime: string;
  setSelectedTime: (time: string) => void;
  selectedDate: string;
  setSelectedDate: (date: string) => void;

  forecast: ForecastResponse | null;
  activeTimeStep: TimeStep;
  timeline: TimeStep[];
  isForecastLoading: boolean;
  forecastError: string | null;

  // Universal Location State
  selectedLocation: SelectedLocation;
  locationForecast: LocationForecastResponse | null;
  isLocationForecastLoading: boolean;
  locationForecastError: string | null;
  selectLocation: (loc: SelectedLocation) => Promise<void>;
  selectCoordinates: (lat: number, lon: number, displayName?: string) => Promise<void>;
  recentSearches: SelectedLocation[];
  clearRecentSearches: () => void;

  // Map state
  mapData: MapResponse | null;
  isMapLoading: boolean;

  // Model health state
  modelHealth: ModelHealthResponse | null;
  isModelHealthLoading: boolean;

  // Validation state
  validationData: ValidationResponse | null;
  isValidationLoading: boolean;
}

const BackendContext = createContext<BackendContextType | null>(null);

export const BackendProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [backendUrl, setBackendUrl] = useState<string>(ApiService.getBaseUrl());
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(false);
  const [isConnecting, setIsConnecting] = useState<boolean>(true);
  const [backendError, setBackendError] = useState<string | null>(null);

  const [selectedSector, setSelectedSector] = useState<SectorOption>(SECTOR_OPTIONS[0]);
  const [selectedTime, setSelectedTime] = useState<string>('20:00');
  const [selectedDate, setSelectedDate] = useState<string>('Mon, Oct 24');

  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [isForecastLoading, setIsForecastLoading] = useState<boolean>(false);
  const [forecastError, setForecastError] = useState<string | null>(null);

  // Universal Location State
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation>(DEFAULT_LOCATION);
  const selectedLocationRef = useRef<SelectedLocation>(DEFAULT_LOCATION);
  const locationRequestSeqRef = useRef<number>(0);
  const [locationForecast, setLocationForecast] = useState<LocationForecastResponse | null>(null);
  const [isLocationForecastLoading, setIsLocationForecastLoading] = useState<boolean>(false);
  const [locationForecastError, setLocationForecastError] = useState<string | null>(null);

  const [recentSearches, setRecentSearches] = useState<SelectedLocation[]>(() => {
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('strata_recent_searches');
        if (stored) return JSON.parse(stored);
      } catch {
        // ignore parse errors
      }
    }
    return [
      {
        displayName: 'Chicago, Cook County, Illinois, United States',
        latitude: 41.8781,
        longitude: -87.6298,
        regionId: 'chicago',
        coverageStatus: 'SUPPORTED',
        timezone: 'America/Chicago',
        sourceType: 'search'
      },
      {
        displayName: 'Mumbai, Maharashtra, India',
        latitude: 19.0760,
        longitude: 72.8777,
        regionId: 'mumbai',
        coverageStatus: 'UNSUPPORTED',
        timezone: 'Asia/Kolkata',
        sourceType: 'search'
      }
    ];
  });

  const [mapData, setMapData] = useState<MapResponse | null>(null);
  const [isMapLoading, setIsMapLoading] = useState<boolean>(false);

  const [modelHealth, setModelHealth] = useState<ModelHealthResponse | null>(null);
  const [isModelHealthLoading, setIsModelHealthLoading] = useState<boolean>(false);

  const [validationData, setValidationData] = useState<ValidationResponse | null>(null);
  const [isValidationLoading, setIsValidationLoading] = useState<boolean>(false);

  // Check backend health
  const checkConnection = useCallback(async () => {
    setIsConnecting(true);
    setBackendError(null);
    try {
      const healthRes = await ApiService.checkHealth();
      if (healthRes.ok) {
        setIsBackendOnline(true);
        setBackendError(null);
      } else {
        setIsBackendOnline(false);
        setBackendError(healthRes.error || 'FastAPI service offline on ' + ApiService.getBaseUrl());
      }
    } catch (err: any) {
      setIsBackendOnline(false);
      setBackendError(err.message || 'Failed to connect to backend');
    } finally {
      setIsConnecting(false);
    }
  }, []);

  // Fetch sector forecast data (legacy/compatibility)
  const fetchForecast = useCallback(async () => {
    setIsForecastLoading(true);
    setForecastError(null);

    const res = await ApiService.getForecast({
      sectorId: selectedSector.id,
      time: selectedTime,
      date: selectedDate
    });

    if (res.ok && res.data) {
      setForecast(res.data);
      setIsBackendOnline(true);
      setBackendError(null);
    } else {
      setForecastError(res.error || 'Failed to fetch risk forecast');
      if (res.isOffline) {
        setIsBackendOnline(false);
      }
    }
    setIsForecastLoading(false);
  }, [selectedSector.id, selectedTime, selectedDate]);

  // Fetch location-aware forecast with request sequencing (cancels out-of-order stale responses)
  const fetchLocationForecast = useCallback(
    async (loc: SelectedLocation) => {
      const seq = ++locationRequestSeqRef.current;
      setIsLocationForecastLoading(true);
      setLocationForecastError(null);

      const res = await ApiService.getLocationForecast({
        latitude: loc.latitude,
        longitude: loc.longitude,
        horizonHours: 4,
        time: selectedTime,
        date: selectedDate,
        timezone: loc.timezone
      });

      // Discard stale response if a newer request was dispatched
      if (seq !== locationRequestSeqRef.current) {
        return;
      }

      if (res.ok && res.data) {
        setLocationForecast(res.data);
        setIsBackendOnline(true);
        setLocationForecastError(null);

        // Update selectedLocation with resolved metadata if available
        if (res.data.location.resolved_sector_id) {
          const resolvedSec = SECTOR_OPTIONS.find(
            (s) => s.id === res.data!.location.resolved_sector_id
          );
          if (resolvedSec && resolvedSec.id !== selectedSector.id) {
            setSelectedSector(resolvedSec);
          }
        }
      } else {
        setLocationForecastError(res.error || 'Failed to retrieve location forecast');
      }
      setIsLocationForecastLoading(false);
    },
    [selectedTime, selectedDate, selectedSector.id]
  );

  // Fetch map layers
  const fetchMap = useCallback(async () => {
    setIsMapLoading(true);
    const res = await ApiService.getMap({
      sectorId: selectedSector.id,
      time: selectedTime
    });

    if (res.ok && res.data) {
      setMapData(res.data);
    }
    setIsMapLoading(false);
  }, [selectedSector.id, selectedTime]);

  // Fetch model health
  const fetchModelHealth = useCallback(async () => {
    setIsModelHealthLoading(true);
    const res = await ApiService.getModelHealth();
    if (res.ok && res.data) {
      setModelHealth(res.data);
    }
    setIsModelHealthLoading(false);
  }, []);

  // Fetch validation metrics
  const fetchValidation = useCallback(async () => {
    setIsValidationLoading(true);
    const res = await ApiService.getValidation();
    if (res.ok && res.data) {
      setValidationData(res.data);
    } else {
      setValidationData({ validation_status: 'pending' });
    }
    setIsValidationLoading(false);
  }, []);

  // Handler to select location from search / history / current
  const selectLocation = useCallback(
    async (loc: SelectedLocation) => {
      selectedLocationRef.current = loc;
      setSelectedLocation(loc);

      // Save to recent searches if not a raw precise GPS coordinate
      if (loc.sourceType === 'search' || loc.sourceType === 'preset') {
        setRecentSearches((prev) => {
          const filtered = prev.filter(
            (p) =>
              Math.abs(p.latitude - loc.latitude) > 0.005 ||
              Math.abs(p.longitude - loc.longitude) > 0.005
          );
          const updated = [loc, ...filtered].slice(0, 6);
          if (typeof window !== 'undefined') {
            try {
              localStorage.setItem('strata_recent_searches', JSON.stringify(updated));
            } catch {
              // ignore storage issues
            }
          }
          return updated;
        });
      }

      await fetchLocationForecast(loc);
    },
    [fetchLocationForecast]
  );

  // Handler to select arbitrary coordinates (e.g. Map click or Coordinate modal)
  const selectCoordinates = useCallback(
    async (lat: number, lon: number, customName?: string) => {
      // Check coverage first
      let covStatus: GeographicCoverageStatus = 'UNSUPPORTED';
      let displayName = customName || `Location (${lat.toFixed(4)}°, ${lon.toFixed(4)}°)`;
      let regId: string | null = null;
      let regName: string | null = null;

      try {
        const covRes = await ApiService.checkCoverage(lat, lon);
        if (covRes.ok && covRes.data) {
          covStatus = covRes.data.status;
          regId = covRes.data.region_id || null;
          regName = covRes.data.region_name || null;
        }
      } catch {
        // coverage check fallback
      }

      const newLoc: SelectedLocation = {
        displayName,
        latitude: lat,
        longitude: lon,
        regionId: regId,
        regionName: regName,
        coverageStatus: covStatus,
        sourceType: customName ? 'coordinates' : 'map_click'
      };

      await selectLocation(newLoc);
    },
    [selectLocation]
  );

  const clearRecentSearches = useCallback(() => {
    setRecentSearches([]);
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem('strata_recent_searches');
      } catch {
        // ignore
      }
    }
  }, []);

  // Initial connection and telemetry load on mount
  useEffect(() => {
    checkConnection();
    fetchModelHealth();
    fetchValidation();
  }, [checkConnection, fetchModelHealth, fetchValidation]);

  // Synchronize sector forecast, map layers, and current location forecast when parameters change
  useEffect(() => {
    fetchForecast();
    fetchMap();
    fetchLocationForecast(selectedLocationRef.current);
  }, [fetchForecast, fetchMap, fetchLocationForecast]);

  const updateBackendUrl = (newUrl: string) => {
    ApiService.setBaseUrl(newUrl);
    setBackendUrl(ApiService.getBaseUrl());
    checkConnection();
    fetchForecast();
    fetchLocationForecast(selectedLocationRef.current);
    fetchMap();
    fetchModelHealth();
    fetchValidation();
  };

  // Resolve active time step
  const activeTimeStep: TimeStep =
    forecast?.time_step ||
    FORECAST_TIMELINE.find((t) => t.hour === selectedTime) ||
    FORECAST_TIMELINE[3];

  const timeline: TimeStep[] =
    forecast?.timeline && forecast.timeline.length > 0
      ? forecast.timeline
      : FORECAST_TIMELINE;

  return (
    <BackendContext.Provider
      value={{
        backendUrl,
        isBackendOnline,
        isConnecting,
        backendError,
        retryConnection: checkConnection,
        updateBackendUrl,
        selectedSector,
        setSelectedSector,
        selectedTime,
        setSelectedTime,
        selectedDate,
        setSelectedDate,
        forecast,
        activeTimeStep,
        timeline,
        isForecastLoading,
        forecastError,
        selectedLocation,
        locationForecast,
        isLocationForecastLoading,
        locationForecastError,
        selectLocation,
        selectCoordinates,
        recentSearches,
        clearRecentSearches,
        mapData,
        isMapLoading,
        modelHealth,
        isModelHealthLoading,
        validationData,
        isValidationLoading
      }}
    >
      {children}
    </BackendContext.Provider>
  );
};

export const useBackend = (): BackendContextType => {
  const context = useContext(BackendContext);
  if (!context) {
    throw new Error('useBackend must be used within a BackendProvider');
  }
  return context;
};
