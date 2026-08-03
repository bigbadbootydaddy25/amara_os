export * from "./types";
export * from "./legal";
export * from "./divisions";
export * from "./value-chain";
export { capitalContent } from "./capital";
export { landDevelopmentContent } from "./land-development";
export { investmentHoldingsContent } from "./investment-holdings";
export { titleLandIntelligenceContent } from "./title-land-intelligence";

import type { SiteContent } from "./types";
import type { SiteKey } from "@aces/brand";
import { capitalContent } from "./capital";
import { landDevelopmentContent } from "./land-development";
import { investmentHoldingsContent } from "./investment-holdings";
import { titleLandIntelligenceContent } from "./title-land-intelligence";

export const siteContent: Record<SiteKey, SiteContent> = {
  capital: capitalContent,
  "land-development": landDevelopmentContent,
  "investment-holdings": investmentHoldingsContent,
  "title-land-intelligence": titleLandIntelligenceContent,
};

export function getSiteContent(key: SiteKey): SiteContent {
  return siteContent[key];
}
