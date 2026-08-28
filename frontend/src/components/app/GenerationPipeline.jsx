import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

/**
 * Maps the backend's 12 pipeline stages onto 6 learner-friendly phases and
 * renders them as a vertical stepper with the active phase spinning.
 *
 * `stage` is the backend stage name from `api.getJob().stage`; `progress` is
 * the 0..1 fraction; `status` is "running" | "done" | "failed".
 */
const PHASES = [
  { label: "Reading your content", stages: ["convert", "chunk"] },
  { label: "Extracting text & images", stages: ["vision_ocr", "index"] },
  { label: "Understanding structure", stages: ["layout", "visual_plan"] },
  { label: "Designing visual layouts", stages: ["enhance", "density"] },
  { label: "Creating checkpoint quiz", stages: ["quiz", "score"] },
  { label: "Preparing your presentation", stages: ["build_pptx", "build_html"] },
];

const ORDER = PHASES.flatMap((p) => p.stages);

export default function GenerationPipeline({ stage, progress = 0, status = "running" }) {
  const done = status === "done";
  const failed = status === "failed";
  const currentIdx = done
    ? PHASES.length
    : Math.max(
        0,
        PHASES.findIndex((p) => p.stages.includes(stage))
      );
  const stageIdx = ORDER.indexOf(stage);
  const pct = done ? 100 : Math.round(((stageIdx + (progress || 0)) / ORDER.length) * 100);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium">
            {done ? "Done" : failed ? "Something went wrong" : "Creating your learning experience"}
          </span>
          <span className="tabular-nums text-muted-foreground">{Math.max(pct, 0)}%</span>
        </div>
        <Progress value={Math.max(pct, 3)} />
      </div>

      <ol className="flex flex-col gap-1">
        {PHASES.map((phase, i) => {
          const state =
            i < currentIdx ? "done" : i === currentIdx && !done ? "active" : done ? "done" : "todo";
          return (
            <li
              key={phase.label}
              className={cn(
                "flex items-center gap-3 rounded-lg px-2 py-2 text-sm transition-colors",
                state === "active" && "bg-primary/10 ring-1 ring-inset ring-primary/25"
              )}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs transition-colors",
                  state === "done" && "border-primary bg-primary text-primary-foreground",
                  state === "active" && "border-primary text-primary shadow-[0_0_0_4px_color-mix(in_oklch,var(--color-primary)_18%,transparent)]",
                  state === "todo" && "border-border text-muted-foreground"
                )}
              >
                {state === "done" ? (
                  <Check className="size-3.5" />
                ) : state === "active" ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  i + 1
                )}
              </span>
              <span
                className={cn(
                  state === "todo" && "text-muted-foreground",
                  state === "active" && "font-medium"
                )}
              >
                {phase.label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
