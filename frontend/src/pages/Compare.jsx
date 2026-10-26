import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, ArrowRight, Check, GitCompare, ImageIcon, Lightbulb } from "lucide-react";
import * as api from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const pct = (n) => `${Math.round(Number(n) || 0)}%`;

function Stat({ label, children, bar }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 text-xl font-semibold tabular-nums">{children}</div>
      {bar != null ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.min(100, bar)}%` }} />
        </div>
      ) : null}
    </Card>
  );
}

function Arrow({ a, b }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-muted-foreground">{a}</span>
      <ArrowRight className="size-4 text-muted-foreground" />
      <span>{b}</span>
    </span>
  );
}

function Summary({ s }) {
  const types = Object.entries(s.visual_types || {});
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Stat label="Visual coverage" bar={s.visual_coverage_after_pct}>
        <Arrow a={pct(s.visual_coverage_before_pct)} b={pct(s.visual_coverage_after_pct)} />
        <span className="ml-2 text-xs font-normal text-muted-foreground">
          {s.visual_slides_before}→{s.visual_slides_after} of {s.slides_after} slides
        </span>
      </Stat>
      <Stat label="Words">
        <Arrow a={s.words_before} b={s.words_after} />
        <span className="ml-2 text-xs font-normal text-muted-foreground">{s.words_change_pct > 0 ? "+" : ""}{pct(s.words_change_pct)}</span>
      </Stat>
      <Stat label="Fact retention" bar={s.fact_retention_pct}>
        {pct(s.fact_retention_pct)}
        <span className="ml-2 text-xs font-normal text-muted-foreground">{s.facts_kept}/{s.facts_total} facts</span>
      </Stat>
      <Stat label="Illustrations">{s.illustrations ?? 0}</Stat>
      <Stat label={`Visual types (${s.distinct_visual_types ?? types.length})`}>
        <div className="flex flex-wrap gap-1">
          {types.length ? types.map(([k, v]) => <Badge key={k} variant="secondary">{k} · {v}</Badge>) : <span className="text-sm font-normal text-muted-foreground">—</span>}
        </div>
      </Stat>
      <Stat label="Engagement score" bar={s.engagement_score}>
        {Math.round(Number(s.engagement_score) || 0)}<span className="text-sm font-normal text-muted-foreground"> / 100</span>
      </Stat>
    </div>
  );
}

function SlideRow({ s }) {
  const { before: b = {}, after: a = {}, change: c = {} } = s;
  const missing = c.facts_missing ?? [];
  const delta = c.words_delta ?? 0;
  return (
    <Card className="grid overflow-hidden md:grid-cols-2">
      <div className="space-y-2 bg-[#F7EFE8] p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Original · {s.index}</p>
          <Badge variant="outline">{b.visual || "text only"}</Badge>
        </div>
        <h3 className="font-medium">{b.title || s.title}</h3>
        <p className="line-clamp-[10] whitespace-pre-line text-sm text-muted-foreground">{b.text}</p>
        <p className="text-xs text-muted-foreground">{b.words ?? 0} words{b.has_figure ? " · figure" : ""}{b.has_table ? " · table" : ""}</p>
      </div>
      <div className="space-y-2 border-t p-4 md:border-l md:border-t-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#B44A22]">New slide</p>
          <div className="flex flex-wrap gap-1">
            {a.family_label ? <Badge>{a.family_label}</Badge> : null}
            <Badge variant={delta <= 0 ? "success" : "warning"}>{delta > 0 ? "+" : ""}{delta} words</Badge>
          </div>
        </div>
        <h3 className="font-medium">{a.title || s.title}</h3>
        {a.reason ? <p className="flex items-start gap-1 text-xs text-muted-foreground"><Lightbulb className="mt-px size-3 shrink-0" /> <span className="line-clamp-1">{a.reason}</span></p> : null}
        {a.bullets?.length ? (
          <ul className="list-disc space-y-0.5 pl-5 text-sm">{a.bullets.map((x, i) => <li key={i}>{x}</li>)}</ul>
        ) : null}
        {a.takeaway ? <p className="rounded-lg bg-[#FCE5D6] px-2.5 py-1.5 text-sm font-medium text-[#6B2A10]">{a.takeaway}</p> : null}
        {a.notes?.length ? <p className="text-xs italic text-muted-foreground">Notes: {a.notes.join(" ")}</p> : null}
        {a.has_illustration ? (
          <Badge variant="secondary" className="gap-1 whitespace-normal"><ImageIcon className="size-3 shrink-0" /> {a.illustration_reason || "Illustration"}</Badge>
        ) : null}
        <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
          <span className={cn("font-semibold", missing.length ? "text-[#A53125]" : "text-[#2F5D37]")}>
            Facts kept {c.facts_kept ?? 0}/{c.facts_total ?? 0}
          </span>
          {missing.map((m, i) => (
            <span key={i} className="rounded-full border border-[#F0B9B2] bg-[#FBE9E7] px-2 py-0.5 text-[#8E2A1F]" title={m.kind}>{m.value}</span>
          ))}
        </div>
      </div>
    </Card>
  );
}

function Quiz({ s }) {
  const q = s.quiz || {};
  return (
    <Card className="space-y-2 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium">{q.question || s.title}</h3>
        {q.difficulty ? <Badge variant="outline">{q.difficulty}</Badge> : null}
      </div>
      <ul className="space-y-1 text-sm">
        {(q.options ?? []).map((o, i) => {
          const ok = o === q.correct || i === q.correct || String.fromCharCode(65 + i) === q.correct;
          return (
            <li key={i} className={cn("flex items-center gap-2 rounded-lg border px-2.5 py-1.5", ok && "border-[#6B9B72] bg-[#E6F2E8] text-[#2F5D37]")}>
              {ok ? <Check className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />} {o}
            </li>
          );
        })}
      </ul>
      {q.explanation ? <p className="text-sm text-muted-foreground">{q.explanation}</p> : null}
    </Card>
  );
}

export default function Compare() {
  const { jobId } = useParams();
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading"); // loading | ok | empty | error
  const [error, setError] = useState("");
  const [onlyMissing, setOnlyMissing] = useState(false);

  useEffect(() => {
    let dead = false;
    setState("loading");
    api
      .getAnalysis(jobId)
      .then((d) => !dead && (setData(d), setState("ok")))
      .catch((e) => {
        if (dead) return;
        setError(e.message);
        setState(e.status === 404 ? "empty" : "error");
      });
    return () => {
      dead = true;
    };
  }, [jobId]);

  const content = useMemo(() => (data?.slides ?? []).filter((s) => s.kind !== "quiz"), [data]);
  const quizzes = useMemo(() => (data?.slides ?? []).filter((s) => s.kind === "quiz"), [data]);
  const shown = onlyMissing ? content.filter((s) => s.change?.facts_missing?.length) : content;

  return (
    <div data-learnova-app className="min-h-svh bg-[#FFFAF5] text-[#402B25]">
      <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b bg-white px-3 sm:px-4">
        <Button asChild variant="ghost" size="icon" className="rounded-full">
          <Link to={`/app/preview/${jobId}`} aria-label="Back to preview"><ArrowLeft /></Link>
        </Button>
        <GitCompare className="size-4 text-[#B44A22]" />
        <h1 className="truncate font-semibold">Before vs after{data?.summary?.source_name ? ` · ${data.summary.source_name}` : ""}</h1>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6">
        {state === "loading" ? (
          <div className="space-y-4" role="status" aria-label="Loading comparison">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => <div key={i} className="lv-skel h-24 rounded-2xl" />)}
            </div>
            {Array.from({ length: 3 }).map((_, i) => <div key={i} className="lv-skel h-48 rounded-2xl" />)}
          </div>
        ) : state === "empty" ? (
          <Card className="grid place-items-center gap-3 p-10 text-center">
            <GitCompare className="size-8 text-muted-foreground" />
            <p className="font-medium">No comparison for this deck — regenerate it</p>
            <Button asChild variant="outline" size="sm"><Link to={`/app/preview/${jobId}`}>Back to preview</Link></Button>
          </Card>
        ) : state === "error" ? (
          <Card className="flex items-center gap-3 border-[#F0B9B2] bg-[#FBE9E7] p-4 text-[#8E2A1F]">
            <AlertTriangle className="size-5 shrink-0" /> <span className="text-sm">Could not load the comparison: {error}</span>
          </Card>
        ) : (
          <>
            <Summary s={data.summary || {}} />
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={onlyMissing} onCheckedChange={setOnlyMissing} />
              Only slides with missing facts
              <span className="text-muted-foreground">({content.filter((s) => s.change?.facts_missing?.length).length})</span>
            </label>
            <div className="space-y-4">
              {shown.length ? shown.map((s) => <SlideRow key={s.index} s={s} />) : (
                <p className="py-8 text-center text-sm text-muted-foreground">{onlyMissing ? "No slides are missing facts." : "No slides."}</p>
              )}
            </div>
            {quizzes.length ? (
              <section className="space-y-3">
                <h2 className="text-lg font-semibold">Checkpoints</h2>
                {quizzes.map((s) => <Quiz key={s.index} s={s} />)}
              </section>
            ) : null}
          </>
        )}
      </main>
    </div>
  );
}
