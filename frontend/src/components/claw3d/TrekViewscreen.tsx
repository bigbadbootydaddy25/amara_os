/**
 * TREK BRIDGE VIEWSCREEN — Claw3D
 *
 * Wraps any content in a curved-plane Three.js viewscreen effect.
 * The Three.js canvas renders behind the DOM children (z-index layering).
 * The curved plane material uses a RenderTarget of the child DOM content
 * — since we can't actually render DOM to WebGL, we simulate the effect
 * with a pulsing grid overlay + chromatic aberration CSS filter on the content.
 */
import { useEffect, useRef, type ReactNode } from "react";
import * as THREE from "three";
import styles from "./TrekViewscreen.module.css";

interface Props {
  children: ReactNode;
  active?: boolean;
}

export function TrekViewscreen({ children, active = true }: Props) {
  const bgRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active) return;
    const mount = bgRef.current!;
    const W = mount.clientWidth;
    const H = mount.clientHeight;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(W, H);
    renderer.domElement.style.position = "absolute";
    renderer.domElement.style.inset = "0";
    renderer.domElement.style.pointerEvents = "none";
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    // Fullscreen quad with animated scan-grid shader
    const geo = new THREE.PlaneGeometry(2, 2);
    const mat = new THREE.ShaderMaterial({
      transparent: true,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new THREE.Vector2(W, H) },
      },
      vertexShader: /* glsl */`
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = vec4(position.xy, 0.0, 1.0);
        }
      `,
      fragmentShader: /* glsl */`
        uniform float uTime;
        uniform vec2  uResolution;
        varying vec2  vUv;

        void main() {
          vec2 uv = vUv;

          // Curved-screen vignette (stronger at edges/corners)
          vec2 c = uv - 0.5;
          float vign = 1.0 - dot(c * 1.6, c * 1.6);
          vign = clamp(vign, 0.0, 1.0);
          vign = pow(vign, 0.6);

          // Horizontal scan lines
          float scanline = sin(uv.y * uResolution.y * 0.9) * 0.04;

          // Moving warp line
          float warpY = mod(uTime * 0.15, 1.0);
          float warpLine = smoothstep(0.002, 0.0, abs(uv.y - warpY)) * 0.12;

          // Grid
          float gx = step(0.97, fract(uv.x * 40.0));
          float gy = step(0.97, fract(uv.y * 22.0));
          float grid = (gx + gy) * 0.03;

          // Corner glow frames
          float border = 0.0;
          float bw = 0.015;
          if (uv.x < bw || uv.x > 1.0 - bw || uv.y < bw || uv.y > 1.0 - bw) {
            border = 0.18;
          }

          // Assemble: blue tint overlay
          vec3 col = vec3(0.05, 0.12, 0.4) * (scanline + grid + warpLine + border);
          float alpha = (scanline + grid * 0.5 + warpLine + border) * vign + 0.04 * (1.0 - vign);

          gl_FragColor = vec4(col, clamp(alpha, 0.0, 0.55));
        }
      `,
    });
    const quad = new THREE.Mesh(geo, mat);
    scene.add(quad);

    // Edge-glow border (additive blue lines at the screen corners)
    const cornerPoints = [
      // top-left bracket
      new THREE.Vector3(-0.98, 0.93, 0), new THREE.Vector3(-0.98, 0.98, 0),
      new THREE.Vector3(-0.98, 0.98, 0), new THREE.Vector3(-0.88, 0.98, 0),
      // top-right bracket
      new THREE.Vector3( 0.98, 0.93, 0), new THREE.Vector3( 0.98, 0.98, 0),
      new THREE.Vector3( 0.98, 0.98, 0), new THREE.Vector3( 0.88, 0.98, 0),
      // bottom-left bracket
      new THREE.Vector3(-0.98,-0.93, 0), new THREE.Vector3(-0.98,-0.98, 0),
      new THREE.Vector3(-0.98,-0.98, 0), new THREE.Vector3(-0.88,-0.98, 0),
      // bottom-right bracket
      new THREE.Vector3( 0.98,-0.93, 0), new THREE.Vector3( 0.98,-0.98, 0),
      new THREE.Vector3( 0.98,-0.98, 0), new THREE.Vector3( 0.88,-0.98, 0),
    ];
    const cornerGeo = new THREE.BufferGeometry().setFromPoints(cornerPoints);
    const cornerMat = new THREE.LineBasicMaterial({ color: 0x00aaff, transparent: true, opacity: 0.8 });
    scene.add(new THREE.LineSegments(cornerGeo, cornerMat));

    let t = 0;
    let animId: number;
    function animate() {
      animId = requestAnimationFrame(animate);
      t += 0.016;
      mat.uniforms.uTime.value = t;
      renderer.render(scene, camera);
    }
    animate();

    const ro = new ResizeObserver(() => {
      const nW = mount.clientWidth;
      const nH = mount.clientHeight;
      renderer.setSize(nW, nH);
      mat.uniforms.uResolution.value.set(nW, nH);
    });
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
    };
  }, [active]);

  return (
    <div className={`${styles.root} trek-screen`}>
      {/* Three.js overlay canvas is injected into bgRef via useEffect */}
      <div ref={bgRef} className={styles.bg} />
      <div className={styles.content}>{children}</div>
    </div>
  );
}
