import { Link } from "react-router-dom";
import { Download, Eye, FileDown, MoreHorizontal, Play, Trash2 } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/api";
import { deckId, deckTitle } from "@/lib/useDecks";
import { deckSlides, deckUpdated, relativeTime } from "@/lib/format";
import DeckThumb from "@/components/app/DeckThumb";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export function statusDot(status = "ready") {
  if (/fail|error/i.test(status)) return { color: "#EF4444", label: "Failed" };
  if (/draft|await|run|process|generat/i.test(status)) return { color: "#FFC93C", label: "In progress" };
  return { color: "#6B9B72", label: "Ready" };
}

export async function downloadDeck(deck, artifact) {
  const id = deckId(deck);
  const name = `${deckTitle(deck).replace(/[^\w\- ]+/g, "").trim() || "Learnova"}.${artifact}`;
  const t = toast.loading(`Preparing ${artifact.toUpperCase()}…`);
  try {
    await api.downloadArtifact(api.deckDownloadPath(id, artifact), name);
    toast.success("Download started", { id: t });
  } catch (e) {
    toast.error(e.message || "Download failed", { id: t });
  }
}

export function confirmDelete(deck, removeWithUndo) {
  if (window.confirm(`Delete “${deckTitle(deck)}”? You can undo for a few seconds.`)) removeWithUndo(deck);
}

export function DeckMenu({ deck, onDelete, className, triggerClassName }) {
  const id = deckId(deck);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label={`Actions for ${deckTitle(deck)}`}
          className={cn(
            "grid size-8 place-items-center rounded-lg bg-white/90 text-[#402B25] shadow-sm backdrop-blur transition hover:bg-white",
            triggerClassName
          )}
        >
          <MoreHorizontal className="size-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className={cn("w-48", className)}>
        <DropdownMenuItem asChild>
          <Link to={`/app/preview/${id}`}><Eye /> Open</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to={`/app/present/${id}`}><Play /> Present</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => downloadDeck(deck, "pptx")}>
          <FileDown /> Download PPTX
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => downloadDeck(deck, "html")}>
          <Download /> Download HTML
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive focus:text-destructive" onSelect={() => onDelete?.(deck)}>
          <Trash2 /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** A deck tile: real thumbnail, hover lift, ⋯ menu, centre Present button. */
export default function PresentationCard({ deck, index = 0, onDelete, className }) {
  const id = deckId(deck);
  const slides = deckSlides(deck);
  const when = relativeTime(deckUpdated(deck));
  const st = statusDot(deck.status);

  return (
    <article
      className={cn("lv-surface lv-lift lv-in group relative overflow-hidden", className)}
      style={{ animationDelay: `${Math.min(index, 12) * 40}ms` }}
    >
      <div className="relative">
        <Link to={`/app/preview/${id}`} aria-label={`Open ${deckTitle(deck)}`} className="block">
          <DeckThumb id={id} title={deckTitle(deck)} className="border-b" />
        </Link>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#402B25]/0 opacity-0 transition-all duration-180 group-hover:bg-[#402B25]/25 group-hover:opacity-100 group-focus-within:opacity-100">
          <Link
            to={`/app/present/${id}`}
            className="pointer-events-auto inline-flex h-9 translate-y-1 items-center gap-1.5 rounded-full bg-white px-4 text-[13px] font-semibold text-[#402B25] shadow-lg transition-transform duration-180 hover:scale-105 group-hover:translate-y-0"
          >
            Present <Play className="size-3.5 fill-current" />
          </Link>
        </div>
        <span className="pointer-events-none absolute bottom-2 left-2 rounded-full bg-[#402B25]/80 px-2 py-0.5 text-[11px] font-semibold text-white backdrop-blur">
          {slides} slide{slides === 1 ? "" : "s"}
        </span>
        <div className="absolute right-2 top-2 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 data-[state=open]:opacity-100">
          <DeckMenu deck={deck} onDelete={onDelete} />
        </div>
      </div>
      <div className="px-3.5 pb-3 pt-2.5">
        <div className="flex items-center gap-2">
          <p
            className="t-card min-w-0 flex-1 truncate text-[#402B25]"
            title={deckTitle(deck)}
          >
            {deckTitle(deck)}
          </p>
          <span title={st.label} className="size-2 shrink-0 rounded-full" style={{ background: st.color }} />
        </div>
        <p className="t-meta mt-0.5 truncate">
          {when ? `Edited ${when} · ` : ""}
          {slides} slide{slides === 1 ? "" : "s"}
        </p>
      </div>
    </article>
  );
}
