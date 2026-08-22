import { getBrand } from "@aces/brand";
import { capitalContent } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  InfoCards,
  IconFeatureRow,
  FamilyGrid,
  SpadeIcon,
  DiamondIcon,
  ClubIcon,
  HeartIcon,
} from "@aces/ui";
import { CapitalDiagram } from "@/components/CapitalDiagram";

const brand = getBrand("capital");
const suitIcons = [SpadeIcon, DiamondIcon, ClubIcon, HeartIcon];

const aboutCards = [
  {
    title: "Strategic Capital",
    body: "Disciplined alignment of capital, intelligence, and execution.",
  },
  {
    title: "Enterprise Command",
    body: "A central platform coordinating all Aces N 8s companies.",
  },
  {
    title: "Lasting Value",
    body: "Long-horizon thinking with discreet, selective execution.",
  },
];

export default function Home() {
  const suitFeatures = capitalContent.sections.slice(0, 4).map((section, i) => {
    const Icon = suitIcons[i];
    return {
      icon: <Icon className="h-6 w-6" />,
      label: section.title,
      body: section.body,
    };
  });

  return (
    <main>
      <Hero hero={capitalContent.hero} eyebrow={brand.eyebrow} backgroundVariant="skyline" />

      <IconFeatureRow items={suitFeatures} />

      <section id="about" className="scroll-mt-24 border-t border-white/10 py-24">
        <div className="mx-auto max-w-[1240px] px-6">
          <SectionTitle eyebrow="Our Focus" title={brand.tagline ?? "About Aces N 8s Capital"} />
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
          <SectionTitle eyebrow="Interactive System" title="The enterprise command center" />
          <p className="mt-5 max-w-2xl text-[#bfb7a9] leading-relaxed">
            Select each stage to see how the platform advances from intelligence and planning
            through execution and value creation.
          </p>
          <CapitalDiagram />
        </div>
      </section>

      {capitalContent.stats ? <StatsStrip stats={capitalContent.stats} /> : null}

      <section className="mx-auto max-w-[1240px] px-6 py-24">
        <SectionTitle
          eyebrow="What We Do"
          title="Strategic capital, applied with precision."
        />
        <div className="mt-14">
          <FeatureGrid sections={capitalContent.sections} columns={3} />
        </div>
      </section>

      <FamilyGrid currentKey="capital" />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-white/10 bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-[1240px] px-6 py-24">
          <SectionTitle eyebrow="Get In Touch" title={capitalContent.contact.heading} />
          <div className="mt-14">
            <ContactForm contact={capitalContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}
