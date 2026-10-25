import { Component, lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BarChart3, BrainCircuit, GitBranch, Home, Layers, LogIn, Presentation, Smartphone, Sparkles, Timer, Wand2 } from "lucide-react";
import { SignedIn, SignedOut } from "@/auth";
import { CountUp, Magnetic, Reveal, TiltCard } from "@/components/fx/Effects";
import { BorderTrail, Dock, InfiniteSlider, ScrollProgress, TextScramble } from "@/components/fx/Primitives";
import Compare from "@/components/landing2/Compare";
import { MaskLine, SplitChars, WordCycle, WordScrub } from "@/components/landing2/Text";
import "./landing.css";

const World = lazy(() => import("@/components/world/World"));

class WorldBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? null : this.props.children; }
}

const FEATURES = [
  [Layers, "1000+ visuals", "Flowcharts, timelines, Venns, mind maps — picked by the shape of your content.", "wide"],
  [BrainCircuit, "Inline quizzes", "Recall checkpoints attach to the slide, not as interruptions."],
  [BarChart3, "Engagement score", "Every slide is scored and repaginated against cognitive load."],
  [GitBranch, "Progressive reveal", "One idea per click, like a lecturer at a board."],
  [Timer, "Presenter console", "Notes, timer, next-slide preview, reveal-step indicator.", "wide"],
  [Wand2, "Works without keys", "Heuristic layout runs offline. Keys only improve the writing."],
];
const KINDS = ["Bar chart", "Flowchart", "Timeline", "KPI cards", "Cycle", "Comparison", "Mind map", "Venn", "Pyramid", "Pie chart", "Matrix", "Definition"];
const STATEMENT = "Most slides are walls of text nobody reads. Learnova reads your content, finds the steps, the dates, the numbers and the contrasts, and turns each one into the visual that makes it click.";

function Stats() {
  const S = [[1000, "+", "addressable visuals"], [39, "", "ready gallery decks"], [4, "", "export formats"], [0, "", "API keys required"]];
  return (
    <div className="lx-stats">
      {S.map(([n, s, l]) => (<Reveal key={l}><div className="lx-stat"><b><CountUp to={n} suffix={s} /></b><span>{l}</span></div></Reveal>))}
    </div>
  );
}

export default function Landing() {
  return (
    <div data-learnova-app className="lx">
      <WorldBoundary><Suspense fallback={null}><World /></Suspense></WorldBoundary>
      <ScrollProgress />
      <Dock items={[
        { label: "Top", href: "#top", icon: Home },
        { label: "The engine", href: "#engine", icon: Presentation },
        { label: "Features", href: "#features", icon: Sparkles },
        { label: "Sign in", href: "/sign-in", icon: LogIn },
      ]} />
      <header className="lx-nav">
        <Link to="/" className="lx-logo"><Sparkles size={18} /> Learnova</Link>
        <nav><a href="#engine">The engine</a><a href="#gallery">Visuals</a><a href="#features">Features</a></nav>
        <SignedOut><Link to="/sign-in" className="lx-btn lx-btn-ghost sm">Sign in</Link></SignedOut>
        <SignedIn><Link to="/app" className="lx-btn lx-btn-primary sm">Open app</Link></SignedIn>
      </header>

      <main>
        <section id="top" className="lx-s hero">
          <div className="lx-box left">
            <span className="lx-pill"><Sparkles size={14} /> AI presentation engine</span>
            <h1 className="lx-h1">Turn any <WordCycle words={["syllabus", "chapter", "lecture", "PDF"]} /><br />into slides that <em>teach.</em></h1>
            <p className="lx-lead">Learnova reads your content and decides, slide by slide, whether to keep text, tighten it, or turn it into a flowchart, timeline or diagram.</p>
            <div className="lx-cta-row">
              <SignedOut>
                <Magnetic><BorderTrail><Link to="/sign-in" className="lx-btn lx-btn-primary"><Smartphone size={18} /> Continue with mobile <ArrowRight size={16} /></Link></BorderTrail></Magnetic>
              </SignedOut>
              <SignedIn><Link to="/app" className="lx-btn lx-btn-primary">Open app <ArrowRight size={16} /></Link></SignedIn>
              <a href="#engine" className="lx-btn lx-btn-ghost">Fly in ↓</a>
            </div>
          </div>
          <div className="lx-scrollhint"><i /> scroll</div>
        </section>

        <section className="lx-s tall">
          <div className="lx-box right wide">
            <span className="lx-mono lx-eyebrow">// THE PROBLEM</span>
            <WordScrub text={STATEMENT} />
          </div>
        </section>

        <section id="engine" className="lx-s tall">
          <div className="lx-box left">
            <span className="lx-mono lx-eyebrow"><TextScramble text="// THE ENGINE" /></span>
            <SplitChars text="Fly through the gate." className="lx-h2" />
            <p className="lx-lead"><MaskLine>Raw pages go in on one side.</MaskLine><br /><MaskLine delay={0.1}>Designed, visual slides come out the other.</MaskLine></p>
            <ul className="lx-checks">
              <li>Reads steps, dates, numbers and contrasts</li>
              <li>Picks the visual that fits — never a wall of text</li>
              <li>Keeps definitions and formulae word for word</li>
            </ul>
          </div>
        </section>

        <section id="gallery" className="lx-s tall">
          <div className="lx-box right">
            <span className="lx-mono lx-eyebrow">// ONE SOURCE, EVERY VISUAL</span>
            <SplitChars text="Every idea gets its own picture." className="lx-h2" />
            <div className="lx-slider-wrap"><InfiniteSlider duration={30}>{KINDS.map((t) => <span key={t} className="fx-pchip">{t}</span>)}</InfiniteSlider></div>
          </div>
        </section>

        <section id="features" className="lx-s features">
          <div className="lx-wrapw">
            <span className="lx-mono lx-eyebrow center"><TextScramble text="// FEATURES" /></span>
            <SplitChars text="Everything a lecture needs" className="lx-h2 center" />
            <div className="lx-bento">
              {FEATURES.map(([Icon, t, b, w], i) => (
                <Reveal key={t} delay={i * 0.05} className={w === "wide" ? "span2" : ""}>
                  <TiltCard><Icon size={26} className="lx-ico" /><h3>{t}</h3><p>{b}</p></TiltCard>
                </Reveal>
              ))}
            </div>
            <Stats />
          </div>
        </section>

        <section className="lx-s cmp-sec">
          <div className="lx-wrapw">
            <span className="lx-mono lx-eyebrow center">// BEFORE / AFTER</span>
            <SplitChars text="Drag. Feel the difference." className="lx-h2 center" />
            <Reveal delay={0.1}><Compare /></Reveal>
          </div>
        </section>

        <section className="lx-s final">
          <div className="lx-box center">
            <h2 className="lx-h2 big"><MaskLine>Your next lecture,</MaskLine><br /><MaskLine delay={0.12}><em>ready before the coffee cools.</em></MaskLine></h2>
            <div className="lx-cta-row center">
              <Magnetic><BorderTrail><Link to="/sign-in" className="lx-btn lx-btn-primary big">Get started with your number <ArrowRight size={18} /></Link></BorderTrail></Magnetic>
            </div>
          </div>
        </section>
      </main>
      <footer className="lx-footer">
        © Learnova · Turn text into teaching. · <Link to="/privacy">Privacy</Link> · <Link to="/terms">Terms</Link>
      </footer>
    </div>
  );
}
