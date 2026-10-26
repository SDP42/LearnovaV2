import { useEffect, useRef, useState } from "react";
import { animate, motion, useInView, useReducedMotion } from "framer-motion";

/**
 * Small motion kit for the signed-in app. Everything runs once, is transform /
 * opacity only (no layout thrash), and collapses to nothing for people who
 * ask for reduced motion.
 */

const container = (stagger, delay) => ({
  hidden: {},
  show: { transition: { staggerChildren: stagger, delayChildren: delay } },
});
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] } },
};

/** Parent that staggers its <StaggerItem> children in once, when it scrolls into view. */
export function Stagger({ as = "div", stagger = 0.05, delay = 0, className, children, ...rest }) {
  const reduce = useReducedMotion();
  const Comp = motion[as] || motion.div;
  const ref = useRef(null);
  const seen = useInView(ref, { once: true, margin: "0px 0px -8% 0px" });
  if (reduce) {
    const Plain = as;
    return (
      <Plain className={className} {...rest}>
        {children}
      </Plain>
    );
  }
  return (
    <Comp ref={ref} className={className} variants={container(stagger, delay)} initial="hidden" animate={seen ? "show" : "hidden"} {...rest}>
      {children}
    </Comp>
  );
}

/**
 * Child of <Stagger>. Keep hover-lift classes on an inner element: framer-motion
 * writes an inline `transform` here, which would otherwise beat `:hover` transforms.
 */
export function StaggerItem({ as = "div", className, children, ...rest }) {
  const reduce = useReducedMotion();
  const Comp = motion[as] || motion.div;
  if (reduce) {
    const Plain = as;
    return (
      <Plain className={className} {...rest}>
        {children}
      </Plain>
    );
  }
  return (
    <Comp className={className} variants={item} {...rest}>
      {children}
    </Comp>
  );
}

/** Counts up from 0 to `value` the first time it is seen; non-numbers render as-is. */
export function CountUp({ value, duration = 0.9, className, format = (n) => String(n) }) {
  const reduce = useReducedMotion();
  const ref = useRef(null);
  const seen = useInView(ref, { once: true });
  const numeric = typeof value === "number" && Number.isFinite(value);
  const [n, setN] = useState(0);

  useEffect(() => {
    if (!numeric) return undefined;
    if (reduce || !seen) {
      if (reduce) setN(value);
      return undefined;
    }
    const ctl = animate(0, value, { duration, ease: [0.22, 1, 0.36, 1], onUpdate: (v) => setN(Math.round(v)) });
    return () => ctl.stop();
  }, [value, numeric, seen, reduce, duration]);

  if (!numeric) return <span ref={ref} className={className}>{value}</span>;
  return (
    <span ref={ref} className={className} aria-label={String(value)}>
      {format(reduce ? value : n)}
    </span>
  );
}
