export interface Phase {
  id: string;
  label: string;
  description: string;
}

export const phases: Phase[] = [
  {
    id: "raw-land",
    label: "Raw Land",
    description: "An unimproved tract, evaluated for its future potential.",
  },
  {
    id: "survey",
    label: "Survey & Preliminary Planning",
    description: "The tract boundary is surveyed and preliminary planning begins.",
  },
  {
    id: "entitlement",
    label: "Entitlement & Final Plat",
    description: "Roads and lots are platted and entitlement approvals are secured.",
  },
  {
    id: "infrastructure",
    label: "Horizontal Infrastructure",
    description: "Roads are graded and paved; water, sewer, storm, and utility systems are installed.",
  },
  {
    id: "buildout",
    label: "Finished Lots & Community Buildout",
    description: "Finished lots are delivered and the community takes shape.",
  },
];

export type LayerKey =
  | "boundary"
  | "lots"
  | "roads"
  | "water"
  | "sewer"
  | "storm"
  | "electrical";

export interface LayerDef {
  key: LayerKey;
  label: string;
  color: string;
  /** Minimum phase index at which this layer exists and can be toggled on. */
  availableFromPhase: number;
}

export const layers: LayerDef[] = [
  { key: "boundary", label: "Tract Boundary", color: "#d8ac6f", availableFromPhase: 1 },
  { key: "lots", label: "Lot Lines & Numbers", color: "#e8e2d5", availableFromPhase: 2 },
  { key: "roads", label: "Roads", color: "#c7c2b8", availableFromPhase: 2 },
  { key: "water", label: "Water Lines", color: "#5fa8d3", availableFromPhase: 3 },
  { key: "sewer", label: "Sanitary Sewer", color: "#b98b4e", availableFromPhase: 3 },
  { key: "storm", label: "Storm Drainage", color: "#5fd3c4", availableFromPhase: 3 },
  { key: "electrical", label: "Electrical & Utility Corridors", color: "#e0c34a", availableFromPhase: 3 },
];

export const tractBoundary = "6,10 94,6 97,90 4,94";

export const mainRoad = { x1: 6, y1: 50, x2: 94, y2: 50 };
export const crossRoads = [
  { x1: 32, y1: 9, x2: 32, y2: 91 },
  { x1: 68, y1: 9, x2: 68, y2: 91 },
];

interface Block {
  x: number;
  y: number;
  w: number;
  h: number;
}

const blocks: Block[] = [
  { x: 8, y: 12, w: 22, h: 36 },
  { x: 36, y: 12, w: 30, h: 36 },
  { x: 70, y: 12, w: 22, h: 36 },
  { x: 8, y: 52, w: 22, h: 36 },
  { x: 36, y: 52, w: 30, h: 36 },
  { x: 70, y: 52, w: 22, h: 36 },
];

export interface Lot {
  id: number;
  x: number;
  y: number;
  w: number;
  h: number;
  status: string;
  hasStructure: boolean;
}

const statuses = ["Available", "Reserved", "Under Contract", "Infrastructure Complete"];

function buildLots(): Lot[] {
  const lots: Lot[] = [];
  let id = 1;
  const gap = 1.2;

  for (const block of blocks) {
    const cols = 2;
    const rows = 2;
    const cellW = (block.w - gap * (cols - 1)) / cols;
    const cellH = (block.h - gap * (rows - 1)) / rows;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        lots.push({
          id,
          x: block.x + c * (cellW + gap),
          y: block.y + r * (cellH + gap),
          w: cellW,
          h: cellH,
          status: statuses[id % statuses.length],
          hasStructure: id % 3 === 0,
        });
        id += 1;
      }
    }
  }

  return lots;
}

export const lots: Lot[] = buildLots();

export interface LineSeg {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

function offsetLine(line: LineSeg, dist: number): LineSeg {
  const dx = line.x2 - line.x1;
  const dy = line.y2 - line.y1;
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  return {
    x1: line.x1 + nx * dist,
    y1: line.y1 + ny * dist,
    x2: line.x2 + nx * dist,
    y2: line.y2 + ny * dist,
  };
}

const roadLines = [mainRoad, ...crossRoads];

export const waterLines = roadLines.map((line) => offsetLine(line, -1.6));
export const sewerLines = roadLines.map((line) => offsetLine(line, 1.6));
export const stormLines = roadLines.map((line) => offsetLine(line, 3.2));

function insetPolygon(points: string, factor: number): string {
  const pairs = points
    .split(" ")
    .map((p) => p.split(",").map(Number) as [number, number]);
  const cx = pairs.reduce((sum, p) => sum + p[0], 0) / pairs.length;
  const cy = pairs.reduce((sum, p) => sum + p[1], 0) / pairs.length;
  return pairs
    .map(([x, y]) => `${cx + (x - cx) * factor},${cy + (y - cy) * factor}`)
    .join(" ");
}

export const electricalCorridor = insetPolygon(tractBoundary, 0.9);
