'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useNeuralStore, AGENT_CONFIG, type AgentState } from '@/stores/neural-store';

// ── constants ────────────────────────────────────────────────────────────────

const ORBIT_RADIUS = 4.5;
const RING_TILT = 0.38; // radians — ~22°

const INTENSITY: Record<AgentState, number> = {
  idle: 0.28, searching: 0.60, processing: 0.85, verified: 1.10, nuclear: 1.50,
};
const PULSE_SPEED: Record<AgentState, number> = {
  idle: 0.8, searching: 2.0, processing: 3.5, verified: 1.2, nuclear: 8.0,
};
const COLOR_OVERRIDE: Partial<Record<AgentState, string>> = {
  verified: '#00ff88',
  nuclear: '#ff6600',
};

const NUM_STREAM_PARTICLES = 40;

// ── shaders ──────────────────────────────────────────────────────────────────

const CORE_VERT = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vViewDir = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

const CORE_FRAG = /* glsl */ `
  uniform float uTime;
  uniform float uNuclear;
  uniform float uOscFreq;
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    float fresnel = pow(1.0 - clamp(dot(vNormal, vViewDir), 0.0, 1.0), 2.5);
    vec3 coolA = vec3(0.05, 0.20, 0.90);
    vec3 coolB = vec3(0.10, 0.80, 1.00);
    vec3 hotA  = vec3(0.65, 0.08, 0.00);
    vec3 hotB  = vec3(1.00, 0.50, 0.10);
    vec3 color = mix(mix(coolA, coolB, fresnel), mix(hotA, hotB, fresnel), uNuclear);
    float osc   = 0.85 + 0.15 * sin(uTime * uOscFreq);
    float alpha = (0.28 + 0.72 * fresnel) * osc;
    gl_FragColor = vec4(color * (1.0 + fresnel * 1.8), alpha);
  }
`;

// ── helpers ──────────────────────────────────────────────────────────────────

function easeInOut(t: number) {
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

function hexToThree(hex: string): THREE.Color {
  return new THREE.Color(hex);
}

// ── scene builder ─────────────────────────────────────────────────────────────

function buildScene() {
  const scene = new THREE.Scene();

  // ── AMARA core ──────────────────────────────────────────────────────────────
  const coreUniforms = {
    uTime: { value: 0 },
    uNuclear: { value: 0 },
    uOscFreq: { value: 1.0 },
  };
  const coreMat = new THREE.ShaderMaterial({
    uniforms: coreUniforms,
    vertexShader: CORE_VERT,
    fragmentShader: CORE_FRAG,
    transparent: true,
    depthWrite: false,
    side: THREE.FrontSide,
  });
  const coreGeo = new THREE.SphereGeometry(1.0, 48, 48);
  const coreMesh = new THREE.Mesh(coreGeo, coreMat);

  // outer glow
  const glowMat = new THREE.MeshBasicMaterial({
    color: new THREE.Color(0x0055ff),
    transparent: true,
    opacity: 0.08,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.BackSide,
  });
  const glowMesh = new THREE.Mesh(new THREE.SphereGeometry(1.7, 32, 32), glowMat);

  // rings
  const ringColors = [0x00ccff, 0x0088ff, 0x0044cc];
  const ringAngles = [
    new THREE.Euler(Math.PI / 2, 0, 0),
    new THREE.Euler(0, 0, Math.PI / 3),
    new THREE.Euler(Math.PI / 5, Math.PI / 4, 0),
  ];
  const ringMeshes: THREE.Mesh[] = ringAngles.map((euler, i) => {
    const mat = new THREE.MeshBasicMaterial({
      color: ringColors[i],
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const m = new THREE.Mesh(new THREE.TorusGeometry(2.1 + i * 0.18, 0.012, 8, 96), mat);
    m.rotation.copy(euler);
    return m;
  });

  const coreGroup = new THREE.Group();
  coreGroup.add(coreMesh, glowMesh, ...ringMeshes);
  scene.add(coreGroup);

  // ── agent orbs ──────────────────────────────────────────────────────────────
  const orbGroup = new THREE.Group();
  orbGroup.rotation.x = RING_TILT;
  scene.add(orbGroup);

  const orbMeshes: THREE.Mesh[] = [];
  const orbGlows: THREE.Mesh[] = [];
  const labelSprites: THREE.Sprite[] = [];

  AGENT_CONFIG.forEach((cfg, i) => {
    const angle = (i / AGENT_CONFIG.length) * Math.PI * 2;
    const x = Math.cos(angle) * ORBIT_RADIUS;
    const z = Math.sin(angle) * ORBIT_RADIUS;

    const color = hexToThree(cfg.color);

    // orb
    const orbMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: INTENSITY.idle,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const orb = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 16), orbMat);
    orb.position.set(x, 0, z);
    orb.userData = { agentIndex: i };
    orbMeshes.push(orb);

    // glow
    const glowOrbMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.06,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const glowOrb = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 16), glowOrbMat);
    glowOrb.position.copy(orb.position);
    orbGlows.push(glowOrb);

    // label canvas texture
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 32;
    const ctx = canvas.getContext('2d')!;
    ctx.font = 'bold 14px monospace';
    ctx.fillStyle = cfg.color;
    ctx.textAlign = 'center';
    ctx.fillText(cfg.name, 64, 20);
    const tex = new THREE.CanvasTexture(canvas);
    const spriteMat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      opacity: 0.75,
      depthWrite: false,
    });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.0, 0.25, 1);
    sprite.position.set(x, 0.55, z);
    labelSprites.push(sprite);

    orbGroup.add(orb, glowOrb, sprite);
  });

  // ── connection beams ────────────────────────────────────────────────────────
  const beamGroup = new THREE.Group();
  scene.add(beamGroup);

  const beamLines: THREE.Line[] = [];
  const beamGeos: THREE.BufferGeometry[] = [];
  const pulseMeshes: THREE.Mesh[] = [];

  AGENT_CONFIG.forEach((cfg, i) => {
    const geo = new THREE.BufferGeometry();
    const posArr = new Float32Array(6); // [cx,cy,cz, ox,oy,oz]
    geo.setAttribute('position', new THREE.BufferAttribute(posArr, 3));
    const mat = new THREE.LineBasicMaterial({
      color: hexToThree(cfg.color),
      transparent: true,
      opacity: 0.12,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const line = new THREE.Line(geo, mat);
    beamLines.push(line);
    beamGeos.push(geo);
    beamGroup.add(line);

    // pulse bead
    const bead = new THREE.Mesh(
      new THREE.SphereGeometry(0.055, 8, 8),
      new THREE.MeshBasicMaterial({
        color: hexToThree(cfg.color),
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    bead.userData = { beadIndex: i };
    pulseMeshes.push(bead);
    beamGroup.add(bead);
  });

  // ── data streams ────────────────────────────────────────────────────────────
  const streamGroup = new THREE.Group();
  scene.add(streamGroup);

  const streamGeos: THREE.BufferGeometry[] = [];
  const streamPoints: THREE.Points[] = [];

  AGENT_CONFIG.forEach((cfg) => {
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(NUM_STREAM_PARTICLES * 3);
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.PointsMaterial({
      color: hexToThree(cfg.color),
      size: 0.045,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const pts = new THREE.Points(geo, mat);
    streamGeos.push(geo);
    streamPoints.push(pts);
    streamGroup.add(pts);
  });

  // ── background ──────────────────────────────────────────────────────────────

  // stars
  const starGeo = new THREE.BufferGeometry();
  const starPos = new Float32Array(2000 * 3);
  for (let i = 0; i < 2000; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 60 + Math.random() * 40;
    starPos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    starPos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    starPos[i * 3 + 2] = r * Math.cos(phi);
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
  const starField = new THREE.Points(
    starGeo,
    new THREE.PointsMaterial({
      color: 0xaaccff,
      size: 0.15,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  scene.add(starField);

  // nebula clouds
  const nebGeo = new THREE.BufferGeometry();
  const nebPos = new Float32Array(600 * 3);
  for (let i = 0; i < 600; i++) {
    nebPos[i * 3] = (Math.random() - 0.5) * 80;
    nebPos[i * 3 + 1] = (Math.random() - 0.5) * 50;
    nebPos[i * 3 + 2] = -20 - Math.random() * 40;
  }
  nebGeo.setAttribute('position', new THREE.BufferAttribute(nebPos, 3));
  const nebula = new THREE.Points(
    nebGeo,
    new THREE.PointsMaterial({
      color: 0x1133aa,
      size: 1.8,
      transparent: true,
      opacity: 0.18,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  scene.add(nebula);

  return {
    scene,
    coreGroup,
    coreUniforms,
    glowMat,
    ringMeshes,
    orbGroup,
    orbMeshes,
    orbGlows,
    beamLines,
    beamGeos,
    pulseMeshes,
    streamGeos,
    streamPoints,
    starField,
    nebula,
  };
}

// ── component ─────────────────────────────────────────────────────────────────

export function NeuralBrainScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);

    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 300);
    camera.position.set(0, 2.5, 11);
    camera.lookAt(0, 0, 0);

    const refs = buildScene();
    const { scene, coreUniforms, ringMeshes, orbGroup, orbMeshes, orbGlows,
      beamLines, beamGeos, pulseMeshes, streamGeos, streamPoints, starField } = refs;

    // particle time offsets for data streams
    const streamOffsets = AGENT_CONFIG.map(() =>
      Array.from({ length: NUM_STREAM_PARTICLES }, (_, j) => j / NUM_STREAM_PARTICLES),
    );

    // raycaster
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points = { threshold: 0.2 };
    const mouse = new THREE.Vector2();

    const onCanvasClick = (e: MouseEvent) => {
      mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(orbMeshes);
      if (hits.length > 0) {
        const idx = (hits[0].object as THREE.Mesh).userData.agentIndex as number;
        useNeuralStore.getState().selectAgent(AGENT_CONFIG[idx].id);
      } else {
        useNeuralStore.getState().selectAgent(null);
      }
    };
    canvas.addEventListener('click', onCanvasClick);

    // resize
    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', onResize);

    // ── animation loop ────────────────────────────────────────────────────────
    let rafId = 0;
    let time = 0;
    let prevTs = performance.now();
    const center = new THREE.Vector3(0, 0, 0);

    const tick = (ts: number) => {
      rafId = requestAnimationFrame(tick);
      const delta = Math.min((ts - prevTs) / 1000, 0.05);
      prevTs = ts;
      time += delta;

      const store = useNeuralStore.getState();
      const { agents } = store;
      const isNuclear = store.nuclearAgentId !== null;

      // ── AMARA core ─────────────────────────────────────────────────────────
      coreUniforms.uTime.value = time;
      const nuclearTarget = isNuclear ? 1.0 : 0.0;
      coreUniforms.uNuclear.value += (nuclearTarget - coreUniforms.uNuclear.value) * delta * 3;
      coreUniforms.uOscFreq.value = isNuclear ? 8.0 : 1.0;

      const ringSpeedMult = isNuclear ? 3 : 1;
      ringMeshes[0].rotation.y += delta * 0.4 * ringSpeedMult;
      ringMeshes[1].rotation.z += delta * 0.28 * ringSpeedMult;
      ringMeshes[2].rotation.x += delta * 0.18 * ringSpeedMult;

      // glow tint
      (refs.glowMat as THREE.MeshBasicMaterial).color.set(isNuclear ? 0xff3300 : 0x0055ff);

      // ── orbital ring rotation ──────────────────────────────────────────────
      orbGroup.rotation.y += delta * 0.08;
      orbGroup.updateMatrixWorld(true);

      // ── per-agent updates ──────────────────────────────────────────────────
      agents.forEach((agent, i) => {
        const agentColor = COLOR_OVERRIDE[agent.state]
          ? hexToThree(COLOR_OVERRIDE[agent.state]!)
          : hexToThree(agent.color);
        const intensity = INTENSITY[agent.state];
        const pulseSpeed = PULSE_SPEED[agent.state];
        const pulse = 0.6 + 0.4 * Math.sin(time * pulseSpeed * Math.PI * 2);

        const orbMat = orbMeshes[i].material as THREE.MeshBasicMaterial;
        orbMat.color.copy(agentColor);
        orbMat.opacity = intensity * pulse;

        const glowMat = orbGlows[i].material as THREE.MeshBasicMaterial;
        glowMat.color.copy(agentColor);
        glowMat.opacity = intensity * 0.12 * pulse;

        // world position of this orb
        const worldPos = new THREE.Vector3();
        orbMeshes[i].getWorldPosition(worldPos);

        // sync glow to orb world pos (glow is a sibling in orbGroup)
        // they share the same local position so this is automatic

        // ── beam ──────────────────────────────────────────────────────────────
        const beamPosArr = beamGeos[i].attributes.position.array as Float32Array;
        beamPosArr[0] = 0; beamPosArr[1] = 0; beamPosArr[2] = 0;
        beamPosArr[3] = worldPos.x; beamPosArr[4] = worldPos.y; beamPosArr[5] = worldPos.z;
        beamGeos[i].attributes.position.needsUpdate = true;

        const beamMat = beamLines[i].material as THREE.LineBasicMaterial;
        const active = agent.state !== 'idle';
        beamMat.opacity = active ? intensity * 0.45 * pulse : 0.08;

        // ── pulse bead ────────────────────────────────────────────────────────
        const bead = pulseMeshes[i];
        const beadMat = bead.material as THREE.MeshBasicMaterial;
        if (active && agent.state !== 'verified') {
          const t = easeInOut((time * pulseSpeed * 0.25) % 1);
          bead.position.lerpVectors(center, worldPos, t);
          beadMat.opacity = 0.9 * pulse;
          beadMat.color.copy(agentColor);
        } else {
          beadMat.opacity = 0;
        }

        // ── data stream particles ─────────────────────────────────────────────
        const showStream = agent.state === 'processing' || agent.state === 'nuclear';
        const streamPts = streamPoints[i];
        const streamMat = streamPts.material as THREE.PointsMaterial;
        streamMat.opacity = showStream ? intensity * 0.65 : 0;
        streamMat.color.copy(agentColor);

        if (showStream) {
          const posArr = streamGeos[i].attributes.position.array as Float32Array;
          const offsets = streamOffsets[i];
          for (let p = 0; p < NUM_STREAM_PARTICLES; p++) {
            const t = easeInOut(((time * 0.4 + offsets[p]) % 1));
            const px = worldPos.x + (center.x - worldPos.x) * t;
            const py = worldPos.y + (center.y - worldPos.y) * t;
            const pz = worldPos.z + (center.z - worldPos.z) * t;
            posArr[p * 3] = px;
            posArr[p * 3 + 1] = py;
            posArr[p * 3 + 2] = pz;
          }
          streamGeos[i].attributes.position.needsUpdate = true;
        }
      });

      // ── camera drift ──────────────────────────────────────────────────────
      camera.position.x = Math.sin(time * 0.2) * 0.55;
      camera.position.y = 2.5 + Math.sin(time * 0.15) * 0.35;
      camera.lookAt(0, 0, 0);

      // ── star rotation ────────────────────────────────────────────────────
      starField.rotation.y += delta * 0.008;

      renderer.render(scene, camera);
    };

    rafId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', onResize);
      canvas.removeEventListener('click', onCanvasClick);
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
