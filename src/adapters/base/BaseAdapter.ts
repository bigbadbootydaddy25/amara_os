/**
 * AMARA OS — Base Adapter
 * All source adapters extend this.
 * Playwright is the execution layer only — intelligence lives in the engines.
 */

import { CanonicalDeal, DataSource } from "@/core/schema/canonical";

export interface AdapterConfig {
  source: DataSource;
  username: string;
  password: string;
  markets: string[];
  rateLimit: {
    requestsPerMinute: number;
    delayBetweenPages: number;   // ms
  };
  retryPolicy: {
    maxRetries: number;
    backoffMs: number;
  };
}

export interface RawProperty {
  // Raw fields extracted from source — before normalization
  [key: string]: unknown;
}

export interface AdapterSearchFilter {
  market: string;
  zips?: string[];
  propertyTypes?: string[];
  minPrice?: number;
  maxPrice?: number;
  minBeds?: number;
  maxBeds?: number;
  minDom?: number;
  priceReduced?: boolean;
  listingStatuses?: string[];
  keywords?: string[];
  distressOnly?: boolean;
}

export interface AdapterRunResult {
  source: DataSource;
  market: string;
  rawCount: number;
  normalizedCount: number;
  qualifiedCount: number;   // passed deal gate
  rejectedCount: number;
  errorCount: number;
  startedAt: string;
  completedAt: string;
  errors: string[];
}

export abstract class BaseAdapter {
  protected config: AdapterConfig;

  constructor(config: AdapterConfig) {
    this.config = config;
  }

  abstract login(): Promise<void>;
  abstract applyFilters(filter: AdapterSearchFilter): Promise<void>;
  abstract extractRawData(): Promise<RawProperty[]>;
  abstract normalizeToCanonical(raw: RawProperty): Partial<CanonicalDeal>;
  abstract handlePagination(): Promise<boolean>;  // returns false when no more pages
  abstract logout(): Promise<void>;

  // Utility: delay between requests
  protected async delay(ms?: number): Promise<void> {
    const wait = ms ?? this.config.rateLimit.delayBetweenPages;
    return new Promise((resolve) => setTimeout(resolve, wait));
  }

  // Utility: retry wrapper
  protected async retry<T>(fn: () => Promise<T>, label: string): Promise<T> {
    let lastError: Error | null = null;
    for (let i = 0; i <= this.config.retryPolicy.maxRetries; i++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err as Error;
        console.error(`[${this.config.source}] ${label} attempt ${i + 1} failed:`, lastError.message);
        if (i < this.config.retryPolicy.maxRetries) {
          await this.delay(this.config.retryPolicy.backoffMs * Math.pow(2, i));
        }
      }
    }
    throw lastError;
  }

  // Utility: safe text extraction
  protected safeText(val: unknown): string | null {
    if (typeof val === "string") return val.trim() || null;
    if (val === null || val === undefined) return null;
    return String(val).trim() || null;
  }

  // Utility: safe number extraction
  protected safeNum(val: unknown): number | null {
    if (typeof val === "number" && !isNaN(val)) return val;
    if (typeof val === "string") {
      const cleaned = val.replace(/[$,\s]/g, "");
      const n = parseFloat(cleaned);
      return isNaN(n) ? null : n;
    }
    return null;
  }

  // Utility: parse price string
  protected parsePrice(val: unknown): number | null {
    if (!val) return null;
    const str = String(val).replace(/[$,\s]/g, "");
    const n = parseFloat(str);
    return isNaN(n) ? null : n;
  }

  // Utility: parse date string
  protected parseDate(val: unknown): string | null {
    if (!val) return null;
    try {
      const d = new Date(String(val));
      if (isNaN(d.getTime())) return null;
      return d.toISOString();
    } catch {
      return null;
    }
  }
}
