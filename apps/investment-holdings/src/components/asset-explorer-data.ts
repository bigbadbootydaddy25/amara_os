export type DiagramKind = "concentric" | "categories" | "nodes" | "radar" | "ascend" | "pathway";

export interface Topic {
  key: string;
  label: string;
  body: string;
  diagram: DiagramKind;
}

export const topics: Topic[] = [
  {
    key: "philosophy",
    label: "Investment Philosophy",
    body: "We approach capital deployment with discipline, patience, and a long-term view, favoring durable value over short-term speculation.",
    diagram: "concentric",
  },
  {
    key: "assets",
    label: "Strategic Asset Categories",
    body: "Our platform considers a restrained set of asset categories, each evaluated on its own strategic merit rather than market trend.",
    diagram: "categories",
  },
  {
    key: "partnership",
    label: "Partnership Approach",
    body: "We work closely and privately with our partners, aligning interests and maintaining open, direct communication throughout every engagement.",
    diagram: "nodes",
  },
  {
    key: "risk",
    label: "Risk Governance",
    body: "Rigorous risk governance underlies every decision we make, protecting capital while positioning for long-term growth.",
    diagram: "radar",
  },
  {
    key: "value",
    label: "Long-Term Value Creation",
    body: "We build for the long term, prioritizing sustainable value creation over transactional gains.",
    diagram: "ascend",
  },
  {
    key: "pathways",
    label: "Hold, Partnership, or Exit",
    body: "Every asset follows a deliberate pathway. The right path is chosen on its own merits, not on a fixed schedule.",
    diagram: "pathway",
  },
];

export const assetCategories = [
  { label: "Real Assets", body: "Tangible, strategically positioned assets held for the long term." },
  { label: "Operating Businesses", body: "Businesses with durable operating models and disciplined management." },
  { label: "Strategic Partnerships", body: "Minority or joint positions aligned with long-term partners." },
  { label: "Special Situations", body: "Selective, opportunity-specific positions evaluated on their own merits." },
];

export const pathwaySteps = ["Hold", "Partnership", "Development", "Exit"];
