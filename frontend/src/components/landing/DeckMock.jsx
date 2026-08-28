/**
 * A stylised mock of the Learnova editor — shown under the hero so the product
 * is visible above the fold. Pure CSS/SVG, theme-token driven, no data.
 */
export default function DeckMock() {
  return (
    <div className="lv-card overflow-hidden rounded-xl shadow-2xl">
      {/* window chrome */}
      <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-destructive/70" />
        <span className="size-2.5 rounded-full bg-amber-400/70" />
        <span className="size-2.5 rounded-full bg-emerald-400/70" />
        <span className="ml-3 text-xs text-muted-foreground">Neural Networks — Preview</span>
      </div>

      <div className="grid grid-cols-[110px_1fr_150px] gap-0 text-[10px]">
        {/* slide rail */}
        <div className="flex flex-col gap-2 border-r p-2.5">
          {["Definition", "flowchart", "bar_chart", "pros_cons", "quiz"].map((t, i) => (
            <div
              key={t}
              className={`rounded-md border p-1.5 ${i === 1 ? "border-primary bg-primary/10" : "bg-card"}`}
            >
              <div className="mb-1 flex justify-between text-muted-foreground">
                <span>{i + 1}</span>
                <span className="rounded bg-muted px-1 text-[8px]">{t}</span>
              </div>
              <div className="h-1 w-4/5 rounded bg-muted-foreground/30" />
            </div>
          ))}
        </div>

        {/* stage — a mini flowchart slide */}
        <div className="flex items-center justify-center bg-muted/20 p-4">
          <div className="w-full max-w-[280px] rounded-lg border bg-card p-3">
            <div className="mb-2 h-1.5 w-2/3 rounded bg-primary/70" />
            <div className="flex items-center gap-1.5">
              {["Input", "Hidden", "Output"].map((n, i) => (
                <div key={n} className="flex items-center gap-1.5">
                  <div className="rounded border border-primary/50 bg-primary/10 px-2 py-1 text-[8px] font-medium">
                    {n}
                  </div>
                  {i < 2 && <span className="text-primary">→</span>}
                </div>
              ))}
            </div>
            <div className="mt-3 space-y-1">
              <div className="h-1 w-full rounded bg-muted-foreground/20" />
              <div className="h-1 w-4/5 rounded bg-muted-foreground/20" />
            </div>
            <div className="mt-3 rounded bg-primary/10 px-2 py-1 text-[8px] text-primary">
              Key takeaway: the network learns a mapping from inputs to outputs.
            </div>
          </div>
        </div>

        {/* properties */}
        <div className="flex flex-col gap-2.5 border-l p-2.5 text-muted-foreground">
          {[
            ["Visual", "flowchart"],
            ["Transition", "slide"],
            ["Summarise", "BALANCED"],
            ["Reveal", "4 steps"],
            ["Time", "~48s"],
          ].map(([k, v]) => (
            <div key={k} className="flex flex-col">
              <span className="text-[8px] uppercase tracking-wide opacity-70">{k}</span>
              <span className="text-[9px] text-foreground">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
