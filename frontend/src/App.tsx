import { useState, useCallback, useEffect } from "react";
import { FilterBar } from "./components/FilterBar";
import { ParcelTable } from "./components/ParcelTable";
import { ParcelDetail } from "./components/ParcelDetail";
import { MapView } from "./components/MapView";
import type { ParcelFilters, ParcelListItem, Parcel } from "./types/parcel";
import { useParcels } from "./hooks/useParcels";
import { api } from "./api/client";
import styles from "./App.module.css";

type PanelView = "map" | "table";

export default function App() {
  const [filters, setFilters] = useState<ParcelFilters>({ page: 1, limit: 50 });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedParcel, setSelectedParcel] = useState<Parcel | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [panelView, setPanelView] = useState<PanelView>("table");

  const { data, loading, error, refresh } = useParcels(filters);

  const handleSelectRow = useCallback(async (p: ParcelListItem) => {
    setSelectedId(p.id);
    setDetailLoading(true);
    try {
      const res = await api.getParcel(p.id);
      setSelectedParcel(res.data);
    } catch {
      // ignore — detail panel shows its own state
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const handleRecomputed = useCallback((updated: Parcel) => {
    setSelectedParcel(updated);
    refresh();
  }, [refresh]);

  return (
    <div className={styles.root}>
      {/* Top Nav */}
      <header className={styles.topbar}>
        <div className={styles.logo}>PropVision <span>Land Console</span></div>
        <div className={styles.viewToggle}>
          <button
            className={panelView === "map" ? styles.activeView : ""}
            onClick={() => setPanelView("map")}
          >
            Map
          </button>
          <button
            className={panelView === "table" ? styles.activeView : ""}
            onClick={() => setPanelView("table")}
          >
            Table
          </button>
        </div>
      </header>

      {/* Filters */}
      <FilterBar filters={filters} onChange={setFilters} />

      {/* Main layout */}
      <div className={styles.main}>
        {/* Left: Map or Table */}
        <div className={styles.left}>
          {panelView === "map" ? (
            <MapView
              parcels={data?.data ?? []}
              selectedId={selectedId}
              onSelect={handleSelectRow}
            />
          ) : (
            <ParcelTable
              data={data}
              loading={loading}
              error={error}
              selectedId={selectedId}
              onSelect={handleSelectRow}
              filters={filters}
              onFiltersChange={setFilters}
            />
          )}
        </div>

        {/* Right: Detail + Assistant */}
        <div className={styles.right}>
          <ParcelDetail
            parcel={selectedParcel}
            loading={detailLoading}
            onRecomputed={handleRecomputed}
          />
        </div>
      </div>
    </div>
  );
}
