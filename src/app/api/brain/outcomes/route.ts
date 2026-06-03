import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { recordOutcomeAndLearn } from '../../../../../services/brain/src/ingestion/persistent-pipeline.js';
import { syncDealOutcome } from '../../../../../services/brain/src/memory/neo4j/graph-sync.js';
import type { ExitType, ScenarioType } from '../../../../../services/brain/src/types.js';

const Schema = z.object({
  dealId:              z.string().uuid(),
  propertyId:          z.string().uuid(),
  zip:                 z.string().regex(/^\d{5}/),
  actualContractPrice: z.number().positive(),
  actualArv:           z.number().positive().optional(),
  actualRehab:         z.number().nonnegative().optional(),
  actualDom:           z.number().int().positive().optional(),
  actualProfit:        z.number(),
  exitType:            z.enum(['assigned', 'double_close', 'listed', 'rented', 'held', 'lost']),
  actualScenario:      z.enum(['conservative', 'base', 'aggressive']).optional(),
  buyerId:             z.string().uuid().optional(),
  strategy:            z.string().optional(),

  // Predictions (from the simulation) for error calculation
  predictedMao:    z.number().positive(),
  predictedArv:    z.number().positive(),
  predictedRehab:  z.number().nonnegative(),
});

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: 'Invalid JSON' }, { status: 400 });
  }

  const parsed = Schema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: parsed.error.flatten() }, { status: 400 });
  }

  const d = parsed.data;

  const { weightVersion, mae } = await recordOutcomeAndLearn(
    {
      dealId:              d.dealId,
      actualContractPrice: d.actualContractPrice,
      actualArv:           d.actualArv,
      actualRehab:         d.actualRehab,
      actualDom:           d.actualDom,
      actualProfit:        d.actualProfit,
      exitType:            d.exitType as ExitType,
      actualScenario:      d.actualScenario as ScenarioType | undefined,
    },
    d.predictedMao,
    d.predictedArv,
    d.predictedRehab,
    d.zip,
  );

  // Sync graph (non-fatal)
  await syncDealOutcome({
    dealId:        d.dealId,
    propertyId:    d.propertyId,
    buyerId:       d.buyerId,
    contractPrice: d.actualContractPrice,
    actualProfit:  d.actualProfit,
    daysToClose:   d.actualDom ?? 30,
    strategy:      d.strategy ?? 'wholesale',
  }).catch((err: Error) => console.warn('[neo4j] syncDealOutcome failed:', err.message));

  return NextResponse.json({
    success: true,
    weightVersion,
    mae,
    message: `Model updated to ${weightVersion}. MAE: $${mae.toLocaleString()}`,
  });
}
