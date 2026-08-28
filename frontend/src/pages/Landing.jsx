import { Link } from "react-router-dom";
import { ArrowRight, Check, GraduationCap, Presentation, Users, X } from "lucide-react";
import LandingNav from "@/components/landing/LandingNav";
import Hero from "@/components/landing/Hero";
import FeatureBento from "@/components/landing/FeatureBento";
import { Button } from "@/components/ui/button";

const STEPS = [
  ["Ingest", "Upload a PPTX or PDF, or paste a syllabus. Everything converges on one editable markdown representation."],
  ["Review", "See the structure the pipeline will reason over. Edit it — what you change is what gets built."],
  ["Generate", "Layout classification, visual planning, progressive-reveal timing, quizzes, and engagement scoring."],
  ["Present", "An animated PPTX and an interactive web deck with speaker notes, a timer, and a next-slide preview."],
];

const AUDIENCES = [
  {
    icon: GraduationCap,
    title: "Educators & lecturers",
    body: "Drop in a week's lecture notes and get a deck that paces one idea at a time, with checkpoint questions already placed. Spend your prep time on delivery, not on dragging text boxes.",
  },
  {
    icon: Users,
    title: "Trainers & onboarding leads",
    body: "Turn a process document or SOP into a walkthrough with flowcharts and comparisons drawn from the actual steps — not a bullet dump of the source file.",
  },
  {
    icon: Presentation,
    title: "Students & researchers",
    body: "Paste a paper's method section or a chapter summary and rehearse with the presenter console: notes, a timer, a next-slide preview, and a reveal-step indicator.",
  },
];

const IS = [
  "Reads the structure of your content and picks a visual to match it",
  "Keeps definitions, theorems, quotations and formulae verbatim",
  "Builds one idea per click, like a lecturer working through a board",
  "Scores every slide against a cognitive-load metric and repaginates",
  "Exports an animated PPTX and a standalone web deck from one source",
];

const ISNT = [
  "A template gallery you pour text into",
  "A summariser that flattens everything to three bullets",
  "A wall-of-text generator with clip-art headers",
  "A tool that needs you to choose the chart type yourself",
  "A slideshow locked to one export format or one player",
];

const RESEARCH = [
  {
    tag: "Scoring",
    title: "Every slide gets an engagement score",
    body: "Three things, multiplied: how much meaningful content per unit of space, how much the slide asks working memory to hold at once, and whether the visual and the text say the same thing. Multiplied, not averaged — so one bad dimension can't hide behind two good ones.",
  },
  {
    tag: "Pagination",
    title: "It decides where slides break",
    body: "Rather than cutting at a fixed bullet count, it searches the possible break points for the split that keeps every slide's cognitive load reasonable across the whole deck.",
  },
  {
    tag: "Transitions",
    title: "Animation that means something",
    body: "A slide that continues the last one gets no visual break; a contrast gets a different move; a new section gets a hard cut. The build steps come from the same read of the content.",
  },
];

const FAQ = [
  {
    q: "Do I need an API key to try it?",
    a: "No. Without a key, an extractive summariser scores and compresses sentences and the full visual pipeline still runs. Add a free Groq key (or an NVIDIA NIM key) for LLM rewriting, analogies, and quiz generation.",
  },
  {
    q: "What can I feed it?",
    a: "A .pptx or .pdf upload, or text typed straight into the Create screen — a syllabus, lecture notes, a chapter summary, a process document. Scanned PDFs are OCR'd when a Gemini key is present.",
  },
  {
    q: "Will it rewrite text I need kept exact?",
    a: "No. Definitions, theorems, quotations, code, and formulae are detected and left verbatim. Only wordy explanatory prose is tightened, and you see the editable structure before anything is built.",
  },
  {
    q: "What do I get out?",
    a: "An animated PowerPoint (.pptx) with entrance builds, and a standalone Reveal.js web deck with a built-in presenter view. Both are generated from the same slide model, so they stay in step.",
  },
  {
    q: "Where does my content go?",
    a: "Decks are stored per-user on the server running the app. LLM calls go to whichever provider's key you configured (Groq / NVIDIA / Gemini) and nowhere else.",
  },
];

export default function Landing() {
  return (
    <div data-learnova-app className="min-h-svh bg-background text-foreground">
      <LandingNav />
      <Hero />
      <FeatureBento />

      <section id="how" className="border-t bg-muted/20">
        <div className="mx-auto max-w-6xl px-4 py-20">
          <h2 className="text-center text-3xl font-semibold tracking-tight">How it works</h2>
          <div className="lv-rule mx-auto mt-4 w-24" />
          <div className="mt-12 grid gap-4 md:grid-cols-4">
            {STEPS.map(([title, body], i) => (
              <div key={title} className="lv-card flex flex-col gap-2 rounded-xl p-5">
                <span className="inline-flex w-fit items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  Step {i + 1}
                </span>
                <h3 className="font-medium">{title}</h3>
                <p className="text-sm text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">Who it's for</h2>
          <p className="mt-3 text-muted-foreground">
            Anyone who has to turn dense source material into something a room can follow.
          </p>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {AUDIENCES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="lv-card flex flex-col gap-3 rounded-xl p-6">
              <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="size-5" />
              </span>
              <h3 className="font-medium">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t bg-muted/20">
        <div className="mx-auto max-w-5xl px-4 py-20">
          <h2 className="text-center text-3xl font-semibold tracking-tight">
            What Learnova is — and isn't
          </h2>
          <div className="lv-rule mx-auto mt-4 w-24" />
          <div className="mt-12 grid gap-4 md:grid-cols-2">
            <div className="lv-card rounded-xl p-6">
              <p className="mb-4 flex items-center gap-2 font-medium text-primary">
                <Check className="size-4" /> It is
              </p>
              <ul className="flex flex-col gap-3">
                {IS.map((t) => (
                  <li key={t} className="flex gap-2 text-sm text-muted-foreground">
                    <Check className="mt-0.5 size-4 shrink-0 text-primary" /> {t}
                  </li>
                ))}
              </ul>
            </div>
            <div className="lv-card rounded-xl p-6">
              <p className="mb-4 flex items-center gap-2 font-medium text-muted-foreground">
                <X className="size-4" /> It isn't
              </p>
              <ul className="flex flex-col gap-3">
                {ISNT.map((t) => (
                  <li key={t} className="flex gap-2 text-sm text-muted-foreground">
                    <X className="mt-0.5 size-4 shrink-0 opacity-60" /> {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="research" className="relative mx-auto max-w-5xl overflow-hidden px-4 py-24">
        <div className="lv-glow left-1/2 top-8 h-[200px] w-[400px] -translate-x-1/2 opacity-25" />
        <div className="relative mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">The parts that make it teach</h2>
          <p className="mx-auto mt-3 text-muted-foreground">
            Grounded in Cognitive Load Theory and Mayer's multimedia principles.
            The score that judges a finished deck is the same model that plans it.
          </p>
        </div>
        <div className="relative mt-12 grid gap-4 md:grid-cols-3">
          {RESEARCH.map(({ tag, title, body }) => (
            <div key={title} className="lv-card flex flex-col gap-3 rounded-xl p-6">
              <span className="inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-xs font-medium text-muted-foreground">
                {tag}
              </span>
              <h3 className="font-medium leading-snug">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
        <div className="relative mt-10 text-center">
          <Button asChild variant="outline">
            <Link to="/app/create">
              Try it now <ArrowRight />
            </Link>
          </Button>
        </div>
      </section>

      <section id="faq" className="border-t bg-muted/20">
        <div className="mx-auto max-w-3xl px-4 py-20">
          <h2 className="text-center text-3xl font-semibold tracking-tight">
            Frequently asked
          </h2>
          <div className="lv-rule mx-auto mt-4 w-24" />
          <div className="mt-10 flex flex-col gap-3">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="lv-card group rounded-xl p-5">
                <summary className="flex cursor-pointer list-none items-center justify-between font-medium">
                  {q}
                  <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="relative mx-auto max-w-3xl overflow-hidden px-4 py-24 text-center">
        <div className="lv-dots absolute inset-0" />
        <div className="lv-glow left-1/2 top-1/2 h-[240px] w-[440px] -translate-x-1/2 -translate-y-1/2 opacity-30" />
        <div className="relative">
          <h2 className="text-3xl font-semibold tracking-tight">
            Try it with something real
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-muted-foreground">
            Paste a week of lecture notes, or start from a ready-made lesson. The
            denser the source, the more the difference shows.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button asChild size="lg" className="lv-cta rounded-lg">
              <Link to="/app/create">
                Create a presentation <ArrowRight />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/app/library">Browse lessons</Link>
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:grid-cols-4">
          <div className="sm:col-span-2">
            <p className="font-semibold">Learnova</p>
            <p className="mt-2 max-w-xs text-sm text-muted-foreground">
              An AI presentation engine that reasons about your content's
              structure — cognitive-load aware, research-grounded.
            </p>
          </div>
          <div className="flex flex-col gap-2 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Product</p>
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#how" className="hover:text-foreground">How it works</a>
            <a href="#research" className="hover:text-foreground">Research</a>
            <a href="#faq" className="hover:text-foreground">FAQ</a>
          </div>
          <div className="flex flex-col gap-2 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Get started</p>
            <Link to="/app/create" className="hover:text-foreground">Create a deck</Link>
            <Link to="/sign-in" className="hover:text-foreground">Sign in</Link>
            <Link to="/app/docs" className="hover:text-foreground">Documentation</Link>
          </div>
        </div>
        <div className="border-t">
          <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-muted-foreground">
            © {new Date().getFullYear()} Learnova
          </div>
        </div>
      </footer>
    </div>
  );
}
