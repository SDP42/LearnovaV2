import { Link } from "react-router-dom";
import { ListChecks, Monitor, Play, Presentation, Sparkles, Timer } from "lucide-react";
import AppLayout from "@/components/app/AppLayout";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageContainer, PageHeader } from "@/components/app/Page";
import { EmptyState, ErrorNote, LoadingGrid } from "@/components/app/states";

export default function Presentations() {
  const { decks, error } = useDecks();

  return (
    <AppLayout title="Presentations">
      <PageContainer>
        <PageHeader
          title="Presentations"
          subtitle="Open a deck in the editor or start presenting."
          actions={
            <Button asChild>
              <Link to="/app/create"><Sparkles /> New</Link>
            </Button>
          }
        />

        <ErrorNote error={error} />

        {decks === null ? (
          <LoadingGrid count={6} />
        ) : decks.length === 0 ? (
          <EmptyState
            icon={Presentation}
            title="No presentations yet"
            description="Generate your first deck from a syllabus, a chapter or a set of notes."
            action={{ to: "/app/create", label: "Create one" }}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {decks.map((d, idx) => {
              const id = deckId(d);
              const score = d.overall_score ?? null;
              return (
                <Card
                  key={id}
                  className="lv-card lv-in group flex flex-col overflow-hidden"
                  style={{ animationDelay: `${idx * 40}ms` }}
                >
                  <Link
                    to={`/app/preview/${id}`}
                    className="relative flex aspect-video items-center justify-center overflow-hidden border-b bg-gradient-to-br from-primary/10 via-muted/30 to-transparent p-4"
                  >
                    <div className="lv-dots absolute inset-0 opacity-60" />
                    <div className="relative w-full max-w-[210px] rounded-md border bg-card p-3 shadow-sm transition-transform duration-300 group-hover:-translate-y-1 group-hover:shadow-lg">
                      <div className="mb-2 h-2 w-2/3 rounded bg-primary/70" />
                      <div className="flex gap-1.5">
                        {[0, 1, 2].map((k) => (
                          <div key={k} className="h-8 flex-1 rounded bg-primary/15" />
                        ))}
                      </div>
                      <div className="mt-2 space-y-1">
                        <div className="h-1 w-full rounded bg-muted-foreground/25" />
                        <div className="h-1 w-4/5 rounded bg-muted-foreground/25" />
                      </div>
                    </div>
                    <span className="absolute right-2 top-2 rounded-md bg-background/80 px-2 py-0.5 text-[10px] font-medium text-muted-foreground backdrop-blur">
                      {d.slide_count ?? d.slides ?? 0} slides
                    </span>
                  </Link>
                  <CardContent className="flex flex-1 flex-col gap-2 p-4">
                    <p className="truncate text-sm font-medium">{deckTitle(d)}</p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <ListChecks className="size-3" /> {d.quiz_count ?? d.quizzes ?? 0} quizzes
                      </span>
                      {score != null ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="h-1 w-10 overflow-hidden rounded-full bg-muted">
                            <span
                              className="block h-full rounded-full bg-primary"
                              style={{ width: `${Math.min(100, score)}%` }}
                            />
                          </span>
                          {score}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-auto flex gap-2 pt-1">
                      <Button asChild size="sm" variant="outline" className="flex-1">
                        <Link to={`/app/preview/${id}`}>Open</Link>
                      </Button>
                      <Button asChild size="sm" className="flex-1">
                        <Link to={`/app/present/${id}`}><Play /> Present</Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="lv-card">
            <CardContent className="flex flex-col gap-3 p-5">
              <div className="flex items-center gap-2">
                <Monitor className="size-4 text-primary" />
                <p className="font-medium">The presenter console</p>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Hit <span className="font-medium text-foreground">Present</span> to open a
                dual-screen view: current slide, next-slide preview, speaker notes, a
                large timer and wall clock, a filmstrip to jump anywhere, and a
                reveal-step indicator. Open the audience view on a second screen — it
                stays in sync, including blackout.
              </p>
            </CardContent>
          </Card>
          <Card className="lv-card">
            <CardContent className="flex flex-col gap-3 p-5">
              <div className="flex items-center gap-2">
                <Timer className="size-4 text-primary" />
                <p className="font-medium">Keys while presenting</p>
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                {[
                  ["→ / Space", "Next"],
                  ["←", "Previous"],
                  ["Home / End", "First / last"],
                  ["F", "Fullscreen"],
                  ["B or .", "Blackout"],
                  ["P / R", "Pause / reset timer"],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between gap-2">
                    <dt className="text-muted-foreground">{v}</dt>
                    <dd>
                      <kbd className="rounded border bg-muted px-1.5 py-0.5 text-[11px] font-medium">
                        {k}
                      </kbd>
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>
      </PageContainer>
    </AppLayout>
  );
}
