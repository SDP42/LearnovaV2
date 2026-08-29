import { useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, PlayCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import DeckMock from "@/components/landing/DeckMock";

const WORDS = ["Turn", "any", "syllabus", "into", "a", "presentation", "that", "teaches."];

export default function Hero() {
  const ref = useRef(null);

  function onMove(e) {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--x", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--y", `${((e.clientY - r.top) / r.height) * 100}%`);
  }

  return (
    <section ref={ref} onMouseMove={onMove} className="relative overflow-hidden border-b">
      <div className="pointer-events-none absolute inset-0 lv-grid-bg" />
      <div className="pointer-events-none absolute inset-0 lv-spotlight" />
      <div className="lv-glow left-1/2 top-[-10%] h-[420px] w-[720px] -translate-x-1/2" />

      <div className="relative mx-auto flex max-w-3xl flex-col items-center gap-6 px-4 pt-24 pb-8 text-center sm:pt-32">
        <span className="lv-rise inline-flex items-center gap-2 rounded-full border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <span className="relative flex size-1.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
          </span>
          AI presentation engine · cognitive-load aware
        </span>

        <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight sm:text-[3.25rem]">
          {WORDS.map((w, i) => (
            <span
              key={i}
              className="lv-rise mr-[0.28em] inline-block"
              style={{ animationDelay: `${0.05 + i * 0.06}s` }}
            >
              {w === "presentation" ? <span className="lv-gradient-text">{w}</span> : w}
            </span>
          ))}
        </h1>

        <p
          className="lv-rise max-w-xl text-balance text-muted-foreground"
          style={{ animationDelay: "0.6s" }}
        >
          Learnova reads your content and decides — per slide — whether to keep it
          as text, tighten it, or turn it into a flowchart, timeline, chart, or
          diagram. Then it builds an animated deck with a presenter view.
        </p>

        <div
          className="lv-rise flex flex-wrap items-center justify-center gap-3"
          style={{ animationDelay: "0.72s" }}
        >
          <Button asChild size="lg" className="lv-cta rounded-lg">
            <Link to="/app/create">
              Create presentation <ArrowRight />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <a href="#features">
              <PlayCircle /> Explore features
            </a>
          </Button>
        </div>

        <div
          className="lv-rise mt-2 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-sm text-muted-foreground"
          style={{ animationDelay: "0.84s" }}
        >
          {[
            ["40", "visual families"],
            ["1 click", "per idea"],
            ["2 files", "web deck + PPTX"],
          ].map(([v, l]) => (
            <span key={l} className="flex items-baseline gap-1.5">
              <span className="text-base font-semibold text-foreground">{v}</span> {l}
            </span>
          ))}
        </div>
      </div>

      <div
        className="lv-rise relative mx-auto -mb-24 max-w-4xl px-4 sm:-mb-32"
        style={{ animationDelay: "0.95s" }}
      >
        <DeckMock />
      </div>
    </section>
  );
}
