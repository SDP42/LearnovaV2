import {
  BrainCircuit,
  GaugeCircle,
  LayoutTemplate,
  ScanText,
  Sparkles,
  Wand2,
} from "lucide-react";
import { cn } from "@/lib/utils";

function Feature({ icon: Icon, title, body, className }) {
  return (
    <div className={cn("lv-card group flex flex-col gap-3 rounded-xl p-5", className)}>
      <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
        <Icon className="size-5" />
      </span>
      <div>
        <h3 className="font-medium">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      </div>
    </div>
  );
}

export default function FeatureBento() {
  return (
    <section id="features" className="relative mx-auto max-w-6xl px-4 pb-20 pt-40 sm:pt-48">
      <div className="lv-glow left-1/2 top-24 h-[300px] w-[600px] -translate-x-1/2 opacity-30" />
      <div className="relative mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight">
          It reads your content, then decides
        </h2>
        <p className="mt-3 text-muted-foreground">
          Per slide: keep it as text, tighten it, or turn it into a flowchart,
          chart, timeline or comparison. Choose a transition. Time the reveal.
          Drop in a checkpoint. You review, then generate.
        </p>
      </div>

      <div className="relative mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Feature
          icon={LayoutTemplate}
          title="40 visual families"
          body="Flowcharts, timelines, bar and line charts, comparison tables, 2×2 matrices, pyramids, mind maps, worked examples — picked by matching the shape of your content, not by keyword."
          className="lg:col-span-2"
        />
        <Feature
          icon={Wand2}
          title="Builds one idea per click"
          body="Points, then a chart's bars, then the takeaway — earlier steps stay on screen. A worked example reveals a line at a time."
        />
        <Feature
          icon={ScanText}
          title="Handles the figures"
          body="Each image in your source is kept, captioned, or left out — a decision based on what it actually shows, not a blanket rule."
        />
        <Feature
          icon={BrainCircuit}
          title="Checkpoint quizzes"
          body="A question every few slides — or after the ones you choose. Click an option, see why it's right or wrong. In the deck and the PowerPoint."
        />
        <Feature
          icon={GaugeCircle}
          title="An engagement score you can act on"
          body="Every slide is scored for information density, cognitive load and how well the visual matches the text. Low scores tell you which slides to split."
        />
        <Feature
          icon={Sparkles}
          title="Two files, one source"
          body="An animated PowerPoint and a standalone web deck with a built-in presenter console — speaker notes, timer, next-slide preview, jump-to-slide."
          className="lg:col-span-2"
        />
      </div>
    </section>
  );
}
