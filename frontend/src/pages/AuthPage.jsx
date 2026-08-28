import { Link } from "react-router-dom";
import { BrainCircuit, GaugeCircle, LayoutTemplate, Sparkles } from "lucide-react";
import { SignIn, SignUp } from "@/auth";
import { ThemeToggle } from "@/components/theme.jsx";

const POINTS = [
  [LayoutTemplate, "1000+ addressable visuals", "Flowcharts, timelines, charts, Venn, mind maps — chosen by matching your content's shape."],
  [BrainCircuit, "Progressive reveal & quizzes", "Slides build one idea per click, with checkpoint questions for active recall."],
  [GaugeCircle, "Cognitive-load aware", "A research-grounded engagement metric scores every slide and repaginates it."],
];

/**
 * Sign-in / sign-up on the new design shell. Clerk's own card styling is set
 * globally via ClerkThemed's `appearance`, so the component just drops in.
 */
export default function AuthPage({ mode = "sign-in" }) {
  const isSignIn = mode === "sign-in";
  const Clerk = isSignIn ? SignIn : SignUp;

  return (
    <div
      data-learnova-app
      className="relative flex min-h-svh flex-col overflow-hidden bg-background text-foreground"
    >
      <div className="pointer-events-none absolute inset-0 lv-grid-bg" />
      <div className="lv-glow left-1/2 top-0 h-[380px] w-[620px] -translate-x-1/2" />

      <header className="relative flex items-center justify-between px-5 py-4">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </span>
          <span className="text-base font-semibold tracking-tight">Learnova</span>
        </Link>
        <ThemeToggle />
      </header>

      <div className="relative mx-auto grid w-full max-w-5xl flex-1 items-center gap-12 px-4 py-10 lg:grid-cols-2">
        <div className="hidden flex-col gap-8 lg:flex">
          <div>
            <h2 className="text-3xl font-semibold leading-tight tracking-tight">
              Turn any syllabus into a{" "}
              <span className="lv-gradient-text">presentation that teaches</span>.
            </h2>
            <p className="mt-3 max-w-md text-muted-foreground">
              Learnova reads your content and decides — per slide — how to present
              it, then builds an animated deck with a presenter view.
            </p>
          </div>
          <ul className="flex flex-col gap-5">
            {POINTS.map(([Icon, h, b]) => (
              <li key={h} className="flex gap-3">
                <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </span>
                <div>
                  <p className="font-medium">{h}</p>
                  <p className="text-sm text-muted-foreground">{b}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex w-full flex-col items-center gap-6">
          <div className="text-center lg:hidden">
            <h1 className="text-2xl font-semibold tracking-tight">
              {isSignIn ? "Welcome back" : "Create your account"}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Continue to your Learnova studio and deck library.
            </p>
          </div>

          <Clerk
            routing="path"
            path={isSignIn ? "/sign-in" : "/sign-up"}
            {...(isSignIn ? { signUpUrl: "/sign-up" } : { signInUrl: "/sign-in" })}
            fallbackRedirectUrl="/app"
            forceRedirectUrl="/app"
          />

          <p className="text-center text-xs text-muted-foreground">
            {isSignIn ? (
              <>New here? <Link to="/sign-up" className="underline">Create an account</Link></>
            ) : (
              <>Already have an account? <Link to="/sign-in" className="underline">Sign in</Link></>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
