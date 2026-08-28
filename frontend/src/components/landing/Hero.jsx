import { useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, PlayCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

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
    <section
      ref={ref}
      onMouseMove={onMove}
      className="relative overflow-hidden border-b"
    >
      <div className="pointer-events-none absolute inset-0 lv-grid-bg" />
      <div className="pointer-events-none absolute inset-0 lv-spotlight" />

      <div className="relative mx-auto flex max-w-3xl flex-col items-center gap-6 px-4 py-24 text-center sm:py-32">
        <span className="lv-rise inline-flex items-center gap-2 rounded-full border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <span className="size-1.5 rounded-full bg-primary" />
          AI presentation engine · cognitive-load aware
        </span>

        <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
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
          Learnova converts text-heavy PPTX, PDFs, and typed syllabi into
          structured, visually engaging decks — flowcharts, timelines, charts,
          progressive reveals, and inline checkpoint quizzes.
        </p>

        <div
          className="lv-rise flex flex-wrap items-center justify-center gap-3"
          style={{ animationDelay: "0.72s" }}
        >
          <Button asChild size="lg">
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
          className="lv-rise mt-4 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-sm text-muted-foreground"
          style={{ animationDelay: "0.84s" }}
        >
          {[
            ["1000+", "addressable visuals"],
            ["0", "API keys required"],
            ["PSF", "engagement metric"],
          ].map(([v, l]) => (
            <span key={l} className="flex items-baseline gap-1.5">
              <span className="text-base font-semibold text-foreground">{v}</span> {l}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
