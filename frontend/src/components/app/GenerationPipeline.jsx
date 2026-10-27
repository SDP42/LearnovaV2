import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, animate, motion, useReducedMotion } from "framer-motion";
import { BookOpenText, Brain, Check, LayoutPanelTop, ListChecks, PackageCheck, Play, RotateCcw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Generation screen. Props contract (unchanged from the old stepper):
 *   stage    backend stage name from api.getJob().stage
 *   progress 0..1 within the stage
 *   status   "running" | "done" | "failed"
 * Optional: title, error, onOpen, onPresent, onRetry.
 */
const PHASES = [
  { key: "read", label: "Reading", sub: "Pulling text, figures and structure", icon: BookOpenText, stages: ["convert", "chunk", "vision_ocr", "index"] },
  { key: "understand", label: "Understanding", sub: "Finding the ideas and how they connect", icon: Brain, stages: ["layout", "visual_plan", "visual_data", "expand", "enhance", "density"] },
  { key: "design", label: "Designing", sub: "Illustrating and scoring every slide", icon: LayoutPanelTop, stages: ["illustrate", "labs", "score"] },
  { key: "quiz", label: "Quizzing", sub: "Writing checkpoint questions", icon: ListChecks, stages: ["quiz"] },
  { key: "pack", label: "Packaging", sub: "Building your PowerPoint and web deck", icon: PackageCheck, stages: ["build_pptx", "build_html"] },
];
// Real execution order of the backend pipeline.
const ORDER = [
  "convert", "chunk", "vision_ocr", "index",
  "layout", "visual_plan", "visual_data", "expand", "enhance", "density",
  "quiz", "illustrate", "labs", "score",
  "build_pptx", "build_html",
];

// What the backend is doing right now, in plain words (keys = real stage names).
const STAGE_LABEL = {
  convert: "Reading your document",
  chunk: "Splitting it into sections",
  vision_ocr: "Reading text inside images",
  index: "Indexing the content",
  layout: "Choosing a layout for each slide",
  visual_plan: "Planning the visuals",
  visual_data: "Pulling out figures and data",
  expand: "Expanding the explanations",
  enhance: "Adding examples and analogies",
  density: "Tuning how much text each slide holds",
  quiz: "Writing checkpoint questions",
  illustrate: "Illustrating the slides",
  labs: "Building interactive labs",
  score: "Scoring every slide",
  build_pptx: "Building the PowerPoint",
  build_html: "Building the web deck",
};

/** Eases a number toward its target so the percentage glides instead of jumping. */
function useTween(value) {
  const reduce = useReducedMotion();
  const [v, setV] = useState(value);
  const prev = useRef(value);
  useEffect(() => {
    if (reduce) {
      setV(value);
      prev.current = value;
      return undefined;
    }
    const c = animate(prev.current, value, { duration: 0.6, ease: "easeOut", onUpdate: (x) => setV(Math.round(x)) });
    prev.current = value;
    return () => c.stop();
  }, [value, reduce]);
  return v;
}

const TIPS = [
  "Tip: press Present, then S, to open the speaker view with notes and a timer.",
  "Tip: the AI tab in the editor can rewrite any slide for Grade 6 or an executive.",
  "Tip: Before vs after shows what the engine changed from your raw text.",
  "Tip: drop a PDF on the home composer and Learnova will read it for you.",
  "Tip: press Cmd+K anywhere to jump to a deck.",
];

const SLIDES = 8;
const BURST = Array.from({ length: 28 }, (_, i) => {
  const a = (i / 28) * Math.PI * 2 + (i % 3) * 0.2;
  const r = 90 + ((i * 37) % 90);
  return {
    x: Math.cos(a) * r,
    y: Math.sin(a) * r - 20,
    rot: (i * 53) % 360,
    c: ["#C2502A", "#6B9B72", "#FFC93C", "#402B25"][i % 4],
    w: 6 + (i % 3) * 3,
  };
});

function MiniSlide({ i, newest }) {
  const v = i % 4;
  return (
    <div className="relative flex h-full w-full flex-col gap-1.5 overflow-hidden rounded-lg border border-[#E8D8C9] bg-white p-2.5 shadow-sm">
      <div className="h-1.5 w-2/3 rounded-full bg-[#C2502A]" />
      {v === 0 && (
        <>
          <div className="h-1 w-full rounded-full bg-[#EFE1D4]" />
          <div className="h-1 w-5/6 rounded-full bg-[#EFE1D4]" />
          <div className="h-1 w-3/4 rounded-full bg-[#EFE1D4]" />
        </>
      )}
      {v === 1 && (
        <div className="mt-0.5 flex flex-1 gap-1.5">
          <div className="flex-1 rounded bg-[#6B9B72]/30" />
          <div className="flex-1 rounded bg-[#FFC93C]/40" />
          <div className="flex-1 rounded bg-[#C2502A]/20" />
        </div>
      )}
      {v === 2 && (
        <div className="mt-0.5 flex flex-1 items-end gap-1">
          {[40, 70, 55, 90].map((h, k) => (
            <div key={k} className="flex-1 rounded-t bg-[#C2502A]/70" style={{ height: `${h}%`, opacity: 0.4 + k * 0.15 }} />
          ))}
        </div>
      )}
      {v === 3 && (
        <>
          <div className="mt-0.5 flex-1 rounded bg-[#FCE5D6]" />
          <div className="h-1 w-1/2 rounded-full bg-[#EFE1D4]" />
        </>
      )}
      {newest ? <div className="lv-skel pointer-events-none absolute inset-0 !bg-transparent opacity-70" /> : null}
    </div>
  );
}

function Ring({ pct, done }) {
  const shown = useTween(pct);
  const R = 44;
  const C = 2 * Math.PI * R;
  return (
    <div className="relative size-[108px] shrink-0">
      <svg viewBox="0 0 108 108" className="size-full -rotate-90">
        <circle cx="54" cy="54" r={R} fill="none" stroke="#EFE1D4" strokeWidth="9" />
        <motion.circle
          cx="54"
          cy="54"
          r={R}
          fill="none"
          stroke={done ? "#6B9B72" : "#C2502A"}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={C}
          animate={{ strokeDashoffset: C * (1 - pct / 100) }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        {done ? (
          <Check className="size-9 text-[#6B9B72]" strokeWidth={3} />
        ) : (
          <span className="font-[Bricolage_Grotesque] text-2xl font-bold tabular-nums text-[#402B25]">{shown}%</span>
        )}
      </div>
    </div>
  );
}

export default function GenerationPipeline({ stage, progress = 0, status = "running", title, error, onOpen, onPresent, onRetry }) {
  const reduce = useReducedMotion();
  const done = status === "done";
  const failed = status === "failed";
  const stageIdx = ORDER.indexOf(stage);

  const rawPct = done ? 100 : stageIdx < 0 ? 2 : Math.round(((stageIdx + (progress || 0)) / ORDER.length) * 100);
  const maxPct = useRef(0);
  maxPct.current = done ? 100 : Math.max(maxPct.current, Math.min(rawPct, 99));
  const pct = maxPct.current;

  const startedAt = useRef(Date.now());
  const [now, setNow] = useState(Date.now());
  const [tip, setTip] = useState(0);
  useEffect(() => {
    if (done || failed) return;
    const a = setInterval(() => setNow(Date.now()), 1000);
    const b = setInterval(() => setTip((t) => (t + 1) % TIPS.length), 4500);
    return () => {
      clearInterval(a);
      clearInterval(b);
    };
  }, [done, failed]);

  const eta = useMemo(() => {
    const elapsed = (now - startedAt.current) / 1000;
    if (pct < 8 || elapsed < 6) return "Estimating time…";
    const left = Math.max(3, Math.round((elapsed / pct) * (100 - pct)));
    return left > 90 ? `About ${Math.round(left / 60)} min left` : `About ${left}s left`;
  }, [now, pct]);

  const phaseState = (p) => {
    if (done) return "done";
    const idxs = p.stages.map((s) => ORDER.indexOf(s));
    if (p.stages.includes(stage)) return "active";
    if (stageIdx >= 0 && Math.max(...idxs) < stageIdx) return "done";
    return "todo";
  };

  const visible = done ? SLIDES : Math.max(1, Math.min(SLIDES, Math.ceil((pct / 100) * SLIDES)));

  if (failed) {
    return (
      <div className="lv-surface lv-r-hero mx-auto flex max-w-lg flex-col items-center gap-4 px-8 py-12 text-center">
        <div className="grid size-14 place-items-center rounded-2xl bg-[#FFF3D6] text-[#B45309]">
          <TriangleAlert className="size-7" />
        </div>
        <h2 className="t-h2">That one didn’t come together</h2>
        <p className="t-body text-muted-foreground">
          Something got in the way while building your deck. Your content is safe — give it another go, or edit it and
          try again.
        </p>
        {error ? <p className="rounded-lg bg-[#FFFAF5] px-3 py-2 text-xs text-[#715A4E]">{error}</p> : null}
        {onRetry ? (
          <Button onClick={onRetry} className="bg-[#402B25] hover:bg-[#2E1E19]">
            <RotateCcw /> Try again
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
      {/* phases */}
      <div className="lv-surface lv-r-hero p-5">
        <div className="mb-4 flex items-center gap-4">
          <Ring pct={pct} done={done} />
          <div className="min-w-0">
            <p className="t-card">{done ? "Your deck is ready" : "Building your deck"}</p>
            {title ? <p className="t-meta mt-0.5 line-clamp-2">{title}</p> : null}
            <p className="t-meta mt-1 font-semibold text-[#B44A22]">{done ? "All done" : eta}</p>
          </div>
        </div>
        <div className="mb-5">
          <div
            className="relative h-2 overflow-hidden rounded-full bg-[#EFE1D4]"
            role="progressbar"
            aria-label="Deck progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
          >
            <motion.div
              className={cn("h-full rounded-full", done ? "bg-[#6B9B72]" : "bg-[#F47B45]")}
              initial={false}
              animate={{ width: `${pct}%` }}
              transition={{ duration: reduce ? 0 : 0.6, ease: "easeOut" }}
            />
            {!done && !reduce ? <span className="lv-skel pointer-events-none absolute inset-0 !bg-transparent opacity-60" /> : null}
          </div>
          <p className="mt-2 min-h-[18px] text-[12.5px] font-medium text-[#5A453B]" aria-live="polite">
            {done ? "Ready to open" : STAGE_LABEL[stage] ? `${STAGE_LABEL[stage]}…` : "Getting started…"}
          </p>
        </div>
        <ol className="flex flex-col gap-1.5">
          {PHASES.map((p) => {
            const st = phaseState(p);
            const Icon = p.icon;
            return (
              <li
                key={p.key}
                className={cn(
                  "flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 transition-colors",
                  st === "active" && "border-[#E3A98B] bg-[#FDEEE3]"
                )}
              >
                <span
                  className={cn(
                    "relative grid size-11 shrink-0 place-items-center rounded-xl transition-all",
                    st === "todo" && "bg-[#F3E6DA] text-[#765F53]",
                    st === "active" && "lv-glow-blue bg-[#C2502A] text-white",
                    st === "done" && "bg-[#6B9B72]/20 text-[#2F5D37]"
                  )}
                >
                  <AnimatePresence mode="wait" initial={false}>
                    {st === "done" ? (
                      <motion.span
                        key="tick"
                        initial={reduce ? false : { scale: 0, rotate: -40 }}
                        animate={{ scale: 1, rotate: 0 }}
                        transition={{ type: "spring", stiffness: 520, damping: 14 }}
                        className="grid size-7 place-items-center rounded-full bg-[#6B9B72] text-white"
                      >
                        <Check className="size-4" strokeWidth={3.5} />
                      </motion.span>
                    ) : (
                      <motion.span key="icon" exit={{ scale: 0.6, opacity: 0 }}>
                        <Icon className={cn("size-[22px]", st === "active" && !reduce && "animate-pulse")} />
                      </motion.span>
                    )}
                  </AnimatePresence>
                </span>
                <span className="min-w-0">
                  <span className={cn("block text-[15px] font-semibold leading-5", st === "todo" ? "text-[#765F53]" : "text-[#402B25]")}>
                    {p.label}
                  </span>
                  <span className="block truncate text-[12px] leading-4 text-[#715A4E]">{p.sub}</span>
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      {/* assembling canvas */}
      <div className="lv-r-hero relative flex min-h-[380px] flex-col overflow-hidden border bg-[#F3E6DA] p-5">
        <div className="mb-3 flex items-center justify-between">
          <p className="t-card">{done ? "Deck assembled" : "Deck assembling"}</p>
          <span className="t-meta tabular-nums">{visible} / {SLIDES} slides sketched</span>
        </div>
        <div className="grid flex-1 grid-cols-2 content-start gap-3 sm:grid-cols-4">
          {Array.from({ length: SLIDES }).map((_, i) => {
            const shown = i < visible;
            return (
              <div key={i} className="aspect-video">
                {shown ? (
                  <motion.div
                    className="h-full"
                    initial={reduce ? false : { opacity: 0, y: -36, scale: 0.88, rotate: i % 2 ? 3 : -3 }}
                    animate={{ opacity: 1, y: 0, scale: 1, rotate: 0 }}
                    transition={{ type: "spring", stiffness: 260, damping: 22, delay: reduce ? 0 : (i % 4) * 0.04 }}
                  >
                    <MiniSlide i={i} newest={!done && i === visible - 1} />
                  </motion.div>
                ) : (
                  <div className="h-full rounded-lg border border-dashed border-[#DCC6B4] bg-white/40" />
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-4 min-h-[44px]">
          {done ? (
            <div className="relative flex flex-wrap items-center justify-center gap-3">
              {!reduce && (
                <div className="pointer-events-none absolute left-1/2 top-1/2" aria-hidden="true">
                  {BURST.map((b, i) => (
                    <span
                      key={i}
                      className="absolute rounded-[2px]"
                      style={{
                        width: b.w,
                        height: b.w * 1.6,
                        background: b.c,
                        "--bx": `${b.x}px`,
                        "--by": `${b.y}px`,
                        "--br": `${b.rot}deg`,
                        animation: `lv-burst 1.1s ${i * 12}ms cubic-bezier(0.2,0.8,0.3,1) forwards`,
                      }}
                    />
                  ))}
                </div>
              )}
              <Button size="lg" onClick={onOpen} className="h-11 bg-[#402B25] px-6 text-[15px] hover:bg-[#2E1E19]">
                Open deck
              </Button>
              <Button size="lg" variant="outline" onClick={onPresent} className="h-11 bg-white px-6 text-[15px]">
                <Play className="fill-current" /> Present
              </Button>
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.p
                key={tip}
                initial={reduce ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.25 }}
                className="text-center text-[13px] text-[#4F3A31]"
              >
                {TIPS[tip]}
              </motion.p>
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  );
}
