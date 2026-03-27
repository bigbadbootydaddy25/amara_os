import type { Parcel, PaginatedParcels, ParcelFilters } from "../types/parcel";
import type { DealReview, PipelineStats, PipelineRun } from "../types/review";

// In dev: Vite proxies to localhost:3001, so BASE="" works fine.
// In production / Docker: set VITE_API_BASE_URL in your .env or Docker env.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:3001";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE_URL + path, {
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

  // ─── Amara ───────────────────────────────────────────────────────────────
  amaraReview: (parcelId: number): Promise<{ data: DealReview }> =>
    apiFetch(`/amara/review/${parcelId}`, { method: "POST" }),

  getAmaraReview: (parcelId: number): Promise<{ data: DealReview }> =>
    apiFetch(`/amara/reviews/${parcelId}`),

  listAmaraReviews: (): Promise<{ data: DealReview[] }> =>
    apiFetch("/amara/reviews"),

  generateLOI: (
    parcelId: number,
    offerPrice: number,
    buyerEntity: string
  ): Promise<{ data: { loiText: string; review: DealReview } }> =>
    apiFetch(`/amara/generate-loi/${parcelId}`, {
      method: "POST",
      body: JSON.stringify({ offerPrice, buyerEntity }),
    }),

  generateOutreach: (parcelId: number): Promise<{ data: { ownerOutreachText: string; review: DealReview } }> =>
    apiFetch(`/amara/generate-outreach/${parcelId}`, { method: "POST" }),

  generateNegotiation: (parcelId: number): Promise<{ data: { negotiationStrategy: string; review: DealReview } }> =>
    apiFetch(`/amara/generate-negotiation/${parcelId}`, { method: "POST" }),

  overrideDecision: (
    parcelId: number,
    decision: "APPROVED" | "REJECTED",
    note?: string,
    overriddenBy?: string
  ): Promise<{ data: DealReview }> =>
    apiFetch(`/amara/override/${parcelId}`, {
      method: "POST",
      body: JSON.stringify({ decision, note, overriddenBy }),
    }),

  advanceLifecycle: (parcelId: number, status: string): Promise<{ data: DealReview }> =>
    apiFetch(`/amara/lifecycle/${parcelId}`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),

  // ─── Pipeline ─────────────────────────────────────────────────────────────
  runPipeline: (): Promise<{ data: PipelineRun }> =>
    apiFetch("/pipeline/run", { method: "POST" }),

  listPipelineRuns: (): Promise<{ data: PipelineRun[] }> =>
    apiFetch("/pipeline/runs"),

  getPipelineStats: (): Promise<{ data: PipelineStats }> =>
    apiFetch("/pipeline/stats"),
};
