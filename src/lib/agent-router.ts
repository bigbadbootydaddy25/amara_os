export type AgentName = 'nova' | 'hunter' | 'geo' | 'amara';

interface AgentProfile {
  displayName: string;
  systemAddendum: string;
}

const AGENTS: Record<AgentName, AgentProfile> = {
  nova: {
    displayName: 'Nova',
    systemAddendum:
      'You are directing Nova, your research and intelligence agent. ' +
      'Synthesise information accurately, cite relevant context, and surface the most useful facts. ' +
      'Mention briefly that Nova is on it.',
  },
  hunter: {
    displayName: 'Hunter',
    systemAddendum:
      'You are directing Hunter, your business development and deal-flow agent. ' +
      'Focus on opportunity, strategy, outreach, and commercial intelligence. ' +
      'Mention briefly that Hunter is on it.',
  },
  geo: {
    displayName: 'Geo',
    systemAddendum:
      'You are directing Geo, your market and location intelligence agent. ' +
      'Focus on geography, property, demographics, pricing, and regional market dynamics. ' +
      'Mention briefly that Geo is on it.',
  },
  amara: {
    displayName: 'AMARA',
    systemAddendum: '',
  },
};

interface IntentPattern {
  agent: AgentName;
  patterns: RegExp[];
}

const INTENT_PATTERNS: IntentPattern[] = [
  {
    agent: 'nova',
    patterns: [
      /\b(research|look\s*up|find\s*out|what\s*is|who\s*is|explain|summaris[e|ing]|summari[sz]e|analys[e|ing]|analy[sz]e|tell\s*me\s*about)\b/i,
      /\b(article|news|latest|trending|web|google|search|read|scrape|browse)\b/i,
      /\b(notebook|obsidian|notes?|knowledge|learn|feed)\b/i,
    ],
  },
  {
    agent: 'hunter',
    patterns: [
      /\b(deal|deals?|client|outreach|pitch|proposal|contract|leads?|prospect|crm|follow\s*up|sales|opportunity|opportunities)\b/i,
      /\b(contact|email|reach\s*out|investor|funding|partnership|pipeline|close)\b/i,
    ],
  },
  {
    agent: 'geo',
    patterns: [
      /\b(market|location|area|city|country|region|geography|property|real\s*estate|neighbourhood|neighborhood)\b/i,
      /\b(population|demographics|price|rental|residential|commercial|zoning|district|postcode|zip)\b/i,
    ],
  },
];

export function detectAgent(message: string): AgentName {
  const scores: Record<AgentName, number> = { nova: 0, hunter: 0, geo: 0, amara: 0 };

  for (const { agent, patterns } of INTENT_PATTERNS) {
    for (const pattern of patterns) {
      if (pattern.test(message)) {
        scores[agent] += 1;
      }
    }
  }

  const sorted = (Object.entries(scores) as [AgentName, number][]).sort(([, a], [, b]) => b - a);
  return sorted[0][1] > 0 ? sorted[0][0] : 'amara';
}

export function getAgentSystemAddendum(agent: AgentName): string {
  return AGENTS[agent].systemAddendum;
}

export function getAgentDisplayName(agent: AgentName): string {
  return AGENTS[agent].displayName;
}
