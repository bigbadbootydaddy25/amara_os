import type { SiteKey } from "@aces/brand";

export interface NavItem {
  label: string;
  href: string;
}

export interface HeroContent {
  eyebrow?: string;
  headline: string[];
  body: string;
  ctaLabel: string;
  ctaHref: string;
  secondaryLabel?: string;
  secondaryHref?: string;
}

export interface SectionContent {
  id: string;
  title: string;
  body: string;
  bullets?: string[];
}

export interface ContactContent {
  heading: string;
  body: string;
  emailPlaceholder: string;
  phonePlaceholder: string;
}

export interface StatItem {
  label: string;
  value: string;
}

export interface SiteContent {
  key: SiteKey;
  nav: NavItem[];
  hero: HeroContent;
  sections: SectionContent[];
  stats?: StatItem[];
  contact: ContactContent;
  footerNote: string;
}
