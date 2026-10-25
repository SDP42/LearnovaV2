/**
 * Auth for Learnova: mobile number + OTP, backed by the FastAPI/SQLite API.
 *
 * The exports mirror the old Clerk shim (useAuth, useUser, SignedIn, SignedOut,
 * UserButton) so pages that already import from "@/auth" keep working. The
 * session token is an opaque string kept in localStorage and sent as a Bearer
 * header by api.js.
 *
 * `VITE_DEMO=1` swaps in stubs so the UI runs against a backend started with
 * LEARNOVA_AUTH=off.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { LogOut, Phone } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import * as api from "@/api";

export const DEMO = import.meta.env.VITE_DEMO === "1";
const KEY = "learnova.token";

const readToken = () => {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
};
const writeToken = (t) => {
  try {
    t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY);
  } catch {
    /* storage blocked — session lasts until reload */
  }
};

const demoUser = { firstName: "Demo", fullName: "Demo User", full_name: "Demo User", completed: true };
const Ctx = createContext(null);

function decorate(u) {
  if (!u) return null;
  const name = (u.full_name || "").trim();
  return { ...u, fullName: name, firstName: name.split(/\s+/)[0] || "" };
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => (DEMO ? null : readToken()));
  const [user, setUser] = useState(DEMO ? demoUser : null);
  const [isLoaded, setLoaded] = useState(DEMO || !readToken());

  useEffect(() => {
    if (DEMO || !token) return;
    let live = true;
    api
      .authMe(token)
      .then((u) => live && setUser(decorate(u)))
      .catch(() => {
        if (!live) return;
        writeToken(null);
        setToken(null);
        setUser(null);
      })
      .finally(() => live && setLoaded(true));
    return () => {
      live = false;
    };
  }, [token]);

  const setSession = useCallback((tok, u) => {
    writeToken(tok);
    setToken(tok);
    setUser(decorate(u));
    setLoaded(true);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.authLogout();
    } catch {
      /* already invalid */
    }
    writeToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      isLoaded,
      isSignedIn: DEMO || (!!token && !!user),
      user,
      token,
      getToken: async () => token,
      setSession,
      setUser: (u) => setUser(decorate(u)),
      signOut,
    }),
    [isLoaded, token, user, setSession, signOut]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
export const useUser = () => {
  const { isLoaded, isSignedIn, user } = useContext(Ctx);
  return { isLoaded, isSignedIn, user };
};

export const SignedIn = ({ children }) => (useContext(Ctx).isSignedIn ? children : null);
export const SignedOut = ({ children }) => (useContext(Ctx).isSignedIn ? null : children);

export function UserButton() {
  const { user, signOut } = useContext(Ctx);
  const navigate = useNavigate();
  const initial = (user?.fullName || user?.phone || "?").replace("+", "").charAt(0).toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label="Account menu"
          className="grid size-8 place-items-center rounded-full bg-primary/20 text-xs font-semibold text-primary outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
        >
          {initial}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="flex flex-col gap-0.5">
          <span>{user?.fullName || "Your account"}</span>
          {user?.phone && (
            <span className="flex items-center gap-1 text-xs font-normal text-muted-foreground">
              <Phone className="size-3" /> {user.phone}
            </span>
          )}
        </DropdownMenuLabel>
        {!DEMO && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={async () => {
                await signOut();
                navigate("/");
              }}
            >
              <LogOut className="size-4" /> Sign out
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Editable profile card for Settings → Account (phone is verified, read-only). */
export function UserProfile() {
  const { user, setUser, signOut } = useContext(Ctx);
  const [f, setF] = useState({
    full_name: user?.full_name || "",
    email: user?.email || "",
    role: user?.role || "",
    organization: user?.organization || "",
    avatar_color: user?.avatar_color || "",
  });
  const [msg, setMsg] = useState("");
  if (DEMO || !user) return <p className="text-sm text-muted-foreground">Account management needs a signed-in user.</p>;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const field = "w-full rounded-md border bg-background px-3 py-2 text-sm";
  return (
    <form
      className="flex max-w-md flex-col gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          setUser(await api.saveProfile(f));
          setMsg("Saved");
        } catch (x) {
          setMsg(x.message);
        }
      }}
    >
      <p className="text-sm text-muted-foreground">Mobile: <b>{user.phone}</b> (verified)</p>
      <input className={field} placeholder="Full name" value={f.full_name} onChange={set("full_name")} required />
      <input className={field} type="email" placeholder="Email" value={f.email} onChange={set("email")} />
      <input className={field} placeholder="Organisation" value={f.organization} onChange={set("organization")} />
      <select className={field} value={f.role} onChange={set("role")}>
        <option value="">Role…</option>
        {["educator", "student", "trainer", "researcher", "other"].map((r) => (
          <option key={r} value={r}>{r}</option>
        ))}
      </select>
      <div className="flex items-center gap-3">
        <button className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">Save</button>
        <button type="button" className="text-sm text-muted-foreground underline" onClick={signOut}>Sign out</button>
        {msg && <span className="text-sm text-muted-foreground">{msg}</span>}
      </div>
      <hr className="my-2" />
      <p className="text-sm font-medium text-destructive">Danger zone</p>
      <p className="text-xs text-muted-foreground">
        Deleting your account permanently removes your profile, sessions and every saved deck. This cannot be undone.
      </p>
      <button
        type="button"
        className="self-start rounded-md border border-destructive px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10"
        onClick={async () => {
          if (!window.confirm("Permanently delete your account and all your decks?")) return;
          try {
            await api.deleteAccount();
            await signOut();
            window.location.assign("/");
          } catch (x) {
            setMsg(x.message);
          }
        }}
      >
        Delete my account
      </button>
    </form>
  );
}
