import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { Command, Search } from "lucide-react";
import { useAuth } from "@/auth";
import AppSidebar, { AccountMenu, MobileTabs } from "@/components/app/AppSidebar";
import CommandPalette from "@/components/app/CommandPalette";
import AssistantWidget from "@/components/app/AssistantWidget";
import { ShellCtx } from "@/components/app/AppLayout";
import ShortcutsOverlay, { APP_SHORTCUTS, useShortcutsKey } from "@/components/app/ShortcutsOverlay";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/i.test(navigator.platform || "");

/** Persistent app chrome used as the layout route for every /app page except Preview/Present. */
export default function AppShell() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user } = useAuth();
  const reduce = useReducedMotion();
  const [titleEl, setTitleEl] = useState(null);
  const [actionsEl, setActionsEl] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  useShortcutsKey(useCallback(() => setHelpOpen((o) => !o), []));

  const newDeck = useCallback(() => navigate("/app", { state: { focus: Date.now() } }), [navigate]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      const t = e.target;
      const typing = t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
      if (!typing && !e.metaKey && !e.ctrlKey && !e.altKey && e.key.toLowerCase() === "n") {
        e.preventDefault();
        newDeck();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [newDeck]);

  const initial = (user?.fullName || user?.phone || "?").replace("+", "").charAt(0).toUpperCase();

  return (
    <div data-learnova-app data-lv-shell className="min-h-svh bg-[#FFFAF5] text-[#402B25]">
      <AppSidebar onNew={newDeck} />
      <div className="lv-shell-main flex min-h-svh min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b bg-[#FFFAF5] px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-1.5 text-[13px]">
            <span className="hidden text-[#765F53] sm:inline">Learnova</span>
            <span aria-hidden className="hidden text-[#B8A396] sm:inline">/</span>
            <span ref={setTitleEl} className="truncate font-semibold text-[#402B25]" />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div ref={setActionsEl} className="flex items-center gap-2" />
            <button
              onClick={() => setPaletteOpen(true)}
              aria-label="Search (Command K)"
              className="flex h-10 items-center gap-2 rounded-full border bg-white px-3.5 text-[13px] text-[#765F53] transition duration-150 hover:-translate-y-px hover:border-[#E3A98B] hover:shadow-[0_8px_18px_-10px_rgb(64_43_37/0.3)] max-sm:w-10 max-sm:justify-center max-sm:px-0 sm:w-60"
            >
              <Search className="size-3.5" />
              <span className="hidden flex-1 text-left sm:inline">Search…</span>
              <kbd className="hidden items-center gap-0.5 rounded border bg-[#FFFAF5] px-1 text-[11px] sm:inline-flex">
                {isMac ? <Command className="size-2.5" /> : "Ctrl"}K
              </kbd>
            </button>
            <div className="md:hidden">
              <AccountMenu align="end" side="bottom">
                <button aria-label="Account" className="grid size-10 place-items-center rounded-full bg-[#F47B45] text-[13px] font-bold text-[#2A1A14]">
                  {initial}
                </button>
              </AccountMenu>
            </div>
          </div>
        </header>

        <ShellCtx.Provider value={{ title: titleEl, actions: actionsEl }}>
          <motion.main
            key={pathname}
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="min-w-0 flex-1 pb-20 md:pb-0"
          >
            <Outlet context={{ newDeck }} />
          </motion.main>
        </ShellCtx.Provider>
      </div>
      <MobileTabs onNew={newDeck} />
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} onNew={newDeck} />
      <AssistantWidget />
      <ShortcutsOverlay open={helpOpen} onOpenChange={setHelpOpen} groups={APP_SHORTCUTS} />
    </div>
  );
}
