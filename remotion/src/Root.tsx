import React from 'react';
import { Composition } from 'remotion';
import { AmaraIntro } from './compositions/AmaraIntro';
import { TOTAL_FRAMES, FPS } from './data/amaraScript';

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="AmaraIntro"
        component={AmaraIntro}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};
