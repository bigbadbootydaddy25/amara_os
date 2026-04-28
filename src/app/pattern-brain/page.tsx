'use client';

const NODES: [number, number, number, number][] = [
  // [cx, cy, animDurSec, animDelaySec]
  // Right hemisphere
  [530,195,2.1,0.0],[572,238,2.4,0.3],[614,196,2.0,0.6],[652,282,2.6,0.9],
  [548,302,2.2,1.2],[592,364,2.5,0.4],[622,304,2.3,0.8],[664,382,2.1,0.2],
  [542,402,2.7,1.5],[582,444,2.4,0.7],[624,422,2.2,1.1],[682,342,2.6,0.5],
  [538,158,2.4,0.9],[702,418,2.3,1.8],
  // Left hemisphere
  [470,195,2.2,0.2],[428,238,2.5,0.5],[386,196,2.1,0.8],[348,282,2.7,1.1],
  [452,302,2.3,1.4],[408,364,2.6,0.6],[378,304,2.4,1.0],[336,382,2.2,0.4],
  [458,402,2.8,1.7],[418,444,2.5,0.9],[376,422,2.3,1.3],[318,342,2.7,0.7],
  [462,158,2.5,1.1],[298,418,2.4,2.0],
  // Center
  [500,250,2.2,0.3],[500,330,2.6,0.8],[500,418,2.3,1.4],
];

const EDGES: [number,number][] = [
  [0,1],[1,2],[2,3],[1,4],[4,5],[5,6],[6,7],[4,8],[8,9],[9,10],[7,10],
  [6,11],[11,13],[0,12],[12,1],[28,0],[28,14],[29,4],[29,18],[30,8],[30,23],
  [14,15],[15,16],[16,17],[15,18],[18,19],[19,20],[20,21],[18,22],[22,23],
  [23,24],[24,25],[21,25],[20,26],[26,27],[13,11],[27,25],[28,29],[29,30],
];

const STREAM_DEFS = [
  { id:'lt', d:'M 0,180 Q 250,272 500,370',  color:'#00f5ff', dur:3.0 },
  { id:'lb', d:'M 0,598 Q 250,482 500,370',  color:'#a855f7', dur:3.2 },
  { id:'rt', d:'M 1000,175 Q 750,272 500,370',color:'#22d3ee', dur:3.1 },
  { id:'rb', d:'M 1000,595 Q 750,482 500,370',color:'#4ade80', dur:3.4 },
  { id:'tl', d:'M 222,0 Q 360,182 500,370',  color:'#f59e0b', dur:3.3 },
  { id:'tr', d:'M 778,0 Q 640,182 500,370',  color:'#ec4899', dur:3.5 },
  { id:'bl', d:'M 195,780 Q 347,580 500,370',color:'#06b6d4', dur:3.2 },
  { id:'br', d:'M 805,780 Q 653,580 500,370',color:'#8b5cf6', dur:3.6 },
];

export default function PatternBrainPage() {
  return (
    <div style={{ position:'fixed', inset:0, background:'#000', overflow:'hidden' }}>
      <style>{`
        @keyframes glowPulse {
          0%,100%{ filter:drop-shadow(0 0 8px #00d4ff) drop-shadow(0 0 22px #004fcc); }
          50%    { filter:drop-shadow(0 0 20px #00e8ff) drop-shadow(0 0 50px #0077ff); }
        }
        @keyframes glowPulse2 {
          0%,100%{ filter:drop-shadow(0 0 8px #00d4ff) drop-shadow(0 0 22px #004fcc); }
          50%    { filter:drop-shadow(0 0 20px #00e8ff) drop-shadow(0 0 50px #0077ff); }
        }
        @keyframes gyriFlicker {
          0%,100%{ opacity:.40; } 50%{ opacity:.68; }
        }
        @keyframes auraBreath {
          0%,100%{ opacity:.72; } 50%{ opacity:1; }
        }
      `}</style>

      <svg
        viewBox="0 0 1000 780"
        style={{ width:'100%', height:'100%' }}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Glow filters */}
          <filter id="gxl" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="10" result="b1"/>
            <feGaussianBlur stdDeviation="4"  result="b2" in="SourceGraphic"/>
            <feMerge><feMergeNode in="b1"/><feMergeNode in="b2"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="gmd" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="gsm" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2.5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>

          {/* Brain fill gradients */}
          <radialGradient id="fillR" cx="62%" cy="32%" r="72%">
            <stop offset="0%"   stopColor="#00aaff" stopOpacity="0.20"/>
            <stop offset="55%"  stopColor="#002299" stopOpacity="0.10"/>
            <stop offset="100%" stopColor="#000033" stopOpacity="0.03"/>
          </radialGradient>
          <radialGradient id="fillL" cx="38%" cy="32%" r="72%">
            <stop offset="0%"   stopColor="#00aaff" stopOpacity="0.20"/>
            <stop offset="55%"  stopColor="#002299" stopOpacity="0.10"/>
            <stop offset="100%" stopColor="#000033" stopOpacity="0.03"/>
          </radialGradient>
          <radialGradient id="aura" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#003399" stopOpacity="0.42"/>
            <stop offset="65%"  stopColor="#001155" stopOpacity="0.15"/>
            <stop offset="100%" stopColor="#000000" stopOpacity="0"/>
          </radialGradient>

          {/* Stream motion paths */}
          {STREAM_DEFS.map(s=>(
            <path key={s.id} id={`sp-${s.id}`} d={s.d}/>
          ))}
        </defs>

        {/* ── Background aura ─────────────────────────── */}
        <ellipse cx="500" cy="370" rx="335" ry="290"
          fill="url(#aura)"
          style={{animation:'auraBreath 4s ease-in-out infinite'}}
        />

        {/* ── Stream trails (faint guide lines) ──────── */}
        {STREAM_DEFS.map(s=>(
          <path key={s.id} d={s.d} fill="none" stroke={s.color} strokeWidth="1.2" opacity="0.20"/>
        ))}

        {/* ── Stream particles ────────────────────────── */}
        {STREAM_DEFS.map(s=>(
          [0,1,2].map(i=>(
            <circle key={`${s.id}-${i}`} r="5.5" fill={s.color} filter="url(#gmd)">
              <animateMotion
                dur={`${s.dur}s`}
                repeatCount="indefinite"
                begin={`${i * (s.dur / 3)}s`}
                calcMode="spline"
                keySplines="0.3 0 0.7 1"
              >
                <mpath href={`#sp-${s.id}`}/>
              </animateMotion>
              <animate
                attributeName="opacity"
                values="0;0.95;0.95;0"
                keyTimes="0;0.06;0.90;1"
                dur={`${s.dur}s`}
                repeatCount="indefinite"
                begin={`${i * (s.dur / 3)}s`}
              />
            </circle>
          ))
        ))}

        {/* ── Brain fills ─────────────────────────────── */}
        <path
          d="M 500,520 C 502,610 650,630 696,580 C 742,530 768,478 770,400
             C 772,322 746,240 704,188 C 662,136 584,94 522,90
             C 510,88 500,104 500,152 C 500,300 500,420 500,520 Z"
          fill="url(#fillR)"
        />
        <path
          d="M 500,520 C 498,610 350,630 304,580 C 258,530 232,478 230,400
             C 228,322 254,240 296,188 C 338,136 416,94 478,90
             C 490,88 500,104 500,152 C 500,300 500,420 500,520 Z"
          fill="url(#fillL)"
        />

        {/* ── Brain outlines ──────────────────────────── */}
        {/* Right hemisphere */}
        <path
          d="M 500,520 C 502,610 650,630 696,580 C 742,530 768,478 770,400
             C 772,322 746,240 704,188 C 662,136 584,94 522,90
             C 510,88 500,104 500,152"
          fill="none" stroke="#00d8ff" strokeWidth="3" strokeLinecap="round"
          filter="url(#gxl)"
          style={{animation:'glowPulse 4s ease-in-out infinite'}}
        />
        {/* Left hemisphere */}
        <path
          d="M 500,520 C 498,610 350,630 304,580 C 258,530 232,478 230,400
             C 228,322 254,240 296,188 C 338,136 416,94 478,90
             C 490,88 500,104 500,152"
          fill="none" stroke="#00d8ff" strokeWidth="3" strokeLinecap="round"
          filter="url(#gxl)"
          style={{animation:'glowPulse2 4s ease-in-out infinite 0.6s'}}
        />

        {/* Interhemispheric fissure */}
        <line x1="500" y1="90" x2="500" y2="520"
          stroke="#00b8ff" strokeWidth="1.8" opacity="0.48" filter="url(#gsm)"/>

        {/* Brainstem */}
        <path
          d="M 474,522 C 470,574 470,594 486,606 C 494,612 506,612 514,606 C 530,594 530,574 526,522"
          fill="none" stroke="#00b8ff" strokeWidth="2.2" opacity="0.55" filter="url(#gsm)"
        />

        {/* ── Gyri (cortical folds) ───────────────────── */}
        <g style={{animation:'gyriFlicker 3.5s ease-in-out infinite'}} filter="url(#gsm)">
          <path d="M 522,100 C 530,160 533,232 524,312" fill="none" stroke="#00bcd4" strokeWidth="1.6"/>
          <path d="M 550,96  C 564,158 570,236 562,322" fill="none" stroke="#00aac4" strokeWidth="1.4"/>
          <path d="M 580,103 C 598,164 608,244 600,332" fill="none" stroke="#00bcd4" strokeWidth="1.6"/>
          <path d="M 614,122 C 635,180 644,260 638,346" fill="none" stroke="#00aac4" strokeWidth="1.4"/>
          <path d="M 648,164 C 668,218 675,288 666,366" fill="none" stroke="#00bcd4" strokeWidth="1.4"/>
          <path d="M 524,430 C 562,442 602,448 640,444" fill="none" stroke="#009eb4" strokeWidth="1.3"/>
          <path d="M 520,468 C 560,478 600,482 636,478" fill="none" stroke="#009eb4" strokeWidth="1.2"/>
          {/* Left (mirror) */}
          <path d="M 478,100 C 470,160 467,232 476,312" fill="none" stroke="#00bcd4" strokeWidth="1.6"/>
          <path d="M 450,96  C 436,158 430,236 438,322" fill="none" stroke="#00aac4" strokeWidth="1.4"/>
          <path d="M 420,103 C 402,164 392,244 400,332" fill="none" stroke="#00bcd4" strokeWidth="1.6"/>
          <path d="M 386,122 C 365,180 356,260 362,346" fill="none" stroke="#00aac4" strokeWidth="1.4"/>
          <path d="M 352,164 C 332,218 325,288 334,366" fill="none" stroke="#00bcd4" strokeWidth="1.4"/>
          <path d="M 476,430 C 438,442 398,448 360,444" fill="none" stroke="#009eb4" strokeWidth="1.3"/>
          <path d="M 480,468 C 440,478 400,482 364,478" fill="none" stroke="#009eb4" strokeWidth="1.2"/>
        </g>

        {/* ── Neural connections ──────────────────────── */}
        <g stroke="#00ccff" strokeWidth="0.9" opacity="0.28">
          {EDGES.map(([a,b],i)=>{
            const na=NODES[a]; const nb=NODES[b];
            return na&&nb
              ? <line key={i} x1={na[0]} y1={na[1]} x2={nb[0]} y2={nb[1]}/>
              : null;
          })}
        </g>

        {/* ── Neural nodes ────────────────────────────── */}
        <g filter="url(#gmd)">
          {NODES.map(([cx,cy,dur,delay],i)=>(
            <circle key={i} cx={cx} cy={cy} r="3.5" fill="#00eeff" opacity="0.7">
              <animate attributeName="r"       values="3;6;3"         dur={`${dur}s`} repeatCount="indefinite" begin={`${delay}s`}/>
              <animate attributeName="opacity" values="0.40;0.95;0.40" dur={`${dur}s`} repeatCount="indefinite" begin={`${delay}s`}/>
            </circle>
          ))}
        </g>
      </svg>
    </div>
  );
}
