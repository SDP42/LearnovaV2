import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { Command, Search } from "lucide-react";
import { useAuth } from "@/auth";
import { Toaster } from "sonner";
import AppSidebar, { AccountMenu, MobileTabs } from "@/components/app/AppSidebar";
import CommandPalette from "@/components/app/CommandPalette";
import AssistantWidget from "@/components/app/AssistantWidget";
import { ShellCtx } from "@/components/app/AppLayout";

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
        <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-3 border-b bg-white/85 px-4 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-1.5 text-[13px]">
            <span className="hidden text-[#8A7468] sm:inline">Learnova</span>
            <span className="hidden text-[#C0CBE0] sm:inline">/</span>
            <span ref={setTitleEl} className="truncate font-semibold text-[#402B25]" />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div ref={setActionsEl} className="flex items-center gap-2" />
            <button
              onClick={() => setPaletteOpen(true)}
              aria-label="Search (Command K)"
              className="flex h-8 items-center gap-2 rounded-full border bg-[#FFFAF5] px-3 text-[13px] text-[#7C6659] transition-colors hover:border-[#DCC6B4] hover:bg-white sm:w-56"
            >
              <Search className="size-3.5" />
              <span className="hidden flex-1 text-left sm:inline">Search…</span>
              <kbd className="hidden items-center gap-0.5 rounded border bg-white px-1 text-[11px] sm:inline-flex">
                {isMac ? <Command className="size-2.5" /> : "Ctrl"}K
              </kbd>
            </button>
            <div className="md:hidden">
              <AccountMenu align="end" side="bottom">
                <button aria-label="Account" className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-[#C2502A] to-[#6B9B72] text-xs font-bold text-white">
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
      <Toaster position="bottom-right" richColors closeButton toastOptions={{ style: { fontFamily: "inherit" } }} />
    </div>
  );
}
