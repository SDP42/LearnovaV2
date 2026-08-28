import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { SignIn, SignUp } from "@/auth";
import { ThemeToggle } from "@/components/theme.jsx";

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
      className="relative flex min-h-svh flex-col items-center justify-center overflow-hidden bg-background px-4 py-12 text-foreground"
    >
      <div className="pointer-events-none absolute inset-0 lv-grid-bg" />
      <div className="lv-glow left-1/2 top-0 h-[380px] w-[620px] -translate-x-1/2" />

      <header className="absolute inset-x-0 top-0 flex items-center justify-between px-5 py-4">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </span>
          <span className="text-base font-semibold tracking-tight">Learnova</span>
        </Link>
        <ThemeToggle />
      </header>

      <div className="relative flex w-full max-w-sm flex-col items-center gap-6">
        <div className="text-center">
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
      </div>
    </div>
  );
}
