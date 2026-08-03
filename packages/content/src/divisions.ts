import type { SiteKey } from "@aces/brand";

export interface DivisionProfile {
  key: SiteKey;
  name: string;
  shortName: string;
  purpose: string;
  role: string;
  href: string;
}

export const divisions: DivisionProfile[] = [
  {
    key: "land-development",
    name: "Aces N 8s Land Development",
    shortName: "Land Development",
    purpose:
      "Acquires, entitles, and develops strategically positioned land into high-value communities.",
    role:
      "Converts Capital's opportunity intelligence into site control, entitlement, and finished infrastructure.",
    href: "https://acesn8sland.com",
  },
  {
    key: "investment-holdings",
    name: "Aces N 8s Investment Holdings",
    shortName: "Investment Holdings",
    purpose:
      "Holds and manages strategic assets with disciplined, long-term capital deployment.",
    role:
      "Receives finished assets from the platform and manages the hold, partnership, or exit decision.",
    href: "https://acesn8sholdings.com",
  },
  {
    key: "title-land-intelligence",
    name: "Aces N 8s Title & Land Intelligence",
    shortName: "Title & Land Intelligence",
    purpose:
      "Delivers title research, mineral research, GIS, and due-diligence intelligence.",
    role:
      "Verifies title and land data at the front end of every decision the platform makes.",
    href: "https://acesn8stitle.com",
  },
];

export function getDivision(key: SiteKey): DivisionProfile | undefined {
  return divisions.find((d) => d.key === key);
}
