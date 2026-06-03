/**
 * Ownership Report Generator
 * Assembles the final deliverable from chain + leases + flags.
 */

import type { TitleChain, OilGasLease, OwnershipReport, TitleFlag, STRLocation } from '../types.js';
import { buildMineralOwners } from './ownership-calculator.js';
import { analyzeChain } from '../rules/title-rules.js';

export interface OwnershipReportInput {
  chain:        TitleChain;
  leases:       OilGasLease[];
  state:        string;
  totalAcres?:  number;
  easements?:   string[];
  mortgages?:   string[];
  notes?:       string;
}

export function generateOwnershipReport(input: OwnershipReportInput): OwnershipReport {
  const { chain, leases, state } = input;

  const mineralOwners = buildMineralOwners(chain.instruments, leases);
  const flags         = analyzeChain(chain, leases, state);
  const unreleaseLeases = leases.filter(
    (l) => l.status === 'in_term' || l.status === 'hbp' || l.status === 'unknown',
  );

  return {
    preparedAt:           new Date(),
    strLocation:          chain.strLocation,
    totalAcres:           input.totalAcres ?? 640,
    mineralOwners,
    unreleaseLeases,
    unreleaseeMortgages:  input.mortgages ?? [],
    easements:            input.easements ?? [],
    flags,
    notes:                buildNotes(flags, input.notes),
  };
}

function buildNotes(flags: TitleFlag[], extra?: string): string {
  const criticals = flags.filter((f) => f.severity === 'critical');
  const warnings  = flags.filter((f) => f.severity === 'warning');
  const lines: string[] = [];

  if (criticals.length > 0) {
    lines.push(`CRITICAL ISSUES (${criticals.length}):`);
    for (const f of criticals) lines.push(`  • ${f.description} — ${f.action}`);
  }

  if (warnings.length > 0) {
    lines.push(`WARNINGS (${warnings.length}):`);
    for (const f of warnings) lines.push(`  • ${f.description}`);
  }

  if (extra) lines.push(extra);

  return lines.join('\n');
}

// ─── Plain-text OR formatter ──────────────────────────────────────────────────

export function formatOwnershipReport(report: OwnershipReport): string {
  const loc = report.strLocation;
  const lines: string[] = [
    '═'.repeat(70),
    'OWNERSHIP REPORT',
    `Prepared: ${report.preparedAt.toISOString()}`,
    `Location: Section ${loc.section}, T${loc.township}${loc.townshipDir}, R${loc.range}${loc.rangeDir}`,
    `County: ${loc.county}  State: ${loc.state}  Total Acres: ${report.totalAcres}`,
    '─'.repeat(70),
    '',
    'MINERAL OWNERSHIP:',
    '',
  ];

  for (const owner of report.mineralOwners) {
    const leaseNote =
      owner.leaseStatus === 'open'    ? '  *** OPEN OF RECORD — UNLEASED ***' :
      owner.leaseStatus === 'hbp'     ? `  [HBP — ${owner.lease?.lessee ?? 'unknown lessee'}]` :
      owner.leaseStatus === 'in_term' ? `  [IN-TERM OGL — ${owner.lease?.lessee ?? 'unknown'} exp ${owner.lease?.expiryDate ?? 'unknown'}]` :
      '';
    lines.push(`  ${owner.name.padEnd(35)} ${owner.fraction.padEnd(10)} (${(owner.decimalInterest * 100).toFixed(4)}%)${leaseNote}`);
  }

  lines.push('');
  lines.push('─'.repeat(70));

  if (report.unreleaseLeases.length > 0) {
    lines.push('UNRELEASED OGLs:');
    for (const l of report.unreleaseLeases) {
      lines.push(`  ${l.book}/${l.page}  ${l.lessor} → ${l.lessee}  [${l.status.toUpperCase()}]`);
    }
    lines.push('');
  }

  if (report.unreleaseeMortgages.length > 0) {
    lines.push('UNRELEASED MORTGAGES:');
    for (const m of report.unreleaseeMortgages) lines.push(`  ${m}`);
    lines.push('');
  }

  if (report.easements.length > 0) {
    lines.push('EASEMENTS / ROW:');
    for (const e of report.easements) lines.push(`  ${e}`);
    lines.push('');
  }

  if (report.flags.length > 0) {
    lines.push('─'.repeat(70));
    lines.push('FLAGS:');
    for (const f of report.flags) {
      const icon = f.severity === 'critical' ? '🔴' : f.severity === 'warning' ? '⚠️ ' : 'ℹ️ ';
      lines.push(`  ${icon} [${f.type}] ${f.description}`);
      lines.push(`       ACTION: ${f.action}`);
    }
    lines.push('');
  }

  if (report.notes) {
    lines.push('─'.repeat(70));
    lines.push('NOTES:');
    lines.push(report.notes);
    lines.push('');
  }

  lines.push('═'.repeat(70));
  return lines.join('\n');
}
