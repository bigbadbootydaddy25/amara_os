import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../api/client";
import type { ParcelListItem, ParcelFilters, PaginatedParcels } from "../types/parcel";

const DEBOUNCE_MS = 400;

export function useParcels(filters: ParcelFilters) {
  const [data, setData] = useState<PaginatedParcels | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetch = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listParcels(filters)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [JSON.stringify(filters)]); // eslint-disable-line

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(fetch, DEBOUNCE_MS);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [fetch]);

  return { data, loading, error, refresh: fetch };
}
