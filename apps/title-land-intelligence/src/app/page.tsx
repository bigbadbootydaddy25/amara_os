import { getBrand } from "@aces/brand";
import { titleLandIntelligenceContent, titleIntelIndustries } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  InfoCards,
  IconFeatureRow,
  DiagonalImageGrid,
  FamilyGrid,
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
import { TitleDiagram } from "@/components/TitleDiagram";

const brand = getBrand("title-land-intelligence");

const topFeatures = [
  { icon: <TargetIcon className="h-6 w-6" />, label: "Accurate Research", body: "Meticulous title abstraction and verification." },
  { icon: <ShieldIcon className="h-6 w-6" />, label: "Risk Reduction", body: "Identify issues early and mitigate costly surprises." },
  { icon: <ClockIcon className="h-6 w-6" />, label: "Timely Delivery", body: "Disciplined turnaround without compromising accuracy." },
  { icon: <LockIcon className="h-6 w-6" />, label: "Confidential", body: "Your data, your deals, always protected." },
  { icon: <UsersIcon className="h-6 w-6" />, label: "Experienced Team", body: "Disciplined research and title professionals." },
];

const industryIcons = [DropIcon, HomeIcon, BlueprintIcon, ChartUpIcon];

const aboutCards = [
  {
    title: "Title Abstracting",
    body: "Structured surface, mineral, and ownership research.",
  },
  {
    title: "Land Intelligence",
    body: "Parcel, deed, GIS, plat, and courthouse intelligence.",
  },
  {
    title: "Curative Support",
    body: "Identify gaps, exceptions, and issues requiring resolution.",
  },
];

export default function Home() {
  const industryItems = titleIntelIndustries.map((industry, i) => {
    const Icon = industryIcons[i];
    return { icon: <Icon className="h-6 w-6" />, label: industry.label, body: industry.body };
  });

  return (
    <main>
      <Hero
        hero={titleLandIntelligenceContent.hero}
        eyebrow={brand.eyebrow}
        backgroundVariant="blueprint"
      />

      <IconFeatureRow items={topFeatures} />

      <section id="about" className="scroll-mt-24 border-t border-white/10 py-24">
        <div className="mx-auto max-w-[1240px] px-6">
          <SectionTitle eyebrow="Our Focus" title="Research depth. Decision clarity." />
          <p className="mt-5 max-w-2xl text-[#bfb7a9] leading-relaxed">
            A discreet operating platform designed to turn complex information, disciplined
            execution and long-range vision into durable value.
          </p>
          <div className="mt-10">
            <InfoCards items={aboutCards} columns={3} />
          </div>
        </div>
      </section>

      <section id="platform" className="scroll-mt-24 border-t border-white/10 py-24">
        <div className="mx-auto max-w-[1240px] px-6">
          <SectionTitle
            eyebrow="Interactive System"
            title="Trace the intelligence beneath the parcel"
          />
          <p className="mt-5 max-w-2xl text-[#bfb7a9] leading-relaxed">
            Select each stage to see how the platform advances from intelligence and planning
            through execution and value creation.
          </p>
          <TitleDiagram />
          <p className="mt-4 text-xs text-[var(--color-text-muted)]">
            This is an illustrative visualization using a fictional parcel. No real client
            data, owner names, or project locations are represented.
          </p>
        </div>
      </section>

      {titleLandIntelligenceContent.stats ? (
        <StatsStrip stats={titleLandIntelligenceContent.stats} />
      ) : null}

      <section className="mx-auto max-w-[1240px] px-6 py-24">
        <SectionTitle
          eyebrow="What We Do"
          title="Intelligence that powers confidence."
        />
        <div className="mt-14">
          <DiagonalImageGrid items={industryItems} />
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-6 py-24">
        <SectionTitle
          eyebrow="Our Services"
          title="Research and intelligence built on precision."
        />
        <div className="mt-14">
          <FeatureGrid sections={titleLandIntelligenceContent.sections} columns={3} />
        </div>
      </section>

      <FamilyGrid currentKey="title-land-intelligence" />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-white/10 bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-[1240px] px-6 py-24">
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
