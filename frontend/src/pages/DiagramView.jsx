import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import * as api from "@/api";
import { UserButton } from "@/auth";
import DiagramEditor from "@/components/app/DiagramEditor";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/** Full-screen diagram editor for one flowchart slide of a generated deck. */
export default function DiagramView() {
  const { jobId, slide } = useParams();
  const idx = Number(slide) || 0;
  const [deck, setDeck] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getDeck(jobId).then(setDeck).catch((e) => setError(e.message));
  }, [jobId]);

  const s = deck?.slides?.[idx];
  const code = useMemo(() => {
    if (s?.mermaid_code) return s.mermaid_code;
    // Build a chain from the bullets as a fallback so there is always a diagram.
    const steps = (s?.bullets || []).slice(0, 8).map((b, i) =>
      `N${i}["${String(b).replace(/["\n]/g, " ").slice(0, 40)}"]`
    );
    return steps.length >= 2 ? `graph TD\n  ${steps.join(" --> ")}` : "";
  }, [s]);

  return (
    <div data-learnova-app className="flex h-svh flex-col bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b px-3">
        <Button asChild variant="ghost" size="icon">
          <Link to={`/app/preview/${jobId}`}>
            <ArrowLeft />
          </Link>
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {s?.title || deck?.summary?.source_name || "Diagram"}
          </p>
          <p className="text-xs text-muted-foreground">
            Slide {idx + 1}
            {s?.variant ? ` · ${s.variant}` : ""} · drag to pan, scroll to zoom
          </p>
        </div>
        <div className="ml-auto">
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      <div className="flex-1 p-4">
        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : !deck ? (
          <Skeleton className="h-full w-full rounded-xl" />
        ) : code ? (
          <DiagramEditor code={code} title={s?.title || "Diagram"} className="h-full" />
        ) : (
          <div className="grid h-full place-items-center rounded-xl border text-sm text-muted-foreground">
            This slide has no diagram.
          </div>
        )}
      </div>
    </div>
  );
}
