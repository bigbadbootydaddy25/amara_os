'use client';

import { Canvas } from '@react-three/fiber';
import { EnergyBrainScene } from './EnergyBrainScene';

export default function EnergyBrainCanvas() {
  return (
    <Canvas
      camera={{ position: [0, 2, 13], fov: 55, near: 0.1, far: 200 }}
      gl={{
        antialias: true,
        alpha: false,
        powerPreference: 'high-performance',
        toneMapping: 3, // THREE.ReinhardToneMapping
        toneMappingExposure: 0.9,
      }}
      dpr={[1, 1.5]}
      style={{ background: 'transparent' }}
    >
      <EnergyBrainScene />
    </Canvas>
  );
}
