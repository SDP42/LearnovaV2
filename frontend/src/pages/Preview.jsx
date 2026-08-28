import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Clock,
  Download,
  FileDown,
  History,
  Loader2,
  Pencil,
  Play,
  RotateCcw,
  Sparkles,
  X,
} from "lucide-react";
import * as api from "@/api";
import { UserButton } from "@/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import ImageEditor from "@/components/app/ImageEditor";
import { Image as ImageIcon } from "lucide-react";

const FAMILIES = [
  ["", "Auto — let the engine choose"],
  ["TEXT", "Plain text"],
  ["PROCESS_LINEAR", "Flowchart / steps"],
  ["PROCESS_CYCLIC", "Cycle"],
  ["WORKED_EXAMPLE", "Worked example"],
  ["TIMELINE", "Timeline"],
  ["COMPARE_TABLE", "Comparison table"],
  ["COMPARE_VISUAL", "Pros & cons"],
  ["MATRIX_GRID", "2×2 matrix"],
  ["HIERARCHY_NEST", "Pyramid"],
  ["MIND_MAP", "Mind map"],
  ["LIST_STRUCTURED", "Card grid"],
  ["CHART_CATEGORICAL", "Bar chart"],
  ["CHART_TREND", "Line chart"],
  ["CHART_PART_TO_WHOLE", "Pie chart"],
  ["SET_DIAGRAM", "Venn"],
  ["DEFINITION", "Definition"],
  ["QUOTE", "Quote"],
  ["KPI", "Big number"],
];

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
  const [deck, setDeck] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(0);
  const [htmlUrl, setHtmlUrl] = useState(null);
  const iframeRef = useRef(null);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null); // editable slide list
  const [meta, setMeta] = useState({ version: 1, versions: [] });
  const [imageSlides, setImageSlides] = useState([]);
  const [figSrc, setFigSrc] = useState(null); // object URL while the figure editor is open
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const loadDeck = useCallback(() => {
    api.getDeck(jobId).then(setDeck).catch((e) => setError(e.message));
  }, [jobId]);

  useEffect(loadDeck, [loadDeck]);

  useEffect(() => {
    api
      .getEditableSlides(jobId)
      .then((r) => {
        setDraft(r.slides || []);
        setMeta({ version: r.version || 1, versions: r.versions || [] });
        setImageSlides(r.image_slides || []);
      })
      .catch(() => setDraft([]));
  }, [jobId]);

  async function openFigureEditor() {
    try {
      setFigSrc(await api.slideImageUrl(jobId, selected));
    } catch (e) {
      setError(e.message);
    }
  }
  async function saveFigure(blob) {
    await api.saveSlideImage(jobId, selected, blob);
    if (!imageSlides.includes(selected)) setImageSlides((s) => [...s, selected]);
    // re-render the deck so the new figure shows
    const r = await api.saveDeckSlides(jobId, draft, "figure edit");
    setMeta((m) => ({ ...m, version: r.version }));
    loadDeck();
    loadHtml();
  }

  const loadHtml = useCallback(() => {
    let url;
    let revoked = false;
    api
      .deckArtifactUrl(jobId, "html")
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

  useEffect(loadHtml, [loadHtml]);

  const slides = deck?.slides ?? [];
  const cur = slides[selected];
  const curDraft = draft?.[selected];
  const summary = deck?.summary;

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
    const name = `Learnova_${summary?.source_name || "deck"}.${artifact}`;
    try {
      await api.downloadArtifact(api.jobDownloadPath(jobId, artifact), name);
    } catch {
      try {
        await api.downloadArtifact(api.deckDownloadPath(jobId, artifact), name);
      } catch (e) {
        setError(e.message);
      }
    }
  }

  function patchDraft(patch) {
    setDraft((d) => d.map((s, i) => (i === selected ? { ...s, ...patch } : s)));
    setDirty(true);
  }

  async function save() {
    if (!draft?.length) return;
    setSaving(true);
    setError("");
    try {
      const r = await api.saveDeckSlides(jobId, draft);
      setMeta((m) => ({ ...m, version: r.version }));
      setDirty(false);
      loadDeck();
      loadHtml();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function restore(v) {
    setSaving(true);
    try {
      await api.restoreDeckVersion(jobId, v);
      const r = await api.getEditableSlides(jobId);
      setDraft(r.slides || []);
      setMeta({ version: r.version || 1, versions: r.versions || [] });
      setDirty(false);
      loadDeck();
      loadHtml();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
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
            {meta.version > 1 ? (
              <span className="ml-1.5 text-xs font-normal text-muted-foreground">v{meta.version}</span>
            ) : null}
          </p>
          <p className="text-xs text-muted-foreground">
            {summary ? `${summary.slide_count} slides · ${summary.quiz_count} quizzes` : "…"}
            {summary?.overall_score != null ? ` · ${summary.overall_score}/100` : ""}
            {estMin ? ` · ≈ ${estMin} min` : ""}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {editing ? (
            <>
              <Button size="sm" onClick={save} disabled={saving || !dirty}>
                {saving ? <Loader2 className="animate-spin" /> : <Check />}
                {saving ? "Re-rendering…" : "Save & re-render"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                <X /> Done
              </Button>
            </>
          ) : (
            <>
              {meta.versions?.length ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="ghost">
                      <History /> History
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuLabel>Restore a previous version</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    {meta.versions
                      .slice()
                      .reverse()
                      .map((v) => (
                        <DropdownMenuItem key={v.v} onSelect={() => restore(v.v)}>
                          <RotateCcw /> v{v.v} — {v.note}
                        </DropdownMenuItem>
                      ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                <Pencil /> Edit
              </Button>
              <Button variant="outline" size="sm" onClick={() => download("html")}>
                <Download /> Web deck
              </Button>
              <Button size="sm" onClick={() => download("pptx")}>
                <FileDown /> PowerPoint
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to={`/app/present/${jobId}`}>
                  <Play /> Present
                </Link>
              </Button>
              <Button asChild size="sm" variant="secondary">
                <Link to={`/app/export/${jobId}`}>Finish</Link>
              </Button>
            </>
          )}
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      {error ? (
        <p className="border-b bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</p>
      ) : null}
      {dirty && !editing ? (
        <p className="border-b bg-amber-500/10 px-4 py-2 text-xs text-amber-700 dark:text-amber-300">
          You have unsaved edits — open Edit to save and re-render.
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-[220px_1fr_320px]">
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
                      <p className="line-clamp-2 font-medium">
                        {draft?.[i]?.title || s.title}
                      </p>
                    </button>
                  </li>
                ))}
          </ul>
        </ScrollArea>

        {/* Viewer */}
        <div className="flex min-w-0 items-center justify-center bg-muted/30 p-4">
          {htmlUrl ? (
            <div className="aspect-video w-full max-w-4xl overflow-hidden rounded-xl border bg-white shadow-sm">
              <iframe
                ref={iframeRef}
                title="Presentation preview"
                src={htmlUrl}
                className="h-full w-full"
                onLoad={() => {
                  try {
                    iframeRef.current?.contentWindow?.Reveal?.slide?.(selected + 1);
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

        {/* Properties / editor */}
        <ScrollArea className="border-l">
          <div className="flex flex-col gap-4 p-4">
            <p className="text-sm font-semibold">
              {editing ? "Edit slide" : "Slide"} {selected + 1}
            </p>

            {editing && curDraft ? (
              <>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Title</label>
                  <Input
                    value={curDraft.title || ""}
                    onChange={(e) => patchDraft({ title: e.target.value })}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    Points (one per line)
                  </label>
                  <Textarea
                    rows={7}
                    value={(curDraft.bullets || []).join("\n")}
                    onChange={(e) =>
                      patchDraft({
                        bullets: e.target.value.split("\n").map((x) => x.trimEnd()).filter(Boolean),
                      })
                    }
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Visual</label>
                  <Select
                    value={curDraft.family || ""}
                    onValueChange={(v) => patchDraft({ family: v || null })}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FAMILIES.map(([v, label]) => (
                        <SelectItem key={v || "auto"} value={v}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Takeaway</label>
                  <Input
                    value={curDraft.takeaway || ""}
                    onChange={(e) => patchDraft({ takeaway: e.target.value })}
                    placeholder="One-line key point (optional)"
                  />
                </div>
                {imageSlides.includes(selected) || cur?.has_image ? (
                  <Button variant="outline" size="sm" onClick={openFigureEditor}>
                    <ImageIcon /> Crop / highlight figure
                  </Button>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  Save re-runs the layout, animation and scoring for the whole deck.
                  Figures are kept and can be cropped or highlighted above.
                </p>
              </>
            ) : !cur ? (
              <Skeleton className="h-40" />
            ) : (
              <>
                <Prop label="Visual">
                  <span className="font-medium">{cur.variant || cur.treatment || cur.layout_type}</span>
                  {cur.family ? <span className="text-muted-foreground"> · {cur.family}</span> : null}
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

                {cur.mermaid_code ||
                (cur.family && /PROCESS|FLOW|DECISION|STATE/.test(cur.family)) ? (
                  <Button asChild variant="outline" size="sm" className="w-full">
                    <Link to={`/app/diagram/${jobId}/${selected}`}>Open in diagram editor</Link>
                  </Button>
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

      {figSrc ? (
        <ImageEditor
          src={figSrc}
          onSave={saveFigure}
          onClose={() => {
            URL.revokeObjectURL(figSrc);
            setFigSrc(null);
          }}
        />
      ) : null}
    </div>
  );
}
