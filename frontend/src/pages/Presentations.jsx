import { Link } from "react-router-dom";
import { Monitor, Presentation, Sparkles, Timer } from "lucide-react";
import AppLayout from "@/components/app/AppLayout";
import { useDecks } from "@/lib/useDecks";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageContainer, PageHeader } from "@/components/app/Page";
import PresentationCard from "@/components/app/PresentationCard";
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
            {decks.map((d, idx) => (
              <PresentationCard key={d.id ?? d.deck_id ?? idx} deck={d} index={idx} />
            ))}
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
