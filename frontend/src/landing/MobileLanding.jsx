import { Link } from "react-router-dom";
import { ArrowRight, BrainCircuit, FileText, GitBranch, LayoutTemplate, ListChecks, MonitorPlay, Share2, Sparkles } from "lucide-react";
import { useAuth } from "@/auth";

const FEATURES = [
  [FileText, "Reads what you already have", "Syllabi, PDF reports, lecture slides, even scanned handouts. Headings, tables and figures are kept."],
  [LayoutTemplate, "Designs each slide for its idea", "A process becomes a flow, a comparison a table, a number a stat tile. You see why each visual was chosen."],
  [GitBranch, "Solves problems step by step", "Equations, probability, Bayes, bigrams, Naive Bayes, Viterbi and CYK — every number computed, every step explained."],
  [ListChecks, "Checks understanding", "Checkpoint quizzes between sections, a click-to-match activity and flip cards for key terms."],
  [BrainCircuit, "A tutor for every deck", "Ask questions about the deck in a persona you pick. Works offline; better with an AI key."],
  [Share2, "Present, share and study", "PowerPoint and a web deck, a presenter console, view-only links, flashcards and a cheat sheet."],
];

const STEPS = ["Upload a PDF, PPT or notes — or type a topic", "Review the outline Learnova extracts", "Generate: visuals, illustrations, quizzes", "Present, download the .pptx, or share a link"];

function Mark({ size = 28 }) {
  return (
    <svg viewBox="0 0 72 72" width={size} height={size} aria-hidden="true">
      <path d="M20 8 H34 V46 L20 62 Z" fill="#402B25" />
      <path d="M20 62 L34 46 H62 L56 62 Z" fill="#F47B45" />
      <path d="M34 46 L20 62 V46 Z" fill="#D95D39" />
    </svg>
  );
}

export default function MobileLanding() {
  const { isSignedIn } = useAuth();
  const start = isSignedIn ? "/app/create" : "/sign-in";
  return (
    <div className="min-h-svh bg-[#FFFAF5] text-[#402B25]" style={{ fontFamily: "Manrope, system-ui, sans-serif" }}>
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-[#F1E6DC] bg-[#FFFAF5]/90 px-4 py-3 backdrop-blur">
        <Link to="/" className="flex items-center gap-2 text-lg font-bold tracking-tight" aria-label="Learnova home">
          <Mark /> learnova
        </Link>
        <Link to={isSignedIn ? "/app" : "/sign-in"} className="rounded-full bg-[#402B25] px-4 py-2 text-sm font-semibold" style={{ color: "#FFFAF5" }}>
          {isSignedIn ? "Dashboard" : "Sign in"}
        </Link>
      </header>

      <section className="px-5 pb-10 pt-10 text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#F3E6DA] px-3 py-1 text-xs font-bold">
          <Sparkles className="size-3.5 text-[#D95D39]" /> AI presentation engine for teaching
        </span>
        <h1 className="mt-5 text-[34px] font-semibold leading-[1.08] tracking-tight" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
          Your lecture notes,
          <br />
          <em className="text-[#D95D39]">designed into a deck.</em>
        </h1>
        <p className="mx-auto mt-4 max-w-md text-[15px] leading-6 text-[#715A4E]">
          Drop in a syllabus, PDF or PPT. Learnova keeps every important point, gives each idea the right visual, and adds quizzes and a study tutor.
        </p>
        <div className="mt-6 flex flex-col gap-3">
          <Link to={start} className="inline-flex items-center justify-center gap-2 rounded-full bg-[#F47B45] px-5 py-3.5 text-[15px] font-bold text-[#2A1A14]">
            Upload a lecture <ArrowRight className="size-4" />
          </Link>
          <a href="#how" className="rounded-full border border-[#E8D8C9] bg-white px-5 py-3.5 text-[15px] font-semibold">
            See how it works
          </a>
        </div>
      </section>

      <section className="px-5 pb-10" aria-label="Features">
        <h2 className="mb-4 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
          Slides take an evening. <em className="text-[#D95D39]">They shouldn’t.</em>
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {FEATURES.map(([Icon, h, b]) => (
            <div key={h} className="rounded-2xl border border-[#F1E6DC] bg-white p-4">
              <span className="grid size-9 place-items-center rounded-xl bg-[#FCE5D6] text-[#B44A22]"><Icon className="size-[18px]" /></span>
              <h3 className="mt-3 text-[15px] font-bold">{h}</h3>
              <p className="mt-1 text-sm leading-6 text-[#715A4E]">{b}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="how" className="bg-[#402B25] px-5 py-10 text-[#FFFAF5]">
        <h2 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>How it works</h2>
        <ol className="mt-5 space-y-3">
          {STEPS.map((t, i) => (
            <li key={t} className="flex items-start gap-3 rounded-2xl bg-white/5 p-4">
              <span className="grid size-7 shrink-0 place-items-center rounded-full bg-[#F47B45] text-sm font-bold text-[#2A1A14]">{i + 1}</span>
              <span className="text-[15px] leading-6">{t}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="px-5 py-10 text-center">
        <MonitorPlay className="mx-auto size-8 text-[#D95D39]" />
        <h2 className="mt-3 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>Turn your next lecture into a deck</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[#715A4E]">Works without any API key. Add one later for AI rewriting and generated pictures.</p>
        <Link to={start} className="mt-5 inline-flex items-center gap-2 rounded-full bg-[#402B25] px-6 py-3.5 text-[15px] font-bold" style={{ color: "#FFFAF5" }}>
          Start for free <ArrowRight className="size-4" />
        </Link>
      </section>

      <footer className="border-t border-[#F1E6DC] px-5 py-6 text-xs text-[#715A4E]">
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          <Link to="/app/docs">Docs</Link>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
        </div>
        <p className="mt-3">© Learnova</p>
      </footer>
    </div>
  );
}
