import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { BarChart3, BookOpen, BrainCircuit, CornerDownLeft, Home, LayoutGrid, Plus, Presentation, Search, Settings } from "lucide-react";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import { cn } from "@/lib/utils";

/** Cmd/Ctrl+K palette: jump to decks and pages, start a new deck. */
export default function CommandPalette({ open, onOpenChange, onNew }) {
  const navigate = useNavigate();
  const { decks } = useDecks();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
    }
  }, [open]);

  const items = useMemo(() => {
    const go = (to) => () => navigate(to);
    const base = [
      { id: "new", label: "New deck", hint: "Action", icon: Plus, run: onNew },
      { id: "home", label: "Home", hint: "Page", icon: Home, run: go("/app") },
      { id: "decks", label: "My Decks", hint: "Page", icon: Presentation, run: go("/app/presentations") },
      { id: "tpl", label: "Templates", hint: "Page", icon: LayoutGrid, run: go("/app/gallery") },
      { id: "quiz", label: "Quizzes", hint: "Page", icon: BrainCircuit, run: go("/app/quizzes") },
      { id: "ins", label: "Insights", hint: "Page", icon: BarChart3, run: go("/app/analytics") },
      { id: "help", label: "Help", hint: "Page", icon: BookOpen, run: go("/app/docs") },
      { id: "set", label: "Settings", hint: "Page", icon: Settings, run: go("/app/settings") },
      ...(decks ?? []).map((d) => ({
        id: `d-${deckId(d)}`,
        label: deckTitle(d),
        hint: "Deck",
        icon: Presentation,
        run: go(`/app/preview/${deckId(d)}`),
      })),
    ];
    const t = q.trim().toLowerCase();
    return t ? base.filter((i) => i.label.toLowerCase().includes(t)) : base.slice(0, 12);
  }, [q, decks, navigate, onNew]);

  useEffect(() => setActive(0), [q]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-i="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function choose(i) {
    const it = items[i];
    if (!it) return;
    onOpenChange(false);
    setTimeout(it.run, 0);
  }

  function onKey(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(items.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(active);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[#402B25]/30 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-[15vh] z-50 w-[calc(100vw-32px)] max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border bg-white shadow-[0_24px_60px_-12px_rgb(64_43_37/0.35)] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <div className="flex items-center gap-2.5 border-b px-4">
            <Search className="size-4 text-[#765F53]" />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={onKey}
              placeholder="Search decks and pages, or run a command…"
              className="h-12 flex-1 bg-transparent text-[14px] outline-none placeholder:text-[#765F53]"
            />
            <kbd className="rounded border bg-[#FFFAF5] px-1.5 text-[11px] text-[#7C6659]">esc</kbd>
          </div>
          <ul ref={listRef} className="max-h-[50vh] overflow-y-auto p-2" role="listbox">
            {items.length === 0 ? (
              <li className="px-3 py-8 text-center text-[13px] text-[#7C6659]">No matches for “{q}”.</li>
            ) : (
              items.map((it, i) => (
                <li key={it.id} data-i={i} role="option" aria-selected={i === active}>
                  <button
                    onMouseMove={() => setActive(i)}
                    onClick={() => choose(i)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[14px]",
                      i === active ? "bg-[#FCE5D6] text-[#8F3A18]" : "text-[#402B25]"
                    )}
                  >
                    <it.icon className="size-4 shrink-0" />
                    <span className="min-w-0 flex-1 truncate">{it.label}</span>
                    <span className="text-[11px] text-[#765F53]">{it.hint}</span>
                    {i === active ? <CornerDownLeft className="size-3.5" /> : null}
                  </button>
                </li>
              ))
            )}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
