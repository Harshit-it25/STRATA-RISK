import { TimeStep, SectorOption } from '../types';

export const FORECAST_TIMELINE: TimeStep[] = [
  {
    hour: '08:00',
    label: '08:00 (Morning Rush)',
    sublabel: 'Peak commuter transition',
    fillPct: '0%',
    zones: {
      market: {
        id: 'sec-04',
        key: 'market',
        name: 'Market Road Corridor',
        code: 'SEC-04',
        tag: 'MARKET ROAD CORRIDOR • SEC-04',
        score: 38,
        delta: '-5',
        trend: 'south_east',
        trendLabel: '-5 vs 04:00',
        level: 'Moderate',
        observations: 31,
        coordinates: { x: 22, y: 18 },
        reasons: [
          'Morning commercial foot traffic ramping up along arterial corridors.',
          'Early precinct dispatch reports remain in normal dispersion band.',
          'Transit hub bus turnstile volume shows steady standard flow.'
        ]
      },
      central: {
        id: 'sec-02',
        key: 'central',
        name: 'Central Station Hub',
        code: 'SEC-02',
        tag: 'CENTRAL TRANSIT HUB • SEC-02',
        score: 71,
        delta: '+24',
        trend: 'north_east',
        trendLabel: '+24 vs 04:00',
        level: 'Higher',
        observations: 94,
        coordinates: { x: 74, y: 36 },
        reasons: [
          'High passenger throughput bottleneck during morning rail transfers.',
          'Dense spatial congregation across concourses A through D.',
          'Sensor velocity spikes on multi-modal escalator junctions.'
        ]
      },
      riverside: {
        id: 'sec-09',
        key: 'riverside',
        name: 'Riverside Recreation Corridor',
        code: 'SEC-09',
        tag: 'RIVERSIDE ESPLANADE • SEC-09',
        score: 14,
        delta: '-2',
        trend: 'south_east',
        trendLabel: '-2 vs 04:00',
        level: 'Lower',
        observations: 12,
        coordinates: { x: 14, y: 72 },
        reasons: [
          'Minimal pedestrian transit activity along waterfront esplanade.',
          'Unobstructed sightlines and ambient illumination active.',
          'Zero historical anomaly spikes in morning recreational periods.'
        ]
      },
      east: {
        id: 'sec-12',
        key: 'east',
        name: 'Industrial East Sector',
        code: 'SEC-12',
        tag: 'EAST LOGISTICS YARDS • SEC-12',
        score: '--',
        delta: '0',
        trend: 'remove',
        trendLabel: 'Sparse',
        level: 'Sparse',
        observations: '3 (Sparse)',
        reasons: [
          'Sensor telemetry coverage below 35% statistical threshold.',
          'Insufficient historical log depth to warrant confident Bayesian projection.',
          'Recommended action: deploy mobile sensor node before tactical routing.'
        ],
        coordinates: { x: 78, y: 68 }
      }
    }
  },
  {
    hour: '12:00',
    label: '12:00 (Midday Transit)',
    sublabel: 'Lunchtime commercial dispersal',
    fillPct: '25%',
    zones: {
      market: {
        id: 'sec-04',
        key: 'market',
        name: 'Market Road Corridor',
        code: 'SEC-04',
        tag: 'MARKET ROAD CORRIDOR • SEC-04',
        score: 44,
        delta: '+6',
        trend: 'north_east',
        trendLabel: '+6 vs 08:00',
        level: 'Moderate',
        observations: 38,
        coordinates: { x: 22, y: 18 },
        reasons: [
          'Midday pedestrian density elevated around dining precincts.',
          'Commercial delivery traffic slowing arterial intersection clearance.',
          'Telemetry indicates localized crowd clustering near Plaza North.'
        ]
      },
      central: {
        id: 'sec-02',
        key: 'central',
        name: 'Central Station Hub',
        code: 'SEC-02',
        tag: 'CENTRAL TRANSIT HUB • SEC-02',
        score: 58,
        delta: '-13',
        trend: 'south_east',
        trendLabel: '-13 vs 08:00',
        level: 'Moderate',
        observations: 82,
        coordinates: { x: 74, y: 36 },
        reasons: [
          'Platform dispersal stabilized following morning commuter surge.',
          'Even passenger distribution on intermediate subway platforms.',
          'Dispatch log frequency tracking within nominal baseline envelope.'
        ]
      },
      riverside: {
        id: 'sec-09',
        key: 'riverside',
        name: 'Riverside Recreation Corridor',
        code: 'SEC-09',
        tag: 'RIVERSIDE ESPLANADE • SEC-09',
        score: 22,
        delta: '+8',
        trend: 'north_east',
        trendLabel: '+8 vs 08:00',
        level: 'Lower',
        observations: 18,
        coordinates: { x: 14, y: 72 },
        reasons: [
          'Slight uptick in park foot traffic during midday lunch breaks.',
          'Clear line of sight maintained along riverbank walk.',
          'Incident rate remains at bottom quartile baseline.'
        ]
      },
      east: {
        id: 'sec-12',
        key: 'east',
        name: 'Industrial East Sector',
        code: 'SEC-12',
        tag: 'EAST LOGISTICS YARDS • SEC-12',
        score: '--',
        delta: '0',
        trend: 'remove',
        trendLabel: 'Sparse',
        level: 'Sparse',
        observations: '4 (Sparse)',
        reasons: [
          'Telemetry nodes offline in sector quadrants 3 & 4.',
          'Bayesian confidence interval exceeds acceptable operational threshold (±18).',
          'Data ingestion rate requires supplementary telemetry log verification.'
        ],
        coordinates: { x: 78, y: 68 }
      }
    }
  },
  {
    hour: '16:00',
    label: '16:00 (Pre-Peak Window)',
    sublabel: 'School & early egress shifts',
    fillPct: '50%',
    zones: {
      market: {
        id: 'sec-04',
        key: 'market',
        name: 'Market Road Corridor',
        code: 'SEC-04',
        tag: 'MARKET ROAD CORRIDOR • SEC-04',
        score: 54,
        delta: '+10',
        trend: 'north_east',
        trendLabel: '+10 vs 12:00',
        level: 'Moderate',
        observations: 40,
        coordinates: { x: 22, y: 18 },
        reasons: [
          'Gradual buildup of retail and early shift worker transitions.',
          'Intersection queuing times rising along Market Blvd & 4th.',
          'Camera crowd density models detect early concentration pockets.'
        ]
      },
      central: {
        id: 'sec-02',
        key: 'central',
        name: 'Central Station Hub',
        code: 'SEC-02',
        tag: 'CENTRAL TRANSIT HUB • SEC-02',
        score: 52,
        delta: '-6',
        trend: 'south_east',
        trendLabel: '-6 vs 12:00',
        level: 'Moderate',
        observations: 76,
        coordinates: { x: 74, y: 36 },
        reasons: [
          'Transit hub entering steady pre-rush holding pattern.',
          'Staff staging and safety personnel deployed across gates 1-6.',
          'Predicted anomaly velocity remains within acceptable variance.'
        ]
      },
      riverside: {
        id: 'sec-09',
        key: 'riverside',
        name: 'Riverside Recreation Corridor',
        code: 'SEC-09',
        tag: 'RIVERSIDE ESPLANADE • SEC-09',
        score: 20,
        delta: '-2',
        trend: 'south_east',
        trendLabel: '-2 vs 12:00',
        level: 'Lower',
        observations: 15,
        coordinates: { x: 14, y: 72 },
        reasons: [
          'Consistent calm baseline along open greenway.',
          'Zero municipal emergency calls recorded in prior 4 hours.',
          'Stable ambient pedestrian distribution.'
        ]
      },
      east: {
        id: 'sec-12',
        key: 'east',
        name: 'Industrial East Sector',
        code: 'SEC-12',
        tag: 'EAST LOGISTICS YARDS • SEC-12',
        score: '--',
        delta: '0',
        trend: 'remove',
        trendLabel: 'Sparse',
        level: 'Sparse',
        observations: '2 (Sparse)',
        reasons: [
          'Sparse sensor density across warehouse access lanes.',
          'Bayesian likelihood distribution is flat/inconclusive.',
          'Requires auxiliary surveillance sweep.'
        ],
        coordinates: { x: 78, y: 68 }
      }
    }
  },
  {
    hour: '20:00',
    label: '20:00 (Evening Peak)',
    sublabel: 'Maximum projected incident variance',
    fillPct: '75%',
    zones: {
      market: {
        id: 'sec-04',
        key: 'market',
        name: 'Market Road Corridor',
        code: 'SEC-04',
        tag: 'MARKET ROAD CORRIDOR • SEC-04',
        score: 72,
        delta: '+18',
        trend: 'north_east',
        trendLabel: '+18 vs 16:00',
        level: 'Higher',
        observations: 42,
        coordinates: { x: 22, y: 18 },
        reasons: [
          'Historical evening spatial clustering around central transit transfer point.',
          'Elevated municipal safety signal velocity reported within 400m perimeter.',
          'High pedestrian density pattern correlation observed during peak hours.'
        ]
      },
      central: {
        id: 'sec-02',
        key: 'central',
        name: 'Central Station Hub',
        code: 'SEC-02',
        tag: 'CENTRAL TRANSIT HUB • SEC-02',
        score: 54,
        delta: '±0',
        trend: 'trending_flat',
        trendLabel: '±0 vs 16:00',
        level: 'Moderate',
        observations: 88,
        coordinates: { x: 74, y: 36 },
        reasons: [
          'Continuous passenger throughput creates stable baseline activity.',
          'High security presence offsets localized density clusters.',
          'Camera telemetry confirms consistent pedestrian departure velocity.'
        ]
      },
      riverside: {
        id: 'sec-09',
        key: 'riverside',
        name: 'Riverside Recreation Corridor',
        code: 'SEC-09',
        tag: 'RIVERSIDE ESPLANADE • SEC-09',
        score: 18,
        delta: '-4',
        trend: 'south_east',
        trendLabel: '-4 vs 16:00',
        level: 'Lower',
        observations: 19,
        coordinates: { x: 14, y: 72 },
        reasons: [
          'Low evening foot traffic along recreational waterfront path.',
          'Consistent ambient lighting and clear visibility corridors.',
          'Absence of recent dispatch calls in preceding 72-hour cycle.'
        ]
      },
      east: {
        id: 'sec-12',
        key: 'east',
        name: 'Industrial East Sector',
        code: 'SEC-12',
        tag: 'EAST LOGISTICS YARDS • SEC-12',
        score: '--',
        delta: '0',
        trend: 'remove',
        trendLabel: 'Sparse',
        level: 'Sparse',
        observations: '3 observations',
        reasons: [
          'Sensor telemetry coverage below 35% statistical threshold.',
          'Insufficient historical log depth to warrant confident Bayesian projection.',
          'Recommended action: deploy mobile sensor node before tactical routing.'
        ],
        coordinates: { x: 78, y: 68 }
      }
    }
  },
  {
    hour: '00:00',
    label: '00:00 (Late Night)',
    sublabel: 'Post-transit curfew dispersion',
    fillPct: '100%',
    zones: {
      market: {
        id: 'sec-04',
        key: 'market',
        name: 'Market Road Corridor',
        code: 'SEC-04',
        tag: 'MARKET ROAD CORRIDOR • SEC-04',
        score: 61,
        delta: '-11',
        trend: 'south_east',
        trendLabel: '-11 vs 20:00',
        level: 'Moderate',
        observations: 27,
        coordinates: { x: 22, y: 18 },
        reasons: [
          'Nightlife dispersal winding down; foot traffic attenuating.',
          'Precinct patrols maintained along central commercial strip.',
          'Risk variance dropping from evening high but remains above baseline.'
        ]
      },
      central: {
        id: 'sec-02',
        key: 'central',
        name: 'Central Station Hub',
        code: 'SEC-02',
        tag: 'CENTRAL TRANSIT HUB • SEC-02',
        score: 32,
        delta: '-22',
        trend: 'south_east',
        trendLabel: '-22 vs 20:00',
        level: 'Moderate',
        observations: 34,
        coordinates: { x: 74, y: 36 },
        reasons: [
          'Subway system operating on late-night reduced schedule.',
          'Terminal gates 4 through 8 closed for maintenance cleaning.',
          'Incident probability returns to tranquil baseline levels.'
        ]
      },
      riverside: {
        id: 'sec-09',
        key: 'riverside',
        name: 'Riverside Recreation Corridor',
        code: 'SEC-09',
        tag: 'RIVERSIDE ESPLANADE • SEC-09',
        score: 12,
        delta: '-6',
        trend: 'south_east',
        trendLabel: '-6 vs 20:00',
        level: 'Lower',
        observations: 8,
        coordinates: { x: 14, y: 72 },
        reasons: [
          'Park gates closed to vehicular and pedestrian throughput.',
          'Motion sensors report near-zero spatial disruption.',
          'Minimal risk expectation until 05:30 morning reopening.'
        ]
      },
      east: {
        id: 'sec-12',
        key: 'east',
        name: 'Industrial East Sector',
        code: 'SEC-12',
        tag: 'EAST LOGISTICS YARDS • SEC-12',
        score: '--',
        delta: '0',
        trend: 'remove',
        trendLabel: 'Sparse',
        level: 'Sparse',
        observations: '1 observation',
        reasons: [
          'Sparse telemetry logs across freight yards overnight.',
          'Model relies strictly on historical aggregate prior distributions.',
          'Uncertainty band remains wide (±22).'
        ],
        coordinates: { x: 78, y: 68 }
      }
    }
  }
];

export const SECTOR_OPTIONS: SectorOption[] = [
  { id: 'zone-04', name: 'Downtown Metro / Loop (CPD 001)', code: 'CPD-01', status: 'Active Monitoring', incidentTrend: '+14% Peak' },
  { id: 'zone-02', name: 'Central Transit Loop / Near North (CPD 018)', code: 'CPD-18', status: 'Moderate Traffic', incidentTrend: 'Baseline' },
  { id: 'zone-09', name: 'Lakefront Esplanade / Town Hall (CPD 019)', code: 'CPD-19', status: 'Normal Flow', incidentTrend: '-4% Calm' },
  { id: 'zone-12', name: 'Industrial South Yards / Deering (CPD 009)', code: 'CPD-09', status: 'Sparse Baseline', incidentTrend: 'Low Base' },
  { id: 'zone-07', name: 'University & Medical Quarter (CPD 012)', code: 'CPD-12', status: 'Active Monitoring', incidentTrend: '+2% Steady' },
];

export const VALIDATION_METRICS = {
  brierScore: '0.142',
  brierTarget: '< 0.150',
  rocAuc: '0.884',
  calibrationSlope: '0.982',
  logLoss: '0.312',
  demographicParity: '0.96',
  disparateImpactRatio: '1.02',
  ingestionIntegrity: '99.4%',
  precinctCount: 14,
  lastCalibrationDate: 'Oct 24, 04:00 UTC',
  modelVersion: 'v4.2.1-calibrated-bayesian',
  totalObservationsProcessed: '124,850'
};
