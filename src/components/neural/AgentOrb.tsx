'use client';

import { useRef, useMemo, useCallback } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import type { AgentDefinition, AgentState } from '@/types/agents';

const ORB_VERT = /* glsl */ `
  varying vec3 vNormal;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const ORB_FRAG = /* glsl */ `
  uniform vec3 color;
  uniform float time;
  uniform float intensity;
  uniform float pulse;
  varying vec3 vNormal;
  void main() {
    float fresnel = pow(1.0 - max(dot(vNormal, vec3(0.0, 0.0, 1.0)), 0.0), 1.8);
    float inner = pow(max(dot(vNormal, vec3(0.0, 0.0, 1.0)), 0.0), 0.4) * 0.4;
    float p = sin(time * pulse) * 0.15 + 0.85;
    float alpha = (fresnel * 0.9 + inner) * intensity * p;
    gl_FragColor = vec4(color, alpha);
  }
`;

function statusToIntensity(status: AgentState['status']): number {
  switch (status) {
    case 'idle': return 0.28;
    case 'searching': return 0.6;
    case 'processing': return 0.85;
    case 'verified': return 1.1;
    case 'nuclear': return 1.5;
  }
}

function statusToPulse(status: AgentState['status']): number {
  switch (status) {
    case 'idle': return 0.8;
    case 'searching': return 2.0;
    case 'processing': return 3.5;
    case 'verified': return 1.2;
    case 'nuclear': return 8.0;
  }
}

function statusToColor(def: AgentDefinition, status: AgentState['status']): string {
  if (status === 'nuclear') return '#ff6600';
  if (status === 'verified') return '#00ff88';
  return def.color;
}

interface Props {
  def: AgentDefinition;
  agentState: AgentState;
  position: [number, number, number];
  onClick: () => void;
  isSelected: boolean;
}

export function AgentOrb({ def, agentState, position, onClick, isSelected }: Props) {
  const orbRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const lightRef = useRef<THREE.PointLight>(null);

  const color = statusToColor(def, agentState.status);
  const intensity = statusToIntensity(agentState.status);
  const pulseSpeed = statusToPulse(agentState.status);

  const orbUniforms = useMemo(
    () => ({
      color: { value: new THREE.Color(color) },
      time: { value: 0 },
      intensity: { value: intensity },
      pulse: { value: pulseSpeed },
    }),
    [color, intensity, pulseSpeed],
  );

  const glowUniforms = useMemo(
    () => ({
      color: { value: new THREE.Color(def.glowColor) },
      time: { value: 0 },
      intensity: { value: intensity * 0.5 },
      pulse: { value: pulseSpeed * 0.7 },
    }),
    [def.glowColor, intensity, pulseSpeed],
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    orbUniforms.time.value = t;
    glowUniforms.time.value = t;
    orbUniforms.color.value.set(statusToColor(def, agentState.status));
    orbUniforms.intensity.value = statusToIntensity(agentState.status);
    orbUniforms.pulse.value = statusToPulse(agentState.status);
    glowUniforms.intensity.value = statusToIntensity(agentState.status) * 0.5;

    if (lightRef.current) {
      lightRef.current.intensity =
        statusToIntensity(agentState.status) * (1 + Math.sin(t * pulseSpeed) * 0.2) * 2;
    }

    if (orbRef.current && agentState.status === 'nuclear') {
      const s = 1 + Math.sin(t * 8) * 0.12;
      orbRef.current.scale.setScalar(s);
    } else if (orbRef.current) {
      orbRef.current.scale.setScalar(1);
    }
  });

  const handleClick = useCallback(
    (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      onClick();
    },
    [onClick],
  );

  const labelColor =
    agentState.status === 'nuclear'
      ? '#ff6600'
      : agentState.status === 'verified'
        ? '#00ff88'
        : agentState.status === 'idle'
          ? '#446677'
          : def.color;

  return (
    <group position={position}>
      {/* Outer glow sphere */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.72, 24, 24]} />
        <shaderMaterial
          vertexShader={ORB_VERT}
          fragmentShader={ORB_FRAG}
          uniforms={glowUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          side={THREE.BackSide}
        />
      </mesh>

      {/* Core orb — clickable */}
      <mesh ref={orbRef} onClick={handleClick}>
        <sphereGeometry args={[0.42, 32, 32]} />
        <shaderMaterial
          vertexShader={ORB_VERT}
          fragmentShader={ORB_FRAG}
          uniforms={orbUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Selection ring */}
      {isSelected && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.65, 0.025, 8, 64]} />
          <meshBasicMaterial color={def.color} transparent opacity={0.9} />
        </mesh>
      )}

      <pointLight
        ref={lightRef}
        color={color}
        intensity={intensity * 2}
        distance={5}
        decay={2}
      />

      {/* HTML label */}
      <Html
        center
        position={[0, 0.85, 0]}
        style={{ pointerEvents: 'none', userSelect: 'none', whiteSpace: 'nowrap' }}
      >
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: labelColor,
              textTransform: 'uppercase',
              textShadow: `0 0 8px ${labelColor}`,
              transition: 'color 0.5s ease',
              fontFamily: 'monospace',
            }}
          >
            {def.label}
          </div>
          {agentState.status !== 'idle' && agentState.currentTask && (
            <div
              style={{
                fontSize: '7px',
                color: '#4a7a8a',
                marginTop: '2px',
                maxWidth: '120px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                fontFamily: 'monospace',
              }}
            >
              {agentState.currentTask}
            </div>
          )}
        </div>
      </Html>
    </group>
  );
}
