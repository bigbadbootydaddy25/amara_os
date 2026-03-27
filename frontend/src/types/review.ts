export type AmaraDecision = "APPROVED" | "REJECTED" | "NEEDS_MORE_INFO" | "PENDING";

export type LifecycleStatus =
  | "UNDER_REVIEW"
  | "APPROVED"
  | "NEEDS_INFO"
  | "REJECTED"
  | "LOI_SENT"
  | "IN_NEGOTIATION"
  | "UNDER_CONTRACT"
  | "CLOSED"
  | "DEAD";

export interface DealReview {
  id: number;
  parcelId: number;
  amaraDecision: AmaraDecision;
  confidenceScore: string | null;
  amaraReasoning: string | null;

  loiText: string | null;
  loiGeneratedAt: string | null;
  ownerOutreachText: string | null;
  outreachGeneratedAt: string | null;
  negotiationStrategy: string | null;
  negotiationGeneratedAt: string | null;

  lifecycleStatus: LifecycleStatus | null;
  pipelineRunId: string | null;
  surfacedAt: string | null;
  reviewedAt: string | null;

  humanOverride: string | null;
  humanOverrideNote: string | null;
  overriddenAt: string | null;
  overriddenBy: string | null;

  createdAt: string | null;
  updatedAt: string | null;
}

export interface PipelineStats {
  total: number;
  approved: number;
  rejected: number;
  pending: number;
  needsInfo: number;
  loi_sent: number;
  in_negotiation: number;
  under_contract: number;
  closed: number;
}

export interface PipelineRun {
  id: number;
  runId: string;
  triggeredBy: string;
  status: string;
  parcelsFound: number;
  parcelsSentToAmara: number;
  amaraApproved: number;
  amaraRejected: number;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
}
