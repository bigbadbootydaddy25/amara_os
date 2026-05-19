'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { AgentState } from '@/types/agents';

interface Props {
  from: [number, number, number];
  to: [number, number, number];
  agentStatus: AgentState['status'];
  color: string;
}

export function ConnectionBeam({ from, to, agentStatus, color }: Props) {
  const pulseRef = useRef<THREE.Mesh>(null);

  const { lineGeometry, midPoint } = useMemo(() => {
    const f = new THREE.Vector3(...from);
    const t = new THREE.Vector3(...to);
    const geo = new THREE.BufferGeometry().setFromPoints([f, t]);
    const mid = f.clone().lerp(t, 0.5);
    return { lineGeometry: geo, midPoint: mid };
  }, [from, to]);

  const lineMaterial = useMemo(() => {
    const isActive =
      agentStatus === 'processing' || agentStatus === 'verified' || agentStatus === 'nuclear';
    const opacity = agentStatus === 'idle' ? 0.06 : agentStatus === 'searching' ? 0.18 : agentStatus === 'processing' ? 0.55 : agentStatus === 'verified' ? 0.75 : 0.95;
    const lineColor = agentStatus === 'nuclear' ? '#ff4400' : agentStatus === 'verified' ? '#00ff88' : agentStatus === 'processing' ? color : '#1a3040';
    return new THREE.LineBasicMaterial({ color: lineColor, transparent: true, opacity, blending: THREE.AdditiveBlending });
  }, [agentStatus, color]);

  const lineObject = useMemo(() => new THREE.Line(lineGeometry, lineMaterial), [lineGeometry, lineMaterial]);

  const isActive =
    agentStatus === 'processing' || agentStatus === 'verified' || agentStatus === 'nuclear';

  const pulseColor =
    agentStatus === 'nuclear' ? '#ff6600' : agentStatus === 'verified' ? '#00ff88' : color;

  useFrame(({ clock }) => {
    if (!isActive || !pulseRef.current) return;
    const t = clock.getElapsedTime();
    const progress = ((t * 1.2) % 1 + 1) % 1;
    const f = new THREE.Vector3(...from);
    const toV = new THREE.Vector3(...to);
    pulseRef.current.position.lerpVectors(f, toV, progress);
    const mat = pulseRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = Math.sin(progress * Math.PI) * 0.9;
  });

  return (
    <group>
      <primitive object={lineObject} />
      {isActive && (
        <mesh ref={pulseRef} position={midPoint}>
          <sphereGeometry args={[0.06, 8, 8]} />
          <meshBasicMaterial
            color={pulseColor}
            transparent
            opacity={0.8}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      )}
    </group>
  );
}
