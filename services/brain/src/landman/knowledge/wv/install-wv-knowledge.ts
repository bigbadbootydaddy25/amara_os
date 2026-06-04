// WV Knowledge Loader — Texhoma Namespace Only
// One-time script: embeds all WV county/law/defect/rule data into Qdrant "amara_learning"
// Every point tagged with namespace: "texhoma" — never written to amara_core, eqt, or 1890

import { QdrantClient } from '@qdrant/js-client-rest';
import { embedText } from '../../../memory/qdrant/embedder.js';
import { VECTOR_SIZE } from '../../../memory/qdrant/qdrant-client.js';
import { WV_COUNTIES } from './wv-counties.js';
import { WV_MINERAL_LAWS, WV_TITLE_DEFECTS, WV_CURATIVE_INSTRUMENTS } from './wv-mineral-law.js';
import { WV_TITLE_EXAMINATION_WORKFLOW, WV_LEASE_CLAUSES_TO_EXAMINE, TEXHOMA_CONTRACT_RULES } from './wv-title-standards.js';

const COLLECTION = 'amara_learning';
const NAMESPACE  = 'texhoma';

// ─── Qdrant client ────────────────────────────────────────────────────────────

function getClient(): QdrantClient {
  return new QdrantClient({
    host: process.env.QDRANT_HOST ?? 'localhost',
    port: parseInt(process.env.QDRANT_PORT ?? '6333', 10),
  });
}

async function ensureLearningCollection(client: QdrantClient): Promise<void> {
  const { collections } = await client.getCollections();
  if (collections.some((c) => c.name === COLLECTION)) return;
  await client.createCollection(COLLECTION, {
    vectors: { size: VECTOR_SIZE, distance: 'Cosine' },
  });
}

// ─── Text builders ────────────────────────────────────────────────────────────

function countyToText(c: (typeof WV_COUNTIES)[number]): string {
  const parts = [
    `WV County: ${c.name} County, West Virginia. FIPS ${c.fips}.`,
    `County seat: ${c.countySeat}. Tier ${c.tier} county.`,
    c.elkProbability ? 'Part of the ELK prospect corridor.' : '',
    `Key formations: ${c.formations.join(', ')}.`,
    c.knownOperators.length ? `Known operators: ${c.knownOperators.join(', ')}.` : '',
    c.knownIssues.length    ? `Known issues: ${c.knownIssues.join('; ')}.`     : '',
    c.recordsPortal         ? `Records portal: ${c.recordsPortal}.`            : '',
    c.notes                 ? c.notes                                           : '',
  ];
  return parts.filter(Boolean).join(' ');
}

function lawToText(l: (typeof WV_MINERAL_LAWS)[number]): string {
  return [
    `WV Mineral Law: ${l.name} (${l.year}).`,
    l.description,
    `Title work impact: ${l.impactOnTitleWork}`,
    l.keyThreshold ? `Key threshold: ${l.keyThreshold}.` : '',
    `Criticality: ${l.criticalityLevel}.`,
  ].filter(Boolean).join(' ');
}

function defectToText(d: (typeof WV_TITLE_DEFECTS)[number]): string {
  return [
    `WV Title Defect: ${d.type}. Severity: ${d.severity}.`,
    d.description,
    `Curative: ${d.curative}`,
  ].join(' ');
}

function curativeToText(c: (typeof WV_CURATIVE_INSTRUMENTS)[number]): string {
  return [
    `WV Curative Instrument: ${c.type}.`,
    `When to use: ${c.when}`,
    `Requirements: ${c.requirements}`,
  ].join(' ');
}

function clauseToText(c: (typeof WV_LEASE_CLAUSES_TO_EXAMINE)[number]): string {
  return [
    `WV Lease Clause — ${c.clause}: ${c.description}`,
    `Check for: ${c.checkFor}`,
  ].join(' ');
}

function contractRulesToText(): string {
  const r = TEXHOMA_CONTRACT_RULES;
  return [
    `Texhoma Contract ${r.contractNumber} — ${r.prospect} Prospect, ${r.state}.`,
    `Service type: ${r.serviceType}.`,
    `Day rate: $${r.dayRate}/day (${r.hoursForFullDay}h). Weekly: $${r.weeklyRate}.`,
    `Invoice frequency: ${r.invoiceFrequency}. Payment hold: ${r.paymentHold} days.`,
    `First invoice date: ${r.firstInvoiceDate}. Contract ends: ${r.contractEndDate}.`,
    `Company contact: ${r.companyContact.name}, ${r.companyContact.title}, ${r.companyContact.company}. Phone: ${r.companyContact.phone}.`,
    `Hard rules: ${r.hardRules.join(' | ')}`,
  ].join(' ');
}

function workflowToText(): string {
  const w = WV_TITLE_EXAMINATION_WORKFLOW;
  return [
    `WV Title Examination Workflow. Standard search period: ${w.standardSearchPeriod} years.`,
    `Extended search triggers: ${w.extendedSearchTriggers.join('; ')}.`,
    `Indexes to search: ${w.indexesToSearch.join(', ')}.`,
    `Output documents: ${w.outputDocuments.map((d) => d.name).join(', ')}.`,
  ].join(' ');
}

// ─── Main loader ──────────────────────────────────────────────────────────────

interface PointBatch {
  id:      number;
  vector:  number[];
  payload: Record<string, unknown>;
}

async function main(): Promise<void> {
  const client = getClient();
  await ensureLearningCollection(client);

  const points: PointBatch[] = [];
  let id = Date.now(); // monotonically increasing int IDs

  async function add(text: string, category: string, extra?: Record<string, unknown>) {
    const vector = await embedText(text);
    points.push({
      id:      id++,
      vector,
      payload: { namespace: NAMESPACE, category, text, state: 'WV', ...extra },
    });
  }

  // Counties (55)
  for (const county of WV_COUNTIES) {
    await add(countyToText(county), 'wv_county', {
      countyName: county.name,
      fips: county.fips,
      tier: county.tier,
      elkCorridor: county.elkProbability ?? false,
    });
  }

  // Mineral laws (6)
  for (const law of WV_MINERAL_LAWS) {
    await add(lawToText(law), 'wv_mineral_law', {
      lawName:      law.name,
      year:         law.year,
      criticality:  law.criticalityLevel,
    });
  }

  // Title defects (12)
  for (const defect of WV_TITLE_DEFECTS) {
    await add(defectToText(defect), 'wv_title_defect', {
      defectType: defect.type,
      severity:   defect.severity,
    });
  }

  // Curative instruments (6)
  for (const instrument of WV_CURATIVE_INSTRUMENTS) {
    await add(curativeToText(instrument), 'wv_curative', { instrumentType: instrument.type });
  }

  // Lease clauses (8)
  for (const clause of WV_LEASE_CLAUSES_TO_EXAMINE) {
    await add(clauseToText(clause), 'wv_lease_clause', { clauseName: clause.clause });
  }

  // Contract rules (1 composite record)
  await add(contractRulesToText(), 'texhoma_contract', { contractNumber: '52446', prospect: 'Elk' });

  // Examination workflow (1 composite record)
  await add(workflowToText(), 'wv_examination_workflow');

  // ── Upsert in batches of 100 ─────────────────────────────────────────────────
  const BATCH = 100;
  let inserted = 0;
  for (let i = 0; i < points.length; i += BATCH) {
    const batch = points.slice(i, i + BATCH);
    await client.upsert(COLLECTION, {
      wait:   true,
      points: batch.map((p) => ({
        id:      p.id,
        vector:  p.vector,
        payload: p.payload,
      })),
    });
    inserted += batch.length;
  }

  const total = await client.count(COLLECTION, { exact: true });
  console.log(`✅ WV knowledge installed — ${inserted} points inserted into "${COLLECTION}"`);
  console.log(`   Collection total: ${total.count} points`);
  console.log(`   Namespace guard: ${NAMESPACE} only — amara_core/eqt/1890 untouched`);
  console.log('\nBreakdown:');
  console.log(`  Counties:            ${WV_COUNTIES.length}`);
  console.log(`  Mineral laws:        ${WV_MINERAL_LAWS.length}`);
  console.log(`  Title defects:       ${WV_TITLE_DEFECTS.length}`);
  console.log(`  Curative instruments:${WV_CURATIVE_INSTRUMENTS.length}`);
  console.log(`  Lease clauses:       ${WV_LEASE_CLAUSES_TO_EXAMINE.length}`);
  console.log(`  Contract + workflow: 2`);
}

main().catch((err) => {
  console.error('WV knowledge install failed:', err);
  process.exit(1);
});
