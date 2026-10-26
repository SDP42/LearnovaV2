import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Clock,
  Download,
  FileDown,
  GitCompare,
  History,
  Keyboard,
  Loader2,
  ChevronDown,
  Pencil,
  Play,
  Undo2,
  Wand2,
  TriangleAlert,
  RotateCcw,
  Sparkles,
  X,
} from "lucide-react";
import * as api from "@/api";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { TutorLauncher } from "@/components/app/TutorPanel";
import ShortcutsOverlay, { PREVIEW_SHORTCUTS, isTypingTarget, useShortcutsKey } from "@/components/app/ShortcutsOverlay";

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
  const [helpOpen, setHelpOpen] = useState(false);
  useShortcutsKey(useCallback(() => setHelpOpen((o) => !o), []));

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
    toast.success("Figure saved");
  }

  const loadHtml = useCallback(() => {
    let dead = false;
    // The blob URL is cached by api.js (shared with Present) — never revoke it here.
    api
      .deckArtifactUrl(jobId, "html")
      .then((u) => !dead && setHtmlUrl(u))
      .catch(() => {});
    return () => {
      dead = true;
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
    const t = toast.loading(`Preparing ${artifact.toUpperCase()}…`);
    try {
      try {
        await api.downloadArtifact(api.jobDownloadPath(jobId, artifact), name);
      } catch {
        await api.downloadArtifact(api.deckDownloadPath(jobId, artifact), name);
      }
      toast.success(`${artifact === "pptx" ? "PowerPoint" : "Web deck"} downloaded`, { id: t });
    } catch (e) {
      setError(e.message);
      toast.error(e.message || "Download failed", { id: t });
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
      toast.success(`Saved · v${r.version} re-rendered`);
    } catch (e) {
      setError(e.message);
      toast.error(e.message || "Couldn’t save your changes");
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
      toast.success(`Restored version ${v}`);
    } catch (e) {
      setError(e.message);
      toast.error(e.message || "Couldn’t restore that version");
    } finally {
      setSaving(false);
    }
  }

  // ── AI assist ─────────────────────────────────────────────────────────
  const [aiOn, setAiOn] = useState(null); // null = unknown, boolean once /status answers
  const [aiBusy, setAiBusy] = useState("");
  const [aiResult, setAiResult] = useState(null); // {label, before, after, applied}
  const [aiUnavailable, setAiUnavailable] = useState(false);
  const [tab, setTab] = useState("design");

  useEffect(() => {
    api.assistStatus().then((r) => setAiOn(!!r?.llm)).catch(() => setAiOn(false));
  }, []);
  useEffect(() => setAiResult(null), [selected]);

  async function runAi(label, instruction, audience = "") {
    const base = curDraft || (cur ? { title: cur.title, bullets: cur.bullets || [] } : null);
    if (!base) return;
    setAiBusy(label);
    setAiUnavailable(false);
    try {
      const out = await api.assistSlide({ title: base.title || "", bullets: base.bullets || [], instruction, audience });
      setAiResult({
        label,
        before: { title: base.title || "", bullets: base.bullets || [] },
        after: { title: out.title ?? base.title ?? "", bullets: out.bullets ?? base.bullets ?? [] },
        applied: false,
      });
    } catch (e) {
      if (e.status === 503) setAiUnavailable(true);
      else toast.error(e.message || "The AI request failed");
    } finally {
      setAiBusy("");
    }
  }
  function acceptAi() {
    if (!aiResult || !curDraft) return;
    patchDraft({ title: aiResult.after.title, bullets: aiResult.after.bullets });
    setEditing(true);
    setAiResult({ ...aiResult, applied: true });
    toast.success("Applied to your draft. Save & re-render to publish it.");
  }
  function undoAi() {
    if (aiResult?.applied) patchDraft({ title: aiResult.before.title, bullets: aiResult.before.bullets });
    setAiResult(null);
  }

  // ↑ ↓ ← → move through slides (not while typing or inside an open menu)
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      const dir = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
      if (!dir) return;
      e.preventDefault();
      setSelected((i) => Math.max(0, Math.min((deck?.slides?.length || 1) - 1, i + dir)));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [deck]);
  useEffect(() => {
    document.querySelector(`[data-rail-i="${selected}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selected]);

  const deckQuizzes = deck?.quizzes ?? [];
  const aiNeedsSetup = aiOn === false || aiUnavailable;
  const aiDisabled = !curDraft || aiNeedsSetup || !!aiBusy;

  const AiButton = ({ label, instruction, audience }) => (
    <button
      disabled={aiDisabled}
      onClick={() => runAi(label, instruction, audience)}
      className="flex items-center justify-between gap-2 rounded-lg border border-[#E8D8C9] bg-white px-3 py-2 text-left text-[13px] font-medium text-[#402B25] transition hover:border-[#E3A98B] hover:bg-[#FFFAF5] disabled:cursor-not-allowed disabled:opacity-50"
    >
      {label}
      {aiBusy === label ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5 text-[#B44A22]" />}
    </button>
  );

  const chip = saving
    ? { text: "Saving…", cls: "bg-[#FDEEE3] text-[#8F3A18]", icon: <Loader2 className="size-3 animate-spin" /> }
    : dirty
    ? { text: "Unsaved changes", cls: "bg-[#FFF3D6] text-[#8A5A00]", icon: <span className="size-1.5 rounded-full bg-[#FFC93C]" /> }
    : { text: `Saved${meta.version > 1 ? ` · v${meta.version}` : ""}`, cls: "bg-[#E6F2E8] text-[#3F6B47]", icon: <Check className="size-3" /> };

  return (
    <div data-learnova-app data-lv-shell className="flex h-svh flex-col bg-[#FFFAF5] text-[#402B25]">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-white px-3 sm:px-4">
        <Button asChild variant="ghost" size="icon" className="size-10 shrink-0 rounded-full" title="Back to My Decks">
          <Link to="/app/presentations" aria-label="Back to My Decks">
            <ArrowLeft />
          </Link>
        </Button>
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <p className="t-card truncate" title={summary?.source_name || ""}>
            {summary?.source_name || deck?.job_id || "Presentation"}
          </p>
          <span className={cn("hidden shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-semibold sm:inline-flex", chip.cls)}>
            {chip.icon} {chip.text}
          </span>
          <span className="t-meta hidden truncate xl:block">
            {summary ? `${summary.slide_count} slides · ${summary.quiz_count} quizzes` : ""}
            {summary?.overall_score != null ? ` · ${summary.overall_score}/100` : ""}
            {estMin ? ` · ≈ ${estMin} min` : ""}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {editing ? (
            <>
              <Button size="sm" onClick={save} disabled={saving || !dirty} className="h-9 rounded-full bg-[#F47B45] px-4 font-bold text-[#2A1A14] hover:-translate-y-px hover:bg-[#FF8A58]">
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
                    <Button size="sm" variant="ghost" className="hidden md:inline-flex">
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
              <Button size="sm" variant="outline" onClick={() => { setEditing(true); setTab("content"); }}>
                <Pencil /> <span className="hidden sm:inline">Edit</span>
              </Button>
              <Button asChild variant="outline" size="sm" className="hidden md:inline-flex">
                <Link to={`/app/compare/${jobId}`}>
                  <GitCompare /> Before vs after
                </Link>
              </Button>
            </>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline">
                <Download /> <span className="hidden sm:inline">Export</span> <ChevronDown className="size-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem onSelect={() => download("pptx")}>
                <FileDown /> PowerPoint (.pptx)
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => download("html")}>
                <Download /> Web deck (.html)
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to={`/app/export/${jobId}`}>
                  <Check /> Finish &amp; share
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            size="icon"
            variant="ghost"
            className="hidden size-9 rounded-full text-[#715A4E] md:inline-flex"
            onClick={() => setHelpOpen(true)}
            title="Keyboard shortcuts (?)"
            aria-label="Keyboard shortcuts"
          >
            <Keyboard />
          </Button>
          <Button asChild size="sm" className="h-9 rounded-full bg-[#402B25] px-4 text-white hover:-translate-y-px hover:bg-[#2E1E19]">
            <Link to={`/app/present/${jobId}`}>
              <Play className="fill-current" /> Present
            </Link>
          </Button>
        </div>
      </header>

      {error ? (
        <p className="border-b bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</p>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:grid lg:grid-cols-[232px_minmax(0,1fr)_340px] lg:overflow-hidden">
        {/* Slides rail */}
        <aside className="shrink-0 border-b bg-white lg:min-h-0 lg:overflow-y-auto lg:border-b-0 lg:border-r" aria-label="Slides">
          <ul className="lv-no-scrollbar flex gap-2 overflow-x-auto p-3 lg:flex-col lg:overflow-x-visible" role="listbox" aria-label="Slides">
            {!deck
              ? Array.from({ length: 6 }).map((_, i) => <li key={i} className="lv-skel h-16 w-40 shrink-0 lg:w-auto" />)
              : slides.map((s, i) => (
                  <li key={s.index ?? i} className="w-44 shrink-0 lg:w-auto">
                    <button
                      data-rail-i={i}
                      role="option"
                      aria-selected={i === selected}
                      onClick={() => setSelected(i)}
                      className={cn(
                        "group flex w-full gap-2.5 rounded-[10px] border p-2 text-left transition",
                        i === selected
                          ? "border-[#C2502A] bg-[#FDEEE3] shadow-[0_0_0_3px_rgb(194_80_42/0.12)]"
                          : "border-transparent hover:border-[#E8D8C9] hover:bg-[#FFFAF5]"
                      )}
                    >
                      <span
                        className={cn(
                          "grid size-7 shrink-0 place-items-center rounded-md text-[12px] font-bold tabular-nums",
                          i === selected ? "bg-[#C2502A] text-white" : "bg-[#F3E6DA] text-[#715A4E]"
                        )}
                      >
                        {i + 1}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 text-[12.5px] font-semibold leading-4 text-[#402B25]">
                          {draft?.[i]?.title || s.title}
                        </span>
                        {s.family || s.variant ? (
                          <span className="mt-1 inline-block max-w-full truncate rounded bg-[#EFE1D4] px-1.5 py-px text-[10px] font-medium text-[#664F44]">
                            {(s.variant || s.family || "").toString().replace(/_/g, " ").toLowerCase()}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  </li>
                ))}
          </ul>
        </aside>

        {/* Canvas */}
        <div className="flex min-h-[300px] min-w-0 items-center justify-center bg-[#F3E6DA] p-4 sm:p-6 lg:min-h-0">
          {htmlUrl ? (
            <div className="aspect-video w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-[0_18px_50px_-18px_rgb(64_43_37/0.35),0_2px_6px_rgb(64_43_37/0.08)]">
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
            <div className="lv-skel aspect-video w-full max-w-4xl rounded-xl" />
          )}
        </div>

        {/* Inspector */}
        <aside className="min-h-0 border-t bg-white lg:overflow-y-auto lg:border-l lg:border-t-0" aria-label="Inspector">
          <Tabs value={tab} onValueChange={setTab} className="flex flex-col">
            <TabsList className="m-3 grid h-9 grid-cols-4 rounded-lg bg-[#F3E6DA] p-0.5">
              {[
                ["design", "Design"],
                ["content", "Content"],
                ["quiz", "Quiz"],
                ["ai", "AI"],
              ].map(([v, l]) => (
                <TabsTrigger key={v} value={v} className="relative rounded-md px-2 text-[13px] data-[state=active]:text-[#8F3A18]">
                  {l}
                  {v === "ai" && aiNeedsSetup ? <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-[#FFC93C]" title="Needs setup" /> : null}
                  {v === "ai" && aiOn ? <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-[#6B9B72]" /> : null}
                </TabsTrigger>
              ))}
            </TabsList>

            <div className="px-4 pb-6">
              <p className="t-meta mb-3 font-semibold uppercase tracking-wide">
                {editing ? "Editing slide" : "Slide"} {selected + 1}
                {slides.length ? ` of ${slides.length}` : ""}
              </p>

              <TabsContent value="design" className="mt-0 flex flex-col gap-4">
                {!cur ? (
                  <div className="lv-skel h-40" />
                ) : (
                  <>
                    {editing && curDraft ? (
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Visual</label>
                        <Select value={curDraft.family || ""} onValueChange={(v) => patchDraft({ family: v || null })}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {FAMILIES.map(([v, label]) => (
                              <SelectItem key={v || "auto"} value={v}>{label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    ) : (
                      <Prop label="Visual">
                        <span className="font-medium">{cur.variant || cur.treatment || cur.layout_type}</span>
                        {cur.family ? <span className="text-muted-foreground"> · {cur.family}</span> : null}
                      </Prop>
                    )}
                    <Prop label="Transition in">
                      <Badge variant="secondary">{cur.transition || "slide"}</Badge>
                      {cur.transition_reason ? <p className="mt-1 text-xs text-muted-foreground">{cur.transition_reason}</p> : null}
                    </Prop>
                    <Prop label="Summarisation">
                      <Badge variant={cur.summary_directive === "PRESERVE" ? "warning" : cur.summary_directive === "COMPRESS" ? "destructive" : "secondary"}>
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
                    {editing && (imageSlides.includes(selected) || cur?.has_image) ? (
                      <Button variant="outline" size="sm" onClick={openFigureEditor}>
                        <ImageIcon /> Crop / highlight figure
                      </Button>
                    ) : null}
                    {cur.mermaid_code || (cur.family && /PROCESS|FLOW|DECISION|STATE/.test(cur.family)) ? (
                      <Button asChild variant="outline" size="sm" className="w-full">
                        <Link to={`/app/diagram/${jobId}/${selected}`}>Open in diagram editor</Link>
                      </Button>
                    ) : null}
                  </>
                )}
              </TabsContent>

              <TabsContent value="content" className="mt-0 flex flex-col gap-4">
                {editing && curDraft ? (
                  <>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Title</label>
                      <Input value={curDraft.title || ""} onChange={(e) => patchDraft({ title: e.target.value })} />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Points (one per line)</label>
                      <Textarea
                        rows={7}
                        value={(curDraft.bullets || []).join("\n")}
                        onChange={(e) => patchDraft({ bullets: e.target.value.split("\n").map((x) => x.trimEnd()).filter(Boolean) })}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Takeaway</label>
                      <Input value={curDraft.takeaway || ""} onChange={(e) => patchDraft({ takeaway: e.target.value })} placeholder="One-line key point (optional)" />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Save re-runs the layout, animation and scoring for the whole deck. Figures are kept and can be cropped or highlighted from the Design tab.
                    </p>
                  </>
                ) : !cur ? (
                  <div className="lv-skel h-40" />
                ) : (
                  <>
                    <Prop label="Title"><span className="font-medium">{curDraft?.title || cur.title}</span></Prop>
                    {(curDraft?.bullets || cur.bullets || []).length ? (
                      <ul className="list-disc space-y-1 pl-4 text-[13px] leading-5">
                        {(curDraft?.bullets || cur.bullets).map((b, i) => <li key={i}>{b}</li>)}
                      </ul>
                    ) : null}
                    <Separator />
                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Speaker notes</span>
                      <pre className="whitespace-pre-wrap rounded-md bg-[#FFFAF5] p-2 text-xs leading-relaxed">
                        {cur.speaker_notes || cur.takeaway || "—"}
                      </pre>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                      <Pencil /> Edit this slide
                    </Button>
                  </>
                )}
              </TabsContent>

              <TabsContent value="quiz" className="mt-0 flex flex-col gap-3">
                {!deck ? (
                  <div className="lv-skel h-32" />
                ) : deckQuizzes.length === 0 ? (
                  <p className="t-body text-muted-foreground">No checkpoint questions in this deck.</p>
                ) : (
                  <>
                    <p className="t-meta">{deckQuizzes.length} checkpoint question{deckQuizzes.length === 1 ? "" : "s"} in this deck</p>
                    {deckQuizzes.map((q, i) => {
                      const letter = String(q.correct ?? "").trim().toUpperCase().slice(0, 1);
                      return (
                        <div key={i} className="rounded-lg border border-[#E8D8C9] p-3">
                          <p className="text-[13px] font-semibold leading-5">{i + 1}. {q.question}</p>
                          <ul className="mt-2 space-y-1">
                            {(q.options || []).slice(0, 4).map((o, k) => (
                              <li
                                key={k}
                                className={cn(
                                  "rounded-md px-2 py-1 text-[12.5px]",
                                  "ABCD"[k] === letter ? "bg-[#E6F2E8] font-medium text-[#3F6B47]" : "bg-[#FFFAF5] text-[#664F44]"
                                )}
                              >
                                {String(o)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </>
                )}
              </TabsContent>

              <TabsContent value="ai" className="mt-0 flex flex-col gap-3">
                {aiNeedsSetup ? (
                  <div className="flex gap-2.5 rounded-lg border border-[#FFE29A] bg-[#FFF8E1] p-3 text-[13px] leading-5 text-[#6B4A00]">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                    <p>
                      <b>AI isn’t configured on this server.</b> Add a key in <code className="rounded bg-white/70 px-1">.env</code> (for example GROQ_API_KEY),
                      restart the server, and these tools switch on.
                    </p>
                  </div>
                ) : (
                  <p className="t-body text-muted-foreground">Rewrite this slide with one click. You review a before/after before anything changes.</p>
                )}
                <div className="grid gap-1.5">
                  <AiButton label="Improve this slide" instruction="Improve clarity and flow while keeping every fact." />
                  <AiButton label="Make shorter" instruction="Make it shorter: fewer, tighter bullets." />
                  <AiButton label="Explain like I'm new" instruction="Explain it for someone completely new to the topic, with simple words." />
                </div>
                <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Rewrite for</p>
                <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                  {["Grade 6", "University", "Executive"].map((a) => (
                    <AiButton key={a} label={a} instruction="Rewrite this slide for the target audience." audience={a} />
                  ))}
                </div>

                {aiResult ? (
                  <div className="mt-1 overflow-hidden rounded-xl border border-[#E8D8C9]">
                    <div className="flex items-center justify-between bg-[#FFFAF5] px-3 py-1.5">
                      <span className="text-[12px] font-semibold">{aiResult.label}</span>
                      {aiResult.applied ? <span className="text-[11px] font-semibold text-[#3F6B47]">Applied</span> : null}
                    </div>
                    {[
                      ["Before", aiResult.before, "bg-[#FFF1F1] text-[#7A2E2E]"],
                      ["After", aiResult.after, "bg-[#E6F2E8] text-[#2F5D37]"],
                    ].map(([l, v, cls]) => (
                      <div key={l} className={cn("border-t px-3 py-2", cls)}>
                        <p className="text-[10px] font-bold uppercase tracking-wider opacity-70">{l}</p>
                        <p className="text-[13px] font-semibold leading-5">{v.title}</p>
                        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12.5px] leading-[18px]">
                          {v.bullets.map((b, i) => <li key={i}>{b}</li>)}
                        </ul>
                      </div>
                    ))}
                    <div className="flex gap-2 border-t bg-white p-2">
                      {!aiResult.applied ? (
                        <Button size="sm" onClick={acceptAi} className="flex-1 bg-[#6B9B72] text-[#04382C] hover:bg-[#0FB88C]">
                          <Check /> Accept
                        </Button>
                      ) : null}
                      <Button size="sm" variant="outline" onClick={undoAi} className="flex-1">
                        <Undo2 /> Undo
                      </Button>
                    </div>
                  </div>
                ) : null}
              </TabsContent>
            </div>
          </Tabs>
        </aside>
      </div>

      <TutorLauncher deckId={jobId} onJumpToSlide={setSelected} />
      <ShortcutsOverlay open={helpOpen} onOpenChange={setHelpOpen} groups={PREVIEW_SHORTCUTS} />

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
