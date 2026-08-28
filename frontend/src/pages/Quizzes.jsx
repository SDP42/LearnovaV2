import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BrainCircuit, RotateCcw, Trophy } from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import QuizCard from "@/components/app/QuizCard";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export default function Quizzes() {
  const [params, setParams] = useSearchParams();
  const jobId = params.get("job") || "";

  const [decks, setDecks] = useState(null);
  const [quizzes, setQuizzes] = useState(null);
  const [error, setError] = useState("");
  const [at, setAt] = useState(0);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    api
      .listMyDecks()
      .then((r) => setDecks(Array.isArray(r) ? r : r?.decks ?? []))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!jobId) return;
    setQuizzes(null);
    setAt(0);
    setScore(0);
    setDone(false);
    api
      .getDeck(jobId)
      .then((d) => setQuizzes(d.quizzes ?? []))
      .catch((e) => setError(e.message));
  }, [jobId]);

  const total = quizzes?.length ?? 0;
  const current = quizzes?.[at];

  const pct = useMemo(() => (total ? Math.round((score / total) * 100) : 0), [score, total]);

  return (
    <AppLayout title="Quizzes">
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Checkpoint quizzes</h2>
            <p className="text-sm text-muted-foreground">
              Run the inline questions generated for one of your decks.
            </p>
          </div>
          {decks && decks.length > 0 ? (
            <Select
              value={jobId}
              onValueChange={(v) => setParams(v ? { job: v } : {})}
            >
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Choose a deck" />
              </SelectTrigger>
              <SelectContent>
                {decks.map((d) => (
                  <SelectItem key={d.id ?? d.deck_id} value={String(d.id ?? d.deck_id)}>
                    {d.title ?? d.source_name ?? "Untitled"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
        </div>

        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {!jobId ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
              <BrainCircuit className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {decks === null
                  ? "Loading your decks…"
                  : decks.length === 0
                  ? "No decks yet — generate one first."
                  : "Pick a deck above to start its quiz."}
              </p>
              {decks && decks.length === 0 ? (
                <Button asChild size="sm">
                  <Link to="/app/create">Create a presentation</Link>
                </Button>
              ) : null}
            </CardContent>
          </Card>
        ) : quizzes === null ? (
          <Skeleton className="h-72" />
        ) : total === 0 ? (
          <Card>
            <CardContent className="p-10 text-center text-sm text-muted-foreground">
              This deck has no quiz questions.
            </CardContent>
          </Card>
        ) : done ? (
          <Card className="mx-auto w-full max-w-xl">
            <CardHeader className="items-center gap-2 text-center">
              <Trophy className="size-8 text-primary" />
              <CardTitle>
                {score} / {total} correct
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-4">
              <p className="text-sm text-muted-foreground">
                {pct >= 80 ? "Excellent recall." : pct >= 50 ? "Solid — review the misses." : "Worth another pass."}
              </p>
              <Button
                variant="outline"
                onClick={() => {
                  setAt(0);
                  setScore(0);
                  setDone(false);
                }}
              >
                <RotateCcw /> Retry
              </Button>
            </CardContent>
          </Card>
        ) : (
          <QuizCard
            key={at}
            quiz={current}
            position={at + 1}
            total={total}
            onNext={(wasCorrect) => {
              if (wasCorrect) setScore((s) => s + 1);
              if (at + 1 >= total) setDone(true);
              else setAt((i) => i + 1);
            }}
          />
        )}
      </div>
    </AppLayout>
  );
}
