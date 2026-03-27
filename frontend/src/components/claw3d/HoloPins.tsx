/**
 * NEON HOLOGRAM DISTRESS PINS — Claw3D
 *
 * Renders neon blue (normal) / red (distress) SVG pins as a DOM overlay
 * on top of the Leaflet map. Positions are computed from lat/lng via
 * the Leaflet map instance passed by ref.
 *
 * Distress criteria: tax_delinquent OR foreclosure_status OR owner_absent
 */
import { useEffect, useRef, useState } from "react";
import type { ParcelListItem } from "../../types/parcel";
import type L from "leaflet";
import styles from "./HoloPins.module.css";

interface Props {
  parcels: ParcelListItem[];
  mapRef: React.MutableRefObject<L.Map | null>;
  selectedId: number | null;
}

interface PinPos {
  id: number;
  x: number;
  y: number;
  distress: boolean;
  recommendation: string | null;
  apn: string | null;
}

export function HoloPins({ parcels, mapRef, selectedId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pins, setPins] = useState<PinPos[]>([]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !containerRef.current) return;

    function reproject() {
      const map = mapRef.current;
      if (!map || !containerRef.current) return;
      const container = map.getContainer();
      const rect = container.getBoundingClientRect();
      const parentRect = containerRef.current!.getBoundingClientRect();

      const next: PinPos[] = [];
      for (const p of parcels) {
        if (p.latitude == null || p.longitude == null) continue;
        const point = map.latLngToContainerPoint([p.latitude, p.longitude]);
        const distress = !!(
          (p as any).taxDelinquent ||
          (p as any).foreclosureStatus ||
          (p as any).ownerAbsent ||
          (p as any).tax_delinquent ||
          (p as any).foreclosure_status ||
          (p as any).owner_absent
        );
        next.push({
          id: p.id,
          x: point.x + (rect.left - parentRect.left),
          y: point.y + (rect.top - parentRect.top),
          distress,
          recommendation: p.recommendation ?? null,
          apn: p.apn ?? null,
        });
      }
      setPins(next);
    }

    reproject();
    map.on("move zoom moveend zoomend", reproject);
    return () => {
      map.off("move zoom moveend zoomend", reproject);
    };
  }, [parcels, mapRef]);

  return (
    <div ref={containerRef} className={styles.overlay}>
      {pins.map((pin) => {
        const isSelected = pin.id === selectedId;
        const colorClass = pin.distress
          ? styles.pinRed
          : pin.recommendation === "GO"
          ? styles.pinGreen
          : pin.recommendation === "MAYBE"
          ? styles.pinAmber
          : styles.pinBlue;

        return (
          <div
            key={pin.id}
            className={`${styles.pin} ${colorClass} ${isSelected ? styles.pinSelected : ""} ${pin.distress ? styles.pinDistress : ""}`}
            style={{ left: pin.x, top: pin.y }}
            title={`${pin.apn ?? pin.id}${pin.distress ? " ⚠ DISTRESS" : ""}`}
          >
            <svg width="20" height="28" viewBox="0 0 20 28" fill="none">
              <path
                d="M10 0C4.477 0 0 4.477 0 10c0 7.5 10 18 10 18S20 17.5 20 10C20 4.477 15.523 0 10 0z"
                fill="currentColor"
                fillOpacity="0.85"
              />
              <circle cx="10" cy="10" r="4" fill="white" fillOpacity="0.9" />
              {pin.distress && (
                <text x="10" y="14" textAnchor="middle" fontSize="8" fill="#ff0000" fontWeight="bold">!</text>
              )}
            </svg>
            {/* Hologram beam line */}
            <span className={styles.beam} />
            {/* Pulse ring */}
            {pin.distress && <span className={styles.pulseRing} />}
          </div>
        );
      })}
    </div>
  );
}
