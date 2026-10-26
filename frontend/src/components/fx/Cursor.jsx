import { useEffect, useRef } from "react";

// Anything the pointer can act on swells the dot (the inverted amber state in styles.css).
const ACTIVE = 'a, button, [role="button"], input, textarea, select, label, summary, [data-cursor="active"]';

/**
 * The landing page's custom cursor: an ink dot with an amber ring that follows the pointer exactly (no easing, so
 * it never trails the real one) and swells into an amber fill with a black edge over anything clickable.
 *
 * Only runs on a fine pointer with motion allowed; touch and reduced-motion visitors keep the native cursor.
 */
export default function Cursor() {
  const dot = useRef(null);

  useEffect(() => {
    const el = dot.current;
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!el || !fine || calm) return undefined;

    const root = document.documentElement;
    root.classList.add("has-custom-cursor");
    let x = -100;
    let y = -100;
    let frame = 0;
    const paint = () => {
      frame = 0;
      el.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`;
    };
    const move = (e) => {
      x = e.clientX;
      y = e.clientY;
      el.classList.remove("is-hidden");
      el.classList.toggle("is-active", Boolean(e.target.closest && e.target.closest(ACTIVE)));
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const hide = () => el.classList.add("is-hidden");
    const press = () => { el.style.scale = "0.82"; };
    const release = () => { el.style.scale = ""; };

    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerdown", press, { passive: true });
    window.addEventListener("pointerup", release, { passive: true });
    document.addEventListener("pointerleave", hide);
    window.addEventListener("blur", hide);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", press);
      window.removeEventListener("pointerup", release);
      document.removeEventListener("pointerleave", hide);
      window.removeEventListener("blur", hide);
      if (frame) cancelAnimationFrame(frame);
      root.classList.remove("has-custom-cursor");
    };
  }, []);

  return <div ref={dot} className="cursor-dot is-hidden" aria-hidden="true" />;
}
