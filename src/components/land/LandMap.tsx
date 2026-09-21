'use client';

import { useEffect, useRef } from 'react';
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  type GeoJSONSource,
  type StyleSpecification,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { PowerLinesResult } from '@/lib/land/overpass';
import type { SearchedSite } from '@/lib/land/types';

const POWER_LINES_SOURCE = 'power-lines';
const POWER_POINTS_SOURCE = 'power-points';

// Esri World Imagery: free, keyless raster basemap — same fallback tier
// gods-eye-view uses when no imagery API key is configured.
const STYLE: StyleSpecification = {
  version: 8,
  sources: {
    esri: {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: 'Esri World Imagery',
      maxzoom: 19,
    },
  },
  layers: [{ id: 'esri', type: 'raster', source: 'esri' }],
};

function powerLinesToGeoJson(result: PowerLinesResult | null): GeoJSON.FeatureCollection {
  if (!result) return { type: 'FeatureCollection', features: [] };
  return {
    type: 'FeatureCollection',
    features: result.lines.map((line) => ({
      type: 'Feature',
      id: line.id,
      properties: { voltage: line.voltage ?? 0, operator: line.operator, kind: line.kind },
      geometry: { type: 'LineString', coordinates: line.path },
    })),
  };
}

function powerPointsToGeoJson(result: PowerLinesResult | null): GeoJSON.FeatureCollection {
  if (!result) return { type: 'FeatureCollection', features: [] };
  return {
    type: 'FeatureCollection',
    features: result.points.map((point) => ({
      type: 'Feature',
      id: point.id,
      properties: { voltage: point.voltage ?? 0, kind: point.kind },
      geometry: { type: 'Point', coordinates: [point.lon, point.lat] },
    })),
  };
}

export interface LandMapProps {
  site: SearchedSite | null;
  powerLines: PowerLinesResult | null;
  showPowerLines: boolean;
  onMapReady?: () => void;
}

export function LandMap({ site, powerLines, showPowerLines, onMapReady }: LandMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: STYLE,
      center: [-97.7431, 30.2672],
      zoom: 4,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      map.addSource(POWER_LINES_SOURCE, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: 'power-lines-layer',
        type: 'line',
        source: POWER_LINES_SOURCE,
        paint: {
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'voltage'],
            0,
            '#facc15',
            69000,
            '#fb923c',
            230000,
            '#f87171',
          ],
          'line-width': 3,
          'line-opacity': 0.9,
        },
      });
      map.addSource(POWER_POINTS_SOURCE, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: 'power-points-layer',
        type: 'circle',
        source: POWER_POINTS_SOURCE,
        paint: {
          'circle-radius': 4,
          'circle-color': '#f87171',
          'circle-stroke-color': '#1f2937',
          'circle-stroke-width': 1,
        },
      });
      onMapReady?.();
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !site) return;
    const fly = () => map.flyTo({ center: [site.lon, site.lat], zoom: 15, essential: true });
    if (map.loaded()) fly();
    else map.once('load', fly);

    if (markerRef.current) markerRef.current.remove();
    const marker = new Marker({ color: '#38bdf8' })
      .setLngLat([site.lon, site.lat])
      .setPopup(new Popup({ offset: 16 }).setText(site.label));
    if (map.loaded()) marker.addTo(map);
    else map.once('load', () => marker.addTo(map));
    markerRef.current = marker;
  }, [site]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const linesSource = map.getSource(POWER_LINES_SOURCE) as GeoJSONSource | undefined;
      const pointsSource = map.getSource(POWER_POINTS_SOURCE) as GeoJSONSource | undefined;
      linesSource?.setData(powerLinesToGeoJson(powerLines));
      pointsSource?.setData(powerPointsToGeoJson(powerLines));
    };
    if (map.loaded()) apply();
    else map.once('load', apply);
  }, [powerLines]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const setVisibility = () => {
      const visibility = showPowerLines ? 'visible' : 'none';
      if (map.getLayer('power-lines-layer')) map.setLayoutProperty('power-lines-layer', 'visibility', visibility);
      if (map.getLayer('power-points-layer')) map.setLayoutProperty('power-points-layer', 'visibility', visibility);
    };
    if (map.loaded()) setVisibility();
    else map.once('load', setVisibility);
  }, [showPowerLines]);

  return <div ref={containerRef} data-testid="land-map" className="h-full w-full" />;
}
