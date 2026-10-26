import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  ChevronsUpDown,
  Home,
  LayoutGrid,
  LogOut,
  MoreHorizontal,
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
      className="grid shrink-0 place-items-center rounded-full bg-[#F47B45] text-[13px] font-bold text-[#2A1A14]"
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

/** Tooltips only matter when the rail is collapsed to icons (<1100px). */
function RailTip({ label, children }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent
        side="right"
        sideOffset={10}
        className="border border-[#E8D8C9] bg-[#FFFAF5] text-[12px] font-semibold text-[#402B25] max-[1099px]:block min-[1100px]:hidden"
      >
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

const linkBase =
  "relative flex h-10 items-center gap-3 rounded-xl px-3 text-[14px] font-medium text-[#E8D8C9] transition-[background-color,color,transform] duration-150 hover:bg-[#FFFAF5]/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F47B45] max-[1099px]:justify-center max-[1099px]:px-0";

export default function AppSidebar({ onNew }) {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const { decks } = useDecks();
  const recent = (decks ?? []).slice(0, 3);

  return (
    <TooltipProvider delayDuration={100}>
      <aside
        aria-label="Primary"
        className="fixed inset-y-0 left-0 z-30 hidden w-[72px] flex-col bg-[#402B25] text-[#FFFAF5] md:flex min-[1100px]:w-[248px]"
      >
        <div className="flex h-14 items-center gap-2 px-4 max-[1099px]:justify-center max-[1099px]:px-0">
          <Link to="/app" className="flex items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#F47B45]" aria-label="Learnova home">
            <span className="grid size-8 place-items-center rounded-[10px] bg-[#F47B45] text-[#2A1A14] shadow-sm">
              <Sparkles className="size-[18px]" />
            </span>
            <span className="font-[Bricolage_Grotesque] text-[19px] font-bold tracking-tight text-[#FFFAF5] max-[1099px]:hidden">
              Learnova
            </span>
          </Link>
        </div>

        <div className="px-3 pb-2 pt-1">
          <RailTip label="New deck (N)">
            <button
              onClick={onNew}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-[#F47B45] text-[14px] font-bold text-[#2A1A14] shadow-[0_8px_20px_-8px_rgb(244_123_69/0.7)] transition duration-150 hover:-translate-y-0.5 hover:bg-[#FF8A58] active:translate-y-0 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FFFAF5]"
            >
              <Plus className="size-[18px]" strokeWidth={2.5} />
              <span className="max-[1099px]:hidden">New deck</span>
              <kbd className="ml-1 rounded bg-[#2A1A14]/15 px-1.5 text-[11px] font-semibold max-[1099px]:hidden">N</kbd>
            </button>
          </RailTip>
        </div>

        <nav aria-label="Main" className="flex flex-col gap-1 px-3 pt-2">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <RailTip key={item.to} label={item.title}>
                <Link
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={cn(linkBase, active && "lv-rail-active font-semibold text-white")}
                >
                  <item.icon className={cn("size-[18px] shrink-0", active && "text-[#F47B45]")} />
                  <span className="max-[1099px]:hidden">{item.title}</span>
                </Link>
              </RailTip>
            );
          })}
        </nav>

        <div className="mt-6 min-h-0 flex-1 overflow-y-auto px-3 max-[1099px]:hidden">
          {recent.length ? (
            <>
              <p className="px-3 pb-2 text-[11px] font-bold uppercase tracking-[0.12em] text-[#B8A396]">Recent</p>
              <ul className="flex flex-col gap-1">
                {recent.map((d) => (
                  <li key={deckId(d)}>
                    <Link
                      to={`/app/preview/${deckId(d)}`}
                      className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition-colors hover:bg-[#FFFAF5]/10 focus-visible:outline-2 focus-visible:outline-[#F47B45]"
                    >
                      <span className="w-12 shrink-0 overflow-hidden rounded-md ring-1 ring-[#FFFAF5]/20">
                        <DeckThumb id={deckId(d)} title={deckTitle(d)} />
                      </span>
                      <span className="line-clamp-2 text-[13px] font-medium leading-4 text-[#E8D8C9]">{deckTitle(d)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>

        <div className="mt-auto flex flex-col gap-1 border-t border-[#FFFAF5]/12 p-3 max-[1099px]:items-stretch">
          <RailTip label="Settings">
            <Link
              to="/app/settings"
              aria-current={pathname.startsWith("/app/settings") ? "page" : undefined}
              className={cn(linkBase, "w-full", pathname.startsWith("/app/settings") && "lv-rail-active font-semibold text-white")}
            >
              <Settings className={cn("size-[18px]", pathname.startsWith("/app/settings") && "text-[#F47B45]")} />
              <span className="max-[1099px]:hidden">Settings</span>
            </Link>
          </RailTip>
          <AccountMenu>
            <button className="mt-1 flex w-full items-center gap-2.5 rounded-xl p-2 text-left transition-colors hover:bg-[#FFFAF5]/10 focus-visible:outline-2 focus-visible:outline-[#F47B45] max-[1099px]:justify-center max-[1099px]:p-1.5">
              <Avatar user={user} />
              <span className="min-w-0 flex-1 max-[1099px]:hidden">
                <span className="block truncate text-[13px] font-semibold text-[#FFFAF5]">{user?.fullName || "Account"}</span>
                <span className="block truncate text-[11px] text-[#CDB8A8]">{user?.phone || "Signed in"}</span>
              </span>
              <ChevronsUpDown className="size-4 text-[#CDB8A8] max-[1099px]:hidden" />
            </button>
          </AccountMenu>
        </div>
      </aside>
    </TooltipProvider>
  );
}

/** Mobile (<768px): dark-brown bottom bar — 4 destinations, a centre "new deck" action and a More menu. */
export function MobileTabs({ onNew }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const tabs = [NAV[0], NAV[1], null, NAV[2]];
  const more = [NAV[3], NAV[4], NAV[5], { title: "Settings", to: "/app/settings", icon: Settings }];
  const moreActive = more.some((m) => (m.match ? m.match(pathname) : pathname.startsWith(m.to)));
  const tab = "relative flex h-full min-h-[48px] flex-col items-center justify-center gap-0.5 text-[11px] font-semibold text-[#E8D8C9] transition-colors active:bg-[#FFFAF5]/10";
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 grid h-16 grid-cols-5 items-stretch border-t border-[#FFFAF5]/10 bg-[#402B25] pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {tabs.map((t, i) =>
        t ? (
          <Link
            key={t.to}
            to={t.to}
            aria-current={t.match(pathname) ? "page" : undefined}
            className={cn(tab, t.match(pathname) && "text-[#F47B45]")}
          >
            <t.icon className="size-5" />
            {t.title.replace("My ", "")}
            {t.match(pathname) ? <span className="absolute top-0 h-[3px] w-8 rounded-b-full bg-[#F47B45]" /> : null}
          </Link>
        ) : (
          <button
            key={i}
            onClick={onNew}
            aria-label="New deck"
            className="mx-auto mt-[-14px] grid size-[52px] place-items-center self-start rounded-full bg-[#F47B45] text-[#2A1A14] shadow-[0_8px_20px_-6px_rgb(0_0_0/0.5)] ring-4 ring-[#FFFAF5] transition active:scale-95"
          >
            <Plus className="size-6" strokeWidth={2.6} />
          </button>
        )
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className={cn(tab, moreActive && "text-[#F47B45]")} aria-label="More">
            <MoreHorizontal className="size-5" />
            More
            {moreActive ? <span className="absolute top-0 h-[3px] w-8 rounded-b-full bg-[#F47B45]" /> : null}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="end" className="mb-2 w-52">
          {more.map((m) => (
            <DropdownMenuItem key={m.to} className="h-11 text-[14px]" onSelect={() => navigate(m.to)}>
              <m.icon className="size-4" /> {m.title}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="h-11 text-[14px]"
            onSelect={async () => {
              await signOut();
              navigate("/");
            }}
          >
            <LogOut className="size-4" /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
  );
}
