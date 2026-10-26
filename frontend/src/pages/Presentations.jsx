import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import AppLayout from "@/components/app/AppLayout";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import { deckSlides, deckUpdated, relativeTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { PageContainer, PageHeader } from "@/components/app/Page";
import PresentationCard, { DeckMenu, confirmDelete, statusDot } from "@/components/app/PresentationCard";
import DeckThumb from "@/components/app/DeckThumb";
import LibraryToolbar from "@/components/app/LibraryToolbar";
import { EmptyState, ErrorNote, LoadingGrid, NoResults } from "@/components/app/states";
import { DecksIllustration } from "@/components/app/Illustrations";

const CHIPS = [
  { id: "all", label: "All" },
  { id: "ready", label: "Ready" },
  { id: "progress", label: "In progress" },
  { id: "week", label: "This week" },
];
const SORTS = [
  { id: "recent", label: "Recently edited" },
  { id: "title", label: "Title A–Z" },
  { id: "slides", label: "Most slides" },
];
const ts = (d) => {
  const v = deckUpdated(d);
  return typeof v === "number" ? (v < 1e12 ? v * 1000 : v) : Date.parse(v) || 0;
};

export default function Presentations() {
  const { decks, error, removeWithUndo } = useDecks();
  const [q, setQ] = useState("");
  const [chip, setChip] = useState("all");
  const [sort, setSort] = useState("recent");
  const [view, setView] = useState(() => {
    try {
      return localStorage.getItem("lv-decks-view") || "grid";
    } catch {
      return "grid";
    }
  });
  const setViewP = (v) => {
    setView(v);
    try {
      localStorage.setItem("lv-decks-view", v);
    } catch {
      /* ignore */
    }
  };

  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    const weekAgo = Date.now() - 7 * 864e5;
    let rows = (decks ?? []).filter((d) => {
      if (t && !deckTitle(d).toLowerCase().includes(t)) return false;
      const kind = statusDot(d.status).label;
      if (chip === "ready") return kind === "Ready";
      if (chip === "progress") return kind === "In progress";
      if (chip === "week") return ts(d) >= weekAgo;
      return true;
    });
    rows = [...rows].sort((a, b) =>
      sort === "title" ? deckTitle(a).localeCompare(deckTitle(b)) : sort === "slides" ? deckSlides(b) - deckSlides(a) : ts(b) - ts(a)
    );
    return rows;
  }, [decks, q, chip, sort]);

  const onDelete = (d) => confirmDelete(d, removeWithUndo);
  const clear = () => {
    setQ("");
    setChip("all");
  };

  return (
    <AppLayout title="My Decks">
      <PageContainer>
        <PageHeader
          title="My Decks"
          subtitle={decks ? `${decks.length} deck${decks.length === 1 ? "" : "s"} in your library.` : "Everything you’ve made, in one place."}
          actions={
            <Button asChild className="bg-[#402B25] text-white hover:bg-[#2E1E19]">
              <Link to="/app" state={{ focus: Date.now() }}>
                <Plus /> New deck
              </Link>
            </Button>
          }
        />

        <ErrorNote error={error} />

        {decks !== null && decks.length > 0 ? (
          <LibraryToolbar
            query={q}
            onQuery={setQ}
            placeholder="Search your decks…"
            chips={CHIPS}
            chip={chip}
            onChip={setChip}
            sorts={SORTS}
            sort={sort}
            onSort={setSort}
            view={view}
            onView={setViewP}
          />
        ) : null}

        {decks === null ? (
          <LoadingGrid count={8} />
        ) : decks.length === 0 ? (
          <EmptyState
            illustration={<DecksIllustration />}
            title="No decks yet"
            description="Every deck you generate lands here, with a live thumbnail, one-click present and export."
            action={{ to: "/app", label: "Create your first deck" }}
          />
        ) : shown.length === 0 ? (
          <NoResults query={q} onClear={clear} />
        ) : view === "grid" ? (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
            {shown.map((d, i) => (
              <PresentationCard key={deckId(d)} deck={d} index={i} onDelete={onDelete} />
            ))}
          </div>
        ) : (
          <div className="lv-surface overflow-hidden">
            <table className="w-full text-[14px]">
              <thead>
                <tr className="border-b bg-[#F8FBFF] text-left text-[12px] text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Deck</th>
                  <th className="hidden px-3 py-2 font-medium sm:table-cell">Slides</th>
                  <th className="hidden px-3 py-2 font-medium md:table-cell">Edited</th>
                  <th className="hidden px-3 py-2 font-medium md:table-cell">Status</th>
                  <th className="w-12 px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {shown.map((d) => {
                  const id = deckId(d);
                  const st = statusDot(d.status);
                  return (
                    <tr key={id} className="border-b transition-colors last:border-0 hover:bg-[#FFFAF5]">
                      <td className="px-4 py-2.5">
                        <Link to={`/app/preview/${id}`} className="flex items-center gap-3">
                          <span className="w-24 shrink-0 overflow-hidden rounded-md border">
                            <DeckThumb id={id} title={deckTitle(d)} />
                          </span>
                          <span className="t-card min-w-0 truncate">{deckTitle(d)}</span>
                        </Link>
                      </td>
                      <td className="hidden px-3 tabular-nums text-muted-foreground sm:table-cell">{deckSlides(d)}</td>
                      <td className="hidden px-3 text-muted-foreground md:table-cell">{relativeTime(deckUpdated(d)) || "–"}</td>
                      <td className="hidden px-3 md:table-cell">
                        <span className="inline-flex items-center gap-1.5 text-[13px]">
                          <span className="size-2 rounded-full" style={{ background: st.color }} /> {st.label}
                        </span>
                      </td>
                      <td className="px-3 text-right">
                        <DeckMenu deck={d} onDelete={onDelete} triggerClassName="border bg-white" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </PageContainer>
    </AppLayout>
  );
}
