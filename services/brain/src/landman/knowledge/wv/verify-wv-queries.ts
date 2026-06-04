import { searchMemory } from '../../../memory/mem0/episodic-memory.js';

const queries = [
  'cotenancy majority threshold WV',
  'Texhoma contract invoice rate',
  'ELK corridor counties',
  'dormant mineral interest 20 years',
  'Pugh clause formations Marcellus',
];

async function main() {
  for (const q of queries) {
    const results = await searchMemory('texhoma', q, 1);
    const hit = results[0];
    console.log(`\nQ: "${q}"`);
    if (hit) {
      console.log(`  ✓ score=${hit.score.toFixed(3)} → ${hit.memory.slice(0, 100)}...`);
    } else {
      console.log('  ✗ no result');
    }
  }
  console.log('\n✅ Verification complete');
}

main().catch(console.error);
