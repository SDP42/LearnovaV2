import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BrainCircuit, Lightbulb, RotateCcw, Target, Trophy } from "lucide-react";
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
import { PageContainer, PageHeader } from "@/components/app/Page";

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
      <PageContainer width="prose">
        <PageHeader
          title="Checkpoint quizzes"
          subtitle="Run the inline questions generated for one of your decks."
          actions={
            decks && decks.length > 0 ? (
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
            ) : null
          }
        />

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
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="tabular-nums">
                {at + 1} / {total}
              </span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${(at / total) * 100}%` }}
                />
              </div>
              <span className="inline-flex items-center gap-1 tabular-nums">
                <Target className="size-3" /> {score}
              </span>
            </div>
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
          </div>
        )}

        <Card className="lv-card">
          <CardHeader className="flex flex-row items-center gap-2">
            <Lightbulb className="size-4 text-primary" />
            <CardTitle className="text-base">Why checkpoint quizzes</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm leading-relaxed text-muted-foreground">
            <p>
              Retrieving a fact from memory strengthens it far more than re-reading
              it — the <span className="font-medium text-foreground">testing effect</span>.
              Learnova drops a short question every few slides so a lecture becomes
              an active loop instead of a passive scroll.
            </p>
            <p>
              Questions are generated from the slide content just before them, with
              plausible distractors and a one-line explanation revealed after you
              answer. Change how often they appear with{" "}
              <span className="font-medium text-foreground">Quiz every N</span> in{" "}
              <Link to="/app/settings" className="underline">Settings</Link>.
            </p>
            <p className="text-xs">
              Quiz generation needs an LLM key (Groq or NVIDIA). The extractive
              fallback builds slides but not questions.
            </p>
          </CardContent>
        </Card>
      </PageContainer>
    </AppLayout>
  );
}
