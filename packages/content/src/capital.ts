import type { SiteContent } from "./types";

export const capitalContent: SiteContent = {
  key: "capital",
  nav: [
    { label: "Strategic Capital", href: "#strategic-capital" },
    { label: "Exclusive Access", href: "#exclusive-access" },
    { label: "Execution", href: "#execution-excellence" },
    { label: "About", href: "#about" },
    { label: "Strategy", href: "#investment-strategy" },
    { label: "Contact", href: "#contact" },
  ],
  hero: {
    eyebrow: "Aces N 8s Capital",
    headline: ["CAPITAL.", "VISION.", "LEGACY."],
    body: "We identify opportunity where others see risk and build lasting value where vision meets execution.",
    ctaLabel: "Enter Our World",
    ctaHref: "#strategic-capital",
  },
  sections: [
    {
      id: "strategic-capital",
      title: "Strategic Capital",
      body: "We deploy capital with discipline and conviction, aligning every commitment with a clear strategic thesis rather than chasing momentum.",
    },
    {
      id: "exclusive-access",
      title: "Exclusive Access",
      body: "Our relationships open doors to opportunities that rarely reach the open market, evaluated through a private, discreet process.",
    },
    {
      id: "execution-excellence",
      title: "Execution Excellence",
      body: "Ideas are only as strong as their execution. We operate with the precision and accountability our partners expect at every stage.",
    },
    {
      id: "lasting-impact",
      title: "Lasting Impact",
      body: "We measure success beyond a single transaction, building positions and relationships intended to compound in value over time.",
    },
    {
      id: "about",
      title: "About",
      body: "Aces N 8s Capital is a privately held capital platform built for disciplined, long-horizon decision making. We partner selectively and act deliberately.",
    },
    {
      id: "investment-strategy",
      title: "Investment Strategy",
      body: "Our strategy centers on identifying mispriced opportunity, underwriting it rigorously, and executing with a level of precision that protects downside while positioning for upside.",
    },
  ],
  stats: [
    { label: "Approach", value: "Disciplined Underwriting" },
    { label: "Horizon", value: "Long-Term Value Creation" },
    { label: "Access", value: "Private, Relationship-Driven" },
    { label: "Standard", value: "Execution Excellence" },
  ],
  contact: {
    heading: "Contact",
    body: "For inquiries regarding Aces N 8s Capital, reach out through the form below and our team will follow up directly.",
    emailPlaceholder: "info@acesn8scapital.com",
    phonePlaceholder: "By Appointment",
  },
  footerNote:
    "Aces N 8s Capital is a privately held entity. Information on this site is provided for general informational purposes only and does not constitute an offer to sell or a solicitation of an offer to buy any security.",
};
