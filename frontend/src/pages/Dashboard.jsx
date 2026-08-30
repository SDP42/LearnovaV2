import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useUser } from "@/auth";
import {
  BarChart3,
  FileStack,
  FolderOpen,
  Images,
  Library,
  Lightbulb,
  ListChecks,
  Presentation,
  Rocket,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import StatCard from "@/components/app/StatCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/app/Page";

function statusVariant(status) {
  if (/ready|done|complete/i.test(status)) return "success";
  if (/draft|await/i.test(status)) return "warning";
  return "secondary";
}

export default function Dashboard() {
  const { user } = useUser();
  const [decks, setDecks] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listMyDecks()
      .then((rows) => setDecks(Array.isArray(rows) ? rows : rows?.decks ?? []))
      .catch((e) => {
        setError(e.message);
        setDecks([]);
      });
  }, []);

  const slideCount = (decks ?? []).reduce((n, d) => n + (d.slide_count ?? d.slides ?? 0), 0);
  const quizCount = (decks ?? []).reduce((n, d) => n + (d.quiz_count ?? d.quizzes ?? 0), 0);
  const avgScore =
    decks && decks.length
      ? Math.round(
          decks.reduce((n, d) => n + (d.overall_score ?? d.engagement ?? 0), 0) / decks.length
        )
      : 0;

  const recent = decks ?? [];
  const maxSlides = Math.max(1, ...recent.map((d) => d.slide_count ?? d.slides ?? 0));

  return (
    <AppLayout title="Dashboard">
      <PageContainer className="gap-5">
        {/* hero */}
        <div className="relative overflow-hidden rounded-2xl border p-6 sm:p-8">
          <div className="lv-aurora" />
          <div className="relative flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
              </p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
                Welcome back{user?.firstName ? `, ${user.firstName}` : ""}
              </h2>
              <p className="mt-1.5 max-w-lg text-sm text-muted-foreground">
                Turn a syllabus, a chapter or a set of notes into a deck that
                explains itself — one idea at a time.
              </p>
            </div>
            <div className="flex flex-col items-stretch gap-2 sm:flex-row">
              <Button asChild size="lg" className="lv-cta rounded-lg">
                <Link to="/app/create">
                  <Sparkles /> New presentation
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/app/library">Browse lessons</Link>
              </Button>
            </div>
          </div>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {/* stat row — spans full width */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {decks === null ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)
          ) : (
            <>
              <StatCard label="Projects" value={decks.length} icon={FileStack} hint="all time" />
              <StatCard label="Slides generated" value={slideCount} icon={Presentation} />
              <StatCard label="Quiz questions" value={quizCount} icon={ListChecks} />
              <StatCard label="Avg engagement" value={`${avgScore}`} icon={TrendingUp} hint="/ 100" />
            </>
          )}
        </div>

        {/* main two-column grid fills the width */}
        <div className="grid gap-5 lg:grid-cols-[1.7fr_1fr]">
          {/* left column */}
          <div className="flex flex-col gap-5">
            <Card className="lv-card">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-base">Recent projects</CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/app/projects">View all</Link>
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {decks === null ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
                  </div>
                ) : recent.length === 0 ? (
                  <div className="mx-auto flex max-w-sm flex-col items-center gap-3 p-12 text-center">
                    <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Images className="size-6" />
                    </div>
                    <p className="text-sm font-medium">Nothing here yet</p>
                    <p className="text-sm text-muted-foreground">
                      Generate your first deck — from your own notes or a
                      ready-made lesson.
                    </p>
                    <div className="flex gap-2">
                      <Button asChild size="sm"><Link to="/app/create">Create</Link></Button>
                      <Button asChild size="sm" variant="outline"><Link to="/app/library">Lessons</Link></Button>
                    </div>
                  </div>
                ) : (
                  <ul className="divide-y">
                    {recent.slice(0, 7).map((d) => {
                      const n = d.slide_count ?? d.slides ?? 0;
                      const id = d.id ?? d.deck_id;
                      return (
                        <li key={id} className="group flex items-center gap-3 px-4 py-3 text-sm">
                          <div className="hidden h-9 w-14 shrink-0 overflow-hidden rounded border bg-gradient-to-br from-primary/10 to-transparent sm:block">
                            <div className="mx-1.5 mt-1.5 h-1 w-2/3 rounded bg-primary/50" />
                            <div className="mx-1.5 mt-1 flex gap-0.5">
                              {[0, 1, 2].map((k) => <div key={k} className="h-3 flex-1 rounded-sm bg-primary/15" />)}
                            </div>
                          </div>
                          <div className="min-w-0 flex-1">
                            <Link to={`/app/preview/${id}`} className="truncate font-medium hover:underline">
                              {d.title ?? d.source_name ?? "Untitled deck"}
                            </Link>
                            <div className="mt-1 flex items-center gap-2">
                              <span className="h-1 w-16 overflow-hidden rounded-full bg-muted">
                                <span className="block h-full rounded-full bg-primary/60" style={{ width: `${(n / maxSlides) * 100}%` }} />
                              </span>
                              <span className="text-xs text-muted-foreground">{n} slides</span>
                              {d.overall_score != null ? (
                                <span className="text-xs text-muted-foreground">· {d.overall_score}/100</span>
                              ) : null}
                            </div>
                          </div>
                          <Badge variant={statusVariant(d.status ?? "ready")}>{d.status ?? "Ready"}</Badge>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card className="lv-card">
              <CardHeader className="flex flex-row items-center gap-2">
                <Rocket className="size-4 text-primary" />
                <CardTitle className="text-base">How a deck comes together</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                {[
                  ["Add source material", "Paste a syllabus or upload a PPTX / PDF."],
                  ["Review the structure", "Edit the outline the engine will reason over."],
                  ["Generate", "Layout, visuals, reveal timing, quizzes and scoring — one pass."],
                  ["Present or export", "Presenter console, animated PPTX, standalone web deck."],
                ].map(([t, d], i) => (
                  <div key={t} className="flex gap-3 rounded-lg border bg-muted/20 p-3">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                      {i + 1}
                    </span>
                    <span>
                      <span className="block text-sm font-medium">{t}</span>
                      <span className="block text-xs text-muted-foreground">{d}</span>
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* right column */}
          <div className="flex flex-col gap-5">
            <Card className="lv-card">
              <CardHeader><CardTitle className="text-base">Jump to</CardTitle></CardHeader>
              <CardContent className="grid grid-cols-2 gap-2">
                {[
                  ["Create", Sparkles, "/app/create"],
                  ["Lessons", Library, "/app/library"],
                  ["Projects", FolderOpen, "/app/projects"],
                  ["Analytics", BarChart3, "/app/analytics"],
                  ["Presentations", Presentation, "/app/presentations"],
                  ["Quizzes", ListChecks, "/app/quizzes"],
                ].map(([label, Icon, to]) => (
                  <Link
                    key={label}
                    to={to}
                    className="group flex flex-col items-start gap-2 rounded-lg border p-3 transition-colors hover:border-primary/40 hover:bg-primary/5"
                  >
                    <span className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary transition-transform group-hover:scale-110">
                      <Icon className="size-4" />
                    </span>
                    <span className="text-sm font-medium">{label}</span>
                  </Link>
                ))}
              </CardContent>
            </Card>

            <Card className="lv-card">
              <CardHeader className="flex flex-row items-center gap-2">
                <Lightbulb className="size-4 text-primary" />
                <CardTitle className="text-base">Tips for better decks</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-3 text-sm text-muted-foreground">
                  <li>
                    <span className="font-medium text-foreground">Use headings.</span> Every{" "}
                    <code className="rounded bg-muted px-1">##</code> is a slide boundary.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Number your steps.</span> Three+
                    ordered items become a flowchart with progressive reveal.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Keep definitions tight.</span>{" "}
                    Precise wording is kept verbatim — don't pad it.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Pick a density.</span> "Teaching"
                    keeps every point; "Low" is headline-only.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Watch the score.</span> Below 70 =
                    a slide is still text-heavy; split it in the editor.
                  </li>
                </ul>
                <Button asChild variant="ghost" size="sm" className="mt-3">
                  <Link to="/app/docs">Read the docs</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </PageContainer>
    </AppLayout>
  );
}
