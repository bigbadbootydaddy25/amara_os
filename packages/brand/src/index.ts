export type SiteKey =
  | "capital"
  | "land-development"
  | "investment-holdings"
  | "title-land-intelligence";

export interface BrandColors {
  bg: string;
  bgElevated: string;
  surface: string;
  border: string;
  gold: string;
  goldSoft: string;
  accent: string;
  accentSoft: string;
  text: string;
  textMuted: string;
}

export interface ParentPlatformLink {
  label: string;
  name: string;
  href: string;
}

export interface BrandTokens {
  key: SiteKey;
  name: string;
  shortName: string;
  eyebrow: string;
  tagline?: string;
  description: string;
  domainPlaceholder: string;
  colors: BrandColors;
  glow: string;
  /** True only for the flagship parent platform (Capital). */
  isFlagship?: boolean;
  /** Present on division sites; links back to the Capital command center. */
  parentPlatform?: ParentPlatformLink;
}

/** Shared diagram accent colors used contextually inside interactive SVG diagrams. */
export const diagramColors = {
  red: "#8c1515",
  blue: "#1f5b91",
  green: "#3f6f4f",
};

export const brands: Record<SiteKey, BrandTokens> = {
  capital: {
    key: "capital",
    name: "Aces N 8s Capital",
    shortName: "Capital",
    eyebrow: "Flagship Parent Platform",
    tagline: "WE DON'T PLAY THE ODDS. WE CHANGE THEM.",
    description:
      "We identify opportunity where others see risk and build lasting value where vision meets execution.",
    domainPlaceholder: "acesn8scapital.com",
    isFlagship: true,
    colors: {
      bg: "#070707",
      bgElevated: "#0d0d0f",
      surface: "#0d0d0f",
      border: "#2a2320",
      gold: "#d4af37",
      goldSoft: "#e6c96a",
      accent: "#8c1515",
      accentSoft: "#a8283a",
      text: "#f7f1e3",
      textMuted: "#b7ad98",
    },
    glow: "rgba(212, 175, 55, 0.18)",
  },
  "land-development": {
    key: "land-development",
    name: "Aces N 8s Land Development",
    shortName: "Land Development",
    eyebrow: "Land Transformation Platform",
    description:
      "We acquire, entitle, and develop strategically positioned land into high-value communities designed for the future.",
    domainPlaceholder: "acesn8sland.com",
    parentPlatform: {
      label: "A Division Of",
      name: "Aces N 8s Capital",
      href: "https://acesn8scapital.com",
    },
    colors: {
      bg: "#070707",
      bgElevated: "#0d0f0e",
      surface: "#0d0d0f",
      border: "#2b271e",
      gold: "#b98946",
      goldSoft: "#d3ac74",
      accent: "#8c1515",
      accentSoft: "#a8283a",
      text: "#f7f1e3",
      textMuted: "#b7ad98",
    },
    glow: "rgba(185, 137, 70, 0.16)",
  },
  "investment-holdings": {
    key: "investment-holdings",
    name: "Aces N 8s Investment Holdings",
    shortName: "Investment Holdings",
    eyebrow: "Private Investment Platform",
    description:
      "A privately held investment platform focused on disciplined capital deployment, strategic assets, and long-term value creation.",
    domainPlaceholder: "acesn8sholdings.com",
    parentPlatform: {
      label: "A Division Of",
      name: "Aces N 8s Capital",
      href: "https://acesn8scapital.com",
    },
    colors: {
      bg: "#070707",
      bgElevated: "#0e0d10",
      surface: "#0d0d0f",
      border: "#2a2621",
      gold: "#d8c08d",
      goldSoft: "#e9dab6",
      accent: "#8c1515",
      accentSoft: "#a8283a",
      text: "#f7f1e3",
      textMuted: "#b7ad98",
    },
    glow: "rgba(216, 192, 141, 0.16)",
  },
  "title-land-intelligence": {
    key: "title-land-intelligence",
    name: "Aces N 8s Title & Land Intelligence",
    shortName: "Title Intelligence",
    eyebrow: "Professional Intelligence Platform",
    description:
      "We deliver disciplined title research, land intelligence, and due-diligence support for energy, real estate, development, and private capital decisions.",
    domainPlaceholder: "acesn8stitle.com",
    parentPlatform: {
      label: "A Division Of",
      name: "Aces N 8s Capital",
      href: "https://acesn8scapital.com",
    },
    colors: {
      bg: "#070707",
      bgElevated: "#0b0d12",
      surface: "#0d0d0f",
      border: "#232937",
      gold: "#4f7ea8",
      goldSoft: "#7ba4c8",
      accent: "#8c1515",
      accentSoft: "#a8283a",
      text: "#f7f1e3",
      textMuted: "#b7ad98",
    },
    glow: "rgba(79, 126, 168, 0.22)",
  },
};

export function getBrand(key: SiteKey): BrandTokens {
  return brands[key];
}

export function brandCssVars(brand: BrandTokens): Record<string, string> {
  return {
    "--color-bg": brand.colors.bg,
    "--color-bg-elevated": brand.colors.bgElevated,
    "--color-surface": brand.colors.surface,
    "--color-border": brand.colors.border,
    "--color-gold": brand.colors.gold,
    "--color-gold-soft": brand.colors.goldSoft,
    "--color-accent": brand.colors.accent,
    "--color-accent-soft": brand.colors.accentSoft,
    "--color-text": brand.colors.text,
    "--color-text-muted": brand.colors.textMuted,
    "--glow": brand.glow,
  };
}
