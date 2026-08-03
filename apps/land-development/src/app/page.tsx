import { landDevelopmentContent } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  IconFeatureRow,
  PinIcon,
  DocumentIcon,
  BlueprintIcon,
  BuildingIcon,
  ChartUpIcon,
} from "@aces/ui";
import { SubdivisionVisualizer } from "@/components/SubdivisionVisualizer";

const processIcons = [PinIcon, DocumentIcon, BlueprintIcon, BuildingIcon, ChartUpIcon];
const processIndexes = [0, 1, 2, 3, 5];

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
      <Hero hero={landDevelopmentContent.hero} backgroundVariant="map-grid" accentLastLine />

      <IconFeatureRow items={processFeatures} />

      {landDevelopmentContent.stats ? (
        <StatsStrip stats={landDevelopmentContent.stats} />
      ) : null}

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="Our Process"
          title="From raw land to lasting communities."
        />
        <div className="mt-14">
          <FeatureGrid sections={landDevelopmentContent.sections} columns={3} />
        </div>
      </section>

      <SubdivisionVisualizer />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-7xl px-6 py-24 md:px-10">
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
