import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  ChevronsUpDown,
  Home,
  LayoutGrid,
  LogOut,
  Plus,
  Presentation,
  Settings,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/auth";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import DeckThumb from "@/components/app/DeckThumb";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export const NAV = [
  { title: "Home", to: "/app", icon: Home, match: (p) => p === "/app" || p.startsWith("/app/create") || p.startsWith("/app/generate") },
  { title: "My Decks", to: "/app/presentations", icon: Presentation, match: (p) => p.startsWith("/app/presentations") },
  { title: "Templates", to: "/app/gallery", icon: LayoutGrid, match: (p) => p.startsWith("/app/gallery") },
  { title: "Quizzes", to: "/app/quizzes", icon: BrainCircuit, match: (p) => p.startsWith("/app/quizzes") },
  { title: "Insights", to: "/app/analytics", icon: BarChart3, match: (p) => p.startsWith("/app/analytics") },
  { title: "Help", to: "/app/docs", icon: BookOpen, match: (p) => p.startsWith("/app/docs") },
];

function Avatar({ user, size = 32 }) {
  const initial = (user?.fullName || user?.phone || "?").replace("+", "").charAt(0).toUpperCase();
  return (
    <span
      style={{ width: size, height: size }}
      className="grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#2563EB] to-[#12C99B] text-xs font-bold text-white"
    >
      {initial}
    </span>
  );
}

export function AccountMenu({ children, align = "start", side = "top" }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align={align} side={side} className="w-56">
        <DropdownMenuLabel className="flex flex-col gap-0.5">
          <span>{user?.fullName || "Your account"}</span>
          {user?.phone ? <span className="text-xs font-normal text-muted-foreground">{user.phone}</span> : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/app/settings")}>
          <Settings className="size-4" /> Settings
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={async () => {
            await signOut();
            navigate("/");
          }}
        >
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function RailTip({ label, children }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right" className="max-[1099px]:block min-[1100px]:hidden">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

export default function AppSidebar({ onNew }) {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const { decks } = useDecks();
  const recent = (decks ?? []).slice(0, 3);

  return (
    <TooltipProvider delayDuration={100}>
      <aside
        aria-label="Primary"
        className="fixed inset-y-0 left-0 z-30 hidden w-[72px] flex-col border-r bg-white md:flex min-[1100px]:w-[248px]"
      >
        <div className="flex h-12 items-center gap-2 px-4 max-[1099px]:justify-center max-[1099px]:px-0">
          <Link to="/app" className="flex items-center gap-2.5">
            <span className="grid size-7 place-items-center rounded-lg bg-[#2563EB] text-white shadow-sm">
              <Sparkles className="size-4" />
            </span>
            <span className="font-[Bricolage_Grotesque] text-[17px] font-bold tracking-tight text-[#0B1F44] max-[1099px]:hidden">
              Learnova
            </span>
          </Link>
        </div>

        <div className="px-3 pb-2 pt-2 max-[1099px]:px-3">
          <RailTip label="New deck (N)">
            <button
              onClick={onNew}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-[10px] bg-[#0B1F44] text-[14px] font-semibold text-white shadow-sm transition hover:bg-[#13306a] active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2563EB]"
            >
              <Plus className="size-4" />
              <span className="max-[1099px]:hidden">New deck</span>
              <kbd className="ml-1 rounded bg-white/15 px-1.5 text-[11px] font-medium max-[1099px]:hidden">N</kbd>
            </button>
          </RailTip>
        </div>

        <nav className="flex flex-col gap-0.5 px-3 pt-2">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <RailTip key={item.to} label={item.title}>
                <Link
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex h-9 items-center gap-3 rounded-lg px-3 text-[14px] font-medium text-[#3C4D70] transition-colors hover:bg-[#F0F5FD] hover:text-[#0B1F44] max-[1099px]:justify-center max-[1099px]:px-0",
                    active && "lv-pill-active font-semibold hover:bg-[#E6EEFD] hover:text-[#1D4ED8]"
                  )}
                >
                  <item.icon className="size-[18px] shrink-0" />
                  <span className="max-[1099px]:hidden">{item.title}</span>
                </Link>
              </RailTip>
            );
          })}
        </nav>

        <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-3 max-[1099px]:hidden">
          {recent.length ? (
            <>
              <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#8190AD]">Recent</p>
              <ul className="flex flex-col gap-0.5">
                {recent.map((d) => (
                  <li key={deckId(d)}>
                    <Link
                      to={`/app/preview/${deckId(d)}`}
                      className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-[#F0F5FD]"
                    >
                      <span className="w-12 shrink-0 overflow-hidden rounded-md border">
                        <DeckThumb id={deckId(d)} title={deckTitle(d)} />
                      </span>
                      <span className="line-clamp-2 text-[13px] font-medium leading-4 text-[#2A3B5F]">{deckTitle(d)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>

        <div className="mt-auto flex flex-col gap-0.5 border-t p-3 max-[1099px]:items-center">
          <RailTip label="Settings">
            <Link
              to="/app/settings"
              className={cn(
                "relative flex h-9 w-full items-center gap-3 rounded-lg px-3 text-[14px] font-medium text-[#3C4D70] transition-colors hover:bg-[#F0F5FD] max-[1099px]:justify-center max-[1099px]:px-0",
                pathname.startsWith("/app/settings") && "lv-pill-active font-semibold"
              )}
            >
              <Settings className="size-[18px]" />
              <span className="max-[1099px]:hidden">Settings</span>
            </Link>
          </RailTip>
          <AccountMenu>
            <button className="mt-1 flex w-full items-center gap-2.5 rounded-lg p-2 text-left transition-colors hover:bg-[#F0F5FD] max-[1099px]:justify-center max-[1099px]:p-1">
              <Avatar user={user} />
              <span className="min-w-0 flex-1 max-[1099px]:hidden">
                <span className="block truncate text-[13px] font-semibold text-[#0B1F44]">{user?.fullName || "Account"}</span>
                <span className="block truncate text-[11px] text-[#8190AD]">{user?.phone || "Signed in"}</span>
              </span>
              <ChevronsUpDown className="size-4 text-[#8190AD] max-[1099px]:hidden" />
            </button>
          </AccountMenu>
        </div>
      </aside>
    </TooltipProvider>
  );
}

/** Mobile (<768px): bottom 5-tab bar. */
export function MobileTabs({ onNew }) {
  const { pathname } = useLocation();
  const tabs = [NAV[0], NAV[1], null, NAV[2], NAV[4]];
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 grid h-16 grid-cols-5 items-center border-t bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      {tabs.map((t, i) =>
        t ? (
          <Link
            key={t.to}
            to={t.to}
            className={cn(
              "flex flex-col items-center gap-0.5 py-1 text-[11px] font-medium text-[#6A7A9B]",
              t.match(pathname) && "text-[#2563EB]"
            )}
          >
            <t.icon className="size-5" />
            {t.title.replace("My ", "")}
          </Link>
        ) : (
          <button key={i} onClick={onNew} aria-label="New deck" className="mx-auto grid size-12 -translate-y-3 place-items-center rounded-full bg-[#0B1F44] text-white shadow-lg">
            <Plus className="size-6" />
          </button>
        )
      )}
    </nav>
  );
}
