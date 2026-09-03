import type { Page } from 'playwright';

export interface PortalSearchQuery {
  state: string;
  county: string;
  surveySection?: string | null;
  surveyBlock?: string | null;
  surveyTownship?: string | null;
  surveyAbstractNo?: string | null;
}

export interface PortalSearchHit {
  instrumentNumber: string | null;
  instrumentType: string | null;
  recordingDate: string | null; // ISO yyyy-mm-dd if parseable, else null
  grantor: string | null;
  grantee: string | null;
  /** Opaque handle the driver uses internally to locate/download this hit (e.g. a row selector or doc id). */
  handle: string;
}

/**
 * One implementation per site (TexasFile, a county clerk's own search, etc).
 * Agents talk to this interface only, so swapping PORTAL_NAME in .env swaps
 * the whole retrieval flow without touching instrumentRetrievalAgent.ts.
 */
export interface PortalDriver {
  readonly name: string;
  login(page: Page): Promise<void>;
  search(page: Page, query: PortalSearchQuery): Promise<PortalSearchHit[]>;
  downloadInstrument(page: Page, hit: PortalSearchHit): Promise<Buffer>;
}
