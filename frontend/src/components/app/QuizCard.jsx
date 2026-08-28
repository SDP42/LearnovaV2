import { useState } from "react";
import { ArrowRight, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

const LETTERS = ["A", "B", "C", "D"];

function optionText(opt) {
  return String(opt).replace(/^\s*[A-Da-d][).:]\s*/, "").trim();
}

/**
 * One checkpoint question (section 11 of the UI plan). `quiz` is
 * { question, options[], correct, explanation }. `onNext` advances; `position`
 * / `total` render the "3 / 5" counter.
 */
export default function QuizCard({ quiz, position = 1, total = 1, onNext }) {
  const [choice, setChoice] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const options = (quiz.options ?? []).slice(0, 4);
  const correctLetter = String(quiz.correct ?? "A").trim().toUpperCase().slice(0, 1);
  const correct = submitted && LETTERS[choice] === correctLetter;

  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader className="gap-3">
        <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <span>Checkpoint {String(position).padStart(2, "0")}</span>
          <span>
            {position} / {total}
          </span>
        </div>
        <Progress value={(position / total) * 100} />
        <p className="text-base font-semibold leading-snug">{quiz.question}</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {options.map((opt, i) => {
          const isChoice = choice === i;
          const isCorrect = LETTERS[i] === correctLetter;
          return (
            <button
              key={i}
              type="button"
              disabled={submitted}
              onClick={() => setChoice(i)}
              className={cn(
                "flex items-center gap-3 rounded-lg border p-3 text-left text-sm transition-colors",
                !submitted && isChoice && "border-primary bg-primary/5",
                !submitted && !isChoice && "hover:bg-muted/40",
                submitted && isCorrect && "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40",
                submitted && isChoice && !isCorrect && "border-rose-500 bg-rose-50 dark:bg-rose-950/40",
                submitted && "cursor-default"
              )}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                  isChoice && !submitted && "border-primary text-primary",
                  submitted && isCorrect && "border-emerald-500 text-emerald-600",
                  submitted && isChoice && !isCorrect && "border-rose-500 text-rose-600"
                )}
              >
                {LETTERS[i]}
              </span>
              <span className="flex-1">{optionText(opt)}</span>
              {submitted && isCorrect ? (
                <CheckCircle2 className="size-4 text-emerald-600" />
              ) : submitted && isChoice ? (
                <XCircle className="size-4 text-rose-600" />
              ) : null}
            </button>
          );
        })}

        {submitted ? (
          <div
            className={cn(
              "mt-2 rounded-lg border p-3 text-sm",
              correct
                ? "border-emerald-500/40 bg-emerald-50 dark:bg-emerald-950/30"
                : "border-rose-500/40 bg-rose-50 dark:bg-rose-950/30"
            )}
          >
            <p className="font-medium">{correct ? "✓ Correct" : "Not quite"}</p>
            {quiz.explanation ? (
              <p className="mt-1 text-muted-foreground">{quiz.explanation}</p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-2 flex justify-end">
          {submitted ? (
            <Button onClick={() => onNext?.(correct)}>
              Continue <ArrowRight />
            </Button>
          ) : (
            <Button disabled={choice === null} onClick={() => setSubmitted(true)}>
              Submit answer
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
