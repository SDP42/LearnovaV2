import { Link } from "react-router-dom";
import { ListChecks, Monitor, Play, Presentation, Sparkles, Timer } from "lucide-react";
import AppLayout from "@/components/app/AppLayout";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Presentations() {
  const { decks, error } = useDecks();

  return (
    <AppLayout title="Presentations">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Presentations</h2>
            <p className="text-sm text-muted-foreground">Open a deck in the editor or start presenting.</p>
          </div>
          <Button asChild>
            <Link to="/app/create"><Sparkles /> New</Link>
          </Button>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {decks === null ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-40 rounded-xl" />)}
          </div>
        ) : decks.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 p-12 text-center">
              <Presentation className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No presentations yet.</p>
              <Button asChild size="sm"><Link to="/app/create">Create one</Link></Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {decks.map((d) => {
              const id = deckId(d);
              return (
                <Card key={id} className="lv-card group flex flex-col overflow-hidden">
                  <Link
                    to={`/app/preview/${id}`}
                    className="flex aspect-video items-center justify-center border-b bg-muted/30 p-4"
                  >
                    <div className="w-full max-w-[200px] rounded-md border bg-card p-3">
                      <div className="mb-2 h-1.5 w-2/3 rounded bg-primary/60" />
                      <div className="space-y-1">
                        <div className="h-1 w-full rounded bg-muted-foreground/25" />
                        <div className="h-1 w-5/6 rounded bg-muted-foreground/25" />
                        <div className="h-1 w-3/4 rounded bg-muted-foreground/25" />
                      </div>
                    </div>
                  </Link>
                  <CardContent className="flex flex-1 flex-col gap-2 p-4">
                    <p className="truncate text-sm font-medium">{deckTitle(d)}</p>
                    <p className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{d.slide_count ?? d.slides ?? 0} slides</span>
                      <span className="inline-flex items-center gap-1">
                        <ListChecks className="size-3" /> {d.quiz_count ?? d.quizzes ?? 0}
                      </span>
                      {d.overall_score != null ? <span>{d.overall_score}/100</span> : null}
                    </p>
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
      </div>
    </AppLayout>
  );
}
