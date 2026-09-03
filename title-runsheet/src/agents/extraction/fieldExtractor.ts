/**
 * Heuristic field extraction from recorded-instrument text.
 *
 * This is a regex/keyword baseline meant to get a runsheet moving without an
 * LLM/OCR pipeline configured — it will mis-parse unusual instrument
 * formatting. Each field carries into `raw_extraction` so a human abstractor
 * (or a future LLM-backed pass) can correct it without losing the source
 * text. Swap this module out for an LLM extraction call if you want higher
 * accuracy; the return shape is what `abstractingAgent.ts` expects either way.
 */

const INSTRUMENT_TYPE_PATTERNS: Array<{ type: string; pattern: RegExp }> = [
  { type: 'Oil and Gas Lease', pattern: /oil\s+(?:and|&)\s+gas\s+lease/i },
  { type: 'Warranty Deed', pattern: /warranty\s+deed/i },
  { type: 'Mineral Deed', pattern: /mineral\s+deed/i },
  { type: 'Quitclaim Deed', pattern: /quit\s*claim\s+deed/i },
  { type: 'Assignment', pattern: /assignment\s+of\s+(?:oil\s+and\s+gas\s+lease|interest)/i },
  { type: 'Release', pattern: /release\s+of\s+(?:oil\s+and\s+gas\s+lease|lien)/i },
  { type: 'Affidavit of Heirship', pattern: /affidavit\s+of\s+heirship/i },
  { type: 'Probate / Will', pattern: /(last\s+will\s+and\s+testament|letters\s+testamentary|probate)/i },
  { type: 'Ratification', pattern: /ratification/i },
  { type: 'Correction Instrument', pattern: /correction/i },
];

function firstMatch(text: string, patterns: RegExp[]): string | null {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match?.[1]) return match[1].trim();
  }
  return null;
}

function toIsoDate(raw: string | null): string | null {
  if (!raw) return null;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 10);
}

export interface ExtractedFields {
  instrumentType: string | null;
  executionDate: string | null;
  recordingDate: string | null;
  volume: string | null;
  page: string | null;
  instrumentNumber: string | null;
  grantors: string[];
  grantees: string[];
  legalDescription: string | null;
  confidence: number;
}

function splitNames(raw: string | null): string[] {
  if (!raw) return [];
  return raw
    .split(/,| and /i)
    .map((name) => name.trim())
    .filter((name) => name.length > 1 && name.length < 120);
}

export function extractFields(text: string): ExtractedFields {
  const normalized = text.replace(/\r/g, '');

  let instrumentType: string | null = null;
  for (const { type, pattern } of INSTRUMENT_TYPE_PATTERNS) {
    if (pattern.test(normalized)) {
      instrumentType = type;
      break;
    }
  }

  const recordingDate = toIsoDate(
    firstMatch(normalized, [
      /recorded\s*(?:on|date)?\s*[:\-]?\s*([A-Za-z0-9,./ ]{6,25})/i,
      /filed\s+for\s+record[^\n]*?([A-Za-z0-9,./ ]{6,25})/i,
    ]),
  );

  const executionDate = toIsoDate(
    firstMatch(normalized, [
      /(?:dated|executed)\s*(?:this)?[^\n]{0,20}?([A-Za-z0-9,./ ]{6,25})\s*(?:day of)?/i,
    ]),
  );

  const volume = firstMatch(normalized, [/\bvol(?:ume)?\.?\s*(\d+[A-Za-z]?)/i]);
  const page = firstMatch(normalized, [/\bpa?ge\.?\s*(\d+)/i]);
  const instrumentNumber = firstMatch(normalized, [
    /instrument\s*(?:no|number|#)\.?\s*[:\-]?\s*([A-Za-z0-9\-]+)/i,
    /doc(?:ument)?\s*(?:no|number|#)\.?\s*[:\-]?\s*([A-Za-z0-9\-]+)/i,
  ]);

  const grantors = splitNames(firstMatch(normalized, [/grantors?\s*[:\-]\s*([^\n]+)/i]));
  const grantees = splitNames(firstMatch(normalized, [/grantees?\s*[:\-]\s*([^\n]+)/i]));

  const legalDescription = firstMatch(normalized, [
    /(section\s+\d+[^\n]{0,200}?(?:county|survey)[^\n]{0,100})/i,
  ]);

  const fieldsFound = [instrumentType, recordingDate, executionDate, volume, page, instrumentNumber].filter(
    Boolean,
  ).length;
  const confidence = Math.min(1, fieldsFound / 6);

  return {
    instrumentType,
    executionDate,
    recordingDate,
    volume,
    page,
    instrumentNumber,
    grantors,
    grantees,
    legalDescription,
    confidence,
  };
}
