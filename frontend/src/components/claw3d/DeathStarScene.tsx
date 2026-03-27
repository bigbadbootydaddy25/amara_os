/**
 * DEATH STAR × TREK BRIDGE — Claw3D
 *
 * Three.js canvas:
 *  - Death Star sphere orbiting in the corner (radial laser dish groove)
 *  - Ambient neon starfield
 *  - Exports refs so parent can feed in "distress parcel" data for holographic pins
 */
import { useEffect, useRef } from "react";
import * as THREE from "three";
import styles from "./DeathStarScene.module.css";

interface Props {
  /** When true the orb pulses red (critical deal found) */
  alert?: boolean;
}

export function DeathStarScene({ alert = false }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const alertRef = useRef(alert);
  alertRef.current = alert;

  useEffect(() => {
    const mount = mountRef.current!;
    const W = mount.clientWidth;
    const H = mount.clientHeight;

    // ── Renderer ──────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.shadowMap.enabled = true;
    mount.appendChild(renderer.domElement);

    // ── Scene + Camera ────────────────────────────────────────────
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 200);
    camera.position.set(0, 0, 5);

    // ── Starfield ─────────────────────────────────────────────────
    const starGeo = new THREE.BufferGeometry();
    const starCount = 1200;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i++) {
      starPos[i] = (Math.random() - 0.5) * 80;
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({ color: 0x88aaff, size: 0.06, transparent: true, opacity: 0.7 });
    scene.add(new THREE.Points(starGeo, starMat));

    // ── Death Star ────────────────────────────────────────────────
    const dsGroup = new THREE.Group();
    scene.add(dsGroup);

    // Body
    const dsGeo = new THREE.SphereGeometry(1, 64, 64);
    const dsMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a22,
      roughness: 0.75,
      metalness: 0.4,
    });
    const dsMesh = new THREE.Mesh(dsGeo, dsMat);
    dsGroup.add(dsMesh);

    // Equatorial trench (torus ring)
    const trenchGeo = new THREE.TorusGeometry(1.005, 0.012, 8, 128);
    const trenchMat = new THREE.MeshStandardMaterial({ color: 0x333344, roughness: 1 });
    dsGroup.add(new THREE.Mesh(trenchGeo, trenchMat));

    // Laser dish (flat disc depression)
    const dishGeo = new THREE.CircleGeometry(0.25, 32);
    const dishMat = new THREE.MeshStandardMaterial({
      color: 0x446688,
      emissive: 0x001133,
      roughness: 0.3,
      metalness: 0.8,
    });
    const dish = new THREE.Mesh(dishGeo, dishMat);
    dish.position.set(0.6, 0.5, 0.78);
    dish.lookAt(0, 0, 0);
    dsGroup.add(dish);

    // Dish glow ring
    const dishRingGeo = new THREE.RingGeometry(0.24, 0.27, 32);
    const dishRingMat = new THREE.MeshBasicMaterial({ color: 0x2266ff, side: THREE.DoubleSide, transparent: true, opacity: 0.6 });
    const dishRing = new THREE.Mesh(dishRingGeo, dishRingMat);
    dishRing.position.set(0.6, 0.5, 0.782);
    dishRing.lookAt(0, 0, 0);
    dsGroup.add(dishRing);

    // Grid lines on surface (longitude/latitude scratches using line segments)
    const lineMat = new THREE.LineBasicMaterial({ color: 0x2a2a3a, transparent: true, opacity: 0.5 });
    for (let lat = -4; lat <= 4; lat++) {
      const pts: THREE.Vector3[] = [];
      const phi = (lat / 4) * (Math.PI / 2.4);
      for (let t = 0; t <= 64; t++) {
        const theta = (t / 64) * Math.PI * 2;
        pts.push(new THREE.Vector3(
          1.01 * Math.cos(phi) * Math.cos(theta),
          1.01 * Math.sin(phi),
          1.01 * Math.cos(phi) * Math.sin(theta)
        ));
      }
      const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
      dsGroup.add(new THREE.Line(lineGeo, lineMat));
    }

    // Position sphere in upper-right area
    dsGroup.position.set(2.2, 1.4, 0);

    // ── Orbit path (ring around the DS) ──────────────────────────
    const orbitRingGeo = new THREE.TorusGeometry(1.6, 0.005, 6, 128);
    const orbitRingMat = new THREE.LineBasicMaterial({ color: 0x223355, transparent: true, opacity: 0.3 });
    const orbitRing = new THREE.Mesh(orbitRingGeo, new THREE.MeshBasicMaterial({ color: 0x223355, transparent: true, opacity: 0.15, wireframe: true }));
    orbitRing.rotation.x = Math.PI / 2.5;
    orbitRing.position.copy(dsGroup.position);
    scene.add(orbitRing);

    // Small companion moon orbiting DS
    const moonGeo = new THREE.SphereGeometry(0.08, 16, 16);
    const moonMat = new THREE.MeshStandardMaterial({ color: 0x334455, roughness: 0.9 });
    const moon = new THREE.Mesh(moonGeo, moonMat);
    dsGroup.add(moon);

    // ── Lighting ──────────────────────────────────────────────────
    const ambient = new THREE.AmbientLight(0x111122, 0.8);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0x4466ff, 2.5);
    keyLight.position.set(-3, 3, 4);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0xff3300, 0.4);
    rimLight.position.set(3, -2, -2);
    scene.add(rimLight);

    // Laser glow point light in dish
    const dishLight = new THREE.PointLight(0x2266ff, 1.5, 1.2);
    dishLight.position.set(0.6, 0.5, 0.9);
    dsGroup.add(dishLight);

    // ── Animation loop ────────────────────────────────────────────
    let frame = 0;
    let animId: number;

    function animate() {
      animId = requestAnimationFrame(animate);
      frame += 0.005;

      // Slow DS rotation
      dsGroup.rotation.y += 0.0015;
      dsGroup.rotation.x = Math.sin(frame * 0.3) * 0.04;

      // Moon orbit
      moon.position.set(
        Math.cos(frame * 2.5) * 1.4,
        Math.sin(frame * 0.8) * 0.3,
        Math.sin(frame * 2.5) * 1.4
      );

      // Dish glow pulse
      const pulse = 0.5 + 0.5 * Math.sin(frame * 4);
      dishLight.intensity = alertRef.current ? 3 + pulse * 3 : 1 + pulse * 0.8;
      dishLight.color.setHex(alertRef.current ? 0xff2200 : 0x2266ff);
      (dishRingMat as THREE.MeshBasicMaterial).color.setHex(alertRef.current ? 0xff3300 : 0x2266ff);
      (dishRingMat as THREE.MeshBasicMaterial).opacity = 0.4 + pulse * 0.5;

      // Star twinkle
      starMat.opacity = 0.5 + Math.sin(frame * 0.7) * 0.2;

      renderer.render(scene, camera);
    }
    animate();

    // ── Resize handler ────────────────────────────────────────────
    const onResize = () => {
      const nW = mount.clientWidth;
      const nH = mount.clientHeight;
      camera.aspect = nW / nH;
      camera.updateProjectionMatrix();
      renderer.setSize(nW, nH);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, []);

  return <div ref={mountRef} className={styles.canvas} />;
}
