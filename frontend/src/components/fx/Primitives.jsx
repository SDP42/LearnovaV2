/** Motion-primitives-style building blocks (text effects, trails, dock, progress, blur). */
import { useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useScroll, useSpring, useTransform } from "framer-motion";

const GLYPHS = "!<>-_\\/[]{}—=+*^?#01";

/** Scrambles into `text` when scrolled into view (Motion Primitives "Text Scramble"). */
export function TextScramble({ text, className = "", duration = 1100 }) {
  const [out, setOut] = useState(text);
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    let raf, started;
    const run = () => {
      const t0 = performance.now();
      const tick = (t) => {
        const k = Math.min(1, (t - t0) / duration);
        setOut(text.split("").map((c, i) => (c === " " || i < k * text.length ? c : GLYPHS[(Math.random() * GLYPHS.length) | 0])).join(""));
        if (k < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting && !started) { started = true; run(); } });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [text, duration]);
  return <span ref={ref} className={className} aria-label={text}>{out}</span>;
}

/** Light sweep across text ("Text Shimmer"). */
export function TextShimmer({ children, className = "" }) {
  return <span className={`fx-shimmer ${className}`}>{children}</span>;
}

/** Rotating light that trails the border ("Border Trail"). */
export function BorderTrail({ children, className = "" }) {
  return <span className={`fx-trail ${className}`}>{children}</span>;
}

/** Cursor-following glow that fills its parent ("Spotlight"). */
export function Spotlight({ size = 520, color = "rgba(91,75,255,.18)" }) {
  const ref = useRef(null);
  useEffect(() => {
    const parent = ref.current.parentElement;
    const move = (e) => {
      const r = parent.getBoundingClientRect();
      ref.current.style.background = `radial-gradient(${size}px circle at ${e.clientX - r.left}px ${e.clientY - r.top}px, ${color}, transparent 70%)`;
    };
    parent.addEventListener("pointermove", move);
    return () => parent.removeEventListener("pointermove", move);
  }, [size, color]);
  return <div ref={ref} aria-hidden style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />;
}

/** Thin gradient bar showing page progress ("Scroll Progress"). */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const x = useSpring(scrollYProgress, { stiffness: 140, damping: 24 });
  return <motion.div aria-hidden className="fx-progress" style={{ scaleX: x }} />;
}

/** Floating dock whose icons magnify toward the cursor ("Dock"). */
export function Dock({ items }) {
  const mx = useMotionValue(Infinity);
  return (
    <motion.nav className="fx-dock" onMouseMove={(e) => mx.set(e.clientX)} onMouseLeave={() => mx.set(Infinity)}>
      {items.map((it) => <DockItem key={it.label} mx={mx} {...it} />)}
    </motion.nav>
  );
}
function DockItem({ mx, label, href, icon: Icon, onClick }) {
  const ref = useRef(null);
  const dist = useTransform(mx, (v) => { const b = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 }; return v - b.x - b.width / 2; });
  const w = useSpring(useTransform(dist, [-120, 0, 120], [44, 72, 44]), { stiffness: 260, damping: 20 });
  return (
    <motion.a ref={ref} href={href} onClick={onClick} style={{ width: w, height: w }} className="fx-dock-item" title={label} aria-label={label}>
      <Icon size={20} />
      <span>{label}</span>
    </motion.a>
  );
}

/** Auto-scrolling slider that pauses on hover ("Infinite Slider"). */
export function InfiniteSlider({ children, gap = 16, duration = 40 }) {
  return (
    <div className="fx-slider">
      <div className="fx-slider-track" style={{ gap, animationDuration: `${duration}s` }}>
        {children}{children}
      </div>
    </div>
  );
}

/** Blurs content toward an edge ("Progressive Blur"). */
export function ProgressiveBlur({ side = "bottom", height = 90 }) {
  const dir = side === "bottom" ? "to bottom" : "to top";
  return (
    <div aria-hidden className="fx-pblur" style={{
      [side]: 0, height, backdropFilter: "blur(10px)",
      maskImage: `linear-gradient(${dir}, transparent, #000)`, WebkitMaskImage: `linear-gradient(${dir}, transparent, #000)`,
    }} />
  );
}
