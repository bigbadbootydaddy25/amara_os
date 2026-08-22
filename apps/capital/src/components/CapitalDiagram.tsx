"use client";

import { StepDiagram, DiagramLayer, type StepDiagramStep } from "@aces/ui";

const steps: StepDiagramStep[] = [
  { label: "Capital Alignment" },
  { label: "Opportunity Intelligence" },
  { label: "Title & Land Analysis" },
  { label: "Site Control" },
  { label: "Infrastructure" },
  { label: "Hold or Exit" },
];

export function CapitalDiagram() {
  return (
    <StepDiagram steps={steps}>
      {(active) => (
        <svg
          viewBox="0 0 900 440"
          role="img"
          aria-label="Enterprise value creation flow"
          className="h-full w-full"
        >
          <DiagramLayer layer={0} activeIndex={active}>
            <circle
              cx={450}
              cy={220}
              r={78}
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth={2}
            />
            <text x={450} y={215} fontSize={20} textAnchor="middle" fill="#f6edd8">
              ACES N 8S
            </text>
            <text x={450} y={240} fontSize={14} textAnchor="middle" fill="#f6edd8">
              CAPITAL
            </text>
          </DiagramLayer>

          <DiagramLayer layer={1} activeIndex={active}>
            <path
              d="M450 142V45M528 220H810M450 298V395M372 220H90"
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth={2}
            />
          </DiagramLayer>

          <DiagramLayer layer={2} activeIndex={active}>
            <circle cx={450} cy={45} r={34} fill="none" stroke="var(--color-gold)" strokeWidth={2} />
            <text x={450} y={50} fontSize={9} textAnchor="middle" fill="#f6edd8">
              INTELLIGENCE
            </text>
          </DiagramLayer>

          <DiagramLayer layer={3} activeIndex={active}>
            <circle cx={810} cy={220} r={34} fill="none" stroke="var(--color-gold)" strokeWidth={2} />
            <text x={810} y={225} fontSize={12} textAnchor="middle" fill="#f6edd8">
              LAND
            </text>
          </DiagramLayer>

          <DiagramLayer layer={4} activeIndex={active}>
            <circle cx={450} cy={395} r={34} fill="none" stroke="var(--color-gold)" strokeWidth={2} />
            <text x={450} y={400} fontSize={12} textAnchor="middle" fill="#f6edd8">
              HOLDINGS
            </text>
          </DiagramLayer>

          <DiagramLayer layer={5} activeIndex={active}>
            <circle cx={90} cy={220} r={34} fill="none" stroke="var(--color-gold)" strokeWidth={2} />
            <text x={90} y={225} fontSize={12} textAnchor="middle" fill="#f6edd8">
              TITLE
            </text>
          </DiagramLayer>
        </svg>
      )}
    </StepDiagram>
  );
}
