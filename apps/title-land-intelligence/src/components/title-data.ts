export const parcelBoundary = "8,14 78,8 92,52 66,92 12,80";

export interface OwnershipBlock {
  id: string;
  label: string;
  points: string;
  color: string;
}

export const surfaceOwnership: OwnershipBlock[] = [
  { id: "surface-a", label: "Surface Owner A (fictional)", points: "8,14 45,10 40,50 12,80", color: "#2c567e" },
  { id: "surface-b", label: "Surface Owner B (fictional)", points: "45,10 78,8 66,50 40,50", color: "#3f6d99" },
  { id: "surface-c", label: "Surface Owner C (fictional)", points: "40,50 66,50 92,52 66,92 12,80", color: "#5586b3" },
];

export const mineralOwnership = {
  label: "Mineral Estate (severed, fictional)",
  points: "20,28 70,22 82,55 55,75 22,60",
};

export const easements = [
  { x1: 12, y1: 78, x2: 60, y2: 20, label: "Access Easement (fictional)" },
  { x1: 78, y1: 10, x2: 40, y2: 90, label: "Utility Easement (fictional)" },
];

export const rightOfWay = {
  points: "8,14 20,12 30,78 12,80",
  label: "Road Right-of-Way (fictional)",
};

export const encumbrance = {
  points: "55,55 78,52 82,68 60,74",
  label: "Recorded Lien Area (fictional)",
};

export const gisPins = [
  { x: 24, y: 30 },
  { x: 55, y: 24 },
  { x: 70, y: 45 },
  { x: 44, y: 62 },
  { x: 25, y: 68 },
];

export interface ChainInstrument {
  year: string;
  label: string;
}

export const titleChain: ChainInstrument[] = [
  { year: "1958", label: "Warranty Deed (fictional)" },
  { year: "1974", label: "Warranty Deed (fictional)" },
  { year: "1981", label: "Mineral Reservation (fictional)" },
  { year: "1996", label: "Oil & Gas Lease (fictional)" },
  { year: "2004", label: "Partial Release (fictional)" },
];

export interface FlagMarker {
  id: string;
  x: number;
  y: number;
  kind: "gap" | "curative";
  label: string;
}

export const flags: FlagMarker[] = [
  {
    id: "gap-1",
    x: 50,
    y: 40,
    kind: "gap",
    label: "Gap in title: chain of title incomplete between 1958 and 1961 (fictional).",
  },
  {
    id: "curative-1",
    x: 68,
    y: 60,
    kind: "curative",
    label: "Curative item: outstanding lien release needed before closing (fictional).",
  },
];

export type LayerKey =
  | "boundary"
  | "surface"
  | "mineral"
  | "easements"
  | "row"
  | "encumbrances"
  | "gis";

export interface LayerDef {
  key: LayerKey;
  label: string;
  color: string;
}

export const layers: LayerDef[] = [
  { key: "boundary", label: "Parcel Boundaries", color: "#b99c5e" },
  { key: "surface", label: "Surface Ownership", color: "#3f6d99" },
  { key: "mineral", label: "Mineral Ownership", color: "#8b93a3" },
  { key: "easements", label: "Easements", color: "#dcc389" },
  { key: "row", label: "Rights-of-Way", color: "#2c567e" },
  { key: "encumbrances", label: "Encumbrances", color: "#a8283a" },
  { key: "gis", label: "GIS & Courthouse Records", color: "#5fd3c4" },
];
