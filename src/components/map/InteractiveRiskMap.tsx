import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import { useBackend } from '../../context/BackendContext';
import { MapStyleId, MAP_PROVIDERS, getTileLayerConfig } from '../../services/mapProviders';
import {
  CHICAGO_SECTORS_GEOMETRY,
  CHICAGO_METRO_BOUNDS,
  CHICAGO_ARTERIALS,
  getSectorGeometry,
  ZoneGeometry
} from '../../data/chicagoGeography';
import { MapLayerSwitcher } from './MapLayerSwitcher';
import { MapControls } from './MapControls';
import { MapLegend } from './MapLegend';
import { OverlayLayers, RiskLevel, TimeStep } from '../../types';

interface InteractiveRiskMapProps {
  onSelectZone: (zoneKey: 'market' | 'central' | 'riverside' | 'east') => void;
  activeZoneKey: 'market' | 'central' | 'riverside' | 'east';
  layers: OverlayLayers;
  onOpenLayersModal?: () => void;
  className?: string;
}

export const InteractiveRiskMap: React.FC<InteractiveRiskMapProps> = ({
  onSelectZone,
  activeZoneKey,
  layers,
  onOpenLayersModal,
  className = ''
}) => {
  const {
    selectedLocation,
    selectCoordinates,
    locationForecast,
    activeTimeStep,
    selectedSector
  } = useBackend();

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const baseTileLayerRef = useRef<L.TileLayer | null>(null);
  const overlayTileLayerRef = useRef<L.TileLayer | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const shapesLayerGroupRef = useRef<L.LayerGroup | null>(null);

  const [currentStyle, setCurrentStyle] = useState<MapStyleId>('street');
  const [heatmapOpacity, setHeatmapOpacity] = useState<number>(0.55);
  const [showHeatmap, setShowHeatmap] = useState<boolean>(true);
  const [showZones, setShowZones] = useState<boolean>(true);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [isLocating, setIsLocating] = useState<boolean>(false);

  const isSupported = selectedLocation.coverageStatus === 'SUPPORTED';
  const isPartial = selectedLocation.coverageStatus === 'PARTIAL_COVERAGE';

  // 1. Initialize Leaflet Map once
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialLat = selectedLocation.latitude || 41.8781;
    const initialLng = selectedLocation.longitude || -87.6298;

    const map = L.map(mapContainerRef.current, {
      center: [initialLat, initialLng],
      zoom: 14,
      zoomControl: false, // We use custom Google Maps-style controls
      attributionControl: true,
      fadeAnimation: true,
      zoomAnimation: true,
      maxBoundsViscosity: 0.8
    });

    // Add scale indicator at bottom-left
    L.control.scale({ imperial: true, metric: true, position: 'bottomleft' }).addTo(map);

    // Initial base tile layer
    const tileCfg = getTileLayerConfig(currentStyle);
    const baseTiles = L.tileLayer(tileCfg.url, tileCfg.options).addTo(map);
    baseTileLayerRef.current = baseTiles;

    // Layer group for dynamic polygons, heatmaps, and arterials
    const shapeGroup = L.layerGroup().addTo(map);
    shapesLayerGroupRef.current = shapeGroup;

    // Interactive map click: selects coordinates anywhere in the world!
    map.on('click', (e: L.LeafletMouseEvent) => {
      const lat = parseFloat(e.latlng.lat.toFixed(5));
      const lng = parseFloat(e.latlng.lng.toFixed(5));
      selectCoordinates(lat, lng, `Selected Point (${lat}°, ${lng}°)`);
    });

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // 2. Switch Base Tile Layer when style changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Remove existing tile layers
    if (baseTileLayerRef.current) {
      map.removeLayer(baseTileLayerRef.current);
      baseTileLayerRef.current = null;
    }
    if (overlayTileLayerRef.current) {
      map.removeLayer(overlayTileLayerRef.current);
      overlayTileLayerRef.current = null;
    }

    const tileCfg = getTileLayerConfig(currentStyle);
    const newBase = L.tileLayer(tileCfg.url, tileCfg.options).addTo(map);
    newBase.bringToBack();
    baseTileLayerRef.current = newBase;

    // If style includes label/border overlay (e.g. Hybrid)
    if (tileCfg.overlayLayer) {
      const overlay = L.tileLayer(
        tileCfg.overlayLayer.url,
        tileCfg.overlayLayer.options
      ).addTo(map);
      overlayTileLayerRef.current = overlay;
    }
  }, [currentStyle]);

  // 3. Move/Fly Map when selectedLocation changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const currentCenter = map.getCenter();
    const targetLat = selectedLocation.latitude;
    const targetLng = selectedLocation.longitude;

    // Only fly if distance is noticeable
    const dist = Math.hypot(currentCenter.lat - targetLat, currentCenter.lng - targetLng);
    if (dist > 0.0001) {
      map.flyTo([targetLat, targetLng], Math.max(map.getZoom(), 14), {
        duration: 1.0,
        easeLinearity: 0.25
      });
    }

    const popupHtml = `
      <div style="font-family: inherit; font-size: 12px; min-width: 140px; color: #1b1b1e;">
        <strong style="display: block; font-size: 13px; margin-bottom: 2px;">${selectedLocation.displayName}</strong>
        <span style="font-family: monospace; color: #76777d; font-size: 11px;">${targetLat.toFixed(4)}°, ${targetLng.toFixed(4)}°</span>
        <div style="margin-top: 6px; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px; display: inline-block; background: ${
          isSupported ? '#dcfce7; color: #166534;' : isPartial ? '#fef3c7; color: #92400e;' : '#f1f5f9; color: #475569;'
        }">
          ${selectedLocation.coverageStatus}
        </div>
      </div>
    `;

    // Update or create location marker pin
    if (markerRef.current) {
      markerRef.current.setLatLng([targetLat, targetLng]);
      markerRef.current.setPopupContent(popupHtml);
    } else {
      const pinIcon = L.divIcon({
        className: 'strata-map-pin',
        html: `
          <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 32px; height: 32px;">
            <div style="position: absolute; width: 28px; height: 28px; border-radius: 50%; background: #0051d5; opacity: 0.3; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
            <div style="position: absolute; width: 14px; height: 14px; border-radius: 50%; background: #0051d5; border: 2.5px solid #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.35);"></div>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      const newMarker = L.marker([targetLat, targetLng], { icon: pinIcon, zIndexOffset: 1000 }).addTo(map);
      newMarker.bindPopup(popupHtml);
      markerRef.current = newMarker;
    }
  }, [selectedLocation.latitude, selectedLocation.longitude, selectedLocation.displayName, selectedLocation.coverageStatus, isSupported, isPartial]);

  // 4. Draw Authentic Risk Overlays (Grid Zones, Heatmap & Arterials)
  // ONLY drawn when location is in a SUPPORTED or PARTIAL region (Chicago)!
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = shapesLayerGroupRef.current;
    if (!map || !group) return;

    group.clearLayers();

    // If unsupported (e.g. Mumbai, Paris), DO NOT render Chicago risk overlays!
    if (!isSupported && !isPartial) {
      return;
    }

    const secGeo = getSectorGeometry(selectedSector.id);
    const zonesData = activeTimeStep.zones;

    const getRiskColor = (prob: number | null, level: RiskLevel) => {
      if (level === 'Sparse' || prob === null) return '#64748b'; // Slate
      if (prob >= 0.65) return '#ef4444'; // Red
      if (prob >= 0.30) return '#f59e0b'; // Amber
      return '#10b981'; // Green
    };

    // A. Draw Transit Arteries if layer enabled
    if (layers.transitArteries) {
      CHICAGO_ARTERIALS.forEach((art) => {
        // Road casing
        L.polyline(art.path, {
          color: '#ffffff',
          weight: 4.5,
          opacity: 0.85,
          lineCap: 'round',
          interactive: false
        }).addTo(group);

        // Core road line
        L.polyline(art.path, {
          color: '#0051d5',
          weight: 2,
          opacity: 0.75,
          dashArray: '6, 6',
          interactive: false
        }).addTo(group);
      });
    }

    // B. Draw Micro-Zone Geographic Polygons
    if (showZones && layers.topographicGrid) {
      (['market', 'central', 'riverside', 'east'] as const).forEach((zKey) => {
        const zGeo: ZoneGeometry = secGeo.zones[zKey];
        const zData = zonesData[zKey];
        const rawScore = typeof zData.score === 'number' ? zData.score : parseFloat(String(zData.score)) || 0;
        const prob = rawScore / 100;
        const color = getRiskColor(prob, zData.level);
        const isSelected = activeZoneKey === zKey;

        const polygon = L.polygon(zGeo.polygon, {
          color: isSelected ? '#0051d5' : color,
          weight: isSelected ? 3.5 : 1.8,
          fillColor: color,
          fillOpacity: isSelected ? 0.35 : 0.18,
          dashArray: isSelected ? undefined : '3, 3',
          className: 'strata-zone-poly'
        }).addTo(group);

        // Interaction on polygon
        polygon.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          onSelectZone(zKey);
        });

        polygon.bindTooltip(
          `<strong>${zGeo.name}</strong><br/>Score: ${zData.score}/100 • ${zData.level}`,
          { direction: 'top', sticky: true }
        );
      });
    }

    // C. Draw Risk Density Heatmap (Real geographic radial circles)
    if (showHeatmap && layers.densityHeatmap) {
      (['market', 'central', 'riverside', 'east'] as const).forEach((zKey) => {
        const zGeo = secGeo.zones[zKey];
        const zData = zonesData[zKey];
        const rawScore = typeof zData.score === 'number' ? zData.score : parseFloat(String(zData.score)) || 0;
        const prob = rawScore / 100;
        if (zData.level === 'Sparse' || prob <= 0) return;

        const color = getRiskColor(prob, zData.level);

        // Outer ambient glow
        L.circle(zGeo.center, {
          radius: zGeo.radiusMeters * 1.5,
          color: 'transparent',
          fillColor: color,
          fillOpacity: heatmapOpacity * 0.35 * Math.min(prob * 1.5, 1.0),
          interactive: false
        }).addTo(group);

        // Core intensity hotspot
        L.circle(zGeo.center, {
          radius: zGeo.radiusMeters,
          color: color,
          weight: 1,
          opacity: 0.3,
          fillColor: color,
          fillOpacity: heatmapOpacity * 0.65 * Math.min(prob * 1.5, 1.0),
          interactive: false
        }).addTo(group);
      });
    }

    // D. Sensor Nodes if layer enabled
    if (layers.sensorNodes) {
      (['market', 'central', 'riverside', 'east'] as const).forEach((zKey) => {
        const zGeo = secGeo.zones[zKey];
        L.circleMarker(zGeo.center, {
          radius: 4,
          color: '#ffffff',
          weight: 1.5,
          fillColor: '#0051d5',
          fillOpacity: 0.95,
          interactive: false
        }).addTo(group);
      });
    }
  }, [
    isSupported,
    isPartial,
    selectedSector.id,
    activeTimeStep,
    activeZoneKey,
    showHeatmap,
    showZones,
    heatmapOpacity,
    layers,
    onSelectZone
  ]);

  // Map Control Actions
  const handleZoomIn = useCallback(() => {
    mapInstanceRef.current?.zoomIn();
  }, []);

  const handleZoomOut = useCallback(() => {
    mapInstanceRef.current?.zoomOut();
  }, []);

  const handleRecenter = useCallback(() => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.flyTo(
      [selectedLocation.latitude, selectedLocation.longitude],
      14,
      { duration: 0.8 }
    );
  }, [selectedLocation.latitude, selectedLocation.longitude]);

  const handleLocateMe = useCallback(() => {
    if (!navigator.geolocation) return;
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        const { latitude, longitude } = pos.coords;
        selectCoordinates(
          parseFloat(latitude.toFixed(5)),
          parseFloat(longitude.toFixed(5)),
          'My Current Location'
        );
      },
      () => {
        setIsLocating(false);
      },
      { timeout: 8000 }
    );
  }, [selectCoordinates]);

  const handleToggleFullscreen = useCallback(() => {
    if (!mapContainerRef.current) return;
    if (!document.fullscreenElement) {
      mapContainerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  }, []);

  return (
    <div
      ref={mapContainerRef}
      className={`relative w-full overflow-hidden bg-[#e4e1e6] select-none ${
        isFullscreen ? 'h-screen fixed inset-0 z-50' : 'h-[480px] rounded-2xl border border-[#dcd9dd]'
      } ${className}`}
    >
      {/* Top-Right: Map Style Selector Switcher */}
      <div className="absolute top-3 right-3 flex items-start gap-2 z-[400]">
        <MapLayerSwitcher
          currentStyle={currentStyle}
          onStyleChange={setCurrentStyle}
        />
      </div>

      {/* Top-Right: Zoom, Locate, Fullscreen Floating Controls */}
      <div className="absolute top-14 right-3 z-[400]">
        <MapControls
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onRecenter={handleRecenter}
          onLocateMe={handleLocateMe}
          onToggleFullscreen={handleToggleFullscreen}
          onOpenLayersModal={onOpenLayersModal}
          isFullscreen={isFullscreen}
          isLocating={isLocating}
        />
      </div>

      {/* Top-Left: Real Coordinate & Geographic Boundary Watermark */}
      <div className="absolute top-3 left-3 z-[400] pointer-events-none font-mono text-[10px] bg-white/90 backdrop-blur-md px-2.5 py-1.5 rounded-xl shadow-md border border-[#e4e1e6] flex flex-col gap-0.5 max-w-[260px]">
        <div className="flex items-center gap-1.5 font-bold text-[#1b1b1e]">
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 ${
              isSupported ? 'bg-[#16a34a]' : isPartial ? 'bg-[#d97706]' : 'bg-[#64748b]'
            }`}
          ></span>
          <span className="truncate">
            {selectedLocation.latitude.toFixed(4)}°N, {Math.abs(selectedLocation.longitude).toFixed(4)}°
            {selectedLocation.longitude < 0 ? 'W' : 'E'}
          </span>
        </div>
        <span className="text-[9px] text-[#76777d] truncate">
          {isSupported
            ? 'Chicago Metro • Validated CPD Incident Lattice'
            : isPartial
            ? 'Metro Outer Buffer • Degraded Spatial Confidence'
            : 'Unvalidated Region • Tap Anywhere to Inspect'}
        </span>
      </div>

      {/* Bottom Center: Accessible Risk Spectrum Legend & Opacity Slider */}
      <div className="absolute bottom-3 left-3 right-3 z-[400]">
        <MapLegend
          heatmapOpacity={heatmapOpacity}
          onOpacityChange={setHeatmapOpacity}
          showHeatmap={showHeatmap}
          onToggleHeatmap={() => setShowHeatmap(!showHeatmap)}
          showZones={showZones}
          onToggleZones={() => setShowZones(!showZones)}
          isSupportedRegion={isSupported || isPartial}
        />
      </div>
    </div>
  );
};
