import { getBrand } from "@aces/brand";
import { landDevelopmentContent } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  InfoCards,
  IconFeatureRow,
  FamilyGrid,
  PinIcon,
  DocumentIcon,
  BlueprintIcon,
  BuildingIcon,
  ChartUpIcon,
} from "@aces/ui";
import { LandDevelopmentDiagram } from "@/components/LandDevelopmentDiagram";

const brand = getBrand("land-development");
const processIcons = [PinIcon, DocumentIcon, BlueprintIcon, BuildingIcon, ChartUpIcon];
const processIndexes = [0, 1, 2, 3, 5];

const aboutCards = [
  {
    title: "Land Acquisition",
    body: "Selectively source strategically positioned acreage.",
  },
  {
    title: "Entitlement & Planning",
    body: "Advance land through planning, approvals, and final plat.",
  },
  {
    title: "Horizontal Development",
    body: "Coordinate roads, water, sewer, drainage, and utilities.",
  },
];

export default function Home() {
  const processFeatures = processIndexes.map((idx, i) => {
    const section = landDevelopmentContent.sections[idx];
    const Icon = processIcons[i];
    return {
      icon: <Icon className="h-6 w-6" />,
      label: section.title,
      body: section.body,
    };
  });

  return (
    <main>
      <Hero
        hero={landDevelopmentContent.hero}
        eyebrow={brand.eyebrow}
        backgroundVariant="map-grid"
      />

      <IconFeatureRow items={processFeatures} />

      <section id="about" className="scroll-mt-24 border-t border-white/10 py-24">
        <div className="mx-auto max-w-[1240px] px-6">
          <SectionTitle
            eyebrow="Our Focus"
            title="From raw acreage to buildable community."
          />
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
          <SectionTitle eyebrow="Interactive System" title="Watch a subdivision take shape" />
          <p className="mt-5 max-w-2xl text-[#bfb7a9] leading-relaxed">
            Select each stage to see how the platform advances from intelligence and planning
            through execution and value creation.
          </p>
          <LandDevelopmentDiagram />
          <p className="mt-4 text-xs text-[var(--color-text-muted)]">
            This is an illustrative visualization of a hypothetical tract and does not
            represent an actual project.
          </p>
        </div>
      </section>

      {landDevelopmentContent.stats ? (
        <StatsStrip stats={landDevelopmentContent.stats} />
      ) : null}

      <section className="mx-auto max-w-[1240px] px-6 py-24">
        <SectionTitle
          eyebrow="Our Process"
          title="From raw land to lasting communities."
        />
        <div className="mt-14">
          <FeatureGrid sections={landDevelopmentContent.sections} columns={3} />
        </div>
      </section>

      <FamilyGrid currentKey="land-development" />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-white/10 bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-[1240px] px-6 py-24">
          <SectionTitle
            eyebrow="Get In Touch"
            title={landDevelopmentContent.contact.heading}
          />
          <div className="mt-14">
            <ContactForm contact={landDevelopmentContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}
