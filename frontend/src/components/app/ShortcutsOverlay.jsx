import { useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Keyboard, X } from "lucide-react";
import { cn } from "@/lib/utils";

/** True when the keyboard event came from somewhere the user is typing. */
export function isTypingTarget(t) {
  return (
    t instanceof HTMLElement &&
    (t.isContentEditable ||
      /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) ||
      // open Radix menus / select popups own their keys
      !!t.closest('[data-radix-popper-content-wrapper],[role="menu"]'))
  );
}

/**
 * Calls `onToggle` when the user presses "?" (Shift + /) outside a text field.
 * Pass `enabled=false` to suspend (e.g. while another overlay owns the keys).
 */
export function useShortcutsKey(onToggle, enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined;
    const onKey = (e) => {
      if (e.key !== "?" || e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;
      e.preventDefault();
      onToggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onToggle, enabled]);
}

/** Shortcut groups reused by Preview and the presenter console. */
export const PRESENT_SHORTCUTS = [
  {
    title: "Move",
    rows: [
      [["←", "→"], "Previous / next build or slide"],
      [["Space"], "Next build or slide"],
      [["Home", "End"], "First / last slide"],
      [["1", "2", "↵"], "Type a number, then Enter, to jump"],
    ],
  },
  {
    title: "On stage",
    rows: [
      [["F"], "Fullscreen (F5 starts the show)"],
      [["B"], "Blackout the audience screen"],
      [["W"], "White screen"],
      [["L"], "Laser pointer"],
      [["D", "E"], "Pen / erase ink"],
      [["G"], "Slide sorter"],
      [["P", "R"], "Pause / reset the timer"],
    ],
  },
  {
    title: "Anywhere",
    rows: [
      [["T"], "Open the tutor"],
      [["?"], "This cheat sheet"],
      [["Esc"], "Close tools and overlays"],
    ],
  },
];

export const PREVIEW_SHORTCUTS = [
  {
    title: "Browse",
    rows: [
      [["↑", "↓", "←", "→"], "Previous / next slide"],
    ],
  },
  {
    title: "Present",
    rows: [
      [["Space"], "Next build (in the presenter)"],
      [["F"], "Fullscreen (in the presenter)"],
      [["B"], "Blackout (in the presenter)"],
    ],
  },
  {
    title: "Anywhere",
    rows: [
      [["T"], "Open the tutor"],
      [["⌘/Ctrl", "K"], "Search decks and actions"],
      [["?"], "This cheat sheet"],
    ],
  },
];

export const APP_SHORTCUTS = [
  {
    title: "Navigate",
    rows: [
      [["N"], "New deck"],
      [["⌘/Ctrl", "K"], "Search decks and actions"],
      [["?"], "This cheat sheet"],
    ],
  },
  {
    title: "In a deck",
    rows: [
      [["↑", "↓"], "Previous / next slide in the editor"],
      [["T"], "Open the tutor"],
      [["Space"], "Next build in the presenter"],
      [["F"], "Fullscreen in the presenter"],
      [["B"], "Blackout in the presenter"],
    ],
  },
];

function Key({ children, dark }) {
  return (
    <kbd
      className={cn(
        "inline-flex min-w-[24px] items-center justify-center rounded-md border border-b-2 px-1.5 py-0.5 font-mono text-[11.5px] font-medium",
        dark ? "border-[#FFFAF5]/20 bg-[#FFFAF5]/10 text-[#FFFAF5]" : "border-[#DCC6B4] bg-[#FFFAF5] text-[#402B25]"
      )}
    >
      {children}
    </kbd>
  );
}

/**
 * Keyboard-shortcut cheat sheet. `groups` = [{title, rows:[[keys[], label]]}].
 * `dark` styles it for the presenter console (which is intentionally dark).
 */
export default function ShortcutsOverlay({ open, onOpenChange, groups, title = "Keyboard shortcuts", dark = false }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            "fixed inset-0 z-[70] data-[state=open]:animate-in data-[state=open]:fade-in-0",
            dark ? "bg-black/75" : "bg-[#402B25]/40"
          )}
        />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            "fixed left-1/2 top-1/2 z-[71] max-h-[86svh] w-[min(94vw,640px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[20px] border p-5 shadow-[0_30px_80px_-24px_rgb(0_0_0/0.5)] outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 sm:p-6",
            dark ? "border-[#FFFAF5]/15 bg-[#2A1A14] text-[#FFFAF5]" : "border-[#E8D8C9] bg-white text-[#402B25]"
          )}
        >
          <div className="mb-4 flex items-center gap-3">
            <span className={cn("grid size-9 place-items-center rounded-xl", dark ? "bg-[#F47B45] text-[#2A1A14]" : "bg-[#FCE5D6] text-[#8F3A18]")}>
              <Keyboard className="size-[18px]" />
            </span>
            <Dialog.Title className="font-[Bricolage_Grotesque] text-[20px] font-bold tracking-tight">{title}</Dialog.Title>
            <Dialog.Close
              aria-label="Close shortcuts"
              className={cn(
                "ml-auto grid size-10 place-items-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-[#F47B45] sm:size-9",
                dark ? "text-[#E8D8C9] hover:bg-[#FFFAF5]/10" : "text-[#715A4E] hover:bg-[#F3E6DA]"
              )}
            >
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
            {groups.map((g) => (
              <section key={g.title}>
                <h3
                  className={cn(
                    "mb-2 text-[11px] font-bold uppercase tracking-[0.12em]",
                    dark ? "text-[#CDB8A8]" : "text-[#715A4E]"
                  )}
                >
                  {g.title}
                </h3>
                <dl className="flex flex-col gap-2">
                  {g.rows.map(([keys, label]) => (
                    <div key={keys.join("+") + label} className="flex items-center justify-between gap-3">
                      <dt className={cn("text-[13px]", dark ? "text-[#E8D8C9]" : "text-[#4F3A31]")}>{label}</dt>
                      <dd className="flex shrink-0 items-center gap-1">
                        {keys.map((k) => (
                          <Key key={k} dark={dark}>
                            {k}
                          </Key>
                        ))}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
