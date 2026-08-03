import type { SiteContent } from "./types";

export const landDevelopmentContent: SiteContent = {
  key: "land-development",
  nav: [
    { label: "Acquisition", href: "#land-acquisition" },
    { label: "Entitlement", href: "#entitlement-permitting" },
    { label: "Master Planning", href: "#master-planning" },
    { label: "Development", href: "#development-management" },
    { label: "Projects", href: "#projects" },
    { label: "Contact", href: "#contact" },
  ],
  hero: {
    eyebrow: "Aces N 8s Land Development",
    headline: ["TRANSFORMING LAND.", "BUILDING COMMUNITIES."],
    body: "We acquire, entitle, and develop strategically positioned land into high-value communities designed for the future.",
    ctaLabel: "Our Approach",
    ctaHref: "#land-acquisition",
  },
  sections: [
    {
      id: "land-acquisition",
      title: "Land Acquisition",
      body: "We target strategically positioned parcels with long-term community and market potential, evaluated through a disciplined internal process.",
    },
    {
      id: "entitlement-permitting",
      title: "Entitlement & Permitting",
      body: "Our team navigates the entitlement and permitting process methodically, coordinating with jurisdictions to unlock a parcel's full potential.",
    },
    {
      id: "master-planning",
      title: "Master Planning",
      body: "Every community begins with a master plan designed around connectivity, longevity, and quality of place.",
    },
    {
      id: "development-management",
      title: "Development Management",
      body: "We oversee development from entitlement through delivery, managing infrastructure, timelines, and stakeholders with precision.",
    },
    {
      id: "builder-relationships",
      title: "Builder Relationships",
      body: "We work alongside trusted builder partners to bring finished communities to market, aligning incentives at every phase.",
    },
    {
      id: "maximizing-value",
      title: "Maximizing Value",
      body: "Value is created through disciplined planning, sequencing, and positioning — not shortcuts. Every decision is made with the long-term asset in mind.",
    },
    {
      id: "projects",
      title: "Projects",
      body: "Our current project portfolio is available to qualified partners and stakeholders upon request.",
    },
  ],
  stats: [
    { label: "Focus", value: "Strategic Land Positioning" },
    { label: "Process", value: "Entitlement Through Delivery" },
    { label: "Partnership", value: "Trusted Builder Relationships" },
    { label: "Philosophy", value: "Communities Built to Last" },
  ],
  contact: {
    heading: "Contact",
    body: "For land opportunities, partnership inquiries, or general questions, reach out through the form below.",
    emailPlaceholder: "info@acesn8sland.com",
    phonePlaceholder: "By Appointment",
  },
  footerNote:
    "Aces N 8s Land Development does not disclose proprietary acquisition methods or underwriting criteria. Information on this site is provided for general informational purposes only.",
};
