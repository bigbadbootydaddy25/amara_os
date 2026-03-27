import { useEffect, useRef } from "react";
import type { ParcelListItem } from "../types/parcel";
import { HoloPins } from "./claw3d/HoloPins";
import L from "leaflet";

interface Props {
  parcels: ParcelListItem[];
  selectedId: number | null;
  onSelect: (p: ParcelListItem) => void;
}

const DEFAULT_CENTER: [number, number] = [37.7749, -122.4194]; // SF fallback

export function MapView({ parcels, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Map<number, L.CircleMarker>>(new Map());

  // Initialize map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = L.map(containerRef.current, {
      center: DEFAULT_CENTER,
      zoom: 10,
      zoomControl: true,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(mapRef.current);

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // Sync markers when parcels change
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current.clear();

    const withCoords = parcels.filter((p) => p.latitude != null && p.longitude != null);

    withCoords.forEach((p) => {
      // Keep Leaflet circle markers but make them very subtle — HoloPins renders the holo layer
      const marker = L.circleMarker([p.latitude!, p.longitude!], {
        radius: 5,
        fillColor: "transparent",
        color: "transparent",
        weight: 0,
        fillOpacity: 0,
      })
        .addTo(map)
        .on("click", () => onSelect(p));

      markersRef.current.set(p.id, marker);
    });

    if (withCoords.length > 0) {
      const bounds = L.latLngBounds(
        withCoords.map((p) => [p.latitude!, p.longitude!] as [number, number])
      );
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 14 });
    }
  }, [parcels, onSelect]);

  // Highlight selected via HoloPins (no leaflet marker style change needed)
  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      (marker as any).setStyle({
        weight: id === selectedId ? 3 : 0,
        color: id === selectedId ? "#4f7ef8" : "transparent",
        radius: id === selectedId ? 11 : 5,
      });
    });
  }, [selectedId]);

  return (
    <div ref={wrapRef} style={{ width: "100%", height: "100%", background: "#0b0d16", position: "relative" }}>
      {/* Leaflet tile map */}
      <div
        ref={containerRef}
        style={{ width: "100%", height: "100%", filter: "brightness(0.7) saturate(0.6) hue-rotate(200deg)" }}
      />
      {/* Neon hologram distress pins overlay */}
      <HoloPins parcels={parcels} mapRef={mapRef} selectedId={selectedId} />
    </div>
  );
}
