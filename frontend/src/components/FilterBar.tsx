import { useState, useCallback } from "react";
import type { ParcelFilters } from "../types/parcel";
import styles from "./FilterBar.module.css";

interface Props {
  filters: ParcelFilters;
  onChange: (f: ParcelFilters) => void;
}

const RECOMMENDATION_OPTIONS = ["GO", "MAYBE", "PASS"];
const DISTRESS_OPTIONS = [
  { key: "tax_delinquent", label: "Tax Delinquent" },
  { key: "code_violation", label: "Code Violations" },
  { key: "preforeclosure", label: "Preforeclosure" },
  { key: "vacant",         label: "Vacant" },
];

export function FilterBar({ filters, onChange }: Props) {
  const set = useCallback(
    (patch: Partial<ParcelFilters>) => onChange({ ...filters, ...patch, page: 1 }),
    [filters, onChange]
  );

  function toggleMulti(current: string | undefined, value: string): string {
    const vals = (current ?? "").split(",").filter(Boolean);
    const idx = vals.indexOf(value);
    if (idx >= 0) vals.splice(idx, 1);
    else vals.push(value);
    return vals.join(",");
  }

  const activeRecs = new Set((filters.recommendations ?? "").split(",").filter(Boolean));
  const activeDistress = new Set((filters.distress ?? "").split(",").filter(Boolean));

  return (
    <div className={styles.bar}>
      {/* Location */}
      <div className={styles.group}>
        <label>City</label>
        <input
          value={filters.city ?? ""}
          onChange={(e) => set({ city: e.target.value || undefined })}
          placeholder="e.g. Austin"
        />
      </div>

      <div className={styles.group}>
        <label>County</label>
        <input
          value={filters.county ?? ""}
          onChange={(e) => set({ county: e.target.value || undefined })}
          placeholder="e.g. Travis"
        />
      </div>

      <div className={styles.group}>
        <label>ZIP</label>
        <input
          value={filters.zip ?? ""}
          onChange={(e) => set({ zip: e.target.value || undefined })}
          placeholder="78701"
        />
      </div>

      <div className={styles.group}>
        <label>State</label>
        <input
          value={filters.state ?? ""}
          onChange={(e) => set({ state: e.target.value || undefined })}
          placeholder="TX"
          maxLength={2}
          style={{ width: 48 }}
        />
      </div>

      {/* Acres */}
      <div className={styles.group}>
        <label>Acres</label>
        <div className={styles.rangeRow}>
          <input
            type="number"
            min={0}
            placeholder="Min"
            value={filters.min_acres ?? ""}
            onChange={(e) => set({ min_acres: e.target.value ? Number(e.target.value) : undefined })}
          />
          <span>–</span>
          <input
            type="number"
            min={0}
            placeholder="Max"
            value={filters.max_acres ?? ""}
            onChange={(e) => set({ max_acres: e.target.value ? Number(e.target.value) : undefined })}
          />
        </div>
      </div>

      {/* Feasibility */}
      <div className={styles.group}>
        <label>Feasibility Score</label>
        <div className={styles.rangeRow}>
          <input
            type="number"
            min={0}
            max={100}
            placeholder="Min"
            value={filters.feasibility_min ?? ""}
            onChange={(e) =>
              set({ feasibility_min: e.target.value ? Number(e.target.value) : undefined })
            }
          />
          <span>–</span>
          <input
            type="number"
            min={0}
            max={100}
            placeholder="Max"
            value={filters.feasibility_max ?? ""}
            onChange={(e) =>
              set({ feasibility_max: e.target.value ? Number(e.target.value) : undefined })
            }
          />
        </div>
      </div>

      {/* Zoning */}
      <div className={styles.group}>
        <label>Zoning Codes</label>
        <input
          value={filters.zoning_codes ?? ""}
          onChange={(e) => set({ zoning_codes: e.target.value || undefined })}
          placeholder="R1,R2,MF (comma-sep)"
        />
      </div>

      {/* Allowed use */}
      <div className={styles.group}>
        <label>Allowed Use</label>
        <input
          value={filters.allowed_use_categories ?? ""}
          onChange={(e) => set({ allowed_use_categories: e.target.value || undefined })}
          placeholder="Residential,Mixed (comma-sep)"
        />
      </div>

      {/* Lot count */}
      <div className={styles.group}>
        <label>Est. Lots</label>
        <div className={styles.rangeRow}>
          <input
            type="number"
            min={0}
            placeholder="Min"
            value={filters.min_est_max_lot_count ?? ""}
            onChange={(e) =>
              set({ min_est_max_lot_count: e.target.value ? Number(e.target.value) : undefined })
            }
          />
          <span>–</span>
          <input
            type="number"
            min={0}
            placeholder="Max"
            value={filters.max_est_max_lot_count ?? ""}
            onChange={(e) =>
              set({ max_est_max_lot_count: e.target.value ? Number(e.target.value) : undefined })
            }
          />
        </div>
      </div>

      {/* Recommendation */}
      <div className={styles.group}>
        <label>Recommendation</label>
        <div className={styles.pills}>
          {RECOMMENDATION_OPTIONS.map((r) => (
            <button
              key={r}
              className={`${styles.pill} ${activeRecs.has(r) ? styles.pillActive : ""} ${styles[`pill${r}`]}`}
              onClick={() => set({ recommendations: toggleMulti(filters.recommendations, r) || undefined })}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Distress */}
      <div className={styles.group}>
        <label>Distress Flags</label>
        <div className={styles.pills}>
          {DISTRESS_OPTIONS.map(({ key, label }) => (
            <button
              key={key}
              className={`${styles.pill} ${activeDistress.has(key) ? styles.pillActiveWarn : ""}`}
              onClick={() => set({ distress: toggleMulti(filters.distress, key) || undefined })}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
