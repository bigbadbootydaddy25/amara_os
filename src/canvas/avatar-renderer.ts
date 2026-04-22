import type { AmaraState, AvatarAnimState } from '@/types';

const BLINK_MIN_INTERVAL = 2;
const BLINK_MAX_INTERVAL = 5;

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const lerp = (start: number, end: number, amount: number) =>
  start + (end - start) * amount;

const easeInOut = (value: number) =>
  value < 0.5 ? 2 * value * value : 1 - Math.pow(-2 * value + 2, 2) / 2;

export class AvatarRenderer {
  private ctx: CanvasRenderingContext2D;
  private width: number;
  private height: number;
  private animState: AvatarAnimState;
  private time = 0;
  private lastBlinkTime = 0;
  private nextBlinkInterval = 3.25;
  private errorGlow = 0;
  private lastErrorPulse = 0;

  constructor(ctx: CanvasRenderingContext2D, width: number, height: number) {
    this.ctx = ctx;
    this.width = width;
    this.height = height;
    this.animState = {
      mouthOpenness: 0.08,
      eyeGlow: 0.45,
      blinkProgress: 0,
      headTilt: 0,
      breathScale: 1,
      thinkingPulse: 0,
    };
    this.scheduleNextBlink();
  }

  resize(width: number, height: number): void {
    this.width = width;
    this.height = height;
  }

  update(
    deltaTime: number,
    amaraState: AmaraState,
    audioLevel: number,
    errorPulse: number,
  ): void {
    const dt = Math.min(deltaTime, 0.05);
    this.time += dt;

    if (errorPulse !== this.lastErrorPulse) {
      this.lastErrorPulse = errorPulse;
      this.errorGlow = 1;
    } else {
      this.errorGlow = lerp(this.errorGlow, 0, 1 - Math.exp(-dt / 0.18));
    }

    const breathWave = Math.sin((this.time / 4) * Math.PI * 2);
    const breathScaleTarget = 1 + breathWave * 0.01;
    const headTiltTarget = Math.sin((this.time / 7) * Math.PI * 2) * 0.02;
    const thinkingPulse = (Math.sin((this.time / 1.6) * Math.PI * 2) + 1) * 0.5;

    let targetMouth = 0.04 + (breathWave + 1) * 0.015;
    let targetGlow = 0.4;

    if (amaraState === 'listening') {
      targetMouth = 0.02;
      targetGlow = 0.7;
    }

    if (amaraState === 'thinking') {
      targetMouth = 0.03;
      targetGlow = lerp(0.5, 0.9, thinkingPulse);
    }

    if (amaraState === 'speaking') {
      targetMouth = clamp(audioLevel * 0.8 + 0.1, 0.1, 1);
      targetGlow = 0.8;
    }

    const smoothing = 1 - Math.exp(-dt / 0.18);

    this.animState.breathScale = lerp(
      this.animState.breathScale,
      breathScaleTarget,
      smoothing,
    );
    this.animState.headTilt = lerp(this.animState.headTilt, headTiltTarget, smoothing * 0.7);
    this.animState.mouthOpenness = lerp(
      this.animState.mouthOpenness,
      targetMouth,
      smoothing,
    );
    this.animState.eyeGlow = lerp(this.animState.eyeGlow, targetGlow, smoothing);
    this.animState.thinkingPulse = lerp(
      this.animState.thinkingPulse,
      thinkingPulse,
      1 - Math.exp(-dt / 0.22),
    );

    const blinkBias = amaraState === 'listening' ? 0.85 : 1;
    const blinkElapsed = this.time - this.lastBlinkTime;
    const blinkDuration = 0.18;
    const shouldBlink = blinkElapsed >= this.nextBlinkInterval * blinkBias;

    if (shouldBlink) {
      this.lastBlinkTime = this.time;
      this.scheduleNextBlink();
    }

    const blinkTime = this.time - this.lastBlinkTime;
    if (blinkTime >= 0 && blinkTime <= blinkDuration) {
      const blinkPhase = blinkTime / blinkDuration;
      const triangle = blinkPhase < 0.5 ? blinkPhase * 2 : (1 - blinkPhase) * 2;
      this.animState.blinkProgress = easeInOut(triangle);
    } else {
      this.animState.blinkProgress = lerp(this.animState.blinkProgress, 0, smoothing * 1.3);
    }
  }

  render(): void {
    const ctx = this.ctx;
    const cx = this.width / 2;
    const cy = this.height * 0.45;
    const headWidth = this.width * 0.3;
    const headHeight = this.height * 0.48;
    const neckWidth = headWidth * 0.44;
    const neckHeight = headHeight * 0.2;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.animState.headTilt);
    ctx.scale(this.animState.breathScale, this.animState.breathScale);

    this.drawHairSilhouette(headWidth, headHeight);
    this.drawNeck(neckWidth, neckHeight, headHeight);
    this.drawHead(headWidth, headHeight);
    this.drawPanelLines(headWidth, headHeight);
    this.drawEyes(headWidth, headHeight);
    this.drawMouth(headWidth, headHeight);

    ctx.restore();
  }

  private scheduleNextBlink(): void {
    this.nextBlinkInterval = lerp(
      BLINK_MIN_INTERVAL,
      BLINK_MAX_INTERVAL,
      Math.random(),
    );
  }

  // Subtle holographic hair silhouette — drawn behind the head
  private drawHairSilhouette(headWidth: number, headHeight: number): void {
    const ctx = this.ctx;
    ctx.save();

    const hairPath = new Path2D();
    hairPath.moveTo(-headWidth * 0.40, -headHeight * 0.56);
    hairPath.quadraticCurveTo(0, -headHeight * 0.82, headWidth * 0.40, -headHeight * 0.56);
    hairPath.bezierCurveTo(
      headWidth * 0.64,
      -headHeight * 0.30,
      headWidth * 0.60,
      headHeight * 0.14,
      headWidth * 0.34,
      headHeight * 0.46,
    );
    hairPath.quadraticCurveTo(0, headHeight * 0.61, -headWidth * 0.34, headHeight * 0.46);
    hairPath.bezierCurveTo(
      -headWidth * 0.60,
      headHeight * 0.14,
      -headWidth * 0.64,
      -headHeight * 0.30,
      -headWidth * 0.40,
      -headHeight * 0.56,
    );
    hairPath.closePath();

    const hairGradient = ctx.createLinearGradient(0, -headHeight * 0.78, 0, headHeight * 0.5);
    hairGradient.addColorStop(0, '#130820');
    hairGradient.addColorStop(0.4, '#0e0618');
    hairGradient.addColorStop(1, '#080412');

    ctx.fillStyle = hairGradient;
    ctx.shadowColor = `rgba(140, 80, 255, ${0.14 + this.animState.eyeGlow * 0.10})`;
    ctx.shadowBlur = headWidth * 0.1;
    ctx.fill(hairPath);
    ctx.shadowBlur = 0;

    ctx.strokeStyle = `rgba(150, 90, 255, ${0.09 + this.animState.eyeGlow * 0.07})`;
    ctx.lineWidth = Math.max(1, headWidth * 0.007);
    ctx.stroke(hairPath);

    ctx.restore();
  }

  private drawHead(headWidth: number, headHeight: number): void {
    const ctx = this.ctx;
    const headGradient = ctx.createLinearGradient(0, -headHeight * 0.62, 0, headHeight * 0.7);
    headGradient.addColorStop(0, '#f4f6fb');
    headGradient.addColorStop(0.2, '#e8e8ec');
    headGradient.addColorStop(0.55, '#dddde4');
    headGradient.addColorStop(0.85, '#c8c8d1');
    headGradient.addColorStop(1, '#b9bac3');

    ctx.save();
    const headPath = new Path2D();
    // Narrower jaw than original for a more feminine oval silhouette
    headPath.moveTo(-headWidth * 0.34, -headHeight * 0.49);
    headPath.quadraticCurveTo(0, -headHeight * 0.61, headWidth * 0.34, -headHeight * 0.49);
    headPath.bezierCurveTo(
      headWidth * 0.52,
      -headHeight * 0.26,
      headWidth * 0.44,
      headHeight * 0.22,
      headWidth * 0.21,
      headHeight * 0.46,
    );
    headPath.quadraticCurveTo(0, headHeight * 0.60, -headWidth * 0.21, headHeight * 0.46);
    headPath.bezierCurveTo(
      -headWidth * 0.44,
      headHeight * 0.22,
      -headWidth * 0.52,
      -headHeight * 0.26,
      -headWidth * 0.34,
      -headHeight * 0.49,
    );
    headPath.closePath();

    ctx.fillStyle = headGradient;
    ctx.shadowColor = 'rgba(140, 80, 255, 0.09)';
    ctx.shadowBlur = headWidth * 0.12;
    ctx.fill(headPath);
    ctx.shadowBlur = 0;

    const cheekHighlight = ctx.createLinearGradient(-headWidth * 0.22, 0, headWidth * 0.22, 0);
    cheekHighlight.addColorStop(0, 'rgba(255,255,255,0)');
    cheekHighlight.addColorStop(0.25, 'rgba(255,255,255,0.07)');
    cheekHighlight.addColorStop(0.5, 'rgba(255,255,255,0.18)');
    cheekHighlight.addColorStop(0.75, 'rgba(255,255,255,0.07)');
    cheekHighlight.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = cheekHighlight;
    ctx.beginPath();
    ctx.ellipse(0, headHeight * 0.04, headWidth * 0.22, headHeight * 0.16, 0, 0, Math.PI * 2);
    ctx.fill();

    const rimGradient = ctx.createRadialGradient(0, -headHeight * 0.06, headWidth * 0.05, 0, 0, headWidth * 0.60);
    rimGradient.addColorStop(0, 'rgba(255,255,255,0)');
    rimGradient.addColorStop(0.75, 'rgba(255,255,255,0)');
    rimGradient.addColorStop(1, 'rgba(140, 152, 168, 0.22)');
    ctx.fillStyle = rimGradient;
    ctx.fill(headPath);
    ctx.restore();
  }

  private drawPanelLines(headWidth: number, headHeight: number): void {
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = 'rgba(100, 110, 120, 0.28)';
    ctx.lineWidth = Math.max(1.2, headWidth * 0.006);
    ctx.lineCap = 'round';

    ctx.beginPath();
    ctx.moveTo(-headWidth * 0.26, -headHeight * 0.16);
    ctx.quadraticCurveTo(-headWidth * 0.42, headHeight * 0.04, -headWidth * 0.20, headHeight * 0.32);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(headWidth * 0.26, -headHeight * 0.16);
    ctx.quadraticCurveTo(headWidth * 0.42, headHeight * 0.04, headWidth * 0.20, headHeight * 0.32);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(-headWidth * 0.20, headHeight * 0.22);
    ctx.quadraticCurveTo(0, headHeight * 0.28, headWidth * 0.20, headHeight * 0.22);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(72, 78, 88, 0.22)';
    ctx.lineWidth = Math.max(1, headWidth * 0.004);
    ctx.beginPath();
    ctx.moveTo(-headWidth * 0.18, -headHeight * 0.47);
    ctx.quadraticCurveTo(0, -headHeight * 0.35, headWidth * 0.18, -headHeight * 0.47);
    ctx.stroke();
    ctx.restore();
  }

  private drawEyes(headWidth: number, headHeight: number): void {
    const ctx = this.ctx;
    const eyeY = -headHeight * 0.11;
    const eyeOffsetX = headWidth * 0.16;
    const eyeWidth = headWidth * 0.16;
    const eyeHeight = headHeight * 0.09;
    const irisRadius = eyeHeight * 0.72;
    const blink = easeInOut(this.animState.blinkProgress);
    const errorGlow = this.errorGlow;

    [-1, 1].forEach((direction) => {
      const ex = eyeOffsetX * direction;
      const lidDrop = eyeHeight * 1.8 * blink;
      const apertureHeight = Math.max(eyeHeight * 0.08, eyeHeight * (1 - blink * 0.94));

      // Inner/outer corner for brow placement
      const innerX = ex - direction * eyeWidth * 0.60;
      const outerX = ex + direction * eyeWidth * 0.56;
      const peakX = ex + direction * eyeWidth * 0.10;
      const browBaseY = eyeY - eyeHeight * 1.36;

      ctx.save();
      ctx.beginPath();
      ctx.ellipse(ex, eyeY, eyeWidth * 0.56, eyeHeight * 0.7, 0, 0, Math.PI * 2);
      ctx.clip();

      const socketGradient = ctx.createRadialGradient(ex, eyeY, eyeHeight * 0.1, ex, eyeY, eyeWidth * 0.85);
      socketGradient.addColorStop(0, 'rgba(20, 12, 38, 0.96)');
      socketGradient.addColorStop(0.6, 'rgba(9, 6, 20, 0.93)');
      socketGradient.addColorStop(1, 'rgba(0, 0, 0, 0.98)');
      ctx.fillStyle = socketGradient;
      ctx.fillRect(ex - eyeWidth, eyeY - eyeHeight, eyeWidth * 2, eyeHeight * 2);

      ctx.save();
      ctx.translate(ex, eyeY + blink * eyeHeight * 0.2);
      ctx.scale(1, clamp(apertureHeight / eyeHeight, 0.12, 1));

      // Violet/purple iris — feminine and distinct
      const irisGradient = ctx.createRadialGradient(0, 0, irisRadius * 0.1, 0, 0, irisRadius);
      irisGradient.addColorStop(0, errorGlow > 0.1 ? '#ffb3b3' : '#d4b8ff');
      irisGradient.addColorStop(0.38, errorGlow > 0.1 ? '#ff4d4d' : '#7c3aed');
      irisGradient.addColorStop(0.74, errorGlow > 0.1 ? '#d10000' : '#4c1d95');
      irisGradient.addColorStop(1, errorGlow > 0.1 ? '#220000' : '#1a0533');
      ctx.fillStyle = irisGradient;
      ctx.beginPath();
      ctx.arc(0, 0, irisRadius, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = 'rgba(4, 2, 12, 0.94)';
      ctx.beginPath();
      ctx.arc(0, 0, irisRadius * 0.28, 0, Math.PI * 2);
      ctx.fill();

      // Iris filaments — lavender tinted
      ctx.strokeStyle = errorGlow > 0.1
        ? `rgba(255, 186, 186, ${0.26 + errorGlow * 0.4})`
        : `rgba(196, 162, 255, 0.30)`;
      ctx.lineWidth = Math.max(1, irisRadius * 0.08);
      for (let i = 0; i < 12; i += 1) {
        const angle = (Math.PI * 2 * i) / 12;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * irisRadius * 0.36, Math.sin(angle) * irisRadius * 0.36);
        ctx.lineTo(Math.cos(angle) * irisRadius * 0.82, Math.sin(angle) * irisRadius * 0.82);
        ctx.stroke();
      }

      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      ctx.beginPath();
      ctx.arc(irisRadius * 0.28, -irisRadius * 0.34, irisRadius * 0.16, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.restore();

      // Violet eye glow
      ctx.save();
      const glowRadius = eyeWidth * lerp(0.95, 1.65, this.animState.eyeGlow + errorGlow * 0.2);
      const glowGradient = ctx.createRadialGradient(ex, eyeY, 0, ex, eyeY, glowRadius);
      glowGradient.addColorStop(
        0,
        errorGlow > 0.1
          ? `rgba(255, 74, 74, ${0.24 + errorGlow * 0.36})`
          : `rgba(167, 100, 255, ${0.18 + this.animState.eyeGlow * 0.24})`,
      );
      glowGradient.addColorStop(
        0.55,
        errorGlow > 0.1
          ? `rgba(255, 0, 0, ${0.14 + errorGlow * 0.22})`
          : `rgba(109, 40, 217, ${0.09 + this.animState.eyeGlow * 0.13})`,
      );
      glowGradient.addColorStop(1, errorGlow > 0.1 ? 'rgba(90, 0, 0, 0)' : 'rgba(30, 0, 60, 0)');
      ctx.globalCompositeOperation = 'screen';
      ctx.fillStyle = glowGradient;
      ctx.beginPath();
      ctx.arc(ex, eyeY, glowRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // Upper lid line + eyelid fill
      ctx.save();
      ctx.strokeStyle = 'rgba(255,255,255,0.11)';
      ctx.lineWidth = Math.max(1, headWidth * 0.004);
      ctx.beginPath();
      ctx.moveTo(ex - eyeWidth * 0.66, eyeY - eyeHeight * 0.04);
      ctx.quadraticCurveTo(ex, eyeY - eyeHeight * 0.5, ex + eyeWidth * 0.66, eyeY - eyeHeight * 0.04);
      ctx.stroke();

      ctx.fillStyle = 'rgba(219, 223, 232, 0.92)';
      ctx.beginPath();
      ctx.moveTo(ex - eyeWidth * 0.7, eyeY - eyeHeight * 0.1);
      ctx.quadraticCurveTo(ex, eyeY - eyeHeight * 0.62 + lidDrop, ex + eyeWidth * 0.7, eyeY - eyeHeight * 0.1);
      ctx.lineTo(ex + eyeWidth * 0.7, eyeY - eyeHeight * 0.72 + lidDrop);
      ctx.quadraticCurveTo(ex, eyeY - eyeHeight * 0.2 + lidDrop, ex - eyeWidth * 0.7, eyeY - eyeHeight * 0.72 + lidDrop);
      ctx.closePath();
      ctx.fill();
      ctx.restore();

      // Feminine brow arch
      ctx.save();
      ctx.strokeStyle = 'rgba(115, 125, 150, 0.50)';
      ctx.lineWidth = Math.max(1.5, headWidth * 0.0090);
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(innerX, browBaseY + eyeHeight * 0.42);
      ctx.quadraticCurveTo(peakX, browBaseY, outerX, browBaseY + eyeHeight * 0.30);
      ctx.stroke();
      ctx.restore();
    });
  }

  private drawMouth(headWidth: number, headHeight: number): void {
    const ctx = this.ctx;
    const mouthY = headHeight * 0.22;
    const mouthWidth = headWidth * 0.24;
    const mouthHeight = lerp(headHeight * 0.012, headHeight * 0.11, this.animState.mouthOpenness);
    const radius = mouthHeight * 0.7;

    ctx.save();
    ctx.fillStyle = 'rgba(235, 238, 246, 0.95)';
    ctx.beginPath();
    ctx.roundRect(-mouthWidth * 0.56, mouthY - headHeight * 0.015, mouthWidth * 1.12, mouthHeight + headHeight * 0.03, radius);
    ctx.fill();

    const interiorGradient = ctx.createLinearGradient(0, mouthY - mouthHeight * 0.4, 0, mouthY + mouthHeight * 1.1);
    interiorGradient.addColorStop(0, '#1e0e36');
    interiorGradient.addColorStop(0.2, '#150b28');
    interiorGradient.addColorStop(1, '#080410');
    ctx.fillStyle = interiorGradient;
    ctx.beginPath();
    ctx.roundRect(-mouthWidth * 0.5, mouthY, mouthWidth, mouthHeight, radius * 0.78);
    ctx.fill();

    if (this.animState.mouthOpenness > 0.1) {
      ctx.strokeStyle = `rgba(160, 100, 255, ${0.15 + this.animState.mouthOpenness * 0.2})`;
      ctx.lineWidth = Math.max(1, headWidth * 0.004);
      for (let i = -1; i <= 1; i += 1) {
        const lineY = mouthY + mouthHeight * (0.3 + (i + 1) * 0.18);
        ctx.beginPath();
        ctx.moveTo(-mouthWidth * 0.28, lineY);
        ctx.lineTo(mouthWidth * 0.28, lineY);
        ctx.stroke();
      }

      const glowGradient = ctx.createRadialGradient(0, mouthY + mouthHeight * 0.45, 0, 0, mouthY + mouthHeight * 0.45, mouthWidth * 0.72);
      glowGradient.addColorStop(0, `rgba(150, 80, 255, ${0.1 + this.animState.mouthOpenness * 0.16})`);
      glowGradient.addColorStop(1, 'rgba(150, 80, 255, 0)');
      ctx.globalCompositeOperation = 'screen';
      ctx.fillStyle = glowGradient;
      ctx.beginPath();
      ctx.ellipse(0, mouthY + mouthHeight * 0.48, mouthWidth * 0.72, mouthHeight * 1.2, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  private drawNeck(neckWidth: number, neckHeight: number, headHeight: number): void {
    const ctx = this.ctx;
    const neckTop = headHeight * 0.42;
    const neckGradient = ctx.createLinearGradient(0, neckTop, 0, neckTop + neckHeight * 1.5);
    neckGradient.addColorStop(0, '#b7b8c3');
    neckGradient.addColorStop(0.4, '#a0a0a8');
    neckGradient.addColorStop(1, '#6f7481');

    ctx.save();
    ctx.fillStyle = neckGradient;
    ctx.beginPath();
    ctx.roundRect(-neckWidth * 0.5, neckTop, neckWidth, neckHeight * 1.55, neckWidth * 0.14);
    ctx.fill();

    ctx.strokeStyle = 'rgba(74, 82, 96, 0.40)';
    ctx.lineWidth = Math.max(1.2, neckWidth * 0.016);
    ctx.beginPath();
    ctx.moveTo(-neckWidth * 0.5, neckTop + neckHeight * 0.18);
    ctx.lineTo(neckWidth * 0.5, neckTop + neckHeight * 0.18);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(45, 52, 68, 0.52)';
    ctx.lineWidth = Math.max(1, neckWidth * 0.013);
    [-0.22, 0, 0.22].forEach((offset) => {
      ctx.beginPath();
      ctx.moveTo(neckWidth * offset, neckTop + neckHeight * 0.24);
      ctx.lineTo(neckWidth * offset, neckTop + neckHeight * 1.42);
      ctx.stroke();
    });

    ctx.restore();
  }
}
