import { getBrand } from "@aces/brand";
import { investmentHoldingsContent } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  InfoCards,
  FamilyGrid,
  ChartUpIcon,
  TargetIcon,
  LockIcon,
  ClockIcon,
} from "@aces/ui";
import { HoldingsDiagram } from "@/components/HoldingsDiagram";

const brand = getBrand("investment-holdings");

const statIcons = [
  <ChartUpIcon key="chart" className="h-6 w-6" />,
  <TargetIcon key="target" className="h-6 w-6" />,
  <LockIcon key="lock" className="h-6 w-6" />,
  <ClockIcon key="clock" className="h-6 w-6" />,
];

const aboutCards = [
  {
    title: "Investment Philosophy",
    body: "Selective, disciplined, and patient capital allocation.",
  },
  {
    title: "Strategic Holdings",
    body: "Assets chosen for durable value and strategic fit.",
  },
  {
    title: "Risk Governance",
    body: "Clear controls, measured exposure, and defined pathways.",
  },
];

export default function Home() {
  return (
    <main>
      <Hero hero={investmentHoldingsContent.hero} eyebrow={brand.eyebrow} backgroundVariant="aurora" />

      <section id="about" className="scroll-mt-24 border-t border-white/10 py-24">
        <div className="mx-auto max-w-[1240px] px-6">
          <SectionTitle eyebrow="Our Focus" title="Disciplined capital. Durable value." />
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
            title="Explore the value-creation framework"
          />
          <p className="mt-5 max-w-2xl text-[#bfb7a9] leading-relaxed">
            Select each stage to see how the platform advances from intelligence and planning
            through execution and value creation.
          </p>
          <HoldingsDiagram />
        </div>
      </section>

      {investmentHoldingsContent.stats ? (
        <StatsStrip stats={investmentHoldingsContent.stats} icons={statIcons} />
      ) : null}

      <section className="mx-auto max-w-[1240px] px-6 py-24">
        <SectionTitle
          eyebrow="How We Operate"
          title="Disciplined capital. Private partnership."
        />
        <div className="mt-14">
          <FeatureGrid sections={investmentHoldingsContent.sections} columns={3} />
        </div>
      </section>

      <FamilyGrid currentKey="investment-holdings" />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-white/10 bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-[1240px] px-6 py-24">
          <SectionTitle
            eyebrow="Get In Touch"
            title={investmentHoldingsContent.contact.heading}
          />
          <div className="mt-14">
            <ContactForm contact={investmentHoldingsContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}
