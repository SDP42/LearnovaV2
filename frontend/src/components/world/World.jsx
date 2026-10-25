import { Suspense, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { glowTexture, rawTexture, visualTexture } from "./textures";

const FOG = "#EAF2FF";
const lerp = THREE.MathUtils.lerp;
const rng = (seed) => () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);

/** Camera waypoints keyed by page progress (0..1). pos / look are world coords. */
const KEYS = [
  [0.0, [0, 0.4, 12], [0, 0, 0]],
  [0.116, [1, 0.6, -6], [0, 0, -18]],
  [0.267, [-1.2, 0, -38], [0, 0, -52]],
  [0.34, [0, 0, -62], [0, 0, -76]],
  [0.42, [0, 0, -80], [0, 0, -95]],
  [0.5, [3.8, 0.4, -98], [-0.5, 0, -112]],
  [0.6, [-3.8, -0.2, -114], [0.5, 0, -128]],
  [0.7, [0, 2.8, -128], [0, 0, -142]],
  [0.8, [-3, 1, -136], [0, 0, -148]],
  [0.884, [3, 0.6, -134], [0, 0, -148]],
  [1.0, [0, 0.5, -138], [0, 0, -148]],
];
const mk = (i) => new THREE.CatmullRomCurve3(KEYS.map((k) => new THREE.Vector3(...k[i])), false, "catmullrom", 0.4);
const knotT = KEYS.map((k) => k[0]);

/** Map page progress → curve parameter honouring non-uniform keyframe spacing. */
function curveT(p) {
  for (let i = 0; i < knotT.length - 1; i++) {
    if (p <= knotT[i + 1]) {
      const f = (p - knotT[i]) / (knotT[i + 1] - knotT[i]);
      return (i + f) / (knotT.length - 1);
    }
  }
  return 1;
}

/** One InstancedMesh of identical-texture slides scattered around the flight corridor. */
function Field({ texture, count, z0, z1, seed, corridor = 2.0 }) {
  const ref = useRef();
  useLayoutEffect(() => {
    const r = rng(seed);
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const e = new THREE.Euler();
    for (let i = 0; i < count; i++) {
      const side = r() < 0.5 ? -1 : 1;
      const x = side * (corridor + r() * 6.5);
      const y = (r() - 0.5) * 6;
      const z = lerp(z0, z1, r());
      e.set((r() - 0.5) * 0.4, -side * (0.25 + r() * 0.6), (r() - 0.5) * 0.5);
      q.setFromEuler(e);
      const s = 0.9 + r() * 0.7;
      m.compose(new THREE.Vector3(x, y, z), q, new THREE.Vector3(s, s, s));
      ref.current.setMatrixAt(i, m);
    }
    ref.current.instanceMatrix.needsUpdate = true;
  }, [count, z0, z1, seed, corridor]);
  return (
    <instancedMesh ref={ref} args={[null, null, count]} frustumCulled={false}>
      <planeGeometry args={[3.2, 2]} />
      <meshBasicMaterial map={texture} side={THREE.DoubleSide} fog />
    </instancedMesh>
  );
}

function Gate({ z }) {
  const a = useRef();
  const b = useRef();
  const glow = useRef();
  const g = useMemo(() => glowTexture("#2563EB"), []);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    a.current.rotation.z = t * 0.5;
    b.current.rotation.z = -t * 0.8;
    const s = 1 + Math.sin(t * 2) * 0.04;
    a.current.scale.setScalar(s);
    glow.current.scale.setScalar(11 + Math.sin(t * 2) * 0.6);
  });
  return (
    <group position={[0, 0, z]}>
      <mesh ref={a}><torusGeometry args={[3.6, 0.09, 12, 96]} /><meshBasicMaterial color="#2563EB" fog /></mesh>
      <mesh ref={b}><torusGeometry args={[4.3, 0.05, 10, 96]} /><meshBasicMaterial color="#12C99B" fog /></mesh>
      <mesh><torusGeometry args={[3.0, 0.03, 8, 96]} /><meshBasicMaterial color="#FFC93C" fog /></mesh>
      <sprite ref={glow}><spriteMaterial map={g} transparent depthWrite={false} blending={THREE.AdditiveBlending} /></sprite>
    </group>
  );
}

function Finale({ z, textures }) {
  const orbit = useRef();
  const stack = useRef();
  useFrame((_, dt) => {
    orbit.current.rotation.y += dt * 0.25;
    stack.current.rotation.y = Math.sin(performance.now() / 2500) * 0.25;
  });
  return (
    <group position={[0, 0, z]}>
      <group ref={stack}>
        {[0, 1, 2, 3, 4].map((i) => (
          <mesh key={i} position={[(i - 2) * 1.5, 0, -i * 0.25]} rotation={[0, (2 - i) * 0.2, 0]}>
            <planeGeometry args={[3.4, 2.12]} />
            <meshBasicMaterial map={textures[i % textures.length]} side={THREE.DoubleSide} fog />
          </mesh>
        ))}
      </group>
      <group ref={orbit}>
        {Array.from({ length: 10 }, (_, i) => {
          const a = (i / 10) * Math.PI * 2;
          return (
            <mesh key={i} position={[Math.cos(a) * 7, Math.sin(i) * 0.8, Math.sin(a) * 7]} rotation={[0, -a + Math.PI / 2, 0]}>
              <planeGeometry args={[2.6, 1.62]} />
              <meshBasicMaterial map={textures[i % textures.length]} side={THREE.DoubleSide} fog />
            </mesh>
          );
        })}
      </group>
    </group>
  );
}

function Dust({ count }) {
  const pos = useMemo(() => {
    const r = rng(7);
    const a = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      a[i * 3] = (r() - 0.5) * 22;
      a[i * 3 + 1] = (r() - 0.5) * 12;
      a[i * 3 + 2] = lerp(14, -152, r());
    }
    return a;
  }, [count]);
  return (
    <points frustumCulled={false}>
      <bufferGeometry><bufferAttribute attach="attributes-position" array={pos} count={count} itemSize={3} /></bufferGeometry>
      <pointsMaterial size={0.07} color="#5B8CFF" transparent opacity={0.75} sizeAttenuation depthWrite={false} fog />
    </points>
  );
}

/** Flies the camera along the path as the page scrolls (native scroll, no JS scroller). */
function Rig() {
  const { camera, size } = useThree();
  const state = useRef({ p: 0, max: 1 });
  const curves = useMemo(() => [mk(1), mk(2)], []);
  const v1 = useMemo(() => new THREE.Vector3(), []);
  const v2 = useMemo(() => new THREE.Vector3(), []);
  useLayoutEffect(() => {
    const measure = () => (state.current.max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(document.body);
    return () => ro.disconnect();
  }, [size]);
  useFrame(({ pointer }, dt) => {
    const s = state.current;
    const target = Math.min(1, Math.max(0, window.scrollY / s.max));
    s.p = lerp(s.p, target, 1 - Math.exp(-dt * 5));
    const t = curveT(s.p);
    curves[0].getPoint(t, v1);
    curves[1].getPoint(t, v2);
    camera.position.set(v1.x + pointer.x * 0.5, v1.y + pointer.y * 0.3, v1.z);
    camera.lookAt(v2);
    camera.rotation.z += Math.sin(performance.now() / 3000) * 0.0004;
  });
  return null;
}

export default function World() {
  const small = typeof window !== "undefined" && window.innerWidth < 768;
  const raw = useMemo(() => [0, 1, 2].map(rawTexture), []);
  const vis = useMemo(() => [0, 1, 2, 3, 4, 5].map(visualTexture), []);
  return (
    <Canvas
      dpr={[1, small ? 1.25 : 1.6]}
      camera={{ fov: 55, near: 0.1, far: 120, position: [0, 0.4, 12] }}
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none" }}
    >
      <color attach="background" args={[FOG]} />
      <fog attach="fog" args={[FOG, 14, small ? 45 : 62]} />
      <Suspense fallback={null}>
        {raw.map((t, i) => <Field key={`r${i}`} texture={t} count={small ? 8 : 15} z0={-4} z1={-68} seed={11 + i} corridor={2.4} />)}
        <Gate z={-72} />
        {vis.map((t, i) => <Field key={`v${i}`} texture={t} count={small ? 5 : 8} z0={-76} z1={-132} seed={31 + i} corridor={1.6} />)}
        <Finale z={-148} textures={vis} />
        <Dust count={small ? 220 : 450} />
      </Suspense>
      <Rig />
    </Canvas>
  );
}
