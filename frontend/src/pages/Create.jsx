import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Check, Sparkles } from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import FileDropzone from "@/components/app/FileDropzone";
import GenerationPipeline from "@/components/app/GenerationPipeline";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import DesignPicker, { AUTO_DESIGN, DesignChips, designOptions } from "@/components/app/DesignPicker";
import { PageHeader } from "@/components/app/Page";
import { readPref } from "@/lib/storage";
import { cn } from "@/lib/utils";

const POLL_MS = 800;

const DENSITIES = [
  { id: "low", label: "Low", desc: "Headline only — presenter-led decks." },
  { id: "medium", label: "Medium", desc: "Balanced — teaching and self-study." },
  { id: "teaching", label: "Teaching", desc: "Explain every step, one reveal per click." },
  { id: "heavy", label: "Heavy", desc: "Study notes — examples and revision points." },
];

export default function Create() {
  const navigate = useNavigate();
  const location = useLocation();
  const tpl = location.state?.template;
  const [tab, setTab] = useState(tpl ? "paste" : "upload");

  const [file, setFile] = useState(null);
  const [topic, setTopic] = useState(tpl?.topic ?? "");
  const [typed, setTyped] = useState(tpl?.text ?? "");

  const [job, setJob] = useState(null);
  const [markdown, setMarkdown] = useState("");
  const [sections, setSections] = useState(0);

  const [density, setDensity] = useState(() => readPref("learnova-default-density", "medium") || "medium");
  const [quizFreq, setQuizFreq] = useState(() => readPref("learnova-default-quizfreq", "4") || "4");
  const [quizStyle, setQuizStyle] = useState("inline"); // "inline" | "slide"
  const [quizAfter, setQuizAfter] = useState(""); // e.g. "3, 7, 11"
  const [ocr, setOcr] = useState(true);
  const [wantPptx, setWantPptx] = useState(true);
  const [wantHtml, setWantHtml] = useState(true);
  const [enrich, setEnrich] = useState(true);
  const [themes, setThemes] = useState([]); // legacy curated presets, only used when the palette API is missing
  const [themeId, setThemeId] = useState("auto");
  const [design, setDesign] = useState(AUTO_DESIGN);
  const [paletteApi, setPaletteApi] = useState(true);

  const [phase, setPhase] = useState("input"); // input | review | generating | done
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const poll = useRef(null);

  useEffect(() => () => clearInterval(poll.current), []);
  useEffect(() => {
    api.listThemes().then((r) => setThemes(r.themes || [])).catch(() => {});
    api.listPalettes().then(() => setPaletteApi(true)).catch(() => setPaletteApi(false));
  }, []);

  const loadMarkdown = useCallback(async (id) => {
    const md = await api.getMarkdown(id);
    setMarkdown(md.markdown ?? "");
    setSections(md.section_count ?? 0);
    setPhase("review");
  }, []);

  const watch = useCallback((id, onSettled) => {
    clearInterval(poll.current);
    const startedAt = Date.now();
    const MAX_MS = 25 * 60 * 1000; // matches the backend generation watchdog
    let misses = 0;
    poll.current = setInterval(async () => {
      if (Date.now() - startedAt > MAX_MS) {
        clearInterval(poll.current);
        setBusy(false);
        setError("This is taking longer than expected — check My Decks in a minute.");
        return;
      }
      try {
        const next = await api.getJob(id);
        misses = 0;
        setJob(next);
        if (["awaiting_review", "done", "failed"].includes(next.status)) {
          clearInterval(poll.current);
          setBusy(false);
          if (next.status === "failed") {
            setError(next.error || "The job failed.");
            setPhase("review");
          } else onSettled?.(next);
        }
      } catch (e) {
        // Tolerate a few transient errors (server restart, brief network drop)
        // before giving up — the job may still be fine.
        if (++misses >= 5) {
          clearInterval(poll.current);
          setBusy(false);
          setError(e.message);
        }
      }
    }, POLL_MS);
  }, []);

  async function onUploadFile(f) {
    setFile(f);
    setError("");
    setBusy(true);
    try {
      const created = await api.uploadDocument(f);
      setJob(created);
      watch(created.id, (s) => loadMarkdown(s.id));
    } catch (e) {
      setBusy(false);
      setError(e.message);
    }
  }

  async function onUseTyped() {
    if (!typed.trim()) return;
    setError("");
    setBusy(true);
    try {
      const created = await api.createTypedJob(typed, topic || "Typed syllabus");
      setJob(created);
      await loadMarkdown(created.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onGenerate() {
    if (!job) return;
    setError("");
    setBusy(true);
    setPhase("generating");
    try {
      await api.saveMarkdown(job.id, markdown);
      const positions = quizAfter
        .split(/[,\s]+/)
        .map((n) => parseInt(n, 10))
        .filter((n) => Number.isInteger(n) && n > 0);
      await api.startGenerate(job.id, {
        theme_id: themeId,
        quiz_frequency: Number(quizFreq),
        quiz_style: quizStyle,
        quiz_positions: positions.length ? positions : null,
        enable_vision_ocr: ocr,
        enable_quizzes: Number(quizFreq) > 0 || positions.length > 0,
        enable_enhancement: enrich,
        build_pptx: wantPptx,
        build_html: wantHtml,
        text_density: density,
        markdown,
        ...designOptions(design), // only present when a palette / template was picked explicitly
      });
      watch(job.id, (s) => {
        if (s.status === "done") {
          setPhase("done");
          setTimeout(() => navigate(`/app/preview/${s.id}`), 700);
        }
      });
    } catch (e) {
      setBusy(false);
      setError(e.message);
      setPhase("review");
    }
  }

  const step = phase === "input" ? 1 : phase === "review" ? 2 : 3;
  const STEPS = ["Content", "Review", "Generate"];
  const card = "lv-surface lv-r-hero p-5 sm:p-6";

  return (
    <AppLayout title="Create">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <PageHeader
          title="Create a deck"
          subtitle="Upload a document or paste a syllabus. Review the structure, then generate."
        />

        <ol className="flex items-center gap-2" aria-label="Progress">
          {STEPS.map((l, i) => {
            const n = i + 1;
            const done = step > n;
            const on = step === n;
            return (
              <li key={l} className="flex items-center gap-2" aria-current={on ? "step" : undefined}>
                <span
                  className={cn(
                    "grid size-7 place-items-center rounded-full text-[12px] font-bold tabular-nums transition-colors",
                    on ? "bg-[#F47B45] text-[#2A1A14]" : done ? "bg-[#6B9B72] text-[#1F3A25]" : "bg-[#F3E6DA] text-[#715A4E]"
                  )}
                >
                  {done ? <Check className="size-3.5" strokeWidth={3.5} /> : n}
                </span>
                <span className={cn("text-[13px] font-semibold", on ? "text-[#402B25]" : "text-[#715A4E]")}>{l}</span>
                {n < STEPS.length ? <span aria-hidden className="mx-1 h-px w-6 bg-[#DCC6B4] sm:w-10" /> : null}
              </li>
            );
          })}
        </ol>

        {error ? (
          <Alert variant="destructive" className="rounded-xl bg-[#FBE9E7]">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {phase === "input" && (
          <section className={card}>
            <h2 className="t-h2 mb-4">Provide your content</h2>
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="mb-4 h-11 rounded-full bg-[#F3E6DA] p-1">
                <TabsTrigger value="upload" className="h-9 rounded-full px-4 data-[state=active]:text-[#8F3A18]">Upload file</TabsTrigger>
                <TabsTrigger value="paste" className="h-9 rounded-full px-4 data-[state=active]:text-[#8F3A18]">Paste syllabus</TabsTrigger>
              </TabsList>
              <TabsContent value="upload">
                <FileDropzone file={file} onFile={onUploadFile} onClear={() => setFile(null)} disabled={busy} />
                {busy && file ? (
                  <p className="mt-3 flex items-center gap-2 text-[13px] text-[#715A4E]" role="status">
                    <span className="size-3.5 animate-spin rounded-full border-2 border-[#E3A98B] border-t-[#C2502A]" /> Converting {file.name}…
                  </p>
                ) : null}
              </TabsContent>
              <TabsContent value="paste" className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="topic">Topic (optional)</Label>
                  <Input
                    id="topic"
                    placeholder="Natural Language Processing"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="h-11 rounded-xl bg-white"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="syllabus">Content</Label>
                  <Textarea
                    id="syllabus"
                    rows={8}
                    placeholder={"## Chapter 1: Introduction\n- Key idea one\n- Key idea two"}
                    value={typed}
                    onChange={(e) => setTyped(e.target.value)}
                    className="rounded-xl bg-white font-mono text-xs"
                  />
                </div>
                <Button onClick={onUseTyped} disabled={busy || !typed.trim()} className="h-11 self-start rounded-full px-6 bg-[#F47B45] font-bold text-[#2A1A14] hover:-translate-y-0.5 hover:bg-[#FF8A58]">
                  Continue <ArrowRight />
                </Button>
              </TabsContent>
            </Tabs>
          </section>
        )}

        {phase === "review" && (
          <>
            <section className={card}>
              <h2 className="t-h2 mb-1">Review the structure</h2>
              <p className="mb-3 text-[13px] text-[#715A4E]">
                This markdown is what the pipeline reasons over — edits here change the deck. {sections} section
                {sections === 1 ? "" : "s"} detected.
              </p>
              <Textarea
                rows={12}
                value={markdown}
                onChange={(e) => setMarkdown(e.target.value)}
                spellCheck={false}
                aria-label="Deck markdown"
                className="rounded-xl bg-white font-mono text-xs"
              />
            </section>

            <section className={cn(card, "flex flex-col gap-5")}>
              <h2 className="t-h2">Options</h2>
              <div className="flex flex-col gap-2">
                <Label>Text density</Label>
                <RadioGroup value={density} onValueChange={setDensity} className="grid gap-2 sm:grid-cols-2">
                  {DENSITIES.map((d) => (
                    <label
                      key={d.id}
                      htmlFor={`d-${d.id}`}
                      className={cn(
                        "flex min-h-[64px] cursor-pointer flex-col gap-1 rounded-xl border bg-white p-3 text-sm transition duration-150 hover:-translate-y-px hover:border-[#E3A98B]",
                        density === d.id ? "border-[#C2502A] bg-[#FDEEE3] ring-2 ring-[#C2502A]/20" : "border-[#E8D8C9]"
                      )}
                    >
                      <span className="flex items-center gap-2 font-semibold">
                        <RadioGroupItem id={`d-${d.id}`} value={d.id} />
                        {d.label}
                      </span>
                      <span className="text-xs text-[#715A4E]">{d.desc}</span>
                    </label>
                  ))}
                </RadioGroup>
              </div>

              <p className="text-[13px] leading-5 text-[#715A4E]">
                Learnova reads your content and decides automatically what to keep as text, summarise, or turn into a
                flowchart, timeline, comparison, chart, or diagram — per slide.
              </p>

              <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <div className="flex items-center gap-2">
                  <Label htmlFor="qf" className="text-sm">Quiz every</Label>
                  <Select value={quizFreq} onValueChange={setQuizFreq} disabled={!!quizAfter.trim()}>
                    <SelectTrigger id="qf" className="h-10 w-20 rounded-xl bg-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["2", "3", "4", "5", "6"].map((n) => (
                        <SelectItem key={n} value={n}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="text-sm text-[#715A4E]">slides</span>
                </div>
                <div className="flex items-center gap-2">
                  <Label htmlFor="qstyle" className="text-sm">Checkpoint</Label>
                  <Select value={quizStyle} onValueChange={setQuizStyle}>
                    <SelectTrigger id="qstyle" className="h-10 w-36 rounded-xl bg-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="inline">Inline band</SelectItem>
                      <SelectItem value="slide">Full slide</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <Switch id="ocr" checked={ocr} onCheckedChange={setOcr} />
                  <Label htmlFor="ocr" className="text-sm">Vision OCR for images</Label>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Label htmlFor="qafter" className="whitespace-nowrap text-sm">…or after slides</Label>
                <Input
                  id="qafter"
                  value={quizAfter}
                  onChange={(e) => setQuizAfter(e.target.value)}
                  placeholder="e.g. 3, 7, 11"
                  className="h-10 max-w-[180px] rounded-xl bg-white"
                />
                <span className="text-xs text-[#715A4E]">a full checkpoint slide goes in after each</span>
              </div>

              <div className="rounded-2xl border border-[#E8D8C9] bg-[#FFFAF5] p-4">
                <p className="mb-2 text-[12px] font-bold uppercase tracking-[0.12em] text-[#715A4E]">Look</p>
                {paletteApi ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <DesignPicker design={design} onChange={setDesign} />
                    <DesignChips design={design} onChange={setDesign} />
                  </div>
                ) : themes.length ? (
                  <div className="flex flex-wrap gap-2">
                    {themes.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setThemeId(t.id)}
                        title={t.name}
                        className={cn(
                          "flex min-h-10 items-center gap-2 rounded-full border bg-white px-3 py-1.5 text-xs font-semibold transition duration-150 hover:-translate-y-px hover:border-[#E3A98B]",
                          themeId === t.id ? "border-[#C2502A] bg-[#FDEEE3] text-[#8F3A18]" : "border-[#E8D8C9] text-[#4F3A31]"
                        )}
                      >
                        {t.primary ? (
                          <span className="flex gap-0.5">
                            <span className="size-3 rounded-full" style={{ background: t.primary }} />
                            <span className="size-3 rounded-full" style={{ background: t.secondary }} />
                          </span>
                        ) : (
                          <Sparkles className="size-3.5 text-[#B44A22]" />
                        )}
                        {t.name}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-[13px] text-[#715A4E]">Auto — Learnova picks the colours from your topic.</p>
                )}
              </div>

              <div className="rounded-2xl border border-[#E8D8C9] bg-[#FFFAF5] p-4">
                <p className="mb-3 text-[12px] font-bold uppercase tracking-[0.12em] text-[#715A4E]">Outputs</p>
                <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                  <label className="flex min-h-10 items-center gap-2 text-sm">
                    <Switch checked={wantHtml} onCheckedChange={setWantHtml} />
                    Interactive web deck
                  </label>
                  <label className="flex min-h-10 items-center gap-2 text-sm">
                    <Switch checked={wantPptx} onCheckedChange={setWantPptx} />
                    Animated PowerPoint
                  </label>
                  <label className="flex min-h-10 items-center gap-2 text-sm">
                    <Switch checked={enrich} onCheckedChange={setEnrich} />
                    Examples &amp; analogies
                  </label>
                </div>
              </div>

              <Button
                onClick={onGenerate}
                disabled={busy}
                className="h-11 self-start rounded-full bg-[#F47B45] px-6 text-[14px] font-bold text-[#2A1A14] shadow-[0_10px_22px_-10px_rgb(244_123_69/0.8)] hover:-translate-y-0.5 hover:bg-[#FF8A58]"
              >
                <Sparkles /> Generate deck
              </Button>
            </section>
          </>
        )}

        {(phase === "generating" || phase === "done") && (
          <section>
            <GenerationPipeline
              stage={job?.stage}
              progress={job?.progress}
              status={phase === "done" ? "done" : job?.stage_status || "running"}
            />
            {phase === "done" ? (
              <p className="mt-4 text-sm text-[#715A4E]" role="status">Opening your presentation…</p>
            ) : null}
          </section>
        )}
      </div>
    </AppLayout>
  );
}
