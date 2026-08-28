import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import LandingNav from "@/components/landing/LandingNav";
import Hero from "@/components/landing/Hero";
import FeatureBento from "@/components/landing/FeatureBento";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const STEPS = [
  ["Ingest", "Upload a PPTX or PDF, or paste a syllabus. Everything converges on one editable markdown representation."],
  ["Review", "See the structure the pipeline will reason over. Edit it — what you change is what gets built."],
  ["Generate", "Layout classification, visual planning, progressive-reveal timing, quizzes, and engagement scoring."],
  ["Present", "An animated PPTX and an interactive web deck with speaker notes, a timer, and a next-slide preview."],
];

export default function Landing() {
  return (
    <div data-learnova-app className="min-h-svh bg-background text-foreground">
      <LandingNav />
      <Hero />
      <FeatureBento />

      <section id="how" className="border-t bg-muted/30">
        <div className="mx-auto max-w-6xl px-4 py-20">
          <h2 className="text-center text-3xl font-semibold tracking-tight">How it works</h2>
          <div className="mt-12 grid gap-4 md:grid-cols-4">
            {STEPS.map(([title, body], i) => (
              <Card key={title}>
                <CardContent className="flex flex-col gap-2 p-5">
                  <span className="text-xs font-medium text-primary">Step {i + 1}</span>
                  <h3 className="font-medium">{title}</h3>
                  <p className="text-sm text-muted-foreground">{body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="research" className="mx-auto max-w-3xl px-4 py-20 text-center">
        <h2 className="text-3xl font-semibold tracking-tight">Built on published research</h2>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Learnova's engine is grounded in Cognitive Load Theory and Mayer's
          multimedia principles: a calibrated slide-fitness metric (PSF), an
          optimal cognitive-load-aware segmentation algorithm, and a semantic
          transition selector — the metric that judges a deck is the same model
          that builds it.
        </p>
        <Button asChild variant="outline" className="mt-6">
          <Link to="/app/create">
            Try it now <ArrowRight />
          </Link>
        </Button>
      </section>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-8 text-sm text-muted-foreground sm:flex-row">
          <span>© {new Date().getFullYear()} Learnova</span>
          <div className="flex gap-4">
            <a href="#features" className="hover:text-foreground">Features</a>
            <Link to="/sign-in" className="hover:text-foreground">Sign in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
