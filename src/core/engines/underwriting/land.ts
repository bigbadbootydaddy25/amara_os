/**
 * AMARA OS — Land / Subdivision / Dead Paper Underwriting Engine
 * Strategy C: Developer exits, subdivision plays, entitlement deals
 * RULE: Do NOT use SFR fee math. Target six-figure to eight-figure spreads.
 */

export type LandExitType =
  | "SUBDIVISION_DEVELOPMENT"
  | "INFILL_LOT_SALE"
  | "LAND_ASSIGNMENT"
  | "DEAD_PAPER_TRADE"
  | "ENTITLEMENT_FLIP";

export interface LandInput {
  lotSizeSqft: number | null;
  lotSizeAcres: number | null;
  zoning: string | null;
  frontageLinearFt: number | null;
  hasUtilities: boolean | null;
  floodZone: boolean | null;
  entitlementStage: "RAW" | "PRELIMINARY" | "ENTITLED" | "SHOVEL_READY" | null;
  subdivisionPotentialLots: number | null;  // estimated # of buildable lots
  finishedLotValueEach: number | null;      // developer's finished lot value
  listPrice: number | null;
  arvIfSFR: number | null;
  marketName: string;
}

export interface LandOutput {
  strategy: "LAND_SUBDIVISION" | "DEAD_PAPER" | "LAND_ASSIGNMENT";
  exitType: LandExitType;
  grossDevelopmentValue: number | null;    // total developer exit
  finishedLotValueTotal: number | null;
  entitlementCarryCost: number | null;
  engineeringEstimate: number | null;
  developerProfit: number | null;
  developerMaxPay: number | null;          // what developer will pay for raw land
  ourTargetFee: number;                    // six-figure target minimum
  mao: number | null;
  projectedSpread: number | null;
  passesUnderwriting: boolean;
  rejectReason: string | null;
  confidenceNote: string;
  calcBreakdown: string;
}

// Land cost constants
const ENTITLEMENT_CARRY_PCT    = 0.08;   // 8% of GDV for carry/soft costs
const ENGINEERING_PCT          = 0.04;   // 4% of GDV for engineering/infra
const DEVELOPER_MARGIN_PCT     = 0.25;   // developer needs 25% margin
const MIN_LAND_ASSIGNMENT_FEE  = 50_000; // minimum $50k for any land deal
const TARGET_LAND_SPREAD       = 100_000; // target $100k+ spread

export function underwriteLand(input: LandInput): LandOutput {
  const acres = input.lotSizeAcres ?? (input.lotSizeSqft ? input.lotSizeSqft / 43560 : null);

  // Case 1: Subdivision play with known lot count and FLV
  if (input.subdivisionPotentialLots && input.finishedLotValueEach && input.finishedLotValueEach > 0) {
    const lots = input.subdivisionPotentialLots;
    const flvEach = input.finishedLotValueEach;
    const gdv = lots * flvEach;

    const carryCost    = Math.round(gdv * ENTITLEMENT_CARRY_PCT);
    const engineering  = Math.round(gdv * ENGINEERING_PCT);
    const devMargin    = Math.round(gdv * DEVELOPER_MARGIN_PCT);
    const devMaxPay    = gdv - carryCost - engineering - devMargin;

    if (devMaxPay <= 0) {
      return failLand("developer max pay is negative — not viable");
    }

    // Our fee: target max of what developer will pay minus our buffer
    const ourFee = Math.max(
      MIN_LAND_ASSIGNMENT_FEE,
      Math.round((devMaxPay - (input.listPrice ?? devMaxPay * 0.7)) * 0.5)
    );
    const mao = devMaxPay - ourFee;

    return {
      strategy: "LAND_SUBDIVISION",
      exitType: "SUBDIVISION_DEVELOPMENT",
      grossDevelopmentValue: gdv,
      finishedLotValueTotal: gdv,
      entitlementCarryCost: carryCost,
      engineeringEstimate: engineering,
      developerProfit: devMargin,
      developerMaxPay: devMaxPay,
      ourTargetFee: ourFee,
      mao,
      projectedSpread: devMaxPay - mao,
      passesUnderwriting: ourFee >= MIN_LAND_ASSIGNMENT_FEE,
      rejectReason: null,
      confidenceNote: `${lots} lots × $${flvEach.toLocaleString()} FLV = $${gdv.toLocaleString()} GDV`,
      calcBreakdown: [
        `Gross Dev Value (${lots} lots × $${flvEach.toLocaleString()}): $${gdv.toLocaleString()}`,
        `- Carry/Soft Costs (8%): $${carryCost.toLocaleString()}`,
        `- Engineering (4%):      $${engineering.toLocaleString()}`,
        `- Developer Margin (25%):$${devMargin.toLocaleString()}`,
        `= Developer Max Pay:     $${devMaxPay.toLocaleString()}`,
        `- Our Fee (target):      $${ourFee.toLocaleString()}`,
        `= MAO to Seller:         $${mao.toLocaleString()}`,
      ].join("\n"),
    };
  }

  // Case 2: Infill lot / dead paper play — simpler math
  if (acres && acres > 0 && input.listPrice) {
    // Estimate value per acre based on market
    const pricePerAcre = input.listPrice / acres;
    const targetResale = pricePerAcre * acres * 1.4; // target 40% uplift minimum
    const ourFee = Math.max(MIN_LAND_ASSIGNMENT_FEE, (targetResale - input.listPrice) * 0.5);
    const mao = input.listPrice * 0.65; // offer 65 cents on listed dollar for land

    if (targetResale - mao < MIN_LAND_ASSIGNMENT_FEE) {
      return failLand(`spread too thin for land — need $${MIN_LAND_ASSIGNMENT_FEE.toLocaleString()}+ fee`);
    }

    return {
      strategy: "DEAD_PAPER",
      exitType: "LAND_ASSIGNMENT",
      grossDevelopmentValue: null,
      finishedLotValueTotal: null,
      entitlementCarryCost: null,
      engineeringEstimate: null,
      developerProfit: null,
      developerMaxPay: targetResale,
      ourTargetFee: ourFee,
      mao,
      projectedSpread: targetResale - mao,
      passesUnderwriting: ourFee >= MIN_LAND_ASSIGNMENT_FEE,
      rejectReason: null,
      confidenceNote: `${acres.toFixed(2)} acres at ~$${Math.round(pricePerAcre).toLocaleString()}/ac`,
      calcBreakdown: [
        `Land Size: ${acres.toFixed(2)} acres`,
        `List Price: $${input.listPrice.toLocaleString()}`,
        `Target Resale: $${targetResale.toLocaleString()}`,
        `Our Fee: $${ourFee.toLocaleString()}`,
        `MAO (65% of list): $${mao.toLocaleString()}`,
      ].join("\n"),
    };
  }

  return failLand("insufficient data to underwrite land — need acreage, lot count, or FLV");
}

function failLand(reason: string): LandOutput {
  return {
    strategy: "LAND_SUBDIVISION",
    exitType: "LAND_ASSIGNMENT",
    grossDevelopmentValue: null,
    finishedLotValueTotal: null,
    entitlementCarryCost: null,
    engineeringEstimate: null,
    developerProfit: null,
    developerMaxPay: null,
    ourTargetFee: 0,
    mao: null,
    projectedSpread: null,
    passesUnderwriting: false,
    rejectReason: reason,
    confidenceNote: "",
    calcBreakdown: `FAIL: ${reason}`,
  };
}
