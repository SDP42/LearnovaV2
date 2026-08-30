import { Link } from "react-router-dom";
import { ListChecks, Play } from "lucide-react";
import { deckId, deckTitle } from "@/lib/useDecks";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * A deck tile: mini slide-mockup thumbnail + title + quiz count + score bar +
 * Open / Present actions. Used on the Presentations grid (and reusable
 * anywhere a deck needs a full card rather than a list row).
 */
export default function PresentationCard({ deck, index = 0 }) {
  const id = deckId(deck);
  const score = deck.overall_score ?? null;
  const slides = deck.slide_count ?? deck.slides ?? 0;
  const quizzes = deck.quiz_count ?? deck.quizzes ?? 0;

  return (
    <Card
      className="lv-card lv-in group flex flex-col overflow-hidden"
      style={{ animationDelay: `${index * 40}ms` }}
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
          {slides} slides
        </span>
      </Link>
      <CardContent className="flex flex-1 flex-col gap-2 p-4">
        <p className="truncate text-sm font-medium">{deckTitle(deck)}</p>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <ListChecks className="size-3" /> {quizzes} quizzes
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
}
