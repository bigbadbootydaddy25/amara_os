import { useEffect, useRef } from "react";
import type { ParcelListItem } from "../types/parcel";

// Leaflet is loaded as a side-effect import so it mutates L global
// We import the types only and access `window.L` at runtime to avoid SSR issues.
// In Vite (pure client), direct import works fine.
import L from "leaflet";

interface Props {
  parcels: ParcelListItem[];
  selectedId: number | null;
  onSelect: (p: ParcelListItem) => void;
}

const DEFAULT_CENTER: [number, number] = [37.7749, -122.4194]; // SF fallback

export function MapView({ parcels, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
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

    // Remove old markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current.clear();

    const withCoords = parcels.filter((p) => p.latitude != null && p.longitude != null);

    withCoords.forEach((p) => {
      const color =
        p.recommendation === "GO"    ? "#22c55e" :
        p.recommendation === "MAYBE" ? "#eab308" : "#ef4444";

      const marker = L.circleMarker([p.latitude!, p.longitude!], {
        radius: 8,
        fillColor: color,
        color: "#fff",
        weight: 1.5,
        fillOpacity: 0.85,
      })
        .addTo(map)
        .bindTooltip(
          `<strong>${p.apn ?? "No APN"}</strong><br/>${p.city ?? ""}, ${p.state ?? ""}<br/>Score: ${p.feasibilityScore ?? "N/A"} · ${p.recommendation ?? "—"}`,
          { direction: "top" }
        )
        .on("click", () => onSelect(p));

      markersRef.current.set(p.id, marker);
    });

    // Fit bounds if we have markers
    if (withCoords.length > 0) {
      const bounds = L.latLngBounds(
        withCoords.map((p) => [p.latitude!, p.longitude!] as [number, number])
      );
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 14 });
    }
  }, [parcels, onSelect]);

  // Highlight selected
  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      (marker as any).setStyle({
        weight: id === selectedId ? 3 : 1.5,
        color: id === selectedId ? "#4f7ef8" : "#fff",
        radius: id === selectedId ? 11 : 8,
      });
    });
  }, [selectedId]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", background: "#0f1117" }}
    />
  );
}
