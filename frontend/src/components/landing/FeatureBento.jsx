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
          Not a template filler. A teaching engine.
        </h2>
        <p className="mt-3 text-muted-foreground">
          Every decision — which visual, what to keep verbatim, when to reveal a
          point, how slides transition — is made from the structure of your
          content.
        </p>
      </div>

      <div className="relative mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Feature
          icon={LayoutTemplate}
          title="1000+ addressable visuals"
          body="40 families — flowcharts, timelines, charts, Venn, pyramids, mind maps, proofs, circuits — chosen by matching your content's shape, never keywords."
          className="lg:col-span-2"
        />
        <Feature
          icon={Wand2}
          title="Progressive reveal"
          body="Slides build one idea per click — points, then a chart's series, then the takeaway. Like a lecturer, not a wall of text."
        />
        <Feature
          icon={ScanText}
          title="Image intelligence"
          body="Each figure is kept, redrawn as native structure, enhanced, or dropped — decided from OCR density and relevance."
        />
        <Feature
          icon={BrainCircuit}
          title="Inline checkpoint quizzes"
          body="Auto-generated questions dropped in every N slides to drive active recall, with explanations."
        />
        <Feature
          icon={GaugeCircle}
          title="Pedagogical Slide Fitness"
          body="A calibrated engagement metric grounded in Cognitive Load Theory — the same model that scores slides also paginates them."
        />
        <Feature
          icon={Sparkles}
          title="PPTX + interactive web deck"
          body="Export an animated PowerPoint and a standalone Reveal.js deck with a built-in presenter view — from one source."
          className="lg:col-span-2"
        />
      </div>
    </section>
  );
}
