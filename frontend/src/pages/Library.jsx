import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Clock,
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
    navigate("/app/create", { state: { template: { topic: t.topic, text: t.text } } });
  }

  return (
    <AppLayout title="Library">
      <PageContainer>
        {/* header */}
        <div className="relative overflow-hidden rounded-2xl border p-6 sm:p-8">
          <div className="lv-aurora" />
          <div className="relative">
            <p className="inline-flex items-center gap-1.5 rounded-full border bg-background/60 px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              <Sparkles className="size-3" /> {TEMPLATES.length} ready-made lessons
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight">
              Pick a lesson, hit generate
            </h2>
            <p className="mt-1 max-w-lg text-sm text-muted-foreground">
              Each one is real, complete source material. Open it, tweak a line if
              you want, and you have a deck in a minute. They also show what the
              engine does with each kind of content.
            </p>
          </div>
        </div>

        {/* controls */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search lessons…"
              className="w-56 pl-8"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {["all", ...Object.keys(TEMPLATE_KINDS)].map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  kind === k
                    ? "border-primary bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted/60"
                )}
              >
                {k === "all" ? "All" : TEMPLATE_KINDS[k].label}
              </button>
            ))}
          </div>
        </div>

        {/* grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((t, i) => {
            const M = KIND_META[t.kind] ?? KIND_META.concept;
            return (
              <Card
                key={t.id}
                className="lv-card lv-in group flex flex-col overflow-hidden"
                style={{ animationDelay: `${i * 45}ms` }}
              >
                <CardContent className="flex flex-1 flex-col gap-3 p-5">
                  <div className="flex items-center justify-between">
                    <span className={cn("flex size-9 items-center justify-center rounded-lg bg-primary/10", M.ring)}>
                      <M.icon className="size-5" />
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                      <Clock className="size-3" /> ~{t.minutes} min
                    </span>
                  </div>
                  <div>
                    <h3 className="font-medium leading-snug">{t.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{t.blurb}</p>
                  </div>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
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
                    <pre className="mt-1 max-h-56 overflow-auto rounded-lg border bg-muted/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
                      {t.text}
                    </pre>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </div>

        {filtered.length === 0 ? (
          <Card>
            <CardContent className="p-10 text-center text-sm text-muted-foreground">
              No lessons match that. Clear the filters, or{" "}
              <button className="underline" onClick={() => navigate("/app/create")}>
                start from your own content
              </button>
              .
            </CardContent>
          </Card>
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
              <button onClick={() => navigate("/app/create")}>
                Open Create <ArrowRight />
              </button>
            </Button>
          </CardContent>
        </Card>
      </PageContainer>
    </AppLayout>
  );
}
