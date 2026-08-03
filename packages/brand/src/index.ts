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

export interface BrandTokens {
  key: SiteKey;
  name: string;
  shortName: string;
  tagline?: string;
  description: string;
  domainPlaceholder: string;
  colors: BrandColors;
  glow: string;
}

export const brands: Record<SiteKey, BrandTokens> = {
  capital: {
    key: "capital",
    name: "Aces N 8s Capital",
    shortName: "Capital",
    tagline: "WE DON'T PLAY THE ODDS. WE CHANGE THEM.",
    description:
      "We identify opportunity where others see risk and build lasting value where vision meets execution.",
    domainPlaceholder: "acesn8scapital.com",
    colors: {
      bg: "#07070a",
      bgElevated: "#0d0c10",
      surface: "#131015",
      border: "#2a2320",
      gold: "#c9a24b",
      goldSoft: "#e8cd8a",
      accent: "#7a1220",
      accentSoft: "#a8283a",
      text: "#f5f1e8",
      textMuted: "#a89c8a",
    },
    glow: "rgba(201, 162, 75, 0.18)",
  },
  "land-development": {
    key: "land-development",
    name: "Aces N 8s Land Development",
    shortName: "Land Development",
    description:
      "We acquire, entitle, and develop strategically positioned land into high-value communities designed for the future.",
    domainPlaceholder: "acesn8sland.com",
    colors: {
      bg: "#08090a",
      bgElevated: "#0d0f0e",
      surface: "#12130f",
      border: "#2b271e",
      gold: "#b8894a",
      goldSoft: "#d8ac6f",
      accent: "#3f5c42",
      accentSoft: "#5b7d5e",
      text: "#f1efe6",
      textMuted: "#a09982",
    },
    glow: "rgba(184, 137, 74, 0.16)",
  },
  "investment-holdings": {
    key: "investment-holdings",
    name: "Aces N 8s Investment Holdings",
    shortName: "Investment Holdings",
    description:
      "A privately held investment platform focused on disciplined capital deployment, strategic assets, and long-term value creation.",
    domainPlaceholder: "acesn8sholdings.com",
    colors: {
      bg: "#08080a",
      bgElevated: "#0e0d10",
      surface: "#141216",
      border: "#2a2621",
      gold: "#cbb27f",
      goldSoft: "#e8d7ae",
      accent: "#6b1b23",
      accentSoft: "#8f2d34",
      text: "#f3f0e9",
      textMuted: "#9d9484",
    },
    glow: "rgba(203, 178, 127, 0.16)",
  },
  "title-land-intelligence": {
    key: "title-land-intelligence",
    name: "Aces N 8s Title & Land Intelligence",
    shortName: "Title & Land Intelligence",
    description:
      "We deliver disciplined title research, land intelligence, and due-diligence support for energy, real estate, development, and private capital decisions.",
    domainPlaceholder: "acesn8stitle.com",
    colors: {
      bg: "#06070a",
      bgElevated: "#0b0d12",
      surface: "#10131a",
      border: "#232937",
      gold: "#b99c5e",
      goldSoft: "#dcc389",
      accent: "#1c3a5e",
      accentSoft: "#2c567e",
      text: "#eef1f6",
      textMuted: "#8b93a3",
    },
    glow: "rgba(44, 86, 126, 0.22)",
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
