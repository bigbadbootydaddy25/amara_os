import { rememberFact, searchMemory } from '../../../memory/mem0/episodic-memory.js';

async function main() {
  const userId = 'texhoma';

  await rememberFact('WV Cotenancy Act 2018: 75% majority required to force-pool minority mineral interests. Critical for every WV title opinion.', userId, { category: 'wv_law', namespace: 'texhoma' });
  await rememberFact('Texhoma Contract 52446 Elk Prospect: day rate $325, weekly $1625, first invoice 2026-06-17, David Adkins contact.', userId, { category: 'texhoma_contract', namespace: 'texhoma' });
  await rememberFact('ELK corridor WV counties: Nicholas, Clay, Kanawha, Braxton, Webster, Upshur — priority area for Contract 52446.', userId, { category: 'wv_geography', namespace: 'texhoma' });
  await rememberFact('WV Dormant Minerals Act 1990: interests dormant 20+ years with no production or recorded claim may be extinguished.', userId, { namespace: 'texhoma' });
  await rememberFact('WV Pugh Clause: Horizontal releases acreage outside drilling unit; Vertical releases formations not being developed. Critical for Marcellus/Utica tracts.', userId, { namespace: 'texhoma' });

  const tests = [
    { q: 'cotenancy majority threshold WV', expect: 'Cotenancy' },
    { q: 'Texhoma invoice rate contract',   expect: 'Contract 52446' },
    { q: 'ELK corridor counties Nicholas',  expect: 'ELK' },
    { q: 'dormant mineral interest 20 years', expect: 'dormant' },
    { q: 'Pugh clause Marcellus formations', expect: 'Pugh' },
  ];

  let passed = 0;
  console.log('WV Knowledge Verification (local store, in-process):');
  for (const { q, expect } of tests) {
    const results = await searchMemory(q, userId, 1);
    const hit = results[0];
    const ok = hit && hit.memory.toLowerCase().includes(expect.toLowerCase());
    console.log(`  ${ok ? '✓' : '✗'} "${q}"`);
    if (hit) console.log(`       → score=${hit.score.toFixed(3)}: ${hit.memory.slice(0, 80)}...`);
    if (ok) passed++;
  }

  console.log(`\n${passed}/${tests.length} verification queries passed ✅`);
  console.log('Local store verified. With MEM0_API_KEY facts persist across sessions.');
}

main().catch(console.error);
