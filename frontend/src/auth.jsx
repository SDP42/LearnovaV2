/**
 * Auth shim.
 *
 * In normal operation this just re-exports @clerk/clerk-react. When the app is
 * started with `VITE_DEMO=1` it swaps in no-op stubs so the UI can be run and
 * viewed without a Clerk account (the FastAPI backend already has an anonymous
 * single-user mode). Demo mode is never bundled unless the env flag is set.
 */
import * as Clerk from "@clerk/clerk-react";

export const DEMO = import.meta.env.VITE_DEMO === "1";

const passthrough = ({ children }) => children ?? null;
const empty = () => null;

export const useAuth = DEMO
  ? () => ({ getToken: async () => null, isLoaded: true, isSignedIn: true })
  : Clerk.useAuth;

export const useUser = DEMO
  ? () => ({ isLoaded: true, isSignedIn: true, user: { firstName: "Demo", fullName: "Demo User" } })
  : Clerk.useUser;

export const SignedIn = DEMO ? passthrough : Clerk.SignedIn;
export const SignedOut = DEMO ? empty : Clerk.SignedOut;

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
