/**
 * Map Tile Provider Architecture for Strata Risk.
 *
 * Configurable base-map tile providers adhering to legitimate usage policies,
 * attribution requirements, and rate limits.
 *
 * Supports:
 * - STREET: OpenStreetMap / CARTO Voyager
 * - SATELLITE: ESRI World Imagery (High-res global aerials, no key required) / MapTiler
 * - HYBRID: ESRI World Imagery + World Boundaries & Labels
 * - TERRAIN: OpenTopoMap / USGS Topographic Relief
 * - DARK: CARTO Dark Matter (for low-light operational analysis)
 */

export type MapStyleId = 'street' | 'satellite' | 'hybrid' | 'terrain' | 'dark';

export interface TileLayerConfig {
  id: MapStyleId;
  name: string;
  description: string;
  thumbnailUrl?: string;
  url: string;
  options: {
    attribution: string;
    maxZoom: number;
    minZoom?: number;
    subdomains?: string[] | string;
    ext?: string;
    opacity?: number;
  };
  overlayLayer?: {
    url: string;
    options: {
      attribution: string;
      maxZoom: number;
      subdomains?: string[] | string;
      opacity?: number;
    };
  };
  requiresApiKey?: boolean;
  apiKeyEnvVar?: string;
  isAvailable: boolean;
  unavailableReason?: string;
}

// Optional browser environment keys
const MAPTILER_API_KEY = (import.meta as any).env?.VITE_MAPTILER_API_KEY || '';

export const MAP_PROVIDERS: Record<MapStyleId, TileLayerConfig> = {
  street: {
    id: 'street',
    name: 'Street Map',
    description: 'Detailed roads, neighborhoods, and points of interest (OpenStreetMap / CARTO)',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    options: {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
      minZoom: 2,
      subdomains: 'abcd'
    },
    isAvailable: true
  },

  satellite: {
    id: 'satellite',
    name: 'Satellite',
    description: 'Actual high-resolution aerial and orbital imagery (Esri World Imagery)',
    url: MAPTILER_API_KEY
      ? `https://api.maptiler.com/maps/satellite/{z}/{x}/{y}.jpg?key=${MAPTILER_API_KEY}`
      : 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    options: {
      attribution: MAPTILER_API_KEY
        ? '&copy; <a href="https://www.maptiler.com/copyright/">MapTiler</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        : 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
      maxZoom: 19,
      minZoom: 2
    },
    requiresApiKey: false, // ESRI World Imagery works natively without key
    isAvailable: true
  },

  hybrid: {
    id: 'hybrid',
    name: 'Hybrid',
    description: 'Satellite photography combined with readable streets, borders, and place names',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    options: {
      attribution:
        'Imagery &copy; Esri, USDA, USGS &mdash; Labels &copy; Esri World Reference',
      maxZoom: 19,
      minZoom: 2
    },
    overlayLayer: {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      options: {
        attribution: '&copy; Esri Boundaries & Places',
        maxZoom: 19,
        opacity: 0.95
      }
    },
    isAvailable: true
  },

  terrain: {
    id: 'terrain',
    name: 'Terrain',
    description: 'Topographic contour shading and elevation relief (OpenTopoMap)',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    options: {
      attribution:
        'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
      maxZoom: 17,
      minZoom: 2,
      subdomains: 'abc'
    },
    isAvailable: true
  },

  dark: {
    id: 'dark',
    name: 'Dark Map',
    description: 'Low-light cartography ideal for nighttime risk hot-spot visualization (CARTO Dark Matter)',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    options: {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
      minZoom: 2,
      subdomains: 'abcd'
    },
    isAvailable: true
  }
};

export const getTileLayerConfig = (styleId: MapStyleId): TileLayerConfig => {
  return MAP_PROVIDERS[styleId] || MAP_PROVIDERS.street;
};
