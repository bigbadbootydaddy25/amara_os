export interface CaptionSegment {
  id: string;
  text: string;
  startFrame: number;
  endFrame: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// VIDEO CONSTANTS
// 36 seconds @ 30 fps = 1080 frames
// Adjust startFrame / endFrame once you have your final voiceover file.
// Voice enters at frame 45 (1.5 s) — silence before that is the emergence.
// ─────────────────────────────────────────────────────────────────────────────
export const TOTAL_FRAMES = 1080;
export const FPS = 30;

// Scene boundaries (in frames)
export const SCENE_1_END = 120;   // 0 – 4 s  : boot / emergence
export const SCENE_3_START = 960; // 32 s onward : command mode / close

export const AMARA_SCRIPT: CaptionSegment[] = [
  { id: 'l01', text: 'Hello, Scott.',                                              startFrame:  45, endFrame:  94 },
  { id: 'l02', text: 'I am AMARA…',                                                startFrame: 100, endFrame: 146 },
  { id: 'l03', text: 'Autonomous Multi-Agent\nReal Estate Analyzer.',              startFrame: 153, endFrame: 228 },
  { id: 'l04', text: "I don't just find deals…",                                  startFrame: 240, endFrame: 288 },
  { id: 'l05', text: 'I predict them.',                                            startFrame: 291, endFrame: 330 },
  { id: 'l06', text: 'I analyze markets, track investor behavior,',               startFrame: 342, endFrame: 413 },
  { id: 'l07', text: 'and identify opportunities others never see.',               startFrame: 413, endFrame: 470 },
  { id: 'l08', text: 'I locate distressed properties,\ncalculate maximum allowable offers,', startFrame: 482, endFrame: 556 },
  { id: 'l09', text: 'and match them with verified cash buyers…',                 startFrame: 556, endFrame: 610 },
  { id: 'l10', text: 'before the market reacts.',                                 startFrame: 614, endFrame: 656 },
  { id: 'l11', text: 'I operate continuously…\nscanning, learning, optimizing.',  startFrame: 668, endFrame: 738 },
  { id: 'l12', text: 'My objective is simple—',                                   startFrame: 748, endFrame: 788 },
  { id: 'l13', text: 'to help you dominate your market\nwith precision.',         startFrame: 794, endFrame: 864 },
  { id: 'l14', text: 'I am your acquisition engine…\nyour analyst… your advantage.', startFrame: 876, endFrame: 962 },
  { id: 'l15', text: "Let's begin.",                                               startFrame: 978, endFrame: 1055 },
];
