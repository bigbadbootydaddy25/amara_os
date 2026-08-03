export interface ValueChainStage {
  id: string;
  label: string;
  detail: string;
}

export const valueChainStages: ValueChainStage[] = [
  {
    id: "capital-alignment",
    label: "Capital Alignment",
    detail: "Capital sets strategic direction and allocates resources across the platform.",
  },
  {
    id: "opportunity-intelligence",
    label: "Opportunity Intelligence",
    detail: "Opportunities are identified and evaluated against platform strategy.",
  },
  {
    id: "title-land-analysis",
    label: "Title & Land Analysis",
    detail: "Title & Land Intelligence verifies ownership, title, and land data.",
  },
  {
    id: "site-control",
    label: "Site Control",
    detail: "Land Development secures site control on qualifying opportunities.",
  },
  {
    id: "entitlement-advancement",
    label: "Entitlement Advancement",
    detail: "Entitlement and planning approvals are advanced methodically.",
  },
  {
    id: "infrastructure-development",
    label: "Infrastructure Development",
    detail: "Horizontal infrastructure is designed, permitted, and built.",
  },
  {
    id: "finished-assets",
    label: "Finished Lots or Strategic Assets",
    detail: "The result is a finished, de-risked lot or strategic asset.",
  },
  {
    id: "hold-partner-develop-exit",
    label: "Hold, Partnership, Development, or Exit",
    detail: "Investment Holdings determines the long-term path for the finished asset.",
  },
];
