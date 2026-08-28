import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Clock,
  Download,
  FileDown,
  Play,
  Sparkles,
} from "lucide-react";
import * as api from "@/api";
import { UserButton } from "@/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function Prop({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  );
}

export default function Preview() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [deck, setDeck] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(0);
  const [htmlUrl, setHtmlUrl] = useState(null);
  const iframeRef = useRef(null);

  useEffect(() => {
    api.getDeck(jobId).then(setDeck).catch((e) => setError(e.message));
  }, [jobId]);

  useEffect(() => {
    let revoked = false;
    let url;
    api
      .artifactObjectUrl(api.jobDownloadPath(jobId, "html"))
      .then((u) => {
        if (revoked) return URL.revokeObjectURL(u);
        url = u;
        setHtmlUrl(u);
      })
      .catch(() => {});
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [jobId]);

  const slides = deck?.slides ?? [];
  const cur = slides[selected];
  const summary = deck?.summary;

  // Drive the embedded Reveal.js deck to the selected slide (title slide is #0).
  // Retry: Reveal may not be initialised in the iframe yet on the first tick.
  useEffect(() => {
    let tries = 0;
    const tick = () => {
      const R = iframeRef.current?.contentWindow?.Reveal;
      if (R && typeof R.slide === "function") {
        try {
          R.slide(selected + 1);
          return true;
        } catch {
          /* not ready */
        }
      }
      return false;
    };
    if (tick()) return;
    const id = setInterval(() => {
      if (tick() || ++tries > 50) clearInterval(id);
    }, 100);
    return () => clearInterval(id);
  }, [selected, htmlUrl]);

  const estMin = useMemo(() => {
    const s = slides.reduce((n, x) => n + (x.est_seconds || 0), 0);
    return s ? Math.max(1, Math.round(s / 60)) : null;
  }, [slides]);

  async function download(artifact) {
    try {
      await api.downloadArtifact(
        api.jobDownloadPath(jobId, artifact),
        `Learnova_${summary?.source_name || "deck"}.${artifact}`
      );
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div data-learnova-app className="flex h-svh flex-col bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b px-3">
        <Button asChild variant="ghost" size="icon">
          <Link to="/app">
            <ArrowLeft />
          </Link>
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {summary?.source_name || deck?.job_id || "Presentation"}
          </p>
          <p className="text-xs text-muted-foreground">
            {summary ? `${summary.slide_count} slides · ${summary.quiz_count} quizzes` : "…"}
            {summary?.overall_score != null ? ` · ${summary.overall_score}/100` : ""}
            {estMin ? ` · ≈ ${estMin} min` : ""}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => download("html")}>
            <Download /> Web deck
          </Button>
          <Button size="sm" onClick={() => download("pptx")}>
            <FileDown /> PowerPoint
          </Button>
          <Button asChild variant="outline" size="sm" title="Open presenter view">
            <Link to={`/app/present/${jobId}`}>
              <Play /> Present
            </Link>
          </Button>
          <Button asChild size="sm" variant="secondary">
            <Link to={`/app/export/${jobId}`}>Finish</Link>
          </Button>
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      {error ? <p className="border-b bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</p> : null}

      <div className="grid min-h-0 flex-1 grid-cols-[220px_1fr_300px]">
        {/* Slides rail */}
        <ScrollArea className="border-r">
          <ul className="flex flex-col gap-2 p-3">
            {!deck
              ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16" />)
              : slides.map((s, i) => (
                  <li key={s.index}>
                    <button
                      onClick={() => setSelected(i)}
                      className={cn(
                        "w-full rounded-lg border p-2 text-left text-xs transition-colors",
                        i === selected ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                      )}
                    >
                      <div className="mb-1 flex items-center justify-between">
                        <span className="font-medium text-muted-foreground">
                          {s.is_section_start ? "◆ " : ""}
                          {i + 1}
                        </span>
                        {s.family ? (
                          <span className="rounded bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">
                            {s.variant || s.family}
                          </span>
                        ) : null}
                      </div>
                      <p className="line-clamp-2 font-medium">{s.title}</p>
                    </button>
                  </li>
                ))}
          </ul>
        </ScrollArea>

        {/* Reveal.js viewer */}
        <div className="flex min-w-0 items-center justify-center bg-muted/30 p-4">
          {htmlUrl ? (
            <div className="aspect-video w-full max-w-4xl overflow-hidden rounded-xl border bg-white shadow-sm">
              <iframe
                ref={iframeRef}
                title="Presentation preview"
                src={htmlUrl}
                className="h-full w-full"
                onLoad={() => {
                  const R = iframeRef.current?.contentWindow?.Reveal;
                  try {
                    R?.slide?.(selected + 1);
                  } catch {
                    /* ignore */
                  }
                }}
              />
            </div>
          ) : (
            <Skeleton className="aspect-video w-full max-w-4xl rounded-xl" />
          )}
        </div>

        {/* Properties */}
        <ScrollArea className="border-l">
          <div className="flex flex-col gap-4 p-4">
            <p className="text-sm font-semibold">Slide {selected + 1}</p>
            {!cur ? (
              <Skeleton className="h-40" />
            ) : (
              <>
                <Prop label="Visual">
                  <span className="font-medium">{cur.variant || cur.treatment || cur.layout_type}</span>
                  {cur.family ? (
                    <span className="text-muted-foreground"> · {cur.family}</span>
                  ) : null}
                </Prop>
                <Prop label="Transition in">
                  <Badge variant="secondary">{cur.transition || "slide"}</Badge>
                  {cur.transition_reason ? (
                    <p className="mt-1 text-xs text-muted-foreground">{cur.transition_reason}</p>
                  ) : null}
                </Prop>
                <Prop label="Summarisation">
                  <Badge
                    variant={
                      cur.summary_directive === "PRESERVE"
                        ? "warning"
                        : cur.summary_directive === "COMPRESS"
                        ? "destructive"
                        : "secondary"
                    }
                  >
                    {cur.summary_directive || "BALANCED"}
                  </Badge>
                </Prop>
                <Prop label="Progressive reveal">
                  <span className="inline-flex items-center gap-1">
                    <Sparkles className="size-3.5 text-primary" />
                    {cur.reveal_steps || 1} step{(cur.reveal_steps || 1) === 1 ? "" : "s"}
                  </span>
                </Prop>
                {cur.est_seconds ? (
                  <Prop label="Est. time">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="size-3.5" /> ~{Math.round(cur.est_seconds)}s
                    </span>
                  </Prop>
                ) : null}

                <Separator />
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    Speaker notes
                  </span>
                  <pre className="whitespace-pre-wrap rounded-md bg-muted p-2 text-xs leading-relaxed">
                    {cur.speaker_notes || cur.takeaway || "—"}
                  </pre>
                </div>
              </>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
