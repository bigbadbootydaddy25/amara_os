import { AvatarRenderer } from '@/canvas/avatar-renderer';
import { OrbRenderer } from '@/canvas/orb-renderer';
import { useAmaraStore } from '@/stores/amara-store';

export class AnimationLoop {
  private avatarRenderer: AvatarRenderer;
  private orbRenderer: OrbRenderer;
  private avatarCanvas: HTMLCanvasElement;
  private orbCanvas: HTMLCanvasElement;
  private avatarCtx: CanvasRenderingContext2D;
  private orbCtx: CanvasRenderingContext2D;
  private running = false;
  private frameId = 0;
  private lastTime = 0;

  constructor(avatarCanvas: HTMLCanvasElement, orbCanvas: HTMLCanvasElement) {
    const avatarCtx = avatarCanvas.getContext('2d');
    const orbCtx = orbCanvas.getContext('2d');

    if (!avatarCtx || !orbCtx) {
      throw new Error('Canvas 2D context unavailable');
    }

    this.avatarCanvas = avatarCanvas;
    this.orbCanvas = orbCanvas;
    this.avatarCtx = avatarCtx;
    this.orbCtx = orbCtx;

    const width = typeof window !== 'undefined' ? window.innerWidth : 1920;
    const height = typeof window !== 'undefined' ? window.innerHeight : 1080;

    this.avatarRenderer = new AvatarRenderer(avatarCtx, width, height);
    this.orbRenderer = new OrbRenderer(orbCtx, width, height);
    this.resize();
    this.avatarRenderer.loadImage('/amara-face.png');
  }

  start(): void {
    if (this.running) {
      return;
    }

    this.running = true;
    this.lastTime = performance.now();
    this.frameId = window.requestAnimationFrame(this.tick);
  }

  stop(): void {
    this.running = false;
    window.cancelAnimationFrame(this.frameId);
  }

  resize(): void {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const dpr = window.devicePixelRatio || 1;

    [this.orbCanvas, this.avatarCanvas].forEach((canvas) => {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    });

    this.orbCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.avatarCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.orbRenderer.resize(width, height);
    this.avatarRenderer.resize(width, height);
  }

  private tick = (time: number): void => {
    if (!this.running) {
      return;
    }

    const deltaTime = (time - this.lastTime) / 1000;
    this.lastTime = time;

    const { state, audioLevel, errorPulse } = useAmaraStore.getState();

    this.orbRenderer.update(deltaTime, state, audioLevel);
    this.avatarRenderer.update(deltaTime, state, audioLevel, errorPulse);

    this.orbCtx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    this.avatarCtx.clearRect(0, 0, window.innerWidth, window.innerHeight);

    this.orbRenderer.render();
    this.avatarRenderer.render();

    this.frameId = window.requestAnimationFrame(this.tick);
  };
}
