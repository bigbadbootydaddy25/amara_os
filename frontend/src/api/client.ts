import type { Parcel, PaginatedParcels, ParcelFilters } from "../types/parcel";

const BASE = "";  // proxied via Vite dev server; in production set to your API origin

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as any).error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

function toQueryString(filters: ParcelFilters): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "" && v !== null) {
      params.set(k, String(v));
    }
  }
  return params.toString();
}

export const api = {
  listParcels: (filters: ParcelFilters = {}): Promise<PaginatedParcels> => {
    const qs = toQueryString(filters);
    return apiFetch<PaginatedParcels>(`/parcels${qs ? `?${qs}` : ""}`);
  },

  getParcel: (id: number): Promise<{ data: Parcel }> =>
    apiFetch<{ data: Parcel }>(`/parcels/${id}`),

  recomputeFeasibility: (id: number): Promise<{ data: Parcel }> =>
    apiFetch<{ data: Parcel }>(`/parcels/${id}/recompute-feasibility`, { method: "POST" }),

  createParcel: (body: Partial<Parcel>): Promise<{ data: Parcel }> =>
    apiFetch<{ data: Parcel }>("/parcels", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  assistantQuery: (
    parcelId: number,
    message: string
  ): Promise<{ answer: string; parcelId: number }> =>
    apiFetch("/assistant/query", {
      method: "POST",
      body: JSON.stringify({ parcelId, message }),
    }),
};
