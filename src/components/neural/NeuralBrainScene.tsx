'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useNeuralStore, AGENT_CONFIG, type AgentState } from '@/stores/neural-store';

// ── constants ─────────────────────────────────────────────────────────────────

const ORBIT_R  = 5.2;
const TILT     = 0.34;
const STREAM_N = 40;

const INTENSITY: Record<AgentState, number> = {
  idle: 0.18, searching: 0.55, processing: 0.80, verified: 1.05, nuclear: 1.40,
};
const PULSE_HZ: Record<AgentState, number> = {
  idle: 0.6, searching: 2.0, processing: 3.5, verified: 1.0, nuclear: 9.0,
};
const COLOR_OVERRIDE: Partial<Record<AgentState, string>> = {
  verified: '#00ff88',
  nuclear:  '#ff5500',
};

// ── shaders ───────────────────────────────────────────────────────────────────

const VERT = /* glsl */`
  varying vec3 vN; varying vec3 vV;
  void main(){
    vN=normalize(normalMatrix*normal);
    vec4 mv=modelViewMatrix*vec4(position,1.);
    vV=normalize(-mv.xyz);
    gl_Position=projectionMatrix*mv;
  }`;

const FRAG = /* glsl */`
  uniform float uT; uniform float uNuc; uniform float uFreq;
  varying vec3 vN; varying vec3 vV;
  void main(){
    float f=pow(1.-clamp(dot(vN,vV),0.,1.),2.1);
    vec3 ca=mix(vec3(.1,.7,1.),vec3(.5,.95,1.),f);
    vec3 na=mix(vec3(.9,.2,.0),vec3(1.,.65,.1),f);
    vec3 col=mix(ca,na,uNuc);
    float osc=.8+.2*sin(uT*uFreq*6.283);
    float a=(.3+.7*f)*osc;
    gl_FragColor=vec4(col*(1.6+f*2.),a);
  }`;

// ── glow sprite factory ───────────────────────────────────────────────────────

function glowSprite(hexColor: string, size: number, alpha = 1.0): THREE.Sprite {
  const SZ = 256;
  const cv = document.createElement('canvas');
  cv.width = cv.height = SZ;
  const ctx = cv.getContext('2d')!;
  const r = SZ / 2;
  const g = ctx.createRadialGradient(r, r, 0, r, r, r);
  const c = new THREE.Color(hexColor);
  const hex6 = `#${c.getHexString()}`;
  g.addColorStop(0.00, hex6 + 'ff');
  g.addColorStop(0.25, hex6 + 'cc');
  g.addColorStop(0.60, hex6 + '44');
  g.addColorStop(1.00, hex6 + '00');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, SZ, SZ);
  const mat = new THREE.SpriteMaterial({
    map: new THREE.CanvasTexture(cv),
    transparent: true, opacity: alpha,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const s = new THREE.Sprite(mat);
  s.scale.setScalar(size);
  return s;
}

// ── ring builder ──────────────────────────────────────────────────────────────

function makeRing(r: number, thickness: number, color: number, euler: THREE.Euler) {
  const m = new THREE.Mesh(
    new THREE.TorusGeometry(r, thickness, 12, 128),
    new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.65,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }),
  );
  m.rotation.copy(euler);
  return m;
}

// ── star layer ────────────────────────────────────────────────────────────────

function starLayer(n: number, rMin: number, rMax: number, sz: number, op: number) {
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    const r  = rMin + Math.random() * (rMax - rMin);
    pos[i*3]   = r * Math.sin(ph) * Math.cos(th);
    pos[i*3+1] = r * Math.sin(ph) * Math.sin(th);
    pos[i*3+2] = r * Math.cos(ph);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  return new THREE.Points(geo, new THREE.PointsMaterial({
    color: 0xc8dfff, size: sz, transparent: true, opacity: op,
    blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
  }));
}

// ── main scene builder ────────────────────────────────────────────────────────

function build() {
  const scene = new THREE.Scene();

  // stars
  const s0 = starLayer(1500, 60, 100, 0.08, 0.55);
  const s1 = starLayer(400,  50,  80, 0.20, 0.30);
  const s2 = starLayer(100,  40,  65, 0.45, 0.18);
  scene.add(s0, s1, s2);

  // ── AMARA core ───────────────────────────────────────────────────────────
  const uniforms = { uT: {value:0}, uNuc: {value:0}, uFreq: {value:1} };
  const coreMesh = new THREE.Mesh(
    new THREE.SphereGeometry(1.0, 64, 64),
    new THREE.ShaderMaterial({
      uniforms, vertexShader: VERT, fragmentShader: FRAG,
      transparent: true, depthWrite: false,
    }),
  );

  // glow layers around core (sprites — radial canvas gradient)
  const coreGlowLg = glowSprite('#0055ff', 9.0, 0.35);
  const coreGlowMd = glowSprite('#22aaff', 4.5, 0.55);
  const coreGlowSm = glowSprite('#88ddff', 1.8, 0.80);

  const coreGlowMats = [
    coreGlowLg.material as THREE.SpriteMaterial,
    coreGlowMd.material as THREE.SpriteMaterial,
    coreGlowSm.material as THREE.SpriteMaterial,
  ];

  // orbital rings
  const rings = [
    makeRing(2.05, 0.018, 0x00aaff, new THREE.Euler(Math.PI/2, 0, 0)),
    makeRing(2.40, 0.013, 0x0066dd, new THREE.Euler(0, 0, Math.PI/3.2)),
    makeRing(2.75, 0.009, 0x0033aa, new THREE.Euler(Math.PI/5, Math.PI/4.5, 0)),
  ];
  const ringSpeeds = [0.42, 0.28, 0.17];

  const coreLight = new THREE.PointLight(0x0088ff, 5, 16);

  const coreGroup = new THREE.Group();
  coreGroup.add(coreMesh, coreGlowLg, coreGlowMd, coreGlowSm, coreLight, ...rings);
  scene.add(coreGroup);

  // ── agent orbs ───────────────────────────────────────────────────────────
  const orbGroup = new THREE.Group();
  orbGroup.rotation.x = TILT;
  scene.add(orbGroup);

  // per-agent references
  type OrbRefs = {
    glowLg: THREE.Sprite; glowSm: THREE.Sprite;
    dot: THREE.Mesh; mesh: THREE.Mesh;
  };
  const orbRefs: OrbRefs[] = [];

  // raycasting targets (invisible, larger clickable sphere)
  const hitTargets: THREE.Mesh[] = [];

  AGENT_CONFIG.forEach((cfg, i) => {
    const angle = (i / AGENT_CONFIG.length) * Math.PI * 2;
    const x = Math.cos(angle) * ORBIT_R;
    const z = Math.sin(angle) * ORBIT_R;

    // large soft glow sprite
    const glowLg = glowSprite(cfg.color, 2.8, 0.22);
    glowLg.position.set(x, 0, z);

    // tight bright glow sprite
    const glowSm = glowSprite(cfg.color, 1.0, 0.60);
    glowSm.position.set(x, 0, z);

    // visible mesh (small bright sphere)
    const mat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(cfg.color),
      transparent: true, opacity: 0.90,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.18, 20, 20), mat);
    mesh.position.set(x, 0, z);
    mesh.userData = { agentIndex: i };

    // white inner dot
    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(0.07, 12, 12),
      new THREE.MeshBasicMaterial({
        color: 0xffffff, transparent: true, opacity: 0.8,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }),
    );
    dot.position.set(x, 0, z);

    // invisible click target (larger)
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(0.55, 8, 8),
      new THREE.MeshBasicMaterial({ visible: false }),
    );
    hit.position.set(x, 0, z);
    hit.userData = { agentIndex: i };
    hitTargets.push(hit);

    orbRefs.push({ glowLg, glowSm, dot, mesh });
    orbGroup.add(glowLg, glowSm, mesh, dot, hit);
  });

  // ── beams ────────────────────────────────────────────────────────────────
  const beamGroup = new THREE.Group();
  scene.add(beamGroup);

  const beamGeos:  THREE.BufferGeometry[]    = [];
  const beamMats:  THREE.LineBasicMaterial[]  = [];
  const beamGlows: THREE.LineBasicMaterial[]  = [];
  const beads:     THREE.Sprite[]             = [];

  AGENT_CONFIG.forEach((cfg) => {
    const pa = new Float32Array(6);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pa, 3));
    beamGeos.push(geo);

    const main = new THREE.LineBasicMaterial({
      color: new THREE.Color(cfg.color), transparent: true, opacity: 0.15,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const glow = new THREE.LineBasicMaterial({
      color: new THREE.Color(cfg.color), transparent: true, opacity: 0.06,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    beamMats.push(main);
    beamGlows.push(glow);

    beamGroup.add(new THREE.Line(geo, main), new THREE.Line(geo, glow));

    // pulse bead as glow sprite (starts invisible)
    const bead = glowSprite(cfg.color, 0.6, 0);
    beads.push(bead);
    beamGroup.add(bead);
  });

  // ── data streams ─────────────────────────────────────────────────────────
  const streamGroup = new THREE.Group();
  scene.add(streamGroup);

  const streamGeos: THREE.BufferGeometry[]  = [];
  const streamMats: THREE.PointsMaterial[]  = [];

  AGENT_CONFIG.forEach((cfg) => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(STREAM_N*3), 3));
    const mat = new THREE.PointsMaterial({
      color: new THREE.Color(cfg.color), size: 0.07,
      transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
    });
    streamGeos.push(geo);
    streamMats.push(mat);
    streamGroup.add(new THREE.Points(geo, mat));
  });

  return {
    scene, stars: [s0, s1, s2],
    uniforms, coreGlowMats, coreLight,
    rings, ringSpeeds,
    orbGroup, orbRefs, hitTargets,
    beamGeos, beamMats, beamGlows, beads,
    streamGeos, streamMats,
  };
}

// ── component ─────────────────────────────────────────────────────────────────

export function NeuralBrainScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const W = window.innerWidth, H = window.innerHeight;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x010208, 1);

    const camera = new THREE.PerspectiveCamera(52, W / H, 0.1, 300);
    camera.position.set(0, 3, 12);
    camera.lookAt(0, 0, 0);

    const refs = build();
    const {
      scene, stars, uniforms, coreGlowMats, coreLight,
      rings, ringSpeeds, orbGroup, orbRefs, hitTargets,
      beamGeos, beamMats, beamGlows, beads,
      streamGeos, streamMats,
    } = refs;

    // staggered offsets for stream particles
    const offsets = AGENT_CONFIG.map(() =>
      Array.from({ length: STREAM_N }, (_, j) => j / STREAM_N),
    );

    // ── events ────────────────────────────────────────────────────────────
    const ray   = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onClick = (e: MouseEvent) => {
      mouse.x =  (e.clientX / window.innerWidth)  * 2 - 1;
      mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
      ray.setFromCamera(mouse, camera);
      const hits = ray.intersectObjects(hitTargets);
      if (hits.length) {
        const idx = (hits[0].object as THREE.Mesh).userData.agentIndex as number;
        useNeuralStore.getState().selectAgent(AGENT_CONFIG[idx].id);
      } else {
        useNeuralStore.getState().selectAgent(null);
      }
    };
    canvas.addEventListener('click', onClick);

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', onResize);

    // ── animation loop ─────────────────────────────────────────────────────
    const O = new THREE.Vector3();
    const eio = (t: number) => t < .5 ? 2*t*t : -1+(4-2*t)*t;

    let raf = 0, t = 0, prev = performance.now();

    const tick = (ts: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min((ts - prev) / 1000, 0.05);
      prev = ts;
      t += dt;

      const store   = useNeuralStore.getState();
      const agents  = store.agents;
      const nuclear = store.nuclearAgentId !== null;
      const nv      = uniforms.uNuc.value;

      // ── AMARA core ──────────────────────────────────────────────────────
      uniforms.uT.value    = t;
      uniforms.uNuc.value += ((nuclear ? 1 : 0) - nv) * dt * 4;
      uniforms.uFreq.value = nuclear ? 8 : 1;

      const coreCol = nuclear ? '#ff4400' : '#0066ff';
      coreGlowMats[0].color.set(nuclear ? '#550000' : '#0033aa');
      coreGlowMats[0].opacity = 0.30 + nv * 0.20;
      coreGlowMats[1].color.set(nuclear ? '#ff2200' : '#0066ff');
      coreGlowMats[1].opacity = 0.50 + nv * 0.15;
      coreGlowMats[2].color.set(nuclear ? '#ffaa00' : '#88ddff');
      coreLight.color.set(coreCol);
      coreLight.intensity = nuclear ? 7 : 5;

      const rMult = nuclear ? 3.2 : 1;
      rings[0].rotation.y += dt * ringSpeeds[0] * rMult;
      rings[1].rotation.z += dt * ringSpeeds[1] * rMult;
      rings[2].rotation.x += dt * ringSpeeds[2] * rMult;

      // ── orbital ring rotation ────────────────────────────────────────────
      orbGroup.rotation.y += dt * 0.06;
      orbGroup.updateMatrixWorld(true);

      // ── star slow drift ──────────────────────────────────────────────────
      stars[0].rotation.y += dt * 0.005;
      stars[1].rotation.y -= dt * 0.003;

      // ── per-agent ────────────────────────────────────────────────────────
      agents.forEach((agent, i) => {
        const colStr  = COLOR_OVERRIDE[agent.state] ?? agent.color;
        const col     = new THREE.Color(colStr);
        const intens  = INTENSITY[agent.state];
        const hz      = PULSE_HZ[agent.state];
        const pulse   = 0.50 + 0.50 * Math.sin(t * hz * Math.PI * 2);
        const active  = agent.state !== 'idle';

        const { glowLg, glowSm, mesh, dot } = orbRefs[i];

        // glow sprites
        const lgMat = glowLg.material as THREE.SpriteMaterial;
        lgMat.color.copy(col);
        lgMat.opacity = intens * 0.32 * pulse;
        const smMat = glowSm.material as THREE.SpriteMaterial;
        smMat.color.copy(col);
        smMat.opacity = intens * 0.70 * pulse;

        // sphere mesh
        (mesh.material as THREE.MeshBasicMaterial).color.copy(col);
        (mesh.material as THREE.MeshBasicMaterial).opacity = intens * pulse;

        // inner dot
        (dot.material as THREE.MeshBasicMaterial).opacity = intens * 0.9 * pulse;

        // world position
        const wp = new THREE.Vector3();
        mesh.getWorldPosition(wp);

        // ── beam ────────────────────────────────────────────────────────────
        const pa = beamGeos[i].attributes.position.array as Float32Array;
        pa[3] = wp.x; pa[4] = wp.y; pa[5] = wp.z;
        beamGeos[i].attributes.position.needsUpdate = true;

        const beamOp = active ? intens * 0.55 * pulse : 0.10;
        beamMats[i].color.copy(col);
        beamMats[i].opacity = beamOp;
        beamGlows[i].color.copy(col);
        beamGlows[i].opacity = beamOp * 0.35;

        // ── pulse bead ───────────────────────────────────────────────────────
        const beadMat = beads[i].material as THREE.SpriteMaterial;
        if (active && agent.state !== 'verified') {
          const bt = eio((t * hz * 0.20) % 1);
          beads[i].position.lerpVectors(O, wp, bt);
          beadMat.color.copy(col);
          beadMat.opacity = 0.85 * pulse;
        } else {
          beadMat.opacity = 0;
        }

        // ── data streams ─────────────────────────────────────────────────────
        const streaming = agent.state === 'processing' || agent.state === 'nuclear';
        streamMats[i].color.copy(col);
        streamMats[i].opacity = streaming ? intens * 0.80 : 0;
        if (streaming) {
          const spa = streamGeos[i].attributes.position.array as Float32Array;
          for (let p = 0; p < STREAM_N; p++) {
            const st = eio(((t * 0.36 + offsets[i][p]) % 1));
            spa[p*3]   = wp.x * (1 - st);
            spa[p*3+1] = wp.y * (1 - st);
            spa[p*3+2] = wp.z * (1 - st);
          }
          streamGeos[i].attributes.position.needsUpdate = true;
        }
      });

      // ── camera drift ─────────────────────────────────────────────────────
      camera.position.x = Math.sin(t * 0.17) * 0.65;
      camera.position.y = 3.0 + Math.sin(t * 0.12) * 0.40;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };

    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      canvas.removeEventListener('click', onClick);
      renderer.dispose();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 h-full w-full"
      style={{ cursor: 'crosshair' }}
    />
  );
}
