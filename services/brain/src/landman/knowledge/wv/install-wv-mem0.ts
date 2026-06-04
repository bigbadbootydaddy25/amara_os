// WV Mem0 Fact Loader — Texhoma Namespace Only
// Loads 11 priority facts into Mem0 with userId "texhoma"

import { rememberFact } from '../../../memory/mem0/episodic-memory.js';

const USER_ID = 'texhoma';

const WV_PRIORITY_FACTS = [
  {
    fact: 'WV Cotenancy Modernization Act (2018): 75% majority mineral interest owners can force-pool minority interests. Every WV title opinion must address cotenancy. Know the statutory procedure cold.',
    metadata: { category: 'wv_mineral_law', law: 'Cotenancy Act', year: 2018, criticality: 'critical' },
  },
  {
    fact: 'WV Dormant Oil and Gas Act (1990): Mineral interests dormant 20+ years (no production, development, or recorded claim) may be extinguished by surface owner. Always check old leases for dormancy exposure.',
    metadata: { category: 'wv_mineral_law', law: 'Dormant Minerals Act', year: 1990, criticality: 'critical' },
  },
  {
    fact: 'WV Marketable Title Act (1986): Standard title search is 40 years. Extend to patent only when issues appear in the 40-year window or client specifically requires it.',
    metadata: { category: 'wv_mineral_law', law: 'Marketable Title Act', year: 1986, criticality: 'high' },
  },
  {
    fact: 'WV Flat Rate Royalty Statute (2018): Old flat-rate royalty leases ($300/year per well) must convert to market-based royalties. Flag every flat-rate lease in the chain. Monitor constitutionality litigation.',
    metadata: { category: 'wv_mineral_law', law: 'Flat Rate Royalty Statute', year: 2018, criticality: 'high' },
  },
  {
    fact: 'Texhoma Contract 52446 — Elk Prospect WV: Day rate $325 (8-hour day). Weekly rate $1,625. Invoice no more than every 2 weeks. First invoice date 2026-06-17. Payment hold 30 days. Contract ends 2026-10-01.',
    metadata: { category: 'texhoma_contract', contractNumber: '52446', prospect: 'Elk', state: 'WV' },
  },
  {
    fact: 'Texhoma contact: David Adkins, President, Texhoma Land Consultants 1 Inc. Phone (405) 321-6777. Address: 770 West Rock Creek Road Suite 117, Norman Oklahoma 73069.',
    metadata: { category: 'texhoma_contact', name: 'David Adkins' },
  },
  {
    fact: 'Texhoma hard rules: Keep expense log current — never more than 24 hours behind. Provide receipts for all expenses. Device rule: dedicated Mac Mini only — main Mac never used for this job. Confidentiality survives termination permanently.',
    metadata: { category: 'texhoma_rules', contractNumber: '52446' },
  },
  {
    fact: 'ELK corridor counties in WV (Texhoma prospect area): Nicholas, Clay, Kanawha, Braxton, Webster, Upshur. These are the highest-priority counties for Contract 52446 title work.',
    metadata: { category: 'wv_geography', prospect: 'Elk', counties: ['Nicholas', 'Clay', 'Kanawha', 'Braxton', 'Webster', 'Upshur'] },
  },
  {
    fact: 'WV title examination standard: 40-year search period. Indexes to check: Grantor/Grantee deed, oil and gas lease, mortgage/lien, judgment lien, federal tax lien, lis pendens, probate, WV SOS corporate, circuit court, unit plat records.',
    metadata: { category: 'wv_title_standards', searchPeriod: 40 },
  },
  {
    fact: 'Critical WV title defect — Depth Severance Not Accounted For: Different parties may own different formation depths. Map each depth conveyance separately. Identify every formation owner. This is critical severity.',
    metadata: { category: 'wv_title_defect', defectType: 'Depth Severance', severity: 'critical' },
  },
  {
    fact: 'WV Pugh Clause types: Horizontal Pugh releases acreage outside drilling unit at end of primary term. Vertical Pugh releases formations not being developed. Always check both — critical for Marcellus/Utica multi-formation tracts.',
    metadata: { category: 'wv_lease_clause', clauseType: 'Pugh Clause', formations: ['Marcellus', 'Utica'] },
  },
];

async function main() {
  console.log(`Loading ${WV_PRIORITY_FACTS.length} priority WV facts into Mem0 (userId: "${USER_ID}")...`);
  let loaded = 0;

  for (const { fact, metadata } of WV_PRIORITY_FACTS) {
    await rememberFact(fact, USER_ID, { ...metadata, namespace: 'texhoma', state: 'WV' });
    loaded++;
    console.log(`  [${loaded}/${WV_PRIORITY_FACTS.length}] ✓ ${fact.slice(0, 70)}...`);
  }

  console.log(`\n✅ ${loaded} facts loaded into Mem0 for userId "${USER_ID}"`);
  console.log('   Namespace: texhoma — amara_core/eqt/1890 untouched');
}

main().catch((err) => {
  console.error('Mem0 WV fact load failed:', err);
  process.exit(1);
});
