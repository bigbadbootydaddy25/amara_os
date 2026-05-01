import fs from 'fs';
import path from 'path';

export interface ProgramDirectives {
  priorities: string[];
  targetMarkets: string[];
  dealCriteria: string[];
  doNotPursue: string[];
  notes: string;
  raw: string;
}

function extractSection(text: string, heading: string): string[] {
  const regex = new RegExp(`##\\s+${heading}[\\s\\S]*?(?=##|$)`, 'i');
  const match = text.match(regex);
  if (!match) return [];
  return match[0]
    .split('\n')
    .slice(1)
    .map((l) => l.replace(/^-\s*/, '').trim())
    .filter(Boolean);
}

export function readProgram(): ProgramDirectives {
  const programPath = path.resolve(process.cwd(), 'program.md');

  if (!fs.existsSync(programPath)) {
    return { priorities: [], targetMarkets: [], dealCriteria: [], doNotPursue: [], notes: '', raw: '' };
  }

  const raw = fs.readFileSync(programPath, 'utf-8');

  return {
    priorities: extractSection(raw, 'CURRENT PRIORITIES'),
    targetMarkets: extractSection(raw, 'TARGET MARKETS THIS WEEK'),
    dealCriteria: extractSection(raw, 'DEAL CRITERIA RIGHT NOW'),
    doNotPursue: extractSection(raw, 'DO NOT PURSUE'),
    notes: extractSection(raw, 'NOTES FOR AMARA').join('\n'),
    raw,
  };
}

export function programToSystemContext(directives: ProgramDirectives): string {
  if (!directives.raw) return '';
  return `SCOTT'S CURRENT STRATEGY (from program.md):\nPriorities: ${directives.priorities.join('; ')}\nTarget markets: ${directives.targetMarkets.join(', ')}\nBuy box: ${directives.dealCriteria.join('; ')}\nExclusions: ${directives.doNotPursue.join('; ')}`;
}
