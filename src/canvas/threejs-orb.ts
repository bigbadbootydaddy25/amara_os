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

// ---------------------------------------------------------------------------
// Texture factories
// ---------------------------------------------------------------------------

function makeGlowTexture(): THREE.CanvasTexture {
  const size = 128;
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const ctx = c.getContext('2d')!;
  const h = size / 2;
  const g = ctx.createRadialGradient(h, h, 0, h, h, h);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.18, 'rgba(200,245,255,0.9)');
  g.addColorStop(0.42, 'rgba(0,212,255,0.5)');
  g.addColorStop(0.72, 'rgba(0,100,200,0.15)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
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
  g.addColorStop(0.40, 'rgba(0,0,0,0)');
  g.addColorStop(0.58, 'rgba(0,212,255,0.06)');
  g.addColorStop(0.70, 'rgba(0,180,240,0.14)');
  g.addColorStop(0.82, 'rgba(0,80,160,0.10)');
  g.addColorStop(0.92, 'rgba(0,20,60,0.04)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SPHERE_R = 1.8;
const NODE_COUNT = 165;
const SURFACE_NODES = 58;
const MAX_CONN_DIST = 0.84;
const MAX_EDGES = 500;
const PARTICLE_COUNT = 240;

// ---------------------------------------------------------------------------
// Per-node animation data (kept in JS, not GPU)
// ---------------------------------------------------------------------------

interface NodeData {
  base: THREE.Vector3;
  phase: THREE.Vector3;  // noise phase per axis
  speed: THREE.Vector3;  // noise speed per axis
  amp: number;           // drift amplitude
  bright: number;        // current brightness 0-1
  targetBright: number;
  baseSize: number;      // sprite size in world units
  cur: THREE.Vector3;    // current position (updated per frame)
}

// ---------------------------------------------------------------------------
// Main renderer
// ---------------------------------------------------------------------------

export class ThreeOrbRenderer {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;

  // Groups
  private orbGroup: THREE.Group;    // rotates: wireframe + nodes + edges
  private ringGroup: THREE.Group;   // orbits independently

  // Node point cloud
  private nodePos: Float32Array;
  private nodeColor: Float32Array;
  private nodeGeom: THREE.BufferGeometry;
  private nodePoints!: THREE.Points;
  private nodes: NodeData[] = [];

  // Connection line segments
  private edgePos: Float32Array;
  private edgeColor: Float32Array;
  private edgeGeom: THREE.BufferGeometry;
  private edgeLines!: THREE.LineSegments;

  // Wireframe cage
  private wireMesh!: THREE.LineSegments;

  // Outer ring
  private ringMesh!: THREE.Mesh;

  // Halo sprite
  private haloSprite!: THREE.Sprite;

  // Particle burst
  private partPos: Float32Array;
  private partVel: Float32Array;
  private partLife: Float32Array;
  private partGeom: THREE.BufferGeometry;
  private partSystem!: THREE.Points;

  // Audio
  private outAnalyser: AnalyserNode | null = null;
  private micAnalyser: AnalyserNode | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private outData: any = new Uint8Array(256);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private micData: any = new Uint8Array(256);

  // Smooth audio levels
  private aLow = 0;
  private aMid = 0;
  private aHigh = 0;
  private aOverall = 0;
  private aMic = 0;

  // State
  private state: AmaraState = 'idle';
  private time = 0;

  // Smoothed display values
  private sBright = 0.3;
  private sConnDensity = 0.35;
  private sRotSpeed = 0.004;
  private sRingOpacity = 0.2;
  private sHaloScale = 1.0;

  constructor(canvas: HTMLCanvasElement, width: number, height: number) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 1);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(56, width / height, 0.01, 100);
    this.camera.position.z = 4.8;

    this.orbGroup = new THREE.Group();
    this.ringGroup = new THREE.Group();
    this.scene.add(this.orbGroup);
    this.scene.add(this.ringGroup);

    this.nodePos = new Float32Array(NODE_COUNT * 3);
    this.nodeColor = new Float32Array(NODE_COUNT * 3);
    this.edgePos = new Float32Array(MAX_EDGES * 6);
    this.edgeColor = new Float32Array(MAX_EDGES * 6);
    this.partPos = new Float32Array(PARTICLE_COUNT * 3);
    this.partVel = new Float32Array(PARTICLE_COUNT * 3);
    this.partLife = new Float32Array(PARTICLE_COUNT);

    this.nodeGeom = new THREE.BufferGeometry();
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
    this.buildWireframe();
    this.buildRing();
    this.buildHalo();
    this.buildParticles();
  }

  private buildNodes(): void {
    const glowTex = makeGlowTexture();

    // Surface nodes: fibonacci sphere distribution
    for (let i = 0; i < SURFACE_NODES; i++) {
      const goldenAngle = Math.PI * (Math.sqrt(5) - 1);
      const y = 1 - (i / (SURFACE_NODES - 1)) * 2;
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = goldenAngle * i;
      const pos = new THREE.Vector3(
        Math.cos(theta) * r * SPHERE_R,
        y * SPHERE_R,
        Math.sin(theta) * r * SPHERE_R,
      );
      this.nodes.push({
        base: pos.clone(),
        phase: new THREE.Vector3(
          Math.random() * Math.PI * 2,
          Math.random() * Math.PI * 2,
          Math.random() * Math.PI * 2,
        ),
        speed: new THREE.Vector3(
          0.14 + Math.random() * 0.18,
          0.11 + Math.random() * 0.16,
          0.09 + Math.random() * 0.20,
        ),
        amp: 0.035 + Math.random() * 0.065,
        bright: 0.4 + Math.random() * 0.6,
        targetBright: 0.5,
        baseSize: 7 + Math.random() * 14,
        cur: pos.clone(),
      });
    }

    // Interior nodes: weighted toward outer shell
    const interiorCount = NODE_COUNT - SURFACE_NODES;
    for (let i = 0; i < interiorCount; i++) {
      const u = Math.random();
      const dist = SPHERE_R * Math.pow(u, 0.45) * 0.96;
      const theta2 = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const pos = new THREE.Vector3(
        dist * Math.sin(phi) * Math.cos(theta2),
        dist * Math.sin(phi) * Math.sin(theta2),
        dist * Math.cos(phi),
      );
      this.nodes.push({
        base: pos.clone(),
        phase: new THREE.Vector3(
          Math.random() * Math.PI * 2,
          Math.random() * Math.PI * 2,
          Math.random() * Math.PI * 2,
        ),
        speed: new THREE.Vector3(
          0.07 + Math.random() * 0.22,
          0.05 + Math.random() * 0.18,
          0.08 + Math.random() * 0.21,
        ),
        amp: 0.07 + Math.random() * 0.18,
        bright: 0.15 + Math.random() * 0.55,
        targetBright: 0.25,
        baseSize: 3 + Math.random() * 9,
        cur: pos.clone(),
      });
    }

    this.nodeGeom.setAttribute('position', new THREE.BufferAttribute(this.nodePos, 3));
    this.nodeGeom.setAttribute('color', new THREE.BufferAttribute(this.nodeColor, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.22,
      map: glowTex,
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });

    this.nodePoints = new THREE.Points(this.nodeGeom, mat);
    this.orbGroup.add(this.nodePoints);
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

  private buildWireframe(): void {
    const geom = new THREE.IcosahedronGeometry(SPHERE_R * 1.0, 2);
    const wire = new THREE.WireframeGeometry(geom);
    const mat = new THREE.LineBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.06,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.wireMesh = new THREE.LineSegments(wire, mat);
    this.orbGroup.add(this.wireMesh);
    geom.dispose();
  }

  private buildRing(): void {
    const geom = new THREE.TorusGeometry(SPHERE_R * 1.22, 0.013, 8, 120);
    const mat = new THREE.MeshBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.22,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    this.ringMesh = new THREE.Mesh(geom, mat);
    this.ringMesh.rotation.x = Math.PI * 0.12;

    // Second ring at slight angle for more visual interest
    const geom2 = new THREE.TorusGeometry(SPHERE_R * 1.24, 0.008, 8, 120);
    const mat2 = new THREE.MeshBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.12,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    const ring2 = new THREE.Mesh(geom2, mat2);
    ring2.rotation.x = Math.PI * 0.35;
    ring2.rotation.y = Math.PI * 0.15;

    this.ringGroup.add(this.ringMesh);
    this.ringGroup.add(ring2);
  }

  private buildHalo(): void {
    const haloTex = makeHaloTexture();
    const spriteMat = new THREE.SpriteMaterial({
      map: haloTex,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.haloSprite = new THREE.Sprite(spriteMat);
    this.haloSprite.scale.set(7.2, 7.2, 1);
    this.scene.add(this.haloSprite);
  }

  private buildParticles(): void {
    for (let i = 0; i < PARTICLE_COUNT; i++) this.partLife[i] = 0;
    this.partGeom.setAttribute('position', new THREE.BufferAttribute(this.partPos, 3));
    this.partGeom.setDrawRange(0, 0);

    const mat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.04,
      transparent: true,
      opacity: 0.85,
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
        // Spawn from random point on sphere surface
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = SPHERE_R;
        const px = r * Math.sin(phi) * Math.cos(theta);
        const py = r * Math.sin(phi) * Math.sin(theta);
        const pz = r * Math.cos(phi);
        this.partPos[i * 3] = px;
        this.partPos[i * 3 + 1] = py;
        this.partPos[i * 3 + 2] = pz;
        // Velocity: outward + slight random
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
    this.updateWireframe();
    this.updateRing(safeDt);
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
    let tRing: number;
    let tHalo: number;

    switch (this.state) {
      case 'idle':
        tBright = 0.22 + breathe * 0.10;
        tConn = 0.28 + breathe * 0.08;
        tRot = 0.003 + breathe * 0.001;
        tRing = 0.14 + breathe * 0.05;
        tHalo = 0.88 + breathe * 0.06;
        break;

      case 'listening':
        tBright = 0.18 + this.aMic * 0.38 + (Math.sin(t * 1.8) + 1) * 0.04;
        tConn = 0.20 + this.aMic * 0.25;
        tRot = 0.002 + this.aMic * 0.003;
        tRing = 0.12 + this.aMic * 0.20 + Math.sin(t * 2.2) * 0.04;
        tHalo = 0.90 + this.aMic * 0.22;
        break;

      case 'thinking':
        {
          const pulse = (Math.sin(t * 4.8) + 1) * 0.5;
          tBright = 0.38 + pulse * 0.28;
          tConn = 0.55 + pulse * 0.30;
          tRot = 0.009 + pulse * 0.005;
          tRing = 0.38 + pulse * 0.22;
          tHalo = 1.05 + pulse * 0.15;
        }
        break;

      case 'speaking':
        tBright = 0.42 + this.aMid * 0.52 + this.aHigh * 0.18;
        tConn = 0.45 + this.aOverall * 0.55;
        tRot = 0.005 + this.aLow * 0.012;
        tRing = 0.40 + this.aOverall * 0.58;
        tHalo = 1.0 + this.aOverall * 0.95;
        break;

      default:
        tBright = 0.25;
        tConn = 0.3;
        tRot = 0.003;
        tRing = 0.15;
        tHalo = 0.9;
    }

    const smooth = 0.07;
    this.sBright = lerp(this.sBright, tBright, smooth);
    this.sConnDensity = lerp(this.sConnDensity, tConn, smooth * 1.2);
    this.sRotSpeed = lerp(this.sRotSpeed, tRot, smooth * 0.6);
    this.sRingOpacity = lerp(this.sRingOpacity, tRing, smooth);
    this.sHaloScale = lerp(this.sHaloScale, tHalo, smooth * 0.8);
  }

  // ---------------------------------------------------------------------------
  // Node update
  // ---------------------------------------------------------------------------

  private updateNodes(): void {
    const t = this.time;

    for (let i = 0; i < NODE_COUNT; i++) {
      const n = this.nodes[i];

      // Drift position
      const dx = Math.sin(t * n.speed.x + n.phase.x) * n.amp;
      const dy = Math.sin(t * n.speed.y + n.phase.y) * n.amp;
      const dz = Math.sin(t * n.speed.z + n.phase.z) * n.amp;
      n.cur.set(n.base.x + dx, n.base.y + dy, n.base.z + dz);

      // Clamp to sphere
      const len = n.cur.length();
      if (len > SPHERE_R) n.cur.multiplyScalar(SPHERE_R / len);

      // Write position
      this.nodePos[i * 3] = n.cur.x;
      this.nodePos[i * 3 + 1] = n.cur.y;
      this.nodePos[i * 3 + 2] = n.cur.z;

      // Brightness: base + per-node sparkle + audio
      const sparkle = (Math.sin(t * 1.8 + n.phase.x * 11) + 1) * 0.5;
      const audioBoost = this.state === 'speaking'
        ? this.aMid * 0.5 + this.aHigh * 0.3
        : this.state === 'listening'
          ? this.aMic * 0.3
          : this.state === 'thinking'
            ? (Math.sin(t * 5 + n.phase.z * 3) + 1) * 0.25
            : 0;
      n.targetBright = clamp(this.sBright * n.bright + sparkle * 0.12 + audioBoost, 0.04, 1.0);
      n.bright = lerp(n.bright, n.targetBright, 0.08 + audioBoost * 0.12);

      // Ice blue color: rgb(0, 212, 255) / 255 = (0, 0.831, 1.0)
      const b = n.bright;
      this.nodeColor[i * 3] = 0;
      this.nodeColor[i * 3 + 1] = 0.831 * b;
      this.nodeColor[i * 3 + 2] = b;
    }

    this.nodeGeom.attributes.position.needsUpdate = true;
    this.nodeGeom.attributes.color.needsUpdate = true;
  }

  // ---------------------------------------------------------------------------
  // Edge update
  // ---------------------------------------------------------------------------

  private updateEdges(): void {
    const maxEdgesThisFrame = Math.floor(MAX_EDGES * clamp(this.sConnDensity, 0.1, 1.0));
    let idx = 0;

    for (let a = 0; a < NODE_COUNT && idx < maxEdgesThisFrame; a++) {
      const na = this.nodes[a];
      for (let b = a + 1; b < NODE_COUNT && idx < maxEdgesThisFrame; b++) {
        const nb = this.nodes[b];
        const dist = na.cur.distanceTo(nb.cur);
        if (dist >= MAX_CONN_DIST) continue;

        const fade = 1 - dist / MAX_CONN_DIST;
        const edgeBright = fade * fade * this.sConnDensity * (na.bright + nb.bright) * 0.5;
        const c = clamp(edgeBright * 0.55, 0, 1);

        const base = idx * 6;
        this.edgePos[base] = na.cur.x;
        this.edgePos[base + 1] = na.cur.y;
        this.edgePos[base + 2] = na.cur.z;
        this.edgePos[base + 3] = nb.cur.x;
        this.edgePos[base + 4] = nb.cur.y;
        this.edgePos[base + 5] = nb.cur.z;

        // Ice blue with computed brightness
        this.edgeColor[base] = 0;
        this.edgeColor[base + 1] = 0.831 * c;
        this.edgeColor[base + 2] = c;
        this.edgeColor[base + 3] = 0;
        this.edgeColor[base + 4] = 0.831 * c;
        this.edgeColor[base + 5] = c;
        idx++;
      }
    }

    this.edgeGeom.attributes.position.needsUpdate = true;
    this.edgeGeom.attributes.color.needsUpdate = true;
    this.edgeGeom.setDrawRange(0, idx * 2);
  }

  // ---------------------------------------------------------------------------
  // Wireframe update
  // ---------------------------------------------------------------------------

  private updateWireframe(): void {
    const mat = this.wireMesh.material as THREE.LineBasicMaterial;
    const breathe = (Math.sin(this.time * 0.6) + 1) * 0.5;
    const baseOpacity = this.state === 'idle' ? 0.055 : this.state === 'listening' ? 0.045 : 0.08;
    const audioBoost = this.state === 'speaking' ? this.aMid * 0.06 : 0;
    mat.opacity = clamp(baseOpacity + breathe * 0.02 + audioBoost, 0.03, 0.18);

    // Orb group rotation
    this.orbGroup.rotation.y += this.sRotSpeed * (1 + this.aLow * 1.2);
    this.orbGroup.rotation.x += this.sRotSpeed * 0.18;
  }

  // ---------------------------------------------------------------------------
  // Ring update
  // ---------------------------------------------------------------------------

  private updateRing(dt: number): void {
    this.ringGroup.rotation.y += dt * 0.28;

    // Scale ring on audio peaks
    const peakBoost = this.state === 'speaking' ? 1 + this.aOverall * 0.32 : 1.0;
    this.ringGroup.scale.setScalar(peakBoost);

    // Ripple/pulse ring opacity
    const t = this.time;
    const pulse = this.state === 'speaking'
      ? this.sRingOpacity * (0.9 + Math.sin(t * 8 + this.aHigh * 12) * 0.1)
      : this.sRingOpacity;

    this.ringGroup.children.forEach((child, i) => {
      const mesh = child as THREE.Mesh;
      const mat = mesh.material as THREE.MeshBasicMaterial;
      mat.opacity = clamp(pulse * (i === 0 ? 1.0 : 0.55), 0, 0.75);
    });
  }

  // ---------------------------------------------------------------------------
  // Halo update
  // ---------------------------------------------------------------------------

  private updateHalo(): void {
    const scale = this.sHaloScale * 7.2;
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
        // Deactivate: push far away
        this.partPos[i * 3] = 999;
        this.partPos[i * 3 + 1] = 999;
        this.partPos[i * 3 + 2] = 999;
        continue;
      }

      // Move outward with deceleration
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
    const mat = this.partSystem.material as THREE.PointsMaterial;
    mat.opacity = clamp(0.85, 0, 1);
  }
}
