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
                "flex min-h-12 items-center gap-3 rounded-xl border bg-white p-3 text-left text-sm transition duration-150",
                !submitted && isChoice && "border-[#C2502A] bg-[#FDEEE3] ring-2 ring-[#C2502A]/20",
                !submitted && !isChoice && "hover:-translate-y-px hover:border-[#E3A98B] hover:bg-[#FFFAF5]",
                submitted && isCorrect && "border-[#6B9B72] bg-[#E6F2E8] text-[#2F5D37]",
                submitted && isChoice && !isCorrect && "border-[#C0392B] bg-[#FBE9E7] text-[#8E2A1F]",
                submitted && "cursor-default"
              )}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                  isChoice && !submitted && "border-[#C2502A] text-[#8F3A18]",
                  submitted && isCorrect && "border-[#3F6B47] text-[#2F5D37]",
                  submitted && isChoice && !isCorrect && "border-[#C0392B] text-[#8E2A1F]"
                )}
              >
                {LETTERS[i]}
              </span>
              <span className="flex-1">{optionText(opt)}</span>
              {submitted && isCorrect ? (
                <CheckCircle2 className="size-4 text-[#3F6B47]" />
              ) : submitted && isChoice ? (
                <XCircle className="size-4 text-[#C0392B]" />
              ) : null}
            </button>
          );
        })}

        {submitted ? (
          <div
            className={cn(
              "mt-2 rounded-xl border p-3 text-sm",
              correct
                ? "border-[#6B9B72]/50 bg-[#E6F2E8] text-[#2F5D37]"
                : "border-[#C0392B]/40 bg-[#FBE9E7] text-[#8E2A1F]"
            )}
          >
            <p className="font-medium">{correct ? "✓ Correct" : "Not quite"}</p>
            {quiz.explanation ? (
              <p className="mt-1 text-[#4F3A31]">{quiz.explanation}</p>
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
