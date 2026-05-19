'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const RING_COUNT = 5;

export function NuclearPulse() {
  const rings = useRef<THREE.Mesh[]>([]);

  const ringTimings = useMemo(
    () => Array.from({ length: RING_COUNT }, (_, i) => i * (1 / RING_COUNT)),
    [],
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    rings.current.forEach((ring, i) => {
      if (!ring) return;
      const progress = ((t * 0.7 + ringTimings[i]) % 1 + 1) % 1;
      const scale = 1 + progress * 7;
      ring.scale.setScalar(scale);
      const opacity = Math.max(0, 1 - progress * 1.2) * 0.6;
      (ring.material as THREE.MeshBasicMaterial).opacity = opacity;
    });
  });

  return (
    <group>
      {Array.from({ length: RING_COUNT }, (_, i) => (
        <mesh
          key={i}
          ref={(el) => {
            if (el) rings.current[i] = el;
          }}
          rotation={[Math.PI / 2, 0, 0]}
        >
          <torusGeometry args={[1.6, 0.04, 8, 80]} />
          <meshBasicMaterial
            color={i % 2 === 0 ? '#ff4400' : '#ff8800'}
            transparent
            opacity={0}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      ))}
    </group>
  );
}
