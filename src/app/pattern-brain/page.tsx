'use client';

import { useEffect, useRef } from 'react';

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
    let energyPulse = 0; // 0-1, spikes when streams arrive

    // ─── Canvas sizing with DPR ─────────────────────────────────────
    let W = 0;
    let H = 0;
    let dpr = 1;

    const resize = () => {
      dpr = window.devicePixelRatio || 1;
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      rebuildNodes();
      rebuildStreams();
    };

    // ─── Brain geometry (CSS-pixel space) ───────────────────────────
    const cx = () => W / 2;
    const cy = () => H * 0.46;
    const sc = () => Math.min(W, H) * 0.30;

    // ─── Neural nodes ───────────────────────────────────────────────
    interface Node { x: number; y: number; links: number[]; phase: number; spd: number }
    let nodes: Node[] = [];

    // Ellipse inclusion test for brain interior
    const inBrain = (px: number, py: number) => {
      const dx = (px - cx()) / (sc() * 0.87);
      const dy = (py - cy()) / (sc() * 0.70);
      return dx * dx + dy * dy < 1;
    };

    const rebuildNodes = () => {
      nodes = [];
      let tries = 0;
      while (nodes.length < 70 && tries < 8000) {
        tries++;
        const px = cx() + (Math.random() * 2 - 1) * sc() * 0.85;
        const py = cy() + (Math.random() * 2 - 1) * sc() * 0.68;
        if (inBrain(px, py)) {
          nodes.push({ x: px, y: py, links: [], phase: Math.random(), spd: 0.4 + Math.random() });
        }
      }
      const maxD = sc() * 0.34;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          if (nodes[i].links.length >= 5) break;
          if (nodes[j].links.length >= 5) continue;
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          if (Math.sqrt(dx * dx + dy * dy) < maxD) nodes[i].links.push(j);
        }
      }
    };

    // ─── Energy streams ─────────────────────────────────────────────
    const COLORS = [
      [0, 245, 255],   // cyan
      [168, 85, 247],  // violet
      [34, 211, 238],  // sky
      [74, 222, 128],  // green
      [245, 158, 11],  // amber
      [236, 72, 153],  // pink
      [6, 182, 212],   // teal
      [139, 92, 246],  // purple
    ] as const;

    interface Stream { sx: number; sy: number; r: number; g: number; b: number; progress: number; speed: number; size: number; trail: {x:number;y:number}[] }
    let streams: Stream[] = [];

    const rebuildStreams = () => {
      streams = [];
      const origins = [
        [0,      H * 0.22],
        [0,      H * 0.62],
        [W,      H * 0.28],
        [W,      H * 0.68],
        [W*0.25, 0],
        [W*0.75, 0],
        [W*0.22, H],
        [W*0.78, H],
      ];
      origins.forEach(([sx, sy], i) => {
        const [r, g, b] = COLORS[i % COLORS.length];
        for (let j = 0; j < 3; j++) {
          streams.push({ sx, sy, r, g, b, progress: j / 3 + Math.random() * 0.1, speed: 0.0020 + Math.random() * 0.0018, size: 2 + Math.random() * 2, trail: [] });
        }
      });
    };

    // ─── Draw background glow behind brain ─────────────────────────
    const drawBrainGlow = () => {
      const g = ctx.createRadialGradient(cx(), cy(), 0, cx(), cy(), sc() * 1.1);
      g.addColorStop(0, `rgba(0,60,120,${0.22 + energyPulse * 0.18})`);
      g.addColorStop(0.6, `rgba(0,20,60,${0.10 + energyPulse * 0.08})`);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.ellipse(cx(), cy(), sc() * 1.1, sc() * 0.95, 0, 0, Math.PI * 2);
      ctx.fill();
    };

    // ─── Draw brain ─────────────────────────────────────────────────
    const drawBrain = () => {
      const bx = cx();
      const by = cy();
      const grow = 1 + energyPulse * 0.025;
      const s = sc() * grow * (1 + Math.sin(t * 0.7) * 0.008);

      // Each hemisphere: flip=+1 right, flip=-1 left
      const drawHemi = (flip: number) => {
        const ox = bx + flip * s * 0.025;

        // ── Hemisphere silhouette ────────────────────────────────
        ctx.beginPath();
        ctx.moveTo(ox, by + s * 0.38);

        // temporal lobe → bottom
        ctx.bezierCurveTo(
          ox + flip * s * 0.03, by + s * 0.68,
          ox + flip * s * 0.48, by + s * 0.73,
          ox + flip * s * 0.70, by + s * 0.52,
        );
        // lower lateral
        ctx.bezierCurveTo(
          ox + flip * s * 0.86, by + s * 0.32,
          ox + flip * s * 0.93, by + s * 0.04,
          ox + flip * s * 0.86, by - s * 0.28,
        );
        // upper parietal bump
        ctx.bezierCurveTo(
          ox + flip * s * 0.76, by - s * 0.58,
          ox + flip * s * 0.50, by - s * 0.83,
          ox + flip * s * 0.22, by - s * 0.85,
        );
        // frontal lobe
        ctx.bezierCurveTo(
          ox + flip * s * 0.06, by - s * 0.85,
          ox - flip * s * 0.01, by - s * 0.70,
          ox, by - s * 0.44,
        );
        // corpus callosum side
        ctx.bezierCurveTo(
          ox - flip * s * 0.01, by - s * 0.10,
          ox - flip * s * 0.01, by + s * 0.18,
          ox, by + s * 0.38,
        );
        ctx.closePath();

        // Fill — dark glass
        const fillG = ctx.createRadialGradient(
          ox + flip * s * 0.30, by - s * 0.25, 0,
          ox + flip * s * 0.30, by, s * 1.1,
        );
        fillG.addColorStop(0, `rgba(0,180,255,${0.18 + energyPulse * 0.10})`);
        fillG.addColorStop(0.45, `rgba(0,80,180,${0.10 + energyPulse * 0.05})`);
        fillG.addColorStop(1, 'rgba(0,0,40,0.04)');
        ctx.fillStyle = fillG;
        ctx.fill();

        // Outer glow stroke — BRIGHT, clearly visible
        ctx.shadowBlur = 28 + energyPulse * 30;
        ctx.shadowColor = `rgba(0,210,255,${0.8 + energyPulse * 0.2})`;
        ctx.strokeStyle = `rgba(0,220,255,${0.82 + energyPulse * 0.18})`;
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Second inner stroke for depth
        ctx.strokeStyle = `rgba(0,180,255,0.30)`;
        ctx.lineWidth = 1;
        ctx.stroke();

        // ── Gyri (cortical folds) ────────────────────────────────
        const gyA = 0.45 + Math.sin(t * 0.5) * 0.08;

        const gyrus = (pts: [number, number][]) => {
          ctx.beginPath();
          ctx.moveTo(ox + flip * pts[0][0] * s, by + pts[0][1] * s);
          ctx.bezierCurveTo(
            ox + flip * pts[1][0] * s, by + pts[1][1] * s,
            ox + flip * pts[2][0] * s, by + pts[2][1] * s,
            ox + flip * pts[3][0] * s, by + pts[3][1] * s,
          );
          ctx.shadowBlur = 6;
          ctx.shadowColor = 'rgba(0,200,255,0.4)';
          ctx.strokeStyle = `rgba(0,200,255,${gyA})`;
          ctx.lineWidth = 1.2;
          ctx.stroke();
          ctx.shadowBlur = 0;
        };

        gyrus([[0.10, -0.58], [0.13, -0.33], [0.14, -0.08], [0.14, 0.08]]);
        gyrus([[0.28, -0.71], [0.35, -0.43], [0.40, -0.14], [0.38, 0.14]]);
        gyrus([[0.48, -0.74], [0.57, -0.45], [0.62, -0.13], [0.60, 0.22]]);
        gyrus([[0.66, -0.52], [0.72, -0.26], [0.74, 0.02], [0.70, 0.28]]);
        gyrus([[0.20, 0.28], [0.40, 0.35], [0.56, 0.38], [0.65, 0.34]]);

        // ── Specular highlight (top-left glass shine) ─────────────
        const hx = ox + flip * s * 0.18;
        const hy = by - s * 0.58;
        const hg = ctx.createRadialGradient(hx, hy, 0, hx, hy, s * 0.28);
        hg.addColorStop(0, 'rgba(180,240,255,0.12)');
        hg.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = hg;
        ctx.beginPath();
        ctx.ellipse(hx, hy, s * 0.18, s * 0.10, flip * -0.28, 0, Math.PI * 2);
        ctx.fill();
      };

      ctx.save();
      drawHemi(1);
      drawHemi(-1);

      // Interhemispheric fissure
      ctx.beginPath();
      ctx.moveTo(bx, by - s * 0.44);
      ctx.lineTo(bx, by + s * 0.38);
      ctx.strokeStyle = 'rgba(0,200,255,0.35)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Brainstem
      ctx.beginPath();
      ctx.moveTo(bx - s * 0.11, by + s * 0.52);
      ctx.bezierCurveTo(bx - s * 0.07, by + s * 0.74, bx + s * 0.07, by + s * 0.74, bx + s * 0.11, by + s * 0.52);
      ctx.strokeStyle = 'rgba(0,190,255,0.40)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.restore();
    };

    // ─── Draw neural network ─────────────────────────────────────────
    const drawNeural = (dt: number) => {
      ctx.save();

      nodes.forEach(n => { n.phase = (n.phase + dt * n.spd) % 1; });

      // Connections + traveling signal
      nodes.forEach(n => {
        n.links.forEach(j => {
          const m = nodes[j];
          if (!m) return;
          const pulse = Math.max(Math.sin(n.phase * Math.PI * 2), 0);
          ctx.beginPath();
          ctx.moveTo(n.x, n.y);
          ctx.lineTo(m.x, m.y);
          ctx.strokeStyle = `rgba(0,200,255,${0.06 + pulse * 0.12})`;
          ctx.lineWidth = 0.6;
          ctx.stroke();

          // Signal dot
          const px = n.x + (m.x - n.x) * n.phase;
          const py = n.y + (m.y - n.y) * n.phase;
          ctx.beginPath();
          ctx.arc(px, py, 1.0, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(120,240,255,${0.4 + pulse * 0.3})`;
          ctx.fill();
        });
      });

      // Node dots
      nodes.forEach(n => {
        const g = 0.45 + Math.sin(n.phase * Math.PI * 2) * 0.35;
        ctx.shadowBlur = 8;
        ctx.shadowColor = '#00e8ff';
        ctx.beginPath();
        ctx.arc(n.x, n.y, 2.2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0,230,255,${g})`;
        ctx.fill();
      });

      ctx.restore();
    };

    // ─── Draw energy streams ─────────────────────────────────────────
    const drawStreams = () => {
      ctx.save();
      streams.forEach(sp => {
        sp.progress += sp.speed;
        if (sp.progress >= 1) {
          sp.progress = 0;
          sp.trail = [];
          energyPulse = Math.min(1, energyPulse + 0.18);
          return;
        }
        const et = sp.progress * sp.progress * (3 - 2 * sp.progress);
        const x = sp.sx + (cx() - sp.sx) * et;
        const y = sp.sy + (cy() - sp.sy) * et;

        sp.trail.push({ x, y });
        if (sp.trail.length > 30) sp.trail.shift();

        // Trail
        for (let k = 1; k < sp.trail.length; k++) {
          const a = (k / sp.trail.length) * 0.6;
          ctx.beginPath();
          ctx.moveTo(sp.trail[k - 1].x, sp.trail[k - 1].y);
          ctx.lineTo(sp.trail[k].x, sp.trail[k].y);
          ctx.strokeStyle = `rgba(${sp.r},${sp.g},${sp.b},${a})`;
          ctx.lineWidth = sp.size * (k / sp.trail.length) * 0.8;
          ctx.shadowBlur = 6;
          ctx.shadowColor = `rgba(${sp.r},${sp.g},${sp.b},0.9)`;
          ctx.stroke();
        }

        // Head
        ctx.shadowBlur = 16;
        ctx.shadowColor = `rgba(${sp.r},${sp.g},${sp.b},1)`;
        ctx.beginPath();
        ctx.arc(x, y, sp.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${sp.r},${sp.g},${sp.b},0.95)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      });
      ctx.restore();
    };

    // ─── Render loop ─────────────────────────────────────────────────
    const render = (ts: number) => {
      const dt = Math.min((ts - lastTs) / 1000, 0.05);
      lastTs = ts;
      t += dt;
      energyPulse = Math.max(0, energyPulse - dt * 0.5);

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, W, H);

      drawBrainGlow();
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
    <div style={{ position: 'fixed', inset: 0, background: '#000', overflow: 'hidden' }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
