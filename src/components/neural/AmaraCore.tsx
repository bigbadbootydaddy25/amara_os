'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const CORE_VERT = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const CORE_FRAG = /* glsl */ `
  uniform vec3 color;
  uniform float time;
  uniform float intensity;
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vec3 viewDir = vec3(0.0, 0.0, 1.0);
    float fresnel = 1.0 - max(dot(vNormal, viewDir), 0.0);
    fresnel = pow(fresnel, 1.5);
    float pulse = sin(time * 1.2) * 0.15 + 0.85;
    float innerGlow = pow(max(dot(vNormal, viewDir), 0.0), 0.5) * 0.3;
    float alpha = (fresnel * 0.85 + innerGlow) * intensity * pulse;
    gl_FragColor = vec4(color * (fresnel + innerGlow * 0.5), alpha);
  }
`;

const RING_FRAG = /* glsl */ `
  uniform vec3 color;
  uniform float time;
  uniform float offset;
  varying vec3 vNormal;
  void main() {
    float fresnel = 1.0 - abs(dot(vNormal, vec3(0.0, 1.0, 0.0)));
    float pulse = sin(time * 0.8 + offset) * 0.2 + 0.8;
    gl_FragColor = vec4(color, fresnel * 0.6 * pulse);
  }
`;

interface Props {
  status: 'dormant' | 'online' | 'nuclear';
}

export function AmaraCore({ status }: Props) {
  const coreRef = useRef<THREE.Mesh>(null);
  const haloRef = useRef<THREE.Mesh>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const ring3Ref = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);

  const baseColor = status === 'nuclear' ? '#ff4400' : status === 'online' ? '#00d4ff' : '#1a3a4a';
  const glowColor = status === 'nuclear' ? '#ff8800' : status === 'online' ? '#00ffff' : '#0a1a24';

  const coreUniforms = useMemo(
    () => ({
      color: { value: new THREE.Color(baseColor) },
      time: { value: 0 },
      intensity: { value: status === 'nuclear' ? 1.4 : status === 'online' ? 1.0 : 0.3 },
    }),
    [status, baseColor],
  );

  const glowUniforms = useMemo(
    () => ({
      color: { value: new THREE.Color(glowColor) },
      time: { value: 0 },
      intensity: { value: status === 'nuclear' ? 0.9 : 0.6 },
    }),
    [status, glowColor],
  );

  const ring1Uniforms = useMemo(
    () => ({
      color: { value: new THREE.Color(status === 'nuclear' ? '#ff6600' : '#00d4ff') },
      time: { value: 0 },
      offset: { value: 0 },
    }),
    [status],
  );

  const ring2Uniforms = useMemo(
    () => ({
      color: { value: new THREE.Color(status === 'nuclear' ? '#ff3300' : '#0088cc') },
      time: { value: 0 },
      offset: { value: 2.1 },
    }),
    [status],
  );

  const ring3Uniforms = useMemo(
    () => ({
      color: { value: new THREE.Color(status === 'nuclear' ? '#ff9900' : '#004466') },
      time: { value: 0 },
      offset: { value: 4.2 },
    }),
    [status],
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    coreUniforms.time.value = t;
    glowUniforms.time.value = t;
    ring1Uniforms.time.value = t;
    ring2Uniforms.time.value = t;
    ring3Uniforms.time.value = t;

    const speed = status === 'nuclear' ? 3 : 1;
    if (ring1Ref.current) ring1Ref.current.rotation.z = t * 0.3 * speed;
    if (ring2Ref.current) ring2Ref.current.rotation.z = -t * 0.2 * speed;
    if (ring3Ref.current) ring3Ref.current.rotation.z = t * 0.15 * speed;
    if (ring1Ref.current) ring1Ref.current.rotation.x = Math.PI / 2 + Math.sin(t * 0.4) * 0.3;
    if (ring2Ref.current)
      ring2Ref.current.rotation.x = Math.PI / 3 + Math.cos(t * 0.3) * 0.25;
    if (ring3Ref.current) ring3Ref.current.rotation.x = Math.PI / 4 + Math.sin(t * 0.5) * 0.2;

    const nuclearScale = status === 'nuclear' ? 1 + Math.sin(t * 8) * 0.08 : 1;
    if (coreRef.current) coreRef.current.scale.setScalar(nuclearScale);
  });

  return (
    <group>
      {/* Outer ambient glow */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[2.6, 32, 32]} />
        <shaderMaterial
          vertexShader={CORE_VERT}
          fragmentShader={CORE_FRAG}
          uniforms={glowUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          side={THREE.BackSide}
        />
      </mesh>

      {/* Core orb */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[1.4, 64, 64]} />
        <shaderMaterial
          vertexShader={CORE_VERT}
          fragmentShader={CORE_FRAG}
          uniforms={coreUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Halo layer */}
      <mesh ref={haloRef}>
        <sphereGeometry args={[1.8, 32, 32]} />
        <shaderMaterial
          vertexShader={CORE_VERT}
          fragmentShader={CORE_FRAG}
          uniforms={coreUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          side={THREE.BackSide}
        />
      </mesh>

      {/* Orbital rings */}
      <mesh ref={ring1Ref}>
        <torusGeometry args={[2.2, 0.018, 8, 120]} />
        <shaderMaterial
          vertexShader={CORE_VERT}
          fragmentShader={RING_FRAG}
          uniforms={ring1Uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <mesh ref={ring2Ref}>
        <torusGeometry args={[2.8, 0.012, 8, 120]} />
        <shaderMaterial
          vertexShader={CORE_VERT}
          fragmentShader={RING_FRAG}
          uniforms={ring2Uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <mesh ref={ring3Ref}>
        <torusGeometry args={[3.4, 0.008, 8, 120]} />
        <shaderMaterial
          vertexShader={CORE_VERT}
          fragmentShader={RING_FRAG}
          uniforms={ring3Uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Point light at center */}
      <pointLight
        color={status === 'nuclear' ? '#ff4400' : '#00d4ff'}
        intensity={status === 'nuclear' ? 8 : 4}
        distance={20}
        decay={2}
      />
    </group>
  );
}
