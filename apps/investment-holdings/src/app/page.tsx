import { investmentHoldingsContent } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  ChartUpIcon,
  TargetIcon,
  LockIcon,
  ClockIcon,
} from "@aces/ui";
import { AssetExplorer } from "@/components/AssetExplorer";

const statIcons = [
  <ChartUpIcon key="chart" className="h-6 w-6" />,
  <TargetIcon key="target" className="h-6 w-6" />,
  <LockIcon key="lock" className="h-6 w-6" />,
  <ClockIcon key="clock" className="h-6 w-6" />,
];

export default function Home() {
  return (
    <main>
      <Hero hero={investmentHoldingsContent.hero} backgroundVariant="aurora" />

      {investmentHoldingsContent.stats ? (
        <StatsStrip stats={investmentHoldingsContent.stats} icons={statIcons} />
      ) : null}

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="How We Operate"
          title="Disciplined capital. Private partnership."
        />
        <div className="mt-14">
          <FeatureGrid sections={investmentHoldingsContent.sections} columns={3} />
        </div>
      </section>

      <AssetExplorer />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-7xl px-6 py-24 md:px-10">
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
