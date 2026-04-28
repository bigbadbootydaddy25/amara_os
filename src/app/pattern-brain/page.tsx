'use client';

import { useEffect, useRef } from 'react';

interface NeuralNode {
  x: number;
  y: number;
  connections: number[];
  phase: number;
  speed: number;
}

interface StreamDef {
  sx: number;
  sy: number;
  ex: number;
  ey: number;
  r: number;
  g: number;
  b: number;
}

interface StreamParticle {
  streamIdx: number;
  progress: number;
  speed: number;
  size: number;
  trail: { x: number; y: number }[];
}

export default function PatternBrainPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let raf: number;
    let t = 0;
    let lastTs = 0;
    let energyLevel = 0;

    const nodes: NeuralNode[] = [];
    let streams: StreamParticle[] = [];

    const bc = () => ({ x: canvas.width / 2, y: canvas.height * 0.47 });
    const bs = () => Math.min(canvas.width, canvas.height) * 0.29;

    const inBrain = (px: number, py: number): boolean => {
      const c = bc();
      const s = bs();
      const dx = (px - c.x) / (s * 0.88);
      const dy = (py - c.y) / (s * 0.72);
      return dx * dx + dy * dy < 1.0;
    };

    const initNodes = () => {
      nodes.length = 0;
      const c = bc();
      const s = bs();
      let attempts = 0;
      while (nodes.length < 65 && attempts < 5000) {
        attempts++;
        const px = c.x + (Math.random() * 2 - 1) * s * 0.86;
        const py = c.y + (Math.random() * 2 - 1) * s * 0.70;
        if (inBrain(px, py)) {
          nodes.push({
            x: px,
            y: py,
            connections: [],
            phase: Math.random(),
            speed: 0.5 + Math.random() * 1.0,
          });
        }
      }
      const maxDist = s * 0.36;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          if (nodes[i].connections.length >= 5) break;
          if (nodes[j].connections.length >= 5) continue;
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          if (Math.sqrt(dx * dx + dy * dy) < maxDist) {
            nodes[i].connections.push(j);
          }
        }
      }
    };

    const STREAM_COLORS = [
      { r: 0, g: 245, b: 255 },
      { r: 168, g: 85, b: 247 },
      { r: 34, g: 211, b: 238 },
      { r: 74, g: 222, b: 128 },
      { r: 245, g: 158, b: 11 },
      { r: 236, g: 72, b: 153 },
      { r: 6, g: 182, b: 212 },
      { r: 124, g: 58, b: 237 },
    ];

    const getStreamDefs = (): StreamDef[] => {
      const c = bc();
      const w = canvas.width;
      const h = canvas.height;
      return [
        { sx: 0, sy: h * 0.25, ex: c.x, ey: c.y, ...STREAM_COLORS[0] },
        { sx: 0, sy: h * 0.65, ex: c.x, ey: c.y, ...STREAM_COLORS[1] },
        { sx: w, sy: h * 0.30, ex: c.x, ey: c.y, ...STREAM_COLORS[2] },
        { sx: w, sy: h * 0.70, ex: c.x, ey: c.y, ...STREAM_COLORS[3] },
        { sx: w * 0.25, sy: 0, ex: c.x, ey: c.y, ...STREAM_COLORS[4] },
        { sx: w * 0.75, sy: 0, ex: c.x, ey: c.y, ...STREAM_COLORS[5] },
        { sx: w * 0.25, sy: h, ex: c.x, ey: c.y, ...STREAM_COLORS[6] },
        { sx: w * 0.75, sy: h, ex: c.x, ey: c.y, ...STREAM_COLORS[7] },
      ];
    };

    const initStreams = () => {
      streams = [];
      for (let si = 0; si < 8; si++) {
        for (let j = 0; j < 3; j++) {
          streams.push({
            streamIdx: si,
            progress: j / 3 + Math.random() * 0.1,
            speed: 0.0022 + Math.random() * 0.0018,
            size: 1.8 + Math.random() * 1.8,
            trail: [],
          });
        }
      }
    };

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      initNodes();
      initStreams();
    };

    const drawBrain = () => {
      const c = bc();
      const growth = 1 + energyLevel * 0.028;
      const s = bs() * growth;
      const pulse = 1 + Math.sin(t * 0.75) * 0.01;
      const sp = s * pulse;

      ctx.save();

      const drawHemi = (flip: number) => {
        const ox = c.x + flip * sp * 0.03;
        const oy = c.y;

        const drawGyrus = (p: number[][], alpha: number) => {
          ctx.beginPath();
          ctx.moveTo(ox + flip * p[0][0] * sp, oy + p[0][1] * sp);
          ctx.bezierCurveTo(
            ox + flip * p[1][0] * sp, oy + p[1][1] * sp,
            ox + flip * p[2][0] * sp, oy + p[2][1] * sp,
            ox + flip * p[3][0] * sp, oy + p[3][1] * sp,
          );
          ctx.strokeStyle = `rgba(0,195,255,${alpha})`;
          ctx.lineWidth = 0.75;
          ctx.stroke();
        };

        // Main hemisphere outline
        ctx.beginPath();
        ctx.moveTo(ox, oy + sp * 0.40);
        ctx.bezierCurveTo(
          ox + flip * sp * 0.04, oy + sp * 0.68,
          ox + flip * sp * 0.50, oy + sp * 0.72,
          ox + flip * sp * 0.70, oy + sp * 0.50,
        );
        ctx.bezierCurveTo(
          ox + flip * sp * 0.86, oy + sp * 0.30,
          ox + flip * sp * 0.92, oy + sp * 0.02,
          ox + flip * sp * 0.84, oy - sp * 0.30,
        );
        ctx.bezierCurveTo(
          ox + flip * sp * 0.74, oy - sp * 0.58,
          ox + flip * sp * 0.48, oy - sp * 0.82,
          ox + flip * sp * 0.20, oy - sp * 0.84,
        );
        ctx.bezierCurveTo(
          ox + flip * sp * 0.05, oy - sp * 0.84,
          ox - flip * sp * 0.01, oy - sp * 0.70,
          ox, oy - sp * 0.44,
        );
        ctx.bezierCurveTo(
          ox - flip * sp * 0.01, oy - sp * 0.10,
          ox - flip * sp * 0.01, oy + sp * 0.20,
          ox, oy + sp * 0.40,
        );
        ctx.closePath();

        // Glass fill
        const grd = ctx.createRadialGradient(
          ox + flip * sp * 0.28, oy - sp * 0.28, 0,
          ox + flip * sp * 0.28, oy, sp,
        );
        grd.addColorStop(0, `rgba(0,230,255,${0.11 + energyLevel * 0.07})`);
        grd.addColorStop(0.5, `rgba(0,100,200,${0.05 + energyLevel * 0.03})`);
        grd.addColorStop(1, 'rgba(0,10,60,0.02)');
        ctx.fillStyle = grd;
        ctx.fill();

        // Glowing outer stroke
        ctx.shadowBlur = 18 + energyLevel * 22;
        ctx.shadowColor = `rgba(0,200,255,${0.5 + energyLevel * 0.3})`;
        ctx.strokeStyle = `rgba(0,210,255,${0.44 + Math.sin(t * 0.9 + flip * 0.3) * 0.07 + energyLevel * 0.15})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Gyri (cortical folds)
        const gyA = 0.15 + Math.sin(t * 0.55) * 0.04;
        drawGyrus([[0.10, -0.60], [0.13, -0.35], [0.15, -0.10], [0.15, 0.06]], gyA);
        drawGyrus([[0.28, -0.72], [0.35, -0.44], [0.40, -0.14], [0.38, 0.12]], gyA * 0.85);
        drawGyrus([[0.48, -0.74], [0.56, -0.44], [0.62, -0.12], [0.60, 0.20]], gyA);
        drawGyrus([[0.68, -0.50], [0.74, -0.24], [0.74, 0.04], [0.68, 0.28]], gyA * 0.8);
        drawGyrus([[0.20, 0.28], [0.40, 0.34], [0.56, 0.36], [0.64, 0.32]], gyA * 0.75);

        // Glass highlight (top-left shimmer)
        const hx = ox + flip * sp * 0.18;
        const hy = oy - sp * 0.58;
        const hgrd = ctx.createRadialGradient(hx, hy, 0, hx, hy, sp * 0.30);
        hgrd.addColorStop(0, 'rgba(200,245,255,0.08)');
        hgrd.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = hgrd;
        ctx.beginPath();
        ctx.ellipse(hx, hy, sp * 0.20, sp * 0.12, flip * -0.3, 0, Math.PI * 2);
        ctx.fill();
      };

      drawHemi(1);
      drawHemi(-1);

      // Interhemispheric fissure
      ctx.beginPath();
      ctx.moveTo(c.x, c.y - sp * 0.44);
      ctx.lineTo(c.x, c.y + sp * 0.40);
      ctx.strokeStyle = 'rgba(0,180,255,0.22)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Brainstem
      ctx.beginPath();
      ctx.moveTo(c.x - sp * 0.10, c.y + sp * 0.54);
      ctx.bezierCurveTo(
        c.x - sp * 0.07, c.y + sp * 0.72,
        c.x + sp * 0.07, c.y + sp * 0.72,
        c.x + sp * 0.10, c.y + sp * 0.54,
      );
      ctx.strokeStyle = 'rgba(0,180,255,0.28)';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.restore();
    };

    const drawNeural = (dt: number) => {
      ctx.save();

      nodes.forEach((n) => {
        n.phase = (n.phase + dt * n.speed) % 1;
      });

      nodes.forEach((n) => {
        n.connections.forEach((j) => {
          const m = nodes[j];
          if (!m) return;
          const alpha = 0.04 + Math.max(Math.sin(n.phase * Math.PI * 2), 0) * 0.10;

          ctx.beginPath();
          ctx.moveTo(n.x, n.y);
          ctx.lineTo(m.x, m.y);
          ctx.strokeStyle = `rgba(0,200,255,${alpha})`;
          ctx.lineWidth = 0.45;
          ctx.stroke();

          const prog = n.phase;
          const px = n.x + (m.x - n.x) * prog;
          const py = n.y + (m.y - n.y) * prog;
          ctx.beginPath();
          ctx.arc(px, py, 0.7, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(100,240,255,${0.30 + prog * 0.25})`;
          ctx.fill();
        });
      });

      nodes.forEach((n) => {
        const glow = 0.38 + Math.sin(n.phase * Math.PI * 2) * 0.32;
        ctx.shadowBlur = 5;
        ctx.shadowColor = '#00e0ff';
        ctx.beginPath();
        ctx.arc(n.x, n.y, 1.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0,220,255,${glow})`;
        ctx.fill();
      });

      ctx.restore();
    };

    const drawStreams = () => {
      const defs = getStreamDefs();
      ctx.save();

      streams.forEach((sp) => {
        const def = defs[sp.streamIdx];
        if (!def) return;

        sp.progress += sp.speed;
        if (sp.progress >= 1.0) {
          sp.progress = 0;
          sp.trail = [];
          energyLevel = Math.min(1, energyLevel + 0.12);
          return;
        }

        const et = sp.progress * sp.progress * (3 - 2 * sp.progress);
        const x = def.sx + (def.ex - def.sx) * et;
        const y = def.sy + (def.ey - def.sy) * et;

        sp.trail.push({ x, y });
        if (sp.trail.length > 28) sp.trail.shift();

        for (let k = 1; k < sp.trail.length; k++) {
          const alpha = (k / sp.trail.length) * 0.55;
          ctx.beginPath();
          ctx.moveTo(sp.trail[k - 1].x, sp.trail[k - 1].y);
          ctx.lineTo(sp.trail[k].x, sp.trail[k].y);
          ctx.strokeStyle = `rgba(${def.r},${def.g},${def.b},${alpha})`;
          ctx.lineWidth = sp.size * (k / sp.trail.length) * 0.75;
          ctx.shadowBlur = 5;
          ctx.shadowColor = `rgba(${def.r},${def.g},${def.b},0.8)`;
          ctx.stroke();
        }

        ctx.shadowBlur = 12;
        ctx.shadowColor = `rgba(${def.r},${def.g},${def.b},1)`;
        ctx.beginPath();
        ctx.arc(x, y, sp.size * 0.85, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${def.r},${def.g},${def.b},0.9)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      ctx.restore();
    };

    const render = (ts: number) => {
      const dt = Math.min((ts - lastTs) / 1000, 0.05);
      lastTs = ts;
      t += dt;
      energyLevel = Math.max(0, energyLevel - dt * 0.35);

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#000000';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      drawStreams();
      drawBrain();
      drawNeural(dt);

      raf = requestAnimationFrame(render);
    };

    resize();
    window.addEventListener('resize', resize);
    raf = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000000', overflow: 'hidden' }}>
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
    </div>
  );
}
