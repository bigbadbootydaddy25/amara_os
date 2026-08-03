import type { SiteContent } from "./types";

export const investmentHoldingsContent: SiteContent = {
  key: "investment-holdings",
  nav: [
    { label: "Philosophy", href: "#investment-philosophy" },
    { label: "Holdings", href: "#strategic-holdings" },
    { label: "Partnership", href: "#partnership-approach" },
    { label: "Risk Management", href: "#risk-management" },
    { label: "Contact", href: "#contact" },
  ],
  hero: {
    eyebrow: "Aces N 8s Investment Holdings",
    headline: ["SMART CAPITAL.", "STRONG FUTURES."],
    body: "A privately held investment platform focused on disciplined capital deployment, strategic assets, and long-term value creation.",
    ctaLabel: "For Accredited Investors",
    ctaHref: "#contact",
    secondaryLabel: "Investor Login",
    secondaryHref: "/investor-login",
  },
  sections: [
    {
      id: "investment-philosophy",
      title: "Investment Philosophy",
      body: "We approach capital deployment with discipline, patience, and a long-term view, favoring durable value over short-term speculation.",
    },
    {
      id: "strategic-holdings",
      title: "Strategic Holdings",
      body: "Our holdings are selected for their strategic positioning and long-term potential, managed with a private, hands-on approach.",
    },
    {
      id: "partnership-approach",
      title: "Partnership Approach",
      body: "We work closely and privately with our partners, aligning interests and maintaining open, direct communication throughout every engagement.",
    },
    {
      id: "risk-management",
      title: "Risk Management",
      body: "Rigorous risk management underlies every decision we make, protecting capital while positioning for long-term growth.",
    },
    {
      id: "long-term-value",
      title: "Long-Term Value",
      body: "We build for the long term, prioritizing sustainable value creation over transactional gains.",
    },
  ],
  stats: [
    { label: "Approach", value: "Disciplined Capital Deployment" },
    { label: "Focus", value: "Strategic, Selective Holdings" },
    { label: "Structure", value: "Privately Held" },
    { label: "Orientation", value: "Long-Term Value" },
  ],
  contact: {
    heading: "Contact",
    body: "Aces N 8s Investment Holdings works privately with accredited investors and strategic partners. Reach out to begin a conversation.",
    emailPlaceholder: "info@acesn8sholdings.com",
    phonePlaceholder: "By Appointment",
  },
  footerNote:
    "This site does not constitute an offer to sell or a solicitation of an offer to buy any security. Aces N 8s Investment Holdings does not disclose returns or assets under management publicly.",
};
