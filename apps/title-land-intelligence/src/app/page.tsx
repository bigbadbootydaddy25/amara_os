import { titleLandIntelligenceContent, titleIntelIndustries } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  IconFeatureRow,
  DiagonalImageGrid,
  TargetIcon,
  ShieldIcon,
  ClockIcon,
  LockIcon,
  UsersIcon,
  DropIcon,
  HomeIcon,
  BlueprintIcon,
  ChartUpIcon,
} from "@aces/ui";
import { ParcelIntelligenceViewer } from "@/components/ParcelIntelligenceViewer";

const topFeatures = [
  { icon: <TargetIcon className="h-6 w-6" />, label: "Accurate Research", body: "Meticulous title abstraction and verification." },
  { icon: <ShieldIcon className="h-6 w-6" />, label: "Risk Reduction", body: "Identify issues early and mitigate costly surprises." },
  { icon: <ClockIcon className="h-6 w-6" />, label: "Timely Delivery", body: "Disciplined turnaround without compromising accuracy." },
  { icon: <LockIcon className="h-6 w-6" />, label: "Confidential", body: "Your data, your deals, always protected." },
  { icon: <UsersIcon className="h-6 w-6" />, label: "Experienced Team", body: "Disciplined research and title professionals." },
];

const industryIcons = [DropIcon, HomeIcon, BlueprintIcon, ChartUpIcon];

export default function Home() {
  const industryItems = titleIntelIndustries.map((industry, i) => {
    const Icon = industryIcons[i];
    return { icon: <Icon className="h-6 w-6" />, label: industry.label, body: industry.body };
  });

  return (
    <main>
      <Hero hero={titleLandIntelligenceContent.hero} backgroundVariant="blueprint" />

      <IconFeatureRow items={topFeatures} />

      {titleLandIntelligenceContent.stats ? (
        <StatsStrip stats={titleLandIntelligenceContent.stats} />
      ) : null}

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="What We Do"
          title="Intelligence that powers confidence."
        />
        <div className="mt-14">
          <DiagonalImageGrid items={industryItems} />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="Our Services"
          title="Research and intelligence built on precision."
        />
        <div className="mt-14">
          <FeatureGrid sections={titleLandIntelligenceContent.sections} columns={3} />
        </div>
      </section>

      <ParcelIntelligenceViewer />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-7xl px-6 py-24 md:px-10">
          <SectionTitle
            eyebrow="Get In Touch"
            title={titleLandIntelligenceContent.contact.heading}
          />
          <div className="mt-14">
            <ContactForm contact={titleLandIntelligenceContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}
