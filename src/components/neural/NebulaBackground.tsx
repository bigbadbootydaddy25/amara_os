'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export function NebulaBackground() {
  const starsRef = useRef<THREE.Points>(null);
  const nebulaRef = useRef<THREE.Points>(null);

  const { starPositions, starColors } = useMemo(() => {
    const count = 2000;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 40 + Math.random() * 60;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
      const brightness = 0.4 + Math.random() * 0.6;
      const hue = Math.random();
      if (hue < 0.3) {
        colors[i * 3] = brightness * 0.6;
        colors[i * 3 + 1] = brightness * 0.8;
        colors[i * 3 + 2] = brightness;
      } else if (hue < 0.6) {
        colors[i * 3] = brightness;
        colors[i * 3 + 1] = brightness;
        colors[i * 3 + 2] = brightness;
      } else {
        colors[i * 3] = brightness * 0.8;
        colors[i * 3 + 1] = brightness * 0.6;
        colors[i * 3 + 2] = brightness;
      }
    }
    return { starPositions: positions, starColors: colors };
  }, []);

  const { nebulaPositions, nebulaColors } = useMemo(() => {
    const count = 600;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const spread = 25;
      positions[i * 3] = (Math.random() - 0.5) * spread;
      positions[i * 3 + 1] = (Math.random() - 0.5) * spread * 0.5;
      positions[i * 3 + 2] = (Math.random() - 0.5) * spread - 10;
      colors[i * 3] = 0.05 + Math.random() * 0.1;
      colors[i * 3 + 1] = 0.1 + Math.random() * 0.2;
      colors[i * 3 + 2] = 0.3 + Math.random() * 0.4;
    }
    return { nebulaPositions: positions, nebulaColors: colors };
  }, []);

  useFrame((_, delta) => {
    if (starsRef.current) {
      starsRef.current.rotation.y += delta * 0.01;
    }
    if (nebulaRef.current) {
      nebulaRef.current.rotation.y -= delta * 0.005;
    }
  });

  return (
    <>
      <points ref={starsRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[starPositions, 3]} />
          <bufferAttribute attach="attributes-color" args={[starColors, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.08} vertexColors transparent opacity={0.9} sizeAttenuation />
      </points>
      <points ref={nebulaRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[nebulaPositions, 3]} />
          <bufferAttribute attach="attributes-color" args={[nebulaColors, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.4} vertexColors transparent opacity={0.15} sizeAttenuation />
      </points>
    </>
  );
}
