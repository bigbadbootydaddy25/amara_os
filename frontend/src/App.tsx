import { useState, useCallback } from "react";
import { FilterBar } from "./components/FilterBar";
import { ParcelTable } from "./components/ParcelTable";
import { ParcelDetail } from "./components/ParcelDetail";
import { MapView } from "./components/MapView";
import { PipelineDashboard } from "./components/amara/PipelineDashboard";
import { DealsDashboard } from "./components/deals/DealsDashboard";
import { DeathStarScene } from "./components/claw3d/DeathStarScene";
import { TrekViewscreen } from "./components/claw3d/TrekViewscreen";
import type { ParcelFilters, ParcelListItem, Parcel } from "./types/parcel";
import { useParcels } from "./hooks/useParcels";
import { api } from "./api/client";
import styles from "./App.module.css";

type AppMode = "console" | "deals" | "pipeline";
type PanelView = "map" | "table";

export default function App() {
  const [mode, setMode] = useState<AppMode>("deals");
  const [filters, setFilters] = useState<ParcelFilters>({ page: 1, limit: 50 });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedParcel, setSelectedParcel] = useState<Parcel | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [panelView, setPanelView] = useState<PanelView>("table");

  const { data, loading, error, refresh } = useParcels(
    mode === "console" ? filters : { limit: 0 }
  );

  const handleSelectRow = useCallback(async (p: ParcelListItem) => {
    setSelectedId(p.id);
    setDetailLoading(true);
    try {
      const res = await api.getParcel(p.id);
      setSelectedParcel(res.data);
    } catch {}
    finally { setDetailLoading(false); }
  }, []);

  const handleRecomputed = useCallback(
    (updated: Parcel) => { setSelectedParcel(updated); refresh(); },
    [refresh]
  );

  return (
    <div className={styles.root}>
      {/* ── Top Nav ────────────────────────────────────────────── */}
      <header className={styles.topbar}>
        <div className={styles.logo}>
          PropVision <span>×</span> <span className={styles.amara}>Amara OS</span>
        </div>

        <div className={styles.navCenter}>
          <button
            className={`${styles.navBtn} ${mode === "deals" ? styles.navActive : ""}`}
            onClick={() => setMode("deals")}
          >
            💼 Deals
          </button>
          <button
            className={`${styles.navBtn} ${mode === "console" ? styles.navActive : ""}`}
            onClick={() => setMode("console")}
          >
            🗺 Land Console
          </button>
          <button
            className={`${styles.navBtn} ${mode === "pipeline" ? styles.navActive : ""}`}
            onClick={() => setMode("pipeline")}
          >
            ⚡ Amara Pipeline
          </button>
        </div>

        {mode === "console" && (
          <div className={styles.viewToggle}>
            <button className={panelView === "map"   ? styles.activeView : ""} onClick={() => setPanelView("map")}>Map</button>
            <button className={panelView === "table" ? styles.activeView : ""} onClick={() => setPanelView("table")}>Table</button>
          </div>
        )}
        {mode !== "console" && (
          /* Death Star corner widget in nav right when not in console mode */
          <div className={styles.deathStarCorner} id="deathstar">
            <DeathStarScene />
          </div>
        )}
      </header>

      {/* ── Deals mode (default) ───────────────────────────────── */}
      {mode === "deals" && (
        <div className={styles.fullMain}>
          <TrekViewscreen>
            <DealsDashboard />
          </TrekViewscreen>
        </div>
      )}

      {/* ── Pipeline mode ──────────────────────────────────────── */}
      {mode === "pipeline" && (
        <div className={styles.fullMain}>
          <TrekViewscreen>
            <PipelineDashboard />
          </TrekViewscreen>
        </div>
      )}

      {/* ── Land Console mode ──────────────────────────────────── */}
      {mode === "console" && (
        <>
          <FilterBar filters={filters} onChange={setFilters} />
          <div className={styles.main}>
            <div className={styles.left}>
              {panelView === "map" ? (
                <MapView parcels={data?.data ?? []} selectedId={selectedId} onSelect={handleSelectRow} />
              ) : (
                <ParcelTable data={data} loading={loading} error={error} selectedId={selectedId}
                  onSelect={handleSelectRow} filters={filters} onFiltersChange={setFilters} />
              )}
            </div>
            <div className={styles.right}>
              <ParcelDetail parcel={selectedParcel} loading={detailLoading} onRecomputed={handleRecomputed} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
