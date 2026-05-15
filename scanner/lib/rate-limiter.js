'use strict';

/**
 * Token-bucket rate limiter. Each acquire() waits until a token is available
 * so callers never exceed the configured request rate.
 */
class RateLimiter {
  constructor(intervalMs = 1200) {
    this.intervalMs = intervalMs;
    this.lastRelease = 0;
    this.queue = [];
    this.processing = false;
  }

  acquire() {
    return new Promise((resolve) => {
      this.queue.push(resolve);
      if (!this.processing) this._drain();
    });
  }

  _drain() {
    if (!this.queue.length) {
      this.processing = false;
      return;
    }

    this.processing = true;
    const now = Date.now();
    const wait = Math.max(0, this.lastRelease + this.intervalMs - now);

    setTimeout(() => {
      this.lastRelease = Date.now();
      const resolve = this.queue.shift();
      if (resolve) resolve();
      this._drain();
    }, wait);
  }
}

module.exports = { RateLimiter };
