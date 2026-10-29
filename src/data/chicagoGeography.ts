/**
 * Operational Geographic Geometry and Lattice Definitions for Chicago Sectors.
 *
 * Sector centroids and boundaries are grounded in Chicago Police Department (CPD)
 * police district coordinates (Districts 1, 18, 19, 9, 12).
 * Note: Micro-zone sub-polygons (market, central, riverside, east) represent operational
 * corridor bounding envelopes aligned to commercial, transit, and river landmarks,
 * rather than official CPD beat administrative shapefiles.
 */

export interface ZoneGeometry {
  key: 'market' | 'central' | 'riverside' | 'east';
  name: string;
  code: string;
  center: [number, number]; // [lat, lng]
  polygon: [number, number][]; // LatLng ring
  radiusMeters: number;
}

export interface SectorGeometry {
  sectorId: string;
  name: string;
  code: string;
  center: [number, number];
  bounds: [[number, number], [number, number]]; // SW to NE
  zones: Record<'market' | 'central' | 'riverside' | 'east', ZoneGeometry>;
}

export const CHICAGO_METRO_BOUNDS: [[number, number], [number, number]] = [
  [41.644, -87.940], // Southwest
  [42.023, -87.523]  // Northeast
];

export const CHICAGO_SECTORS_GEOMETRY: Record<string, SectorGeometry> = {
  'zone-04': {
    sectorId: 'zone-04',
    name: 'Downtown Metro / Loop (District 001)',
    code: 'CPD-01',
    center: [41.8719, -87.6283],
    bounds: [
      [41.8550, -87.6450],
      [41.8900, -87.6150]
    ],
    zones: {
      market: {
        key: 'market',
        name: 'Commercial Retail Corridor (State / Michigan)',
        code: 'CPD-COMM',
        center: [41.8820, -87.6278],
        radiusMeters: 450,
        polygon: [
          [41.8855, -87.6320],
          [41.8855, -87.6235],
          [41.8785, -87.6235],
          [41.8785, -87.6320]
        ]
      },
      central: {
        key: 'central',
        name: 'Central Station Transit Hub (Union / Loop)',
        code: 'CPD-TRN',
        center: [41.8785, -87.6390],
        radiusMeters: 400,
        polygon: [
          [41.8820, -87.6440],
          [41.8820, -87.6340],
          [41.8745, -87.6340],
          [41.8745, -87.6440]
        ]
      },
      riverside: {
        key: 'riverside',
        name: 'Lakefront & Riverfront Esplanade (Wacker / Harbor)',
        code: 'CPD-RIV',
        center: [41.8880, -87.6210],
        radiusMeters: 500,
        polygon: [
          [41.8915, -87.6265],
          [41.8915, -87.6155],
          [41.8840, -87.6155],
          [41.8840, -87.6265]
        ]
      },
      east: {
        key: 'east',
        name: 'Logistics Freight Yards (South Loop Terminals)',
        code: 'CPD-IND',
        center: [41.8610, -87.6310],
        radiusMeters: 550,
        polygon: [
          [41.8660, -87.6370],
          [41.8660, -87.6250],
          [41.8560, -87.6250],
          [41.8560, -87.6370]
        ]
      }
    }
  },

  'zone-02': {
    sectorId: 'zone-02',
    name: 'Central Transit Loop / Near North (District 018)',
    code: 'CPD-18',
    center: [41.9003, -87.6336],
    bounds: [
      [41.8850, -87.6520],
      [41.9160, -87.6180]
    ],
    zones: {
      market: {
        key: 'market',
        name: 'Magnificent Mile / Michigan Ave Corridor',
        code: 'CPD-COMM',
        center: [41.9020, -87.6240],
        radiusMeters: 450,
        polygon: [
          [41.9070, -87.6290],
          [41.9070, -87.6200],
          [41.8970, -87.6200],
          [41.8970, -87.6290]
        ]
      },
      central: {
        key: 'central',
        name: 'Clark & Division Transit Intersection',
        code: 'CPD-TRN',
        center: [41.9040, -87.6315],
        radiusMeters: 400,
        polygon: [
          [41.9085, -87.6365],
          [41.9085, -87.6270],
          [41.8995, -87.6270],
          [41.8995, -87.6365]
        ]
      },
      riverside: {
        key: 'riverside',
        name: 'Gold Coast Shoreline & Oak Street Beach',
        code: 'CPD-RIV',
        center: [41.9035, -87.6210],
        radiusMeters: 450,
        polygon: [
          [41.9080, -87.6250],
          [41.9080, -87.6160],
          [41.8990, -87.6160],
          [41.8990, -87.6250]
        ]
      },
      east: {
        key: 'east',
        name: 'Goose Island Industrial / Freight Strip',
        code: 'CPD-IND',
        center: [41.9030, -87.6540],
        radiusMeters: 550,
        polygon: [
          [41.9080, -87.6590],
          [41.9080, -87.6490],
          [41.8980, -87.6490],
          [41.8980, -87.6590]
        ]
      }
    }
  },

  'zone-09': {
    sectorId: 'zone-09',
    name: 'Lakefront Esplanade / Town Hall (District 019)',
    code: 'CPD-19',
    center: [41.9480, -87.6594],
    bounds: [
      [41.9300, -87.6800],
      [41.9660, -87.6400]
    ],
    zones: {
      market: {
        key: 'market',
        name: 'Wrigleyville & Clark St Retail',
        code: 'CPD-COMM',
        center: [41.9485, -87.6555],
        radiusMeters: 450,
        polygon: [
          [41.9530, -87.6605],
          [41.9530, -87.6505],
          [41.9440, -87.6505],
          [41.9440, -87.6605]
        ]
      },
      central: {
        key: 'central',
        name: 'Belmont & Sheffield CTA Junction',
        code: 'CPD-TRN',
        center: [41.9398, -87.6534],
        radiusMeters: 400,
        polygon: [
          [41.9440, -87.6580],
          [41.9440, -87.6485],
          [41.9355, -87.6485],
          [41.9355, -87.6580]
        ]
      },
      riverside: {
        key: 'riverside',
        name: 'Belmont Harbor & Lakefront Trail',
        code: 'CPD-RIV',
        center: [41.9430, -87.6400],
        radiusMeters: 500,
        polygon: [
          [41.9475, -87.6450],
          [41.9475, -87.6350],
          [41.9385, -87.6350],
          [41.9385, -87.6450]
        ]
      },
      east: {
        key: 'east',
        name: 'Ravenswood Rail Yards & Corridor',
        code: 'CPD-IND',
        center: [41.9530, -87.6740],
        radiusMeters: 500,
        polygon: [
          [41.9575, -87.6790],
          [41.9575, -87.6690],
          [41.9485, -87.6690],
          [41.9485, -87.6790]
        ]
      }
    }
  },

  'zone-12': {
    sectorId: 'zone-12',
    name: 'Industrial South Yards / Deering (District 009)',
    code: 'CPD-09',
    center: [41.8169, -87.6652],
    bounds: [
      [41.8000, -87.6850],
      [41.8350, -87.6450]
    ],
    zones: {
      market: {
        key: 'market',
        name: 'Halsted / 35th St Commercial Junction',
        code: 'CPD-COMM',
        center: [41.8310, -87.6465],
        radiusMeters: 450,
        polygon: [
          [41.8355, -87.6515],
          [41.8355, -87.6415],
          [41.8265, -87.6415],
          [41.8265, -87.6515]
        ]
      },
      central: {
        key: 'central',
        name: 'Ashland Ave Transit Corridor',
        code: 'CPD-TRN',
        center: [41.8220, -87.6650],
        radiusMeters: 400,
        polygon: [
          [41.8265, -87.6700],
          [41.8265, -87.6600],
          [41.8175, -87.6600],
          [41.8175, -87.6700]
        ]
      },
      riverside: {
        key: 'riverside',
        name: 'Bubbly Creek Waterfront Channel',
        code: 'CPD-RIV',
        center: [41.8340, -87.6600],
        radiusMeters: 450,
        polygon: [
          [41.8385, -87.6650],
          [41.8385, -87.6550],
          [41.8295, -87.6550],
          [41.8295, -87.6650]
        ]
      },
      east: {
        key: 'east',
        name: 'Stockyards Freight Terminals & Rail Yards',
        code: 'CPD-IND',
        center: [41.8120, -87.6630],
        radiusMeters: 600,
        polygon: [
          [41.8170, -87.6700],
          [41.8170, -87.6560],
          [41.8070, -87.6560],
          [41.8070, -87.6700]
        ]
      }
    }
  },

  'zone-07': {
    sectorId: 'zone-07',
    name: 'University & Medical Quarter (District 012)',
    code: 'CPD-12',
    center: [41.8807, -87.6687],
    bounds: [
      [41.8650, -87.6900],
      [41.8950, -87.6480]
    ],
    zones: {
      market: {
        key: 'market',
        name: 'West Loop / Randolph Restaurant Row',
        code: 'CPD-COMM',
        center: [41.8845, -87.6520],
        radiusMeters: 450,
        polygon: [
          [41.8890, -87.6570],
          [41.8890, -87.6470],
          [41.8800, -87.6470],
          [41.8800, -87.6570]
        ]
      },
      central: {
        key: 'central',
        name: 'Illinois Medical District / CTA Pink Line',
        code: 'CPD-TRN',
        center: [41.8715, -87.6740],
        radiusMeters: 400,
        polygon: [
          [41.8760, -87.6790],
          [41.8760, -87.6690],
          [41.8670, -87.6690],
          [41.8670, -87.6790]
        ]
      },
      riverside: {
        key: 'riverside',
        name: 'Union Park & Ashland Green Spine',
        code: 'CPD-RIV',
        center: [41.8850, -87.6670],
        radiusMeters: 450,
        polygon: [
          [41.8895, -87.6720],
          [41.8895, -87.6620],
          [41.8805, -87.6620],
          [41.8805, -87.6720]
        ]
      },
      east: {
        key: 'east',
        name: 'Kinzie Industrial Corridor & Rail Spur',
        code: 'CPD-IND',
        center: [41.8890, -87.6740],
        radiusMeters: 550,
        polygon: [
          [41.8940, -87.6800],
          [41.8940, -87.6680],
          [41.8840, -87.6680],
          [41.8840, -87.6800]
        ]
      }
    }
  }
};

// Major Chicago Arterial Highways & Thoroughfares (real GPS paths)
export const CHICAGO_ARTERIALS: Array<{ name: string; path: [number, number][] }> = [
  {
    name: 'MICHIGAN AVE',
    path: [
      [41.8500, -87.6242],
      [41.8750, -87.6243],
      [41.8890, -87.6244],
      [41.9000, -87.6245],
      [41.9120, -87.6246]
    ]
  },
  {
    name: 'STATE ST',
    path: [
      [41.8500, -87.6276],
      [41.8750, -87.6276],
      [41.8840, -87.6277],
      [41.9000, -87.6278],
      [41.9120, -87.6278]
    ]
  },
  {
    name: 'WACKER DR',
    path: [
      [41.8750, -87.6370],
      [41.8850, -87.6370],
      [41.8867, -87.6330],
      [41.8867, -87.6220],
      [41.8880, -87.6180]
    ]
  },
  {
    name: 'HALSTED ST',
    path: [
      [41.8100, -87.6465],
      [41.8500, -87.6465],
      [41.8800, -87.6467],
      [41.9200, -87.6470],
      [41.9500, -87.6475]
    ]
  },
  {
    name: 'ASHLAND AVE',
    path: [
      [41.8100, -87.6652],
      [41.8500, -87.6655],
      [41.8800, -87.6660],
      [41.9200, -87.6670],
      [41.9500, -87.6680]
    ]
  }
];

export const getSectorGeometry = (sectorId: string): SectorGeometry => {
  return CHICAGO_SECTORS_GEOMETRY[sectorId] || CHICAGO_SECTORS_GEOMETRY['zone-04'];
};
