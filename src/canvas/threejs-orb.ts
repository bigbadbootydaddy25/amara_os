import * as THREE from 'three';
import type { AmaraState } from '@/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function bandAvg(data: Uint8Array, startRatio: number, endRatio: number): number {
  const len = data.length;
  const s = Math.floor(len * startRatio);
  const e = Math.floor(len * endRatio);
  if (e <= s) return 0;
  let sum = 0;
  for (let i = s; i < e; i++) sum += data[i];
  return sum / ((e - s) * 255);
}

// Per-node color type: 0=cyan, 1=purple, 2=white-blue
function nodeRGB(ct: number, b: number): [number, number, number] {
  if (ct === 1) return [0.72 * b, 0.10 * b, b];   // purple
  if (ct === 2) return [0.75 * b, 0.90 * b, b];   // white-blue
  return [0, 0.831 * b, b];                         // cyan
}

// ---------------------------------------------------------------------------
// Texture factories
// ---------------------------------------------------------------------------

function makeStarTexture(): THREE.CanvasTexture {
  const sz = 128;
  const c = document.createElement('canvas');
  c.width = c.height = sz;
  const ctx = c.getContext('2d')!;
  const h = sz / 2;
  for (let ray = 0; ray < 4; ray++) {
    ctx.save();
    ctx.translate(h, h);
    ctx.rotate(ray * Math.PI / 4);
    const rg = ctx.createLinearGradient(-h, 0, h, 0);
    rg.addColorStop(0, 'rgba(0,210,255,0)');
    rg.addColorStop(0.28, 'rgba(60,220,255,0.5)');
    rg.addColorStop(0.5, 'rgba(255,255,255,1)');
    rg.addColorStop(0.72, 'rgba(60,220,255,0.5)');
    rg.addColorStop(1, 'rgba(0,210,255,0)');
    ctx.fillStyle = rg;
    ctx.fillRect(-h, -1.5, sz, 3);
    ctx.restore();
  }
  const g = ctx.createRadialGradient(h, h, 0, h, h, h * 0.36);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.3, 'rgba(210,248,255,0.95)');
  g.addColorStop(0.7, 'rgba(0,210,255,0.5)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, sz, sz);
  return new THREE.CanvasTexture(c);
}

function makePurpleStarTexture(): THREE.CanvasTexture {
  const sz = 128;
  const c = document.createElement('canvas');
  c.width = c.height = sz;
  const ctx = c.getContext('2d')!;
  const h = sz / 2;
  for (let ray = 0; ray < 4; ray++) {
    ctx.save();
    ctx.translate(h, h);
    ctx.rotate(ray * Math.PI / 4);
    const rg = ctx.createLinearGradient(-h, 0, h, 0);
    rg.addColorStop(0, 'rgba(140,0,255,0)');
    rg.addColorStop(0.28, 'rgba(180,60,255,0.5)');
    rg.addColorStop(0.5, 'rgba(255,255,255,1)');
    rg.addColorStop(0.72, 'rgba(180,60,255,0.5)');
    rg.addColorStop(1, 'rgba(140,0,255,0)');
    ctx.fillStyle = rg;
    ctx.fillRect(-h, -1.5, sz, 3);
    ctx.restore();
  }
  const g = ctx.createRadialGradient(h, h, 0, h, h, h * 0.36);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.3, 'rgba(230,200,255,0.95)');
  g.addColorStop(0.7, 'rgba(160,0,255,0.5)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, sz, sz);
  return new THREE.CanvasTexture(c);
}

function makeHaloTexture(): THREE.CanvasTexture {
  const size = 512;
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const ctx = c.getContext('2d')!;
  const h = size / 2;
  const g = ctx.createRadialGradient(h, h, 0, h, h, h);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(0.38, 'rgba(0,0,0,0)');
  g.addColorStop(0.52, 'rgba(0,212,255,0.07)');
  g.addColorStop(0.65, 'rgba(0,180,240,0.16)');
  g.addColorStop(0.78, 'rgba(60,0,160,0.10)');
  g.addColorStop(0.90, 'rgba(0,20,60,0.04)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SPHERE_R = 2.0;
const NODE_COUNT = 320;
const MAX_EDGES = 3000;
const PARTICLE_COUNT = 350;

// ---------------------------------------------------------------------------
// Per-node data
// ---------------------------------------------------------------------------

interface NodeData {
  bx: number; by: number; bz: number;   // base position (fibonacci surface)
  px: number; py: number; pz: number;   // current animated position
  phX: number; phY: number; phZ: number; // noise phase
  spX: number; spY: number; spZ: number; // noise speed
  amp: number;
  bright: number;
  ct: number;  // color type: 0=cyan, 1=purple, 2=white-blue
}

// ---------------------------------------------------------------------------
// Main renderer
// ---------------------------------------------------------------------------

export class ThreeOrbRenderer {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;

  private orbGroup: THREE.Group;

  private nodePos: Float32Array;
  private nodeColor: Float32Array;
  private nodeGeom: THREE.BufferGeometry;
  private nodePoints!: THREE.Points;
  private purpleNodePos: Float32Array;
  private purpleNodeColor: Float32Array;
  private purpleNodeGeom: THREE.BufferGeometry;
  private purpleNodePoints!: THREE.Points;
  private nodeData: NodeData[] = [];

  private edgePos: Float32Array;
  private edgeColor: Float32Array;
  private edgeGeom: THREE.BufferGeometry;
  private edgeLines!: THREE.LineSegments;
  private edgePairs: Array<[number, number]> = [];

  private haloSprite!: THREE.Sprite;

  private partPos: Float32Array;
  private partVel: Float32Array;
  private partLife: Float32Array;
  private partGeom: THREE.BufferGeometry;
  private partSystem!: THREE.Points;

  private outAnalyser: AnalyserNode | null = null;
  private micAnalyser: AnalyserNode | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private outData: any = new Uint8Array(256);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private micData: any = new Uint8Array(256);

  private aLow = 0;
  private aMid = 0;
  private aHigh = 0;
  private aOverall = 0;
  private aMic = 0;

  private state: AmaraState = 'idle';
  private time = 0;

  private sBright = 0.55;
  private sConn = 0.65;
  private sRotSpeed = 0.004;
  private sHaloScale = 1.0;

  constructor(canvas: HTMLCanvasElement, width: number, height: number) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 1);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(52, width / height, 0.01, 100);
    this.camera.position.z = 4.4;

    this.orbGroup = new THREE.Group();
    this.scene.add(this.orbGroup);

    this.nodePos = new Float32Array(NODE_COUNT * 3);
    this.nodeColor = new Float32Array(NODE_COUNT * 3);
    this.purpleNodePos = new Float32Array(NODE_COUNT * 3);
    this.purpleNodeColor = new Float32Array(NODE_COUNT * 3);
    this.edgePos = new Float32Array(MAX_EDGES * 6);
    this.edgeColor = new Float32Array(MAX_EDGES * 6);
    this.partPos = new Float32Array(PARTICLE_COUNT * 3);
    this.partVel = new Float32Array(PARTICLE_COUNT * 3);
    this.partLife = new Float32Array(PARTICLE_COUNT);

    this.nodeGeom = new THREE.BufferGeometry();
    this.purpleNodeGeom = new THREE.BufferGeometry();
    this.edgeGeom = new THREE.BufferGeometry();
    this.partGeom = new THREE.BufferGeometry();

    this.buildScene();
  }

  // ---------------------------------------------------------------------------
  // Scene construction
  // ---------------------------------------------------------------------------

  private buildScene(): void {
    this.buildNodes();
    this.buildEdges();
    this.buildHalo();
    this.buildParticles();
  }

  private buildNodes(): void {
    const goldenAngle = Math.PI * (Math.sqrt(5) - 1);

    for (let i = 0; i < NODE_COUNT; i++) {
      const y = 1 - (i / (NODE_COUNT - 1)) * 2;
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = goldenAngle * i;
      const bx = Math.cos(theta) * r * SPHERE_R;
      const by = y * SPHERE_R;
      const bz = Math.sin(theta) * r * SPHERE_R;

      const rand = Math.random();
      const ct = rand < 0.72 ? 0 : rand < 0.90 ? 1 : 2;

      this.nodeData.push({
        bx, by, bz,
        px: bx, py: by, pz: bz,
        phX: Math.random() * Math.PI * 2,
        phY: Math.random() * Math.PI * 2,
        phZ: Math.random() * Math.PI * 2,
        spX: 0.10 + Math.random() * 0.20,
        spY: 0.08 + Math.random() * 0.18,
        spZ: 0.09 + Math.random() * 0.22,
        amp: 0.025 + Math.random() * 0.055,
        bright: 0.5 + Math.random() * 0.5,
        ct,
      });
    }

    // Pre-compute edge pairs: always short, probabilistically long
    const order = Array.from({ length: NODE_COUNT }, (_, i) => i)
      .sort(() => Math.random() - 0.5);
    for (let ai = 0; ai < NODE_COUNT && this.edgePairs.length < MAX_EDGES; ai++) {
      const a = order[ai];
      const na = this.nodeData[a];
      for (let bi = ai + 1; bi < NODE_COUNT && this.edgePairs.length < MAX_EDGES; bi++) {
        const b = order[bi];
        const nb = this.nodeData[b];
        const dx = na.bx - nb.bx, dy = na.by - nb.by, dz = na.bz - nb.bz;
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (d > 3.6) continue;
        const prob = d < 1.0 ? 1.0 : 0.10 * Math.pow((3.6 - d) / 2.6, 2.0);
        if (Math.random() < prob) this.edgePairs.push([a, b]);
      }
    }

    // Cyan / white-blue node points
    this.nodeGeom.setAttribute('position', new THREE.BufferAttribute(this.nodePos, 3));
    this.nodeGeom.setAttribute('color', new THREE.BufferAttribute(this.nodeColor, 3));
    const cyanMat = new THREE.PointsMaterial({
      size: 0.26,
      map: makeStarTexture(),
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });
    this.nodePoints = new THREE.Points(this.nodeGeom, cyanMat);
    this.orbGroup.add(this.nodePoints);

    // Purple node points (separate draw call with purple texture)
    this.purpleNodeGeom.setAttribute('position', new THREE.BufferAttribute(this.purpleNodePos, 3));
    this.purpleNodeGeom.setAttribute('color', new THREE.BufferAttribute(this.purpleNodeColor, 3));
    const purpleMat = new THREE.PointsMaterial({
      size: 0.28,
      map: makePurpleStarTexture(),
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });
    this.purpleNodePoints = new THREE.Points(this.purpleNodeGeom, purpleMat);
    this.orbGroup.add(this.purpleNodePoints);
  }

  private buildEdges(): void {
    this.edgeGeom.setAttribute('position', new THREE.BufferAttribute(this.edgePos, 3));
    this.edgeGeom.setAttribute('color', new THREE.BufferAttribute(this.edgeColor, 3));
    this.edgeGeom.setDrawRange(0, 0);

    const mat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.edgeLines = new THREE.LineSegments(this.edgeGeom, mat);
    this.orbGroup.add(this.edgeLines);
  }

  private buildHalo(): void {
    const spriteMat = new THREE.SpriteMaterial({
      map: makeHaloTexture(),
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.haloSprite = new THREE.Sprite(spriteMat);
    this.haloSprite.scale.set(9.5, 9.5, 1);
    this.scene.add(this.haloSprite);
  }

  private buildParticles(): void {
    for (let i = 0; i < PARTICLE_COUNT; i++) this.partLife[i] = 0;
    this.partGeom.setAttribute('position', new THREE.BufferAttribute(this.partPos, 3));
    this.partGeom.setDrawRange(0, 0);

    const sz = 64;
    const pc = document.createElement('canvas');
    pc.width = pc.height = sz;
    const pctx = pc.getContext('2d')!;
    const ph = sz / 2;
    const pg = pctx.createRadialGradient(ph, ph, 0, ph, ph, ph);
    pg.addColorStop(0, 'rgba(255,255,255,1)');
    pg.addColorStop(0.35, 'rgba(200,240,255,0.7)');
    pg.addColorStop(0.7, 'rgba(0,200,255,0.2)');
    pg.addColorStop(1, 'rgba(0,0,0,0)');
    pctx.fillStyle = pg;
    pctx.fillRect(0, 0, sz, sz);

    const mat = new THREE.PointsMaterial({
      map: new THREE.CanvasTexture(pc),
      size: 0.10,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });
    this.partSystem = new THREE.Points(this.partGeom, mat);
    this.scene.add(this.partSystem);
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  setState(state: AmaraState): void {
    this.state = state;
  }

  setOutputAnalyser(analyser: AnalyserNode): void {
    this.outAnalyser = analyser;
    this.outData = new Uint8Array(analyser.frequencyBinCount);
  }

  setMicAnalyser(analyser: AnalyserNode): void {
    this.micAnalyser = analyser;
    this.micData = new Uint8Array(analyser.frequencyBinCount);
  }

  triggerParticleBurst(): void {
    let spawned = 0;
    const burst = 80 + Math.floor(Math.random() * 40);
    for (let i = 0; i < PARTICLE_COUNT && spawned < burst; i++) {
      if (this.partLife[i] <= 0) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = SPHERE_R;
        const px = r * Math.sin(phi) * Math.cos(theta);
        const py = r * Math.sin(phi) * Math.sin(theta);
        const pz = r * Math.cos(phi);
        this.partPos[i * 3] = px;
        this.partPos[i * 3 + 1] = py;
        this.partPos[i * 3 + 2] = pz;
        const speed = 0.8 + Math.random() * 1.6;
        this.partVel[i * 3] = (px / r) * speed + (Math.random() - 0.5) * 0.3;
        this.partVel[i * 3 + 1] = (py / r) * speed + (Math.random() - 0.5) * 0.3;
        this.partVel[i * 3 + 2] = (pz / r) * speed + (Math.random() - 0.5) * 0.3;
        this.partLife[i] = 0.8 + Math.random() * 0.6;
        spawned++;
      }
    }
  }

  resize(width: number, height: number): void {
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  dispose(): void {
    this.nodeGeom.dispose();
    this.purpleNodeGeom.dispose();
    this.edgeGeom.dispose();
    this.partGeom.dispose();
    this.renderer.dispose();
  }

  // ---------------------------------------------------------------------------
  // Per-frame update
  // ---------------------------------------------------------------------------

  update(dt: number): void {
    const safeDt = Math.min(dt, 0.05);
    this.time += safeDt;

    this.sampleAudio();
    this.computeTargets();
    this.updateNodes();
    this.updateEdges();
    this.updateOrbRotation();
    this.updateHalo();
    this.updateParticles(safeDt);
  }

  render(): void {
    this.renderer.render(this.scene, this.camera);
  }

  // ---------------------------------------------------------------------------
  // Audio sampling
  // ---------------------------------------------------------------------------

  private sampleAudio(): void {
    if (this.outAnalyser) {
      this.outAnalyser.getByteFrequencyData(this.outData);
      const raw = bandAvg(this.outData, 0, 1);
      this.aLow = lerp(this.aLow, bandAvg(this.outData, 0, 0.12), 0.15);
      this.aMid = lerp(this.aMid, bandAvg(this.outData, 0.12, 0.5), 0.12);
      this.aHigh = lerp(this.aHigh, bandAvg(this.outData, 0.5, 1.0), 0.1);
      this.aOverall = lerp(this.aOverall, raw, 0.14);
    } else {
      this.aLow = lerp(this.aLow, 0, 0.08);
      this.aMid = lerp(this.aMid, 0, 0.08);
      this.aHigh = lerp(this.aHigh, 0, 0.08);
      this.aOverall = lerp(this.aOverall, 0, 0.08);
    }

    if (this.micAnalyser) {
      this.micAnalyser.getByteFrequencyData(this.micData);
      this.aMic = lerp(this.aMic, bandAvg(this.micData, 0, 0.5), 0.18);
    } else {
      this.aMic = lerp(this.aMic, 0, 0.1);
    }
  }

  // ---------------------------------------------------------------------------
  // State-driven target values
  // ---------------------------------------------------------------------------

  private computeTargets(): void {
    const t = this.time;
    const breathe = (Math.sin(t * 0.7) + 1) * 0.5;

    let tBright: number;
    let tConn: number;
    let tRot: number;
    let tHalo: number;

    switch (this.state) {
      case 'idle':
        tBright = 0.40 + breathe * 0.12;
        tConn   = 0.50 + breathe * 0.10;
        tRot    = 0.003 + breathe * 0.001;
        tHalo   = 0.90 + breathe * 0.06;
        break;

      case 'listening':
        tBright = 0.35 + this.aMic * 0.45 + (Math.sin(t * 1.8) + 1) * 0.05;
        tConn   = 0.45 + this.aMic * 0.30;
        tRot    = 0.002 + this.aMic * 0.004;
        tHalo   = 1.00 + this.aMic * 0.28;
        break;

      case 'thinking': {
        const pulse = (Math.sin(t * 4.8) + 1) * 0.5;
        tBright = 0.55 + pulse * 0.30;
        tConn   = 0.70 + pulse * 0.25;
        tRot    = 0.010 + pulse * 0.005;
        tHalo   = 1.10 + pulse * 0.15;
        break;
      }

      case 'speaking':
        tBright = 0.55 + this.aMid * 0.55 + this.aHigh * 0.20;
        tConn   = 0.60 + this.aOverall * 0.40;
        tRot    = 0.005 + this.aLow * 0.012;
        tHalo   = 1.05 + this.aOverall * 0.95;
        break;

      default:
        tBright = 0.45;
        tConn   = 0.55;
        tRot    = 0.003;
        tHalo   = 0.90;
    }

    const sm = 0.07;
    this.sBright    = lerp(this.sBright, tBright, sm);
    this.sConn      = lerp(this.sConn, tConn, sm * 1.2);
    this.sRotSpeed  = lerp(this.sRotSpeed, tRot, sm * 0.6);
    this.sHaloScale = lerp(this.sHaloScale, tHalo, sm * 0.8);
  }

  // ---------------------------------------------------------------------------
  // Node update
  // ---------------------------------------------------------------------------

  private updateNodes(): void {
    const t = this.time;
    let cyanIdx = 0;
    let purpleIdx = 0;

    for (let i = 0; i < NODE_COUNT; i++) {
      const n = this.nodeData[i];

      // Drift
      n.px = n.bx + Math.sin(t * n.spX + n.phX) * n.amp;
      n.py = n.by + Math.sin(t * n.spY + n.phY) * n.amp;
      n.pz = n.bz + Math.sin(t * n.spZ + n.phZ) * n.amp;

      // Clamp to sphere surface
      const len = Math.sqrt(n.px * n.px + n.py * n.py + n.pz * n.pz);
      if (len > SPHERE_R) {
        const inv = SPHERE_R / len;
        n.px *= inv; n.py *= inv; n.pz *= inv;
      }

      // Sparkle brightness
      const sparkle = (Math.sin(t * 1.8 + n.phX * 11) + 1) * 0.5;
      const audioBoost = this.state === 'speaking'
        ? this.aMid * 0.5 + this.aHigh * 0.3
        : this.state === 'listening'
          ? this.aMic * 0.3
          : this.state === 'thinking'
            ? (Math.sin(t * 5 + n.phZ * 3) + 1) * 0.25
            : 0;
      const b = clamp(this.sBright * n.bright + sparkle * 0.15 + audioBoost, 0.04, 1.0);
      n.bright = lerp(n.bright, b, 0.08 + audioBoost * 0.12);

      const [r, g, bl] = nodeRGB(n.ct, clamp(n.bright, 0, 1));

      if (n.ct === 1) {
        // Purple: goes to purple point cloud
        this.purpleNodePos[purpleIdx * 3] = n.px;
        this.purpleNodePos[purpleIdx * 3 + 1] = n.py;
        this.purpleNodePos[purpleIdx * 3 + 2] = n.pz;
        this.purpleNodeColor[purpleIdx * 3] = r;
        this.purpleNodeColor[purpleIdx * 3 + 1] = g;
        this.purpleNodeColor[purpleIdx * 3 + 2] = bl;
        purpleIdx++;
      } else {
        // Cyan / white-blue: cyan point cloud
        this.nodePos[cyanIdx * 3] = n.px;
        this.nodePos[cyanIdx * 3 + 1] = n.py;
        this.nodePos[cyanIdx * 3 + 2] = n.pz;
        this.nodeColor[cyanIdx * 3] = r;
        this.nodeColor[cyanIdx * 3 + 1] = g;
        this.nodeColor[cyanIdx * 3 + 2] = bl;
        cyanIdx++;
      }
    }

    this.nodeGeom.setDrawRange(0, cyanIdx);
    this.nodeGeom.attributes.position.needsUpdate = true;
    this.nodeGeom.attributes.color.needsUpdate = true;

    this.purpleNodeGeom.setDrawRange(0, purpleIdx);
    this.purpleNodeGeom.attributes.position.needsUpdate = true;
    this.purpleNodeGeom.attributes.color.needsUpdate = true;
  }

  // ---------------------------------------------------------------------------
  // Edge update
  // ---------------------------------------------------------------------------

  private updateEdges(): void {
    const maxE = Math.min(this.edgePairs.length, Math.floor(this.edgePairs.length * clamp(this.sConn, 0.1, 1.0)));

    for (let idx = 0; idx < maxE; idx++) {
      const [ai, bi] = this.edgePairs[idx];
      const na = this.nodeData[ai];
      const nb = this.nodeData[bi];
      const pulse = 0.52 + 0.48 * Math.sin(this.time * 3.0 + idx * 0.35);
      const cA = clamp(this.sConn * na.bright * 0.92 * pulse, 0, 1);
      const cB = clamp(this.sConn * nb.bright * 0.92 * pulse, 0, 1);

      const base = idx * 6;
      this.edgePos[base]     = na.px; this.edgePos[base + 1] = na.py; this.edgePos[base + 2] = na.pz;
      this.edgePos[base + 3] = nb.px; this.edgePos[base + 4] = nb.py; this.edgePos[base + 5] = nb.pz;

      const [rA, gA, bA] = nodeRGB(na.ct, cA);
      this.edgeColor[base]     = rA; this.edgeColor[base + 1] = gA; this.edgeColor[base + 2] = bA;
      const [rB, gB, bB] = nodeRGB(nb.ct, cB);
      this.edgeColor[base + 3] = rB; this.edgeColor[base + 4] = gB; this.edgeColor[base + 5] = bB;
    }

    this.edgeGeom.attributes.position.needsUpdate = true;
    this.edgeGeom.attributes.color.needsUpdate = true;
    this.edgeGeom.setDrawRange(0, maxE * 2);
  }

  // ---------------------------------------------------------------------------
  // Rotation update
  // ---------------------------------------------------------------------------

  private updateOrbRotation(): void {
    this.orbGroup.rotation.y += this.sRotSpeed * (1 + this.aLow * 1.2);
    this.orbGroup.rotation.x += this.sRotSpeed * 0.18;
  }

  // ---------------------------------------------------------------------------
  // Halo update
  // ---------------------------------------------------------------------------

  private updateHalo(): void {
    const scale = this.sHaloScale * 9.5;
    this.haloSprite.scale.set(scale, scale, 1);
  }

  // ---------------------------------------------------------------------------
  // Particle burst update
  // ---------------------------------------------------------------------------

  private updateParticles(dt: number): void {
    let activeCount = 0;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      if (this.partLife[i] <= 0) continue;
      this.partLife[i] -= dt;

      if (this.partLife[i] <= 0) {
        this.partPos[i * 3] = 999;
        this.partPos[i * 3 + 1] = 999;
        this.partPos[i * 3 + 2] = 999;
        continue;
      }

      const drag = Math.pow(0.88, dt * 60);
      this.partVel[i * 3] *= drag;
      this.partVel[i * 3 + 1] *= drag;
      this.partVel[i * 3 + 2] *= drag;

      this.partPos[i * 3] += this.partVel[i * 3] * dt;
      this.partPos[i * 3 + 1] += this.partVel[i * 3 + 1] * dt;
      this.partPos[i * 3 + 2] += this.partVel[i * 3 + 2] * dt;

      activeCount++;
    }

    this.partGeom.attributes.position.needsUpdate = true;
    this.partGeom.setDrawRange(0, activeCount > 0 ? PARTICLE_COUNT : 0);
  }
}
