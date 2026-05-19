'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { AgentState } from '@/types/agents';

const PARTICLE_COUNT = 40;

interface Props {
  from: [number, number, number];
  agentStatus: AgentState['status'];
  color: string;
}

export function DataStream({ from, agentStatus, color }: Props) {
  const pointsRef = useRef<THREE.Points>(null);

  const isActive =
    agentStatus === 'processing' || agentStatus === 'verified' || agentStatus === 'nuclear';

  const { positions, offsets } = useMemo(() => {
    const pos = new Float32Array(PARTICLE_COUNT * 3);
    const off = new Float32Array(PARTICLE_COUNT);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      off[i] = Math.random();
      pos[i * 3] = from[0];
      pos[i * 3 + 1] = from[1];
      pos[i * 3 + 2] = from[2];
    }
    return { positions: pos, offsets: off };
  }, [from]);

  const particleColor = useMemo(
    () =>
      new THREE.Color(
        agentStatus === 'nuclear' ? '#ff6600' : agentStatus === 'verified' ? '#00ff88' : color,
      ),
    [agentStatus, color],
  );

  useFrame(({ clock }) => {
    if (!isActive || !pointsRef.current) return;
    const t = clock.getElapsedTime();
    const geo = pointsRef.current.geometry;
    const pos = geo.attributes.position.array as Float32Array;
    const fx = from[0], fy = from[1], fz = from[2];

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const progress = ((t * 0.9 + offsets[i]) % 1 + 1) % 1;
      const eased = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
      pos[i * 3] = fx + (-fx) * eased + (Math.random() - 0.5) * 0.04 * (1 - eased);
      pos[i * 3 + 1] = fy + (-fy) * eased + (Math.random() - 0.5) * 0.04 * (1 - eased);
      pos[i * 3 + 2] = fz + (-fz) * eased;
    }

    geo.attributes.position.needsUpdate = true;
  });

  if (!isActive) return null;

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={particleColor}
        size={0.055}
        transparent
        opacity={agentStatus === 'nuclear' ? 0.95 : 0.75}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
