"use client";

import { StepDiagram, DiagramLayer, type StepDiagramStep } from "@aces/ui";

const steps: StepDiagramStep[] = [
  { label: "Origination" },
  { label: "Assessment" },
  { label: "Capital Structure" },
  { label: "Strategic Hold" },
  { label: "Value Creation" },
];

export function HoldingsDiagram() {
  return (
    <StepDiagram steps={steps}>
      {(active) => (
        <svg
          viewBox="0 0 900 440"
          role="img"
          aria-label="Strategic holdings framework"
          className="h-full w-full"
        >
          <DiagramLayer layer={1} activeIndex={active}>
            <path
              d="M90 350C230 280 300 320 420 210S650 120 820 70"
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth={2}
            />
          </DiagramLayer>

          <DiagramLayer layer={2} activeIndex={active}>
            <circle cx={150} cy={320} r={45} fill="none" stroke="var(--color-gold)" strokeWidth={2} />
            <rect x={100} y={350} width={100} height={30} fill="var(--color-gold)" />
            <text x={150} y={325} fontSize={12} textAnchor="middle" fill="#f6edd8">
              SOURCE
            </text>
          </DiagramLayer>

          <DiagramLayer layer={3} activeIndex={active}>
            <circle cx={420} cy={210} r={55} fill="none" stroke="var(--color-gold)" strokeWidth={2} />
            <rect x={370} y={270} width={100} height={110} fill="var(--color-gold)" />
            <text x={420} y={215} fontSize={12} textAnchor="middle" fill="#f6edd8">
              HOLD
            </text>
          </DiagramLayer>

          <DiagramLayer layer={4} activeIndex={active}>
            <circle cx={720} cy={100} r={65} fill="none" stroke="var(--color-gold)" strokeWidth={2} />
            <rect x={670} y={180} width={100} height={200} fill="var(--color-gold)" />
            <text x={720} y={105} fontSize={12} textAnchor="middle" fill="#f6edd8">
              CREATE VALUE
            </text>
          </DiagramLayer>
        </svg>
      )}
    </StepDiagram>
  );
}
