import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import FileDropzone from "@/components/app/FileDropzone";
import GenerationPipeline from "@/components/app/GenerationPipeline";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
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

  const [density, setDensity] = useState(
    () => localStorage.getItem("learnova-default-density") || "medium"
  );
  const [quizFreq, setQuizFreq] = useState(
    () => localStorage.getItem("learnova-default-quizfreq") || "4"
  );
  const [quizStyle, setQuizStyle] = useState("inline"); // "inline" | "slide"
  const [quizAfter, setQuizAfter] = useState(""); // e.g. "3, 7, 11"
  const [ocr, setOcr] = useState(true);
  const [wantPptx, setWantPptx] = useState(true);
  const [wantHtml, setWantHtml] = useState(true);
  const [enrich, setEnrich] = useState(true);
  const [themes, setThemes] = useState([]);
  const [themeId, setThemeId] = useState("auto");

  const [phase, setPhase] = useState("input"); // input | review | generating | done
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const poll = useRef(null);

  useEffect(() => () => clearInterval(poll.current), []);
  useEffect(() => {
    api.listThemes().then((r) => setThemes(r.themes || [])).catch(() => {});
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
        setError("This is taking longer than expected — check Projects in a minute.");
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

  return (
    <AppLayout title="Create">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Create a learning experience</h2>
          <p className="text-sm text-muted-foreground">
            Upload a document or paste a syllabus. Review the structure, then generate.
          </p>
        </div>

        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {phase === "input" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">1 · Provide your content</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs value={tab} onValueChange={setTab}>
                <TabsList className="mb-4">
                  <TabsTrigger value="upload">Upload file</TabsTrigger>
                  <TabsTrigger value="paste">Paste syllabus</TabsTrigger>
                </TabsList>
                <TabsContent value="upload">
                  <FileDropzone file={file} onFile={onUploadFile} onClear={() => setFile(null)} disabled={busy} />
                  {busy && file ? (
                    <p className="mt-3 text-xs text-muted-foreground">Converting {file.name}…</p>
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
                      className="font-mono text-xs"
                    />
                  </div>
                  <Button onClick={onUseTyped} disabled={busy || !typed.trim()} className="self-start">
                    Continue <ArrowRight />
                  </Button>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        )}

        {phase === "review" && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">2 · Review the structure</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                <p className="text-xs text-muted-foreground">
                  This markdown is what the pipeline reasons over — edits here change the deck.{" "}
                  {sections} section{sections === 1 ? "" : "s"} detected.
                </p>
                <Textarea
                  rows={12}
                  value={markdown}
                  onChange={(e) => setMarkdown(e.target.value)}
                  spellCheck={false}
                  className="font-mono text-xs"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">3 · Options</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-5">
                <div className="flex flex-col gap-2">
                  <Label>Text density</Label>
                  <RadioGroup value={density} onValueChange={setDensity} className="grid gap-2 sm:grid-cols-2">
                    {DENSITIES.map((d) => (
                      <label
                        key={d.id}
                        htmlFor={`d-${d.id}`}
                        className={cn(
                          "flex cursor-pointer flex-col gap-1 rounded-lg border p-3 text-sm transition-colors",
                          density === d.id ? "border-primary bg-primary/5" : "hover:bg-muted/40"
                        )}
                      >
                        <span className="flex items-center gap-2 font-medium">
                          <RadioGroupItem id={`d-${d.id}`} value={d.id} />
                          {d.label}
                        </span>
                        <span className="text-xs text-muted-foreground">{d.desc}</span>
                      </label>
                    ))}
                  </RadioGroup>
                </div>

                <p className="text-xs text-muted-foreground">
                  Learnova reads your content and decides automatically what to
                  keep as text, summarise, or turn into a flowchart, timeline,
                  comparison, chart, or diagram — per slide.
                </p>

                <div className="flex flex-wrap items-center gap-6">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="qf" className="text-sm">Quiz every</Label>
                    <Select value={quizFreq} onValueChange={setQuizFreq} disabled={!!quizAfter.trim()}>
                      <SelectTrigger id="qf" className="w-20">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {["2", "3", "4", "5", "6"].map((n) => (
                          <SelectItem key={n} value={n}>{n}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <span className="text-sm text-muted-foreground">slides</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label htmlFor="qstyle" className="text-sm">Checkpoint</Label>
                    <Select value={quizStyle} onValueChange={setQuizStyle}>
                      <SelectTrigger id="qstyle" className="w-32">
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
                <div className="flex items-center gap-2">
                  <Label htmlFor="qafter" className="text-sm whitespace-nowrap">
                    …or after slides
                  </Label>
                  <Input
                    id="qafter"
                    value={quizAfter}
                    onChange={(e) => setQuizAfter(e.target.value)}
                    placeholder="e.g. 3, 7, 11"
                    className="max-w-[180px]"
                  />
                  <span className="text-xs text-muted-foreground">
                    a full checkpoint slide goes in after each
                  </span>
                </div>

                {themes.length ? (
                  <div className="rounded-lg border bg-muted/30 p-3">
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Theme
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {themes.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => setThemeId(t.id)}
                          title={t.name}
                          className={cn(
                            "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition-colors",
                            themeId === t.id
                              ? "border-primary bg-primary/10"
                              : "hover:bg-muted/60"
                          )}
                        >
                          {t.primary ? (
                            <span className="flex gap-0.5">
                              <span className="size-3 rounded-full" style={{ background: t.primary }} />
                              <span className="size-3 rounded-full" style={{ background: t.secondary }} />
                            </span>
                          ) : (
                            <span className="text-muted-foreground">✦</span>
                          )}
                          {t.name}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="rounded-lg border bg-muted/30 p-3">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Outputs
                  </p>
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                    <label className="flex items-center gap-2 text-sm">
                      <Switch checked={wantHtml} onCheckedChange={setWantHtml} />
                      Interactive web deck
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <Switch checked={wantPptx} onCheckedChange={setWantPptx} />
                      Animated PowerPoint
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <Switch checked={enrich} onCheckedChange={setEnrich} />
                      Examples & analogies
                    </label>
                  </div>
                </div>

                <Button onClick={onGenerate} disabled={busy} className="self-start">
                  <Sparkles /> Generate deck
                </Button>
              </CardContent>
            </Card>
          </>
        )}

        {(phase === "generating" || phase === "done") && (
          <Card>
            <CardContent className="p-6">
              <GenerationPipeline
                stage={job?.stage}
                progress={job?.progress}
                status={phase === "done" ? "done" : job?.stage_status || "running"}
              />
              {phase === "done" ? (
                <p className="mt-4 text-sm text-muted-foreground">Opening your presentation…</p>
              ) : null}
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
