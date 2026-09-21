import type { GeocodeResult } from './geocode';
import type { PowerLinesResult } from './overpass';
import type { SoilSuitabilityResult } from './soil';

export type { GeocodeResult, PowerLinesResult, SoilSuitabilityResult };

export interface SearchedSite {
  label: string;
  lon: number;
  lat: number;
}
