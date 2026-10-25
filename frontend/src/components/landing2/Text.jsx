import { useEffect, useRef, useState } from "react";
import { motion, useInView, useScroll, useTransform } from "framer-motion";

/** Characters rise out of a mask line; hovering a letter makes it jump. */
export function SplitChars({ text, className = "", delay = 0, as: Tag = "h2" }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-12% 0px" });
  return (
    <Tag ref={ref} className={`sp ${className}`} aria-label={text}>
      {text.split(" ").map((w, wi) => (
        <span key={wi} className="sp-w" aria-hidden>
          {w.split("").map((c, ci) => (
            <span key={ci} className="sp-m">
              <motion.span className="sp-c" initial={{ y: "115%" }} animate={inView ? { y: 0 } : {}}
                transition={{ duration: 0.8, delay: delay + (wi * 4 + ci) * 0.025, ease: [0.22, 1, 0.36, 1] }}
                whileHover={{ y: "-18%", transition: { duration: 0.15 } }}>
                {c}
              </motion.span>
            </span>
          ))}
          &nbsp;
        </span>
      ))}
    </Tag>
  );
}

/** A line that wipes in from behind a mask. */
export function MaskLine({ children, delay = 0, className = "" }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-10% 0px" });
  return (
    <span ref={ref} className={`ml ${className}`}>
      <motion.span className="ml-in" initial={{ y: "110%" }} animate={inView ? { y: 0 } : {}} transition={{ duration: 0.9, delay, ease: [0.22, 1, 0.36, 1] }}>
        {children}
      </motion.span>
    </span>
  );
}

function Word({ w, progress, range }) {
  const o = useTransform(progress, range, [0.14, 1]);
  const y = useTransform(progress, range, [8, 0]);
  return <motion.span style={{ opacity: o, y }} className="ws-w">{w}&nbsp;</motion.span>;
}

/** Words light up one by one as you scroll through the section. */
export function WordScrub({ text }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.8", "end 0.55"] });
  const words = text.split(" ");
  return (
    <p ref={ref} className="ws">
      {words.map((w, i) => <Word key={i} w={w} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]} />)}
    </p>
  );
}

/** Cycles through words on a timer with a vertical slide. */
export function WordCycle({ words, every = 2200 }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % words.length), every);
    return () => clearInterval(t);
  }, [words.length, every]);
  return (
    <span className="wc" aria-label={words.join(", ")}>
      <motion.span className="wc-col" animate={{ y: `${-i * (100 / words.length)}%` }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}>
        {words.map((w) => <span key={w}>{w}</span>)}
      </motion.span>
    </span>
  );
}
