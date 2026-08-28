/**
 * Auth shim.
 *
 * In normal operation this re-exports @clerk/react (v6). When the app is
 * started with `VITE_DEMO=1` it swaps in no-op stubs so the UI can be run and
 * viewed without a Clerk account (the FastAPI backend already has an anonymous
 * single-user mode). Demo mode is never bundled unless the env flag is set.
 */
import * as Clerk from "@clerk/react";

export const DEMO = import.meta.env.VITE_DEMO === "1";

const passthrough = ({ children }) => children ?? null;
const empty = () => null;

export const useAuth = DEMO
  ? () => ({ getToken: async () => null, isLoaded: true, isSignedIn: true })
  : Clerk.useAuth;

export const useUser = DEMO
  ? () => ({ isLoaded: true, isSignedIn: true, user: { firstName: "Demo", fullName: "Demo User" } })
  : Clerk.useUser;

// @clerk/react v6 replaced <SignedIn>/<SignedOut> with <Show when="…">.
// Keep the old names so the rest of the app is unchanged.
export const SignedIn = DEMO
  ? passthrough
  : ({ children }) => <Clerk.Show when="signed-in">{children}</Clerk.Show>;
export const SignedOut = DEMO
  ? empty
  : ({ children }) => <Clerk.Show when="signed-out">{children}</Clerk.Show>;

export const UserButton = DEMO
  ? () => (
      <div
        title="Demo user"
        className="grid size-8 place-items-center rounded-full bg-primary/20 text-xs font-medium text-primary"
      >
        D
      </div>
    )
  : Clerk.UserButton;

export const SignIn = Clerk.SignIn;
export const SignUp = Clerk.SignUp;
export const ClerkProvider = Clerk.ClerkProvider;
