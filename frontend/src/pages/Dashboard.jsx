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

  return (
    <AppLayout title="Dashboard">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="relative overflow-hidden rounded-2xl border p-6 sm:p-8">
          <div className="lv-aurora" />
          <div className="relative flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
              </p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight">
                Welcome back{user?.firstName ? `, ${user.firstName}` : ""}
              </h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Turn a syllabus, a chapter or a set of notes into a deck that
                explains itself — one idea at a time.
              </p>
            </div>
            <Button asChild size="lg" className="lv-cta rounded-lg">
              <Link to="/app/create">
                <Sparkles /> New presentation
              </Link>
            </Button>
          </div>
        </div>

        {/* quick actions */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Create", "From a doc or notes", Sparkles, "/app/create"],
            ["Lessons", "Ready-made examples", Library, "/app/library"],
            ["Projects", "Everything you've made", FolderOpen, "/app/projects"],
            ["Analytics", "Engagement over time", BarChart3, "/app/analytics"],
          ].map(([label, hint, Icon, to], i) => (
            <Link
              key={label}
              to={to}
              className="lv-card lv-in group flex items-center gap-3 rounded-xl p-4"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary transition-transform group-hover:scale-110">
                <Icon className="size-4" />
              </span>
              <span>
                <span className="block text-sm font-medium">{label}</span>
                <span className="block text-xs text-muted-foreground">{hint}</span>
              </span>
            </Link>
          ))}
        </div>

        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {decks === null ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)
          ) : (
            <>
              <StatCard label="Projects" value={decks.length} icon={FileStack} hint="all time" />
              <StatCard label="Slides generated" value={slideCount} icon={Presentation} />
              <StatCard label="Quiz questions" value={quizCount} icon={ListChecks} />
              <StatCard
                label="Avg engagement"
                value={`${avgScore}`}
                icon={TrendingUp}
                hint="/ 100 (PSF)"
              />
            </>
          )}
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Recent projects</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link to="/app/projects">View all</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {decks === null ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : decks.length === 0 ? (
              <div className="flex flex-col items-center gap-3 p-10 text-center">
                <Images className="size-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  No projects yet. Create your first learning experience.
                </p>
                <Button asChild size="sm">
                  <Link to="/app/create">
                    <Sparkles /> Create presentation
                  </Link>
                </Button>
              </div>
            ) : (
              <ul className="divide-y">
                {decks.slice(0, 8).map((d) => (
                  <li
                    key={d.id ?? d.deck_id}
                    className="flex items-center justify-between gap-3 px-4 py-3 text-sm"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {d.title ?? d.source_name ?? "Untitled deck"}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {d.slide_count ?? d.slides ?? 0} slides
                        {d.updated_at ? ` · ${new Date(d.updated_at).toLocaleDateString()}` : ""}
                      </p>
                    </div>
                    <Badge variant={statusVariant(d.status ?? "ready")}>
                      {d.status ?? "Ready"}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="lv-card">
            <CardHeader className="flex flex-row items-center gap-2">
              <Rocket className="size-4 text-primary" />
              <CardTitle className="text-base">Getting started</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="flex flex-col gap-3 text-sm">
                {[
                  ["Add source material", "Paste a syllabus or upload a PPTX/PDF on the Create screen."],
                  ["Check the structure", "Edit the markdown the engine will reason over — headings and lists drive the visual choices."],
                  ["Generate", "Layout, visuals, reveal timing, quizzes and scoring run in one pass."],
                  ["Present or export", "Open the presenter console, or download the animated PPTX and web deck."],
                ].map(([t, d], i) => (
                  <li key={t} className="flex gap-3">
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                      {i + 1}
                    </span>
                    <span>
                      <span className="font-medium text-foreground">{t}</span>{" "}
                      <span className="text-muted-foreground">— {d}</span>
                    </span>
                  </li>
                ))}
              </ol>
              <Button asChild size="sm" className="mt-4">
                <Link to="/app/create">
                  <Sparkles /> Start now
                </Link>
              </Button>
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
                  <code className="rounded bg-muted px-1">##</code> becomes a slide boundary the
                  engine can reason about.
                </li>
                <li>
                  <span className="font-medium text-foreground">Number your steps.</span> Three or
                  more ordered items turn into a flowchart with progressive reveal.
                </li>
                <li>
                  <span className="font-medium text-foreground">Keep definitions tight.</span>{" "}
                  Precise wording is detected and kept verbatim — don't pad it.
                </li>
                <li>
                  <span className="font-medium text-foreground">Add an LLM key.</span> Groq or NVIDIA
                  unlocks rewriting, analogies and checkpoint quizzes.
                </li>
                <li>
                  <span className="font-medium text-foreground">Watch the PSF score.</span> Below 70
                  usually means a slide is still text-heavy — split it.
                </li>
              </ul>
              <Button asChild variant="ghost" size="sm" className="mt-3">
                <Link to="/app/docs">Read the docs</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
