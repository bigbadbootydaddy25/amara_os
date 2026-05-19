'use client';

import { useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { AmaraCore } from './AmaraCore';
import { AgentOrb } from './AgentOrb';
import { ConnectionBeam } from './ConnectionBeam';
import { DataStream } from './DataStream';
import { NuclearPulse } from './NuclearPulse';
import { NebulaBackground } from './NebulaBackground';
import type { AgentId } from '@/types/agents';
import { AGENT_DEFINITIONS } from '@/types/agents';
import { useAgentStore } from '@/stores/agent-store';

function getOrbPosition(index: number, total: number): [number, number, number] {
  const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
  const R = 5.2;
  const tilt = 0.22;
  return [
    R * Math.cos(angle),
    R * Math.sin(angle) * tilt,
    R * Math.sin(angle) * 0.5,
  ];
}

function CameraRig() {
  const { camera } = useThree();
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    camera.position.x = Math.sin(t * 0.04) * 1.5;
    camera.position.y = Math.cos(t * 0.03) * 0.8 + 0.5;
    camera.lookAt(0, 0, 0);
  });
  return null;
}

export function EnergyBrainScene() {
  const { agents, selectedAgentId, amaraStatus, setSelectedAgent, clearSelected } =
    useAgentStore();

  const positions = useMemo(
    () =>
      AGENT_DEFINITIONS.reduce<Record<AgentId, [number, number, number]>>((acc, def, i) => {
        acc[def.id] = getOrbPosition(i, AGENT_DEFINITIONS.length);
        return acc;
      }, {} as Record<AgentId, [number, number, number]>),
    [],
  );

  return (
    <>
      <CameraRig />
      <ambientLight intensity={0.02} />

      <NebulaBackground />

      {/* AMARA core brain */}
      <AmaraCore status={amaraStatus} />
      {amaraStatus === 'nuclear' && <NuclearPulse />}

      {/* Agent orbs + connections + streams */}
      {AGENT_DEFINITIONS.map((def) => {
        const state = agents[def.id];
        const pos = positions[def.id];
        return (
          <group key={def.id}>
            <ConnectionBeam
              from={pos}
              to={[0, 0, 0]}
              agentStatus={state.status}
              color={def.color}
            />
            <DataStream
              from={pos}
              agentStatus={state.status}
              color={def.color}
            />
            <AgentOrb
              def={def}
              agentState={state}
              position={pos}
              onClick={() =>
                selectedAgentId === def.id ? clearSelected() : setSelectedAgent(def.id)
              }
              isSelected={selectedAgentId === def.id}
            />
          </group>
        );
      })}

      {/* Background fog */}
      <fog attach="fog" args={['#010812', 18, 60]} />
    </>
  );
}
