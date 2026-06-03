/**
 * Outcome Learning Agent — LangGraph StateGraph
 *
 * Flow:
 *   load_prediction → compute_errors → update_weights → sync_graph → emit_update
 *
 * Closes the feedback loop: takes a closed deal outcome, computes
 * prediction errors, updates MiroFish weights, and syncs Neo4j.
 */

import { StateGraph, Annotation, END } from '@langchain/langgraph';
import { WeightsRepo } from '../../memory/postgres/weights-repo.js';
import { SimulationRepo } from '../../memory/postgres/simulation-repo.js';
import { updateWeights } from '../../mirofish/learning/weight-updater.js';
import { syncDealOutcome } from '../../memory/neo4j/graph-sync.js';
import { DEFAULT_WEIGHTS } from '../../mirofish/engine/simulator.js';
import type { DealOutcomeInput, MiroFishWeights, SimulationResult, ExitType } from '../../types.js';

// ─── State ────────────────────────────────────────────────────────────────────

const OutcomeLearningState = Annotation.Root({
  // Input
  outcome:    Annotation<DealOutcomeInput>(),
  propertyId: Annotation<string>(),
  zip:        Annotation<string>(),
  buyerId:    Annotation<string | undefined>(),
  strategy:   Annotation<string | undefined>(),

  // Loaded
  priorSimulation: Annotation<SimulationResult | null>({ default: () => null, reducer: (_, v) => v }),
  currentWeights:  Annotation<MiroFishWeights | null>({ default: () => null, reducer: (_, v) => v }),

  // Computed
  predictionErrors: Annotation<PredictionErrors | null>({ default: () => null, reducer: (_, v) => v }),
  updatedWeights:   Annotation<MiroFishWeights | null>({ default: () => null, reducer: (_, v) => v }),
  weightVersion:    Annotation<string>({ default: () => '', reducer: (_, v) => v }),
  mae:              Annotation<number>({ default: () => 0,  reducer: (_, v) => v }),
  graphSynced:      Annotation<boolean>({ default: () => false, reducer: (_, v) => v }),
  errors:           Annotation<string[]>({ default: () => [], reducer: (a, b) => [...a, ...b] }),
});

export type OutcomeLearningStateType = typeof OutcomeLearningState.State;

export interface PredictionErrors {
  maoError:    number;
  arvError:    number;
  rehabError:  number;
  profitError: number;
}

// ─── Nodes ────────────────────────────────────────────────────────────────────

async function loadPrediction(
  state: OutcomeLearningStateType,
): Promise<Partial<OutcomeLearningStateType>> {
  try {
    const [sim, weights] = await Promise.all([
      SimulationRepo.findLatestForProperty(state.propertyId).catch(() => null),
      WeightsRepo.getLatest().catch(() => null),
    ]);
    return {
      priorSimulation: sim,
      currentWeights:  weights ?? DEFAULT_WEIGHTS,
    };
  } catch (err) {
    return {
      currentWeights: DEFAULT_WEIGHTS,
      errors: [`loadPrediction: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

function computeErrors(
  state: OutcomeLearningStateType,
): Partial<OutcomeLearningStateType> {
  const sim = state.priorSimulation;
  const o   = state.outcome;

  if (!sim) {
    return {
      predictionErrors: { maoError: 0, arvError: 0, rehabError: 0, profitError: 0 },
    };
  }

  const predictedMao    = sim.recommendedMao;
  const predictedArv    = sim.features.arvMidpoint;
  const predictedRehab  = sim.features.rehabRisk * sim.features.arvMidpoint;
  const predictedProfit = sim.base.netProfit;

  return {
    predictionErrors: {
      maoError:    o.actualContractPrice - predictedMao,
      arvError:    (o.actualArv   ?? predictedArv)   - predictedArv,
      rehabError:  (o.actualRehab ?? predictedRehab) - predictedRehab,
      profitError: o.actualProfit - predictedProfit,
    },
  };
}

async function doUpdateWeights(
  state: OutcomeLearningStateType,
): Promise<Partial<OutcomeLearningStateType>> {
  const current = state.currentWeights ?? DEFAULT_WEIGHTS;
  const sim     = state.priorSimulation;

  const predictedMao   = sim?.recommendedMao           ?? 0;
  const predictedArv   = sim?.features.arvMidpoint      ?? 0;
  const predictedRehab = sim
    ? sim.features.rehabRisk * sim.features.arvMidpoint
    : 0;

  try {
    const { weights, update } = updateWeights(
      current,
      state.outcome,
      predictedMao,
      predictedArv,
      predictedRehab,
      state.zip,
    );

    await WeightsRepo.save(weights);
    await WeightsRepo.recordOutcome(
      state.outcome.dealId,
      state.propertyId,
      { mao: predictedMao, arv: predictedArv, rehab: predictedRehab, dom: 30, profit: sim?.base.netProfit ?? 0 },
      {
        contractPrice: state.outcome.actualContractPrice,
        arv:           state.outcome.actualArv,
        rehab:         state.outcome.actualRehab,
        dom:           state.outcome.actualDom,
        profit:        state.outcome.actualProfit,
        scenario:      state.outcome.actualScenario,
        modelVersion:  weights.version,
      },
    );

    return { updatedWeights: weights, weightVersion: weights.version, mae: update.mae };
  } catch (err) {
    return {
      errors: [`updateWeights: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

async function doSyncGraph(
  state: OutcomeLearningStateType,
): Promise<Partial<OutcomeLearningStateType>> {
  try {
    await syncDealOutcome({
      dealId:        state.outcome.dealId,
      propertyId:    state.propertyId,
      buyerId:       state.buyerId,
      contractPrice: state.outcome.actualContractPrice,
      actualProfit:  state.outcome.actualProfit,
      daysToClose:   state.outcome.actualDom ?? 30,
      strategy:      state.strategy ?? state.priorSimulation?.recommendedStrategy ?? 'wholesale',
    });
    return { graphSynced: true };
  } catch (err) {
    return {
      graphSynced: false,
      errors: [`syncGraph: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

// ─── Graph ────────────────────────────────────────────────────────────────────

function buildOutcomeLearningGraph() {
  return new StateGraph(OutcomeLearningState)
    .addNode('load_prediction',  loadPrediction)
    .addNode('compute_errors',   computeErrors)
    .addNode('update_weights',   doUpdateWeights)
    .addNode('sync_graph',       doSyncGraph)
    .addEdge('__start__',        'load_prediction')
    .addEdge('load_prediction',  'compute_errors')
    .addEdge('compute_errors',   'update_weights')
    .addEdge('update_weights',   'sync_graph')
    .addEdge('sync_graph',        END)
    .compile();
}

export const outcomeLearningGraph = buildOutcomeLearningGraph();

export async function recordOutcome(
  outcome: DealOutcomeInput,
  propertyId: string,
  zip: string,
  buyerId?: string,
  strategy?: string,
): Promise<OutcomeLearningStateType> {
  return outcomeLearningGraph.invoke({ outcome, propertyId, zip, buyerId, strategy });
}
