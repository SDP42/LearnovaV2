import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  Circle,
  Maximize2,
  MonitorPlay,
  Pause,
  Play,
  RotateCcw,
  SkipBack,
  SkipForward,
  Square,
  X,
} from "lucide-react";
import * as api from "@/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function fmt(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}
function clock() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Mini render of one slide — used for NEXT and the filmstrip. */
function SlideMini({ slide, index, className }) {
  return (
    <div className={cn("rounded-md border border-white/10 bg-white/[0.04] p-2 text-left", className)}>
      <div className="mb-1 flex items-center justify-between text-[10px] text-neutral-400">
        <span>{index}</span>
        {slide?.variant || slide?.family ? (
          <span className="rounded bg-white/10 px-1 py-px">{slide.variant || slide.family}</span>
        ) : null}
      </div>
      <p className="line-clamp-2 text-xs font-medium text-neutral-100">
        {slide?.title || "—"}
      </p>
      <ul className="mt-1 space-y-0.5 text-[10px] text-neutral-400">
        {(slide?.bullets ?? []).slice(0, 2).map((b, i) => (
          <li key={i} className="line-clamp-1">• {b}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Dedicated Canva-style dual-screen presenter console.
 *
 * Left: the live slide. Right: a big timer + wall clock, the next slide, and
 * speaker notes. Bottom: a filmstrip for jump-to-slide. The reveal-step dots
 * show progress through a slide's progressive-reveal builds. "Audience view"
 * opens the clean deck in a second window, kept in sync (incl. blackout) over
 * a BroadcastChannel.
 */
export default function Present() {
  const { jobId } = useParams();
  const mainRef = useRef(null);
  const chan = useRef(null);
  const filmRef = useRef(null);

  const [deck, setDeck] = useState(null);
  const [htmlUrl, setHtmlUrl] = useState(null);
  const [pos, setPos] = useState({ h: 0, f: -1 });
  const [error, setError] = useState("");

  const [running, setRunning] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [now, setNow] = useState(clock());
  const [audienceOpen, setAudienceOpen] = useState(false);
  const [blackout, setBlackout] = useState(false);

  useEffect(() => {
    api.getDeck(jobId).then(setDeck).catch((e) => setError(e.message));
  }, [jobId]);

  useEffect(() => {
    let url;
    let dead = false;
    api
      .deckArtifactUrl(jobId, "html")
      .then((u) => {
        if (dead) return URL.revokeObjectURL(u);
        url = u;
        setHtmlUrl(u);
      })
      .catch((e) => setError(e.message));
    return () => {
      dead = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [jobId]);

  useEffect(() => {
    chan.current = new BroadcastChannel(`learnova-present-${jobId}`);
    return () => chan.current?.close();
  }, [jobId]);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setElapsed((e) => e + 1000), 1000);
    return () => clearInterval(t);
  }, [running]);
  useEffect(() => {
    const t = setInterval(() => setNow(clock()), 15000);
    return () => clearInterval(t);
  }, []);

  const reveal = useCallback(() => mainRef.current?.contentWindow?.Reveal, []);

  const sync = useCallback(() => {
    const R = reveal();
    if (!R) return;
    try {
      const state = R.getState();
      chan.current?.postMessage({ type: "state", state });
      setPos({ h: state.indexh ?? 0, f: state.indexf ?? -1 });
    } catch {
      /* deck still loading */
    }
  }, [reveal]);

  const go = useCallback(
    (dir) => {
      const R = reveal();
      if (!R) return;
      dir > 0 ? R.next() : R.prev();
      setTimeout(sync, 40);
    },
    [reveal, sync]
  );

  const jump = useCallback(
    (h, f) => {
      const R = reveal();
      if (!R) return;
      try {
        R.slide(h, undefined, f);
      } catch {
        /* ignore */
      }
      setTimeout(sync, 40);
    },
    [reveal, sync]
  );

  const toggleBlackout = useCallback(() => {
    setBlackout((b) => {
      chan.current?.postMessage({ type: "blackout", on: !b });
      return !b;
    });
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (["ArrowRight", "PageDown", " "].includes(e.key)) {
        e.preventDefault();
        go(1);
      } else if (["ArrowLeft", "PageUp"].includes(e.key)) {
        e.preventDefault();
        go(-1);
      } else if (e.key === "Home") {
        jump(0);
      } else if (e.key === "End") {
        jump((deck?.slides?.length ?? 0));
      } else if (e.key === "f") {
        mainRef.current?.requestFullscreen?.();
      } else if (e.key === "b" || e.key === ".") {
        toggleBlackout();
      } else if (e.key === "p") {
        setRunning((r) => !r);
      } else if (e.key === "r") {
        setElapsed(0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, jump, toggleBlackout, deck]);

  function openAudience() {
    const w = window.open(`/app/audience/${jobId}`, "learnova-audience");
    setAudienceOpen(!!w);
    const ping = setInterval(() => {
      if (w?.closed) {
        setAudienceOpen(false);
        clearInterval(ping);
      }
    }, 1500);
    setTimeout(() => {
      sync();
      chan.current?.postMessage({ type: "blackout", on: blackout });
    }, 900);
  }

  // keep the current filmstrip thumb visible
  useEffect(() => {
    filmRef.current?.querySelector(`[data-h="${pos.h}"]`)?.scrollIntoView({
      inline: "center",
      block: "nearest",
      behavior: "smooth",
    });
  }, [pos.h]);

  const slides = deck?.slides ?? [];
  const nContent = slides.length;
  const total = nContent + 1; // + title slide
  const curSlide = slides[pos.h - 1] || null;
  const nextSlide = slides[pos.h] || null;

  const steps = curSlide?.reveal_steps || 0;
  const notes = useMemo(() => {
    if (pos.h === 0) return "Title slide. Press → to begin.";
    return curSlide?.speaker_notes || curSlide?.takeaway || "No notes for this slide.";
  }, [curSlide, pos.h]);

  return (
    <div data-learnova-app className="flex h-svh flex-col bg-neutral-950 text-neutral-100">
      {/* header */}
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-white/10 px-3 text-sm">
        <Button asChild variant="ghost" size="icon" className="text-neutral-300 hover:bg-white/10">
          <Link to={`/app/preview/${jobId}`}><X /></Link>
        </Button>
        <span className="truncate font-medium">
          {deck?.summary?.source_name || "Presenter view"}
        </span>
        <span className="hidden text-xs text-neutral-500 sm:inline">
          ← → navigate · B blackout · F fullscreen · P timer
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span
            className={cn(
              "flex items-center gap-1.5 rounded-md px-2 py-1 text-xs",
              audienceOpen ? "bg-emerald-500/15 text-emerald-300" : "bg-white/10 text-neutral-400"
            )}
          >
            <Circle className={cn("size-2 fill-current", audienceOpen && "animate-pulse")} />
            {audienceOpen ? "Audience live" : "Audience off"}
          </span>
          <Button size="sm" variant="secondary" onClick={openAudience}>
            <MonitorPlay /> {audienceOpen ? "Re-sync" : "Audience view"}
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[1fr_380px]">
        {/* ── current slide ─────────────────────────────────────────────── */}
        <div className="flex min-w-0 flex-col gap-3 bg-black p-4">
          <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-white/10 bg-white">
            {htmlUrl ? (
              <iframe
                ref={mainRef}
                title="Current slide"
                src={htmlUrl}
                className="h-full w-full"
                onLoad={() => {
                  try {
                    // The presenter sees the whole slide (text + figures),
                    // upcoming points dimmed; Next still steps the audience.
                    mainRef.current?.contentWindow?.__presenterPeek?.();
                  } catch {
                    /* blob is same-origin */
                  }
                  setTimeout(sync, 500);
                }}
              />
            ) : (
              <Skeleton className="h-full w-full" />
            )}
            {blackout ? (
              <div className="absolute inset-0 grid place-items-center bg-black text-sm text-neutral-500">
                Screen blacked out — press B
              </div>
            ) : null}
          </div>

          {/* transport + step dots */}
          <div className="flex items-center justify-between gap-3">
            <Button variant="ghost" size="icon" className="text-neutral-300 hover:bg-white/10" onClick={() => jump(0)} title="First slide">
              <SkipBack />
            </Button>
            <div className="flex flex-1 items-center justify-center gap-3">
              <Button variant="secondary" onClick={() => go(-1)}>
                <ChevronLeft /> Prev
              </Button>
              <div className="text-center">
                <p className="text-sm font-medium tabular-nums">
                  {pos.h + 1} <span className="text-neutral-500">/ {total}</span>
                </p>
                {steps > 1 ? (
                  <div className="mt-1 flex justify-center gap-1">
                    {Array.from({ length: steps }).map((_, i) => (
                      <button
                        key={i}
                        onClick={() => jump(pos.h, i)}
                        title={`Reveal step ${i + 1}`}
                        className={cn(
                          "h-1.5 w-4 rounded-full transition-colors hover:opacity-80",
                          i <= pos.f ? "bg-primary" : "bg-white/15"
                        )}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
              <Button onClick={() => go(1)}>
                Next <ChevronRight />
              </Button>
            </div>
            <Button variant="ghost" size="icon" className="text-neutral-300 hover:bg-white/10" onClick={() => jump(nContent)} title="Last slide">
              <SkipForward />
            </Button>
            <Button variant="ghost" size="icon" className="text-neutral-300 hover:bg-white/10" onClick={toggleBlackout} title="Blackout (B)">
              <Square className={blackout ? "fill-current" : ""} />
            </Button>
            <Button variant="ghost" size="icon" className="text-neutral-300 hover:bg-white/10" onClick={() => mainRef.current?.requestFullscreen?.()} title="Fullscreen (F)">
              <Maximize2 />
            </Button>
          </div>
        </div>

        {/* ── right rail ────────────────────────────────────────────────── */}
        <aside className="flex min-h-0 flex-col gap-3 border-t border-white/10 p-3 lg:border-l lg:border-t-0">
          {/* timer */}
          <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-mono text-4xl font-semibold tabular-nums text-neutral-50">
                  {fmt(elapsed)}
                </p>
                <p className="mt-0.5 text-xs text-neutral-500">elapsed · {now}</p>
              </div>
              <div className="flex gap-1">
                <Button size="icon" variant="ghost" className="size-8 text-neutral-300 hover:bg-white/10" onClick={() => setRunning((r) => !r)} title="Play / pause (P)">
                  {running ? <Pause /> : <Play />}
                </Button>
                <Button size="icon" variant="ghost" className="size-8 text-neutral-300 hover:bg-white/10" onClick={() => setElapsed(0)} title="Reset (R)">
                  <RotateCcw />
                </Button>
              </div>
            </div>
          </div>

          {/* next */}
          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-neutral-400">Next</p>
            {nextSlide ? (
              <SlideMini slide={nextSlide} index={pos.h + 2} className="border-primary/25 bg-primary/[0.06]" />
            ) : (
              <div className="rounded-md border border-white/10 bg-white/[0.04] p-3 text-sm text-neutral-500">
                End of deck
              </div>
            )}
          </div>

          {/* notes */}
          <div className="flex min-h-0 flex-1 flex-col">
            <p className="mb-1 flex items-center justify-between text-xs uppercase tracking-wide text-neutral-400">
              Speaker notes
              {curSlide?.summary_directive ? (
                <span className="rounded bg-white/10 px-1.5 py-px text-[10px] tracking-normal">
                  {curSlide.summary_directive}
                </span>
              ) : null}
            </p>
            <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-neutral-200">
                {notes}
              </pre>
            </div>
          </div>
        </aside>
      </div>

      {/* ── deck scrubber ──────────────────────────────────────────────── */}
      <div className="flex shrink-0 items-center gap-3 border-t border-white/10 bg-neutral-950 px-3 pt-2 text-[11px] text-neutral-500">
        <span className="tabular-nums">{pos.h + 1}</span>
        <input
          type="range"
          min={0}
          max={total - 1}
          value={Math.min(pos.h, total - 1)}
          onChange={(e) => jump(Number(e.target.value))}
          className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-white/15 accent-primary"
        />
        <span className="tabular-nums">{total}</span>
      </div>

      {/* ── filmstrip (jump to slide) ───────────────────────────────────── */}
      <div ref={filmRef} className="flex shrink-0 gap-2 overflow-x-auto bg-neutral-950 p-2">
        <button
          data-h="0"
          onClick={() => jump(0)}
          className={cn(
            "w-28 shrink-0 rounded-md border p-2 text-left text-[10px] transition-colors",
            pos.h === 0 ? "border-primary bg-primary/10" : "border-white/10 hover:bg-white/[0.06]"
          )}
        >
          <span className="text-neutral-400">Title</span>
          <p className="mt-1 line-clamp-2 font-medium text-neutral-100">
            {deck?.summary?.source_name || "Learnova"}
          </p>
        </button>
        {slides.map((s, i) => (
          <button
            key={s.index ?? i}
            data-h={i + 1}
            onClick={() => jump(i + 1)}
            className={cn(
              "w-28 shrink-0 rounded-md border p-2 transition-colors",
              pos.h === i + 1 ? "border-primary bg-primary/10" : "border-white/10 hover:bg-white/[0.06]"
            )}
          >
            <SlideMini slide={s} index={i + 1} className="border-0 bg-transparent p-0" />
          </button>
        ))}
      </div>

      {error ? <p className="bg-red-950/60 px-4 py-2 text-sm text-red-300">{error}</p> : null}
    </div>
  );
}
