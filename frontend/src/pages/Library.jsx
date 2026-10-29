import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Clock,
  FileText,
  Download,
  GitBranch,
  History,
  Layers,
  Search,
  Sigma,
  Sparkles,
  Table2,
} from "lucide-react";
import AppLayout from "@/components/app/AppLayout";
import { TEMPLATES, TEMPLATE_KINDS } from "@/lib/templates";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { PageContainer } from "@/components/app/Page";
import { Stagger, StaggerItem } from "@/components/app/motion";
import { NoResults } from "@/components/app/states";
import LibraryToolbar from "@/components/app/LibraryToolbar";
import { listSamples } from "@/api";

const KIND_META = {
  process: { icon: GitBranch, ring: "text-chart-1" },
  worked: { icon: Sigma, ring: "text-chart-3" },
  compare: { icon: Table2, ring: "text-chart-2" },
  data: { icon: BarChart3, ring: "text-chart-4" },
  concept: { icon: Layers, ring: "text-chart-5" },
  timeline: { icon: History, ring: "text-chart-1" },
};

export default function Library() {
  const navigate = useNavigate();
  const [kind, setKind] = useState("all");
  const [q, setQ] = useState("");
  const [preview, setPreview] = useState(null);
  const [samples, setSamples] = useState([]);

  useEffect(() => {
    listSamples().then((s) => setSamples(Array.isArray(s) ? s : [])).catch(() => setSamples([]));
  }, []);

  function pickSample(s) {
    navigate("/app", { state: { sample: { url: s.url, file: s.file, title: s.title } } });
  }

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return TEMPLATES.filter(
      (t) =>
        (kind === "all" || t.kind === kind) &&
        (!term ||
          t.title.toLowerCase().includes(term) ||
          t.blurb.toLowerCase().includes(term))
    );
  }, [kind, q]);

  function use(t) {
    navigate("/app", { state: { template: { topic: t.topic, text: t.text } } });
  }

  return (
    <AppLayout title="Library">
      <PageContainer>
        {/* header */}
        <div className="relative overflow-hidden rounded-3xl border border-[#F4C3A8] bg-[#FDEEE3] p-6 sm:p-8">
          <div className="lv-aurora" />
          <div className="relative">
            <p className="inline-flex items-center gap-1.5 rounded-full border border-[#F4C3A8] bg-white px-3 py-1 text-xs font-semibold text-[#8F3A18]">
              <Sparkles className="size-3" /> {TEMPLATES.length} ready-made lessons
            </p>
            <h2 className="mt-3 font-[Bricolage_Grotesque] text-[28px] font-bold leading-8 tracking-tight text-[#402B25]">
              Pick a lesson, hit generate
            </h2>
            <p className="mt-1.5 max-w-lg text-sm leading-6 text-[#5A453B]">
              Each one is real, complete source material. Open it, tweak a line if
              you want, and you have a deck in a minute. They also show what the
              engine does with each kind of content.
            </p>
          </div>
        </div>

        {/* real lecture files: one click attaches the file to the composer */}
        <SampleSection
          title="Sample lecture files (NLP & ML)"
          note="The PowerPoint, slide PDF, notebook and Word files we test Learnova on. Generate one to see what it does with a real teacher's deck."
          items={samples.filter((s) => s.group !== "built")}
          onPick={pickSample}
        />
        {/* finished decks Learnova already made from those files */}
        <SampleSection
          title="Decks Learnova made"
          note="Finished PowerPoints generated from the lecture files above, plus the Haber process gallery deck. Download one to compare with its source."
          items={samples.filter((s) => s.group === "built")}
          built
        />

        {/* controls */}
        <LibraryToolbar
          query={q}
          onQuery={setQ}
          placeholder="Search lessons…"
          chips={["all", ...Object.keys(TEMPLATE_KINDS)].map((k) => ({ id: k, label: k === "all" ? "All" : TEMPLATE_KINDS[k].label }))}
          chip={kind}
          onChip={setKind}
        />

        {/* grid */}
        <Stagger key={`${kind}-${q}`} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((t) => {
            const M = KIND_META[t.kind] ?? KIND_META.concept;
            return (
              <StaggerItem key={t.id}>
              <Card
                className="lv-card lv-lift group flex h-full flex-col overflow-hidden"
              >
                <CardContent className="flex flex-1 flex-col gap-3 p-5">
                  <div className="flex items-center justify-between">
                    <span className={cn("flex size-10 items-center justify-center rounded-xl bg-[#FCE5D6]", M.ring)}>
                      <M.icon className="size-5" />
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#715A4E]">
                      <Clock className="size-3" /> ~{t.minutes} min
                    </span>
                  </div>
                  <div>
                    <h3 className="font-medium leading-snug">{t.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{t.blurb}</p>
                  </div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-[#715A4E]">
                    {TEMPLATE_KINDS[t.kind].label} · {TEMPLATE_KINDS[t.kind].hint}
                  </p>
                  <div className="mt-auto flex gap-2 pt-1">
                    <Button size="sm" className="flex-1" onClick={() => use(t)}>
                      <Sparkles /> Generate
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPreview(preview?.id === t.id ? null : t)}
                    >
                      {preview?.id === t.id ? "Hide" : "Preview"}
                    </Button>
                  </div>
                  {preview?.id === t.id ? (
                    <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-xl border bg-[#FFFAF5] p-3 text-[11.5px] leading-relaxed text-[#5A453B]">
                      {t.text}
                    </pre>
                  ) : null}
                </CardContent>
              </Card>
              </StaggerItem>
            );
          })}
        </Stagger>

        {filtered.length === 0 ? (
          <NoResults query={q} onClear={() => { setQ(""); setKind("all"); }} />
        ) : null}

        <Card className="lv-card">
          <CardContent className="flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <BookOpen className="mt-0.5 size-5 shrink-0 text-primary" />
              <div>
                <p className="font-medium">Bring your own</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  A syllabus, lecture notes, a PDF, a chapter summary — anything
                  with headings and lists works best.
                </p>
              </div>
            </div>
            <Button asChild variant="outline">
              <button onClick={() => navigate("/app")}>
                Open Create <ArrowRight />
              </button>
            </Button>
          </CardContent>
        </Card>
      </PageContainer>
    </AppLayout>
  );
}

function SampleSection({ title, note, items, onPick, built = false }) {
  if (!items.length) return null;
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h3 className="font-[Bricolage_Grotesque] text-lg font-bold text-[#402B25]">{title}</h3>
        <p className="text-sm text-[#5A453B]">{note}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((s) => (
          <Card key={s.id} className="lv-card lv-lift flex h-full flex-col overflow-hidden">
            <CardContent className="flex flex-1 flex-col gap-2 p-4">
              <div className="flex items-center justify-between">
                <span className={cn("flex size-9 items-center justify-center rounded-xl", built ? "bg-[#E4F1E8] text-chart-2" : "bg-[#FCE5D6] text-chart-1")}>
                  {built ? <Sparkles className="size-4" /> : <FileText className="size-4" />}
                </span>
                <span className="rounded-full bg-[#FFF4EC] px-2 py-0.5 text-[10.5px] font-semibold text-[#8F3A18]">
                  {s.kind} · {(s.size / 1048576).toFixed(1)} MB
                </span>
              </div>
              <h4 className="text-sm font-medium leading-snug">{s.title}</h4>
              <p className="text-xs text-muted-foreground">{s.blurb}</p>
              <p className="text-[10.5px] font-semibold uppercase tracking-wide text-[#715A4E]">{s.subject}</p>
              <div className="mt-auto flex gap-2 pt-1">
                {built ? (
                  <Button size="sm" className="flex-1" asChild>
                    <a href={s.url} download={s.file.split("/").pop()}><Download /> Download PPTX</a>
                  </Button>
                ) : (
                  <>
                    <Button size="sm" className="flex-1" onClick={() => onPick(s)}>
                      <Sparkles /> Generate
                    </Button>
                    <Button size="sm" variant="outline" asChild>
                      <a href={s.url} download={s.file} aria-label={`Download ${s.title}`}><Download /></a>
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
