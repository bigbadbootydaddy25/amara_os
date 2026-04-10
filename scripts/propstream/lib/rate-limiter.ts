// ─────────────────────────────────────────────────────────────────────────────
// Rate limiter — prevents hammering PropStream servers
// ─────────────────────────────────────────────────────────────────────────────

export interface RateLimitConfig {
  minDelayMs: number;
  maxDelayMs: number;
  pageDelayMs: number;         // between pages within a list
  listDelayMs: number;         // between different lists
  actionDelayMs: number;       // between individual DOM interactions
}

export const DEFAULT_RATE_LIMITS: RateLimitConfig = {
  minDelayMs:    800,
  maxDelayMs:   2500,
  pageDelayMs:  1500,
  listDelayMs:  3000,
  actionDelayMs: 400,
};

function jitter(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

export class RateLimiter {
  private config: RateLimitConfig;
  private requestCount = 0;
  private windowStart = Date.now();

  constructor(config: RateLimitConfig = DEFAULT_RATE_LIMITS) {
    this.config = config;
  }

  async wait(type: "default" | "page" | "list" | "action" = "default"): Promise<void> {
    let ms: number;
    switch (type) {
      case "page":   ms = jitter(this.config.pageDelayMs,   this.config.pageDelayMs   * 1.5); break;
      case "list":   ms = jitter(this.config.listDelayMs,   this.config.listDelayMs   * 1.5); break;
      case "action": ms = jitter(this.config.actionDelayMs, this.config.actionDelayMs * 2);   break;
      default:       ms = jitter(this.config.minDelayMs,    this.config.maxDelayMs);           break;
    }
    this.requestCount++;
    // Every 50 requests, take a longer cooldown break
    if (this.requestCount % 50 === 0) {
      const cooldown = jitter(8000, 15000);
      console.log(`  [rate-limit] 50-request cooldown: ${cooldown}ms`);
      await sleep(cooldown);
      return;
    }
    await sleep(ms);
  }

  stats() {
    return {
      requests: this.requestCount,
      elapsedMs: Date.now() - this.windowStart,
    };
  }
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
