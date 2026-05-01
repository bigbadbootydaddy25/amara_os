import fs from 'fs';
import path from 'path';
import type { ChainScore } from './performance-evaluator';
import type { RewriteResult } from './chain-rewriter';

export interface TestResult {
  chainName: string;
  deployed: boolean;
  oldScore: number;
  newScore: number;
  delta: number;
  backupPath: string | null;
  reason: string;
}

// Minimal improvement required to deploy a rewrite
const MIN_IMPROVEMENT = 0.05;

export async function testAndDeploy(
  rewrite: RewriteResult,
  originalScore: ChainScore,
): Promise<TestResult> {
  if (!rewrite.attempted || !rewrite.candidatePath) {
    return { chainName: rewrite.chainName, deployed: false, oldScore: originalScore.composite, newScore: originalScore.composite, delta: 0, backupPath: null, reason: rewrite.reason };
  }

  // Candidate exists — run a basic static analysis score
  // Real implementation would run the chain on a test dataset
  // For now: score based on code quality heuristics
  const candidateCode = fs.readFileSync(rewrite.candidatePath, 'utf-8');

  // Heuristic scoring — penalise obvious anti-patterns
  let candidateScore = originalScore.composite;

  // Reward: improved system prompt specificity
  if (candidateCode.includes('distress') || candidateCode.includes('motivated')) candidateScore += 0.03;
  // Reward: better Neo4j queries
  if (candidateCode.includes('ORDER BY') && !candidateCode.includes('LIMIT 1000')) candidateScore += 0.02;
  // Penalise: if file got dramatically longer (over-engineering)
  const originalPath = rewrite.candidatePath.replace(/_candidate_\d+\.ts$/, '.ts');
  if (fs.existsSync(originalPath)) {
    const originalLines = fs.readFileSync(originalPath, 'utf-8').split('\n').length;
    const candidateLines = candidateCode.split('\n').length;
    if (candidateLines > originalLines * 1.5) candidateScore -= 0.05;
  }

  const delta = +(candidateScore - originalScore.composite).toFixed(3);

  if (delta < MIN_IMPROVEMENT) {
    // Discard candidate
    fs.unlinkSync(rewrite.candidatePath);
    return { chainName: rewrite.chainName, deployed: false, oldScore: originalScore.composite, newScore: candidateScore, delta, backupPath: null, reason: `Improvement ${delta} below threshold ${MIN_IMPROVEMENT}` };
  }

  // Deploy — backup current, replace with candidate
  const livePath = rewrite.candidatePath.replace(/_candidate_\d+\.ts$/, '.ts');
  const backupPath = livePath.replace('.ts', `_backup_${new Date().toISOString().slice(0, 10)}.ts`);

  if (fs.existsSync(livePath)) {
    fs.copyFileSync(livePath, backupPath);
  }

  fs.copyFileSync(rewrite.candidatePath, livePath);
  fs.unlinkSync(rewrite.candidatePath);

  return { chainName: rewrite.chainName, deployed: true, oldScore: originalScore.composite, newScore: candidateScore, delta, backupPath, reason: `Deployed — improvement: +${delta}` };
}
