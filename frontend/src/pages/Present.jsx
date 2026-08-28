import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Maximize2,
  Pause,
  Play,
  RotateCcw,
  X,
} from "lucide-react";
import * as api from "@/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

function fmt(ms) {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Canva / PowerPoint-style presenter console.
 *
 * - Big current slide (the Reveal.js deck in an iframe, driven via Reveal.next/prev
 *   so fragment builds are respected).
 * - Next-slide preview, speaker notes, timer, slide counter, step indicator.
 * - "Open audience view" opens /app/audience/:jobId in a new window; the two
 *   stay in sync over a BroadcastChannel (Reveal state is posted on every move).
 */
export default function Present() {
  const { jobId } = useParams();
  const mainRef = useRef(null);
  const chan = useRef(null);
  const audienceWin = useRef(null);

  const [deck, setDeck] = useState(null);
  const [htmlUrl, setHtmlUrl] = useState(null);
  const [pos, setPos] = useState({ h: 0, f: -1 });
  const [error, setError] = useState("");

  const [running, setRunning] = useState(true);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    api.getDeck(jobId).then(setDeck).catch((e) => setError(e.message));
  }, [jobId]);

  useEffect(() => {
    let url;
    let dead = false;
    api
      .artifactObjectUrl(api.jobDownloadPath(jobId, "html"))
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

  useEffect(() => {
    const onKey = (e) => {
      if (["ArrowRight", "PageDown", " "].includes(e.key)) {
        e.preventDefault();
        go(1);
      } else if (["ArrowLeft", "PageUp"].includes(e.key)) {
        e.preventDefault();
        go(-1);
      } else if (e.key === "f") {
        mainRef.current?.requestFullscreen?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  function openAudience() {
    audienceWin.current = window.open(
      `/app/audience/${jobId}`,
      "learnova-audience",
      "noopener=false"
    );
    setTimeout(sync, 800);
  }

  const slides = deck?.slides ?? [];
  // Reveal slide 0 is the generated title slide; deck.slides[0] is content slide 1.
  const curSlide = slides[pos.h - 1] || null;
  const nextSlide = slides[pos.h] || null;
  const total = (deck?.summary?.slide_count ?? slides.length) + 1;

  const notes = useMemo(() => {
    if (!curSlide) return pos.h === 0 ? "Title slide. Press → to begin." : "";
    return curSlide.speaker_notes || curSlide.takeaway || "";
  }, [curSlide, pos.h]);

  return (
    <div data-learnova-app className="flex h-svh flex-col bg-neutral-950 text-neutral-100">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-white/10 px-3 text-sm">
        <Button asChild variant="ghost" size="icon" className="text-neutral-300 hover:bg-white/10">
          <Link to={`/app/preview/${jobId}`}>
            <X />
          </Link>
        </Button>
        <span className="font-medium">{deck?.summary?.source_name || "Presenter view"}</span>
        <span className="tabular-nums text-neutral-400">
          Slide {pos.h + 1} / {total}
          {pos.f >= 0 ? ` · step ${pos.f + 1}` : ""}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span className="rounded-md bg-white/10 px-2 py-1 font-mono text-sm tabular-nums">
            {fmt(elapsed)}
          </span>
          <Button size="icon" variant="ghost" className="text-neutral-300 hover:bg-white/10" onClick={() => setRunning((r) => !r)}>
            {running ? <Pause /> : <Play />}
          </Button>
          <Button size="icon" variant="ghost" className="text-neutral-300 hover:bg-white/10" onClick={() => setElapsed(0)}>
            <RotateCcw />
          </Button>
          <Button size="sm" variant="secondary" onClick={openAudience}>
            <ExternalLink /> Audience view
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[1fr_360px]">
        {/* Current slide */}
        <div className="flex min-w-0 flex-col bg-black p-4">
          <div className="relative flex-1 overflow-hidden rounded-xl border border-white/10 bg-white">
            {htmlUrl ? (
              <iframe
                ref={mainRef}
                title="Current slide"
                src={htmlUrl}
                className="h-full w-full"
                onLoad={() => {
                  try {
                    mainRef.current?.contentWindow?.__enableBuilds?.();
                  } catch {
                    /* cross-origin (shouldn't happen for a blob) */
                  }
                  setTimeout(sync, 500);
                }}
              />
            ) : (
              <Skeleton className="h-full w-full" />
            )}
          </div>
          <div className="mt-3 flex items-center justify-center gap-2">
            <Button variant="secondary" onClick={() => go(-1)}>
              <ChevronLeft /> Previous
            </Button>
            <Button onClick={() => go(1)}>
              Next <ChevronRight />
            </Button>
            <Button variant="ghost" size="icon" className="text-neutral-300 hover:bg-white/10" onClick={() => mainRef.current?.requestFullscreen?.()}>
              <Maximize2 />
            </Button>
          </div>
        </div>

        {/* Notes + next */}
        <aside className="flex min-h-0 flex-col gap-3 border-l border-white/10 p-3">
          <div>
            <p className="mb-1 text-xs uppercase tracking-wide text-neutral-400">Next</p>
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              {nextSlide ? (
                <>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs text-neutral-400">Slide {pos.h + 2}</span>
                    {nextSlide.variant || nextSlide.family ? (
                      <Badge variant="secondary" className="bg-white/10 text-neutral-200">
                        {nextSlide.variant || nextSlide.family}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="line-clamp-2 text-sm font-medium">{nextSlide.title}</p>
                  <ul className="mt-1 space-y-0.5 text-xs text-neutral-400">
                    {(nextSlide.bullets ?? []).slice(0, 3).map((b, i) => (
                      <li key={i} className="line-clamp-1">• {b}</li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-sm text-neutral-500">End of deck</p>
              )}
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col">
            <p className="mb-1 text-xs uppercase tracking-wide text-neutral-400">Speaker notes</p>
            <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-white/10 bg-white/5 p-3">
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-neutral-200">
                {notes || "—"}
              </pre>
            </div>
          </div>

          {curSlide?.transition ? (
            <p className="text-xs text-neutral-500">
              Transition in: <span className="text-neutral-300">{curSlide.transition}</span>
              {curSlide.summary_directive ? ` · ${curSlide.summary_directive}` : ""}
            </p>
          ) : null}
        </aside>
      </div>

      {error ? <p className="bg-red-950/60 px-4 py-2 text-sm text-red-300">{error}</p> : null}
    </div>
  );
}
