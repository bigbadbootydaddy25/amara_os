import type { AmaraState, OrbParticle } from '@/types';

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const lerp = (start: number, end: number, amount: number) =>
  start + (end - start) * amount;

export class OrbRenderer {
  private ctx: CanvasRenderingContext2D;
  private width: number;
  private height: number;
  private orbs: OrbParticle[];
  private time = 0;

  constructor(ctx: CanvasRenderingContext2D, width: number, height: number) {
    this.ctx = ctx;
    this.width = width;
    this.height = height;
    this.orbs = this.createOrbs();
  }

  resize(width: number, height: number): void {
    this.width = width;
    this.height = height;
    this.orbs = this.orbs.map((orb, index) => this.seedOrb(index, orb.phase));
  }

  update(deltaTime: number, amaraState: AmaraState, audioLevel: number): void {
    const dt = Math.min(deltaTime, 0.05);
    this.time += dt;

    const centerX = this.width / 2;
    const centerY = this.height * 0.44;
    const stateOrbitFactor =
      amaraState === 'idle'
        ? 1
        : amaraState === 'listening'
          ? 0.86
          : amaraState === 'thinking'
            ? 1.16
            : 0.94;
    const stateSpeedFactor =
      amaraState === 'idle'
        ? 0.45
        : amaraState === 'listening'
          ? 0.75
          : amaraState === 'thinking'
            ? 1.35
            : 0.95;
    const audioBoost = amaraState === 'speaking' || amaraState === 'listening' ? audioLevel : 0;
    const contractionPulse = amaraState === 'thinking' ? (Math.sin(this.time * 5.2) + 1) * 0.5 : 0;

    this.orbs.forEach((orb, index) => {
      const orbitalNoise = Math.sin(this.time * (0.7 + orb.phase * 0.2) + orb.phase * 7.5);
      const orbitRadius =
        orb.baseRadius * 8 +
        orb.orbitRadius * stateOrbitFactor +
        (contractionPulse * 28 - 12) * (index % 3 === 0 ? 1 : 0.5);
      orb.angle += dt * orb.speed * stateSpeedFactor;

      const driftX = Math.cos(this.time * 0.26 + orb.phase * 11.2) * 26;
      const driftY = Math.sin(this.time * 0.22 + orb.phase * 8.4) * 20;
      orb.x = centerX + Math.cos(orb.angle + orbitalNoise * 0.2) * orbitRadius + driftX;
      orb.y = centerY + Math.sin(orb.angle * 1.15 + orb.phase * 2.1) * orbitRadius * 0.45 + driftY;

      const baseRadiusFactor =
        amaraState === 'idle'
          ? 0.88
          : amaraState === 'listening'
            ? 0.98 + audioBoost * 0.35
            : amaraState === 'thinking'
              ? 1.08 + contractionPulse * 0.22
              : 1.06 + audioBoost * 0.5;
      const targetRadius = orb.baseRadius * baseRadiusFactor + Math.sin(this.time * 1.5 + orb.phase * 10) * 0.8;
      orb.radius = lerp(orb.radius, targetRadius, 1 - Math.exp(-dt / 0.24));

      const baseOpacity =
        amaraState === 'idle'
          ? 0.13
          : amaraState === 'listening'
            ? 0.2
            : amaraState === 'thinking'
              ? 0.26
              : 0.24;
      const sparkle = (Math.sin(this.time * 2.2 + orb.phase * 17) + 1) * 0.5;
      const opacityBoost =
        amaraState === 'speaking'
          ? audioBoost * 0.22
          : amaraState === 'thinking'
            ? contractionPulse * 0.18 + sparkle * 0.08
            : amaraState === 'listening'
              ? audioBoost * 0.12
              : sparkle * 0.03;
      orb.opacity = clamp(baseOpacity + opacityBoost + (index % 4 === 0 ? 0.08 : 0), 0.08, 0.62);
    });
  }

  render(): void {
    const ctx = this.ctx;
    ctx.save();
    ctx.globalCompositeOperation = 'screen';

    for (const orb of this.orbs) {
      const glow = ctx.createRadialGradient(orb.x, orb.y, 0, orb.x, orb.y, orb.radius * 2.6);
      glow.addColorStop(0, `hsla(${orb.hue}, 88%, 72%, ${orb.opacity})`);
      glow.addColorStop(0.28, `hsla(${orb.hue}, 88%, 65%, ${orb.opacity * 0.5})`);
      glow.addColorStop(1, `hsla(${orb.hue}, 88%, 50%, 0)`);
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(orb.x, orb.y, orb.radius * 2.6, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  private createOrbs(): OrbParticle[] {
    const count = 32;
    return Array.from({ length: count }, (_, index) => this.seedOrb(index, Math.random()));
  }

  private seedOrb(index: number, phaseSeed: number): OrbParticle {
    const phase = phaseSeed;
    const baseRadius = 4 + Math.random() * 22;

    // Mix of cyan (185–215), blue-violet (225–255), and violet/purple (265–300)
    const hueRanges: [number, number][] = [[185, 215], [225, 255], [265, 300]];
    const range = hueRanges[Math.floor(Math.random() * hueRanges.length)];
    const hue = range[0] + Math.random() * (range[1] - range[0]);

    return {
      x: this.width / 2,
      y: this.height / 2,
      radius: baseRadius,
      baseRadius,
      angle: (Math.PI * 2 * index) / 32,
      speed: 0.12 + Math.random() * 0.5,
      orbitRadius: Math.min(this.width, this.height) * (0.12 + Math.random() * 0.34),
      opacity: 0.18 + Math.random() * 0.16,
      hue,
      phase,
    };
  }
}
