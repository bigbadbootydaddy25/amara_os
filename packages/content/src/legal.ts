export interface LegalSection {
  heading: string;
  body: string;
}

export function privacyPolicySections(siteName: string): LegalSection[] {
  return [
    {
      heading: "Overview",
      body: `This Privacy Policy describes how ${siteName} ("we," "us," or "our") handles information collected through this website. This is placeholder content pending final legal review and should not be relied upon as a complete or binding privacy policy.`,
    },
    {
      heading: "Information We Collect",
      body: "We may collect information you voluntarily provide through contact or inquiry forms, such as your name, email address, and message content, as well as standard technical information collected automatically by our hosting and analytics providers.",
    },
    {
      heading: "How We Use Information",
      body: "Information submitted through this site is used solely to respond to inquiries and evaluate potential opportunities or engagements. We do not sell personal information to third parties.",
    },
    {
      heading: "Contact",
      body: `Questions about this Privacy Policy may be directed to ${siteName} using the contact information provided on this site.`,
    },
  ];
}

export function termsOfUseSections(siteName: string): LegalSection[] {
  return [
    {
      heading: "Acceptance of Terms",
      body: `By accessing this website, you agree to be bound by these Terms of Use. This is placeholder content pending final legal review and should not be relied upon as a complete or binding terms of use agreement.`,
    },
    {
      heading: "Use of Site",
      body: `This site is provided by ${siteName} for general informational purposes only. Content on this site may not be reproduced, distributed, or used for commercial purposes without prior written consent.`,
    },
    {
      heading: "No Warranty",
      body: "This site and its content are provided on an \"as is\" basis without warranties of any kind, express or implied.",
    },
    {
      heading: "Changes to Terms",
      body: `${siteName} reserves the right to modify these Terms of Use at any time without prior notice.`,
    },
  ];
}

export function disclaimerSections(siteName: string): LegalSection[] {
  return [
    {
      heading: "General Disclaimer",
      body: `The information provided on this website by ${siteName} is for general informational purposes only. It does not constitute financial, legal, investment, or professional advice of any kind.`,
    },
    {
      heading: "No Offer or Solicitation",
      body: "Nothing on this site constitutes an offer to sell, or a solicitation of an offer to buy, any security or investment product. Any such offer or solicitation will be made only through definitive offering documents.",
    },
    {
      heading: "Forward-Looking Content",
      body: "Any statements regarding future plans, strategies, or expectations are inherently uncertain and are not guarantees of future performance or results.",
    },
    {
      heading: "Placeholder Content",
      body: "Portions of this site contain placeholder content pending final client input and legal review, including but not limited to performance data, licensing information, and company history.",
    },
  ];
}
