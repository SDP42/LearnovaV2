import { useState } from "react";
import { Download, Sparkles } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import { PageContainer, PageHeader } from "@/components/app/Page";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const EXAMPLES = [
  "Solve 3x + 5 = 20",
  "Solve x^2 - 5x + 6 = 0",
  "Find the mean of 4, 8, 15, 16, 23, 42",
  "What is 15% of 240?",
];

/** Type a problem, get it solved one small step at a time (every number computed, every step explained). */
export default function Explain() {
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const solve = async (text = problem) => {
    if (text.trim().length < 3) return;
    setBusy(true);
    try {
      setResult(await api.explainProblem(text));
    } catch (e) {
      setResult(null);
      toast.error(e?.message || "Could not solve that one.");
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    const url = URL.createObjectURL(new Blob([result.html], { type: "text/html" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "step-by-step.html" });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  };

  return (
    <AppLayout>
      <PageContainer>
        <PageHeader title="Solve step by step" subtitle="Type a problem. Learnova solves it one small step at a time, with the reason for every step, and gives you a page you can drop into a deck." />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_1fr]">
          <div className="space-y-3">
            <Textarea value={problem} onChange={(e) => setProblem(e.target.value)} placeholder="e.g. Solve 3x + 5 = 20" rows={4} aria-label="Problem" />
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" className="rounded-full bg-[#EFE1D4] px-3 py-1 text-xs font-medium text-[#664F44] hover:bg-[#F3E6DA]" onClick={() => { setProblem(ex); solve(ex); }}>
                  {ex}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <Button onClick={() => solve()} disabled={busy || problem.trim().length < 3}>
                <Sparkles className="mr-1.5 size-4" /> {busy ? "Solving…" : "Solve it"}
              </Button>
              {result ? (
                <Button variant="outline" onClick={download}>
                  <Download className="mr-1.5 size-4" /> Download HTML
                </Button>
              ) : null}
            </div>
          </div>
          <div className="min-h-[420px] overflow-hidden rounded-xl border bg-white">
            {result ? (
              <iframe title="Step-by-step solution" srcDoc={result.html} className="h-[620px] w-full" />
            ) : (
              <p className="p-6 text-sm text-[#664F44]">Equations, percentages, averages, probability, Bayes' rule, derivatives, integrals and CYK parsing are supported.</p>
            )}
          </div>
        </div>
      </PageContainer>
    </AppLayout>
  );
}
