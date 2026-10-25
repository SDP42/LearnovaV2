import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useUser } from "@/auth";
import AppLayout from "@/components/app/AppLayout";
import Composer, { SAMPLE_SYLLABUS, TEMPLATE_CHIPS } from "@/components/app/Composer";
import DashEmpty from "@/components/app/DashEmpty";
import DeckThumb from "@/components/app/DeckThumb";
import PresentationCard, { confirmDelete } from "@/components/app/PresentationCard";
import { ErrorNote, LoadingGrid } from "@/components/app/states";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import { deckSlides, deckUpdated, greeting, relativeTime } from "@/lib/format";
import { ArrowRight } from "lucide-react";

export default function Dashboard() {
  const { user } = useUser();
  const location = useLocation();
  const { decks, error, removeWithUndo } = useDecks();
  const taRef = useRef(null);
  const tpl = location.state?.template;
  const [text, setText] = useState(tpl?.text ?? "");

  // "New deck" button / N shortcut / template hand-off → focus the composer.
  useEffect(() => {
    if (tpl?.text) setText(tpl.text);
    const t = setTimeout(() => taRef.current?.focus(), 60);
    window.scrollTo({ top: 0, behavior: "smooth" });
    return () => clearTimeout(t);
  }, [location.state?.focus, tpl]);

  const list = decks ?? [];
  const stats = useMemo(() => {
    const weekAgo = Date.now() - 7 * 864e5;
    const ts = (d) => {
      const v = deckUpdated(d);
      return typeof v === "number" ? (v < 1e12 ? v * 1000 : v) : Date.parse(v);
    };
    const week = list.filter((d) => ts(d) >= weekAgo).reduce((n, d) => n + deckSlides(d), 0);
    const scored = list.map((d) => d.overall_score ?? d.engagement).filter((n) => typeof n === "number");
    const avg = scored.length ? Math.round(scored.reduce((a, b) => a + b, 0) / scored.length) : null;
    return { week, avg };
  }, [list]);

  const first = user?.firstName || "there";

  return (
    <AppLayout title="Home">
      <div className="mx-auto flex max-w-[960px] flex-col gap-8">
        <section className="flex flex-col gap-5 pt-2">
          <h1 className="t-h1">
            {greeting()}, {first}.
            <br className="sm:hidden" /> <span className="text-[#2563EB]">What are we teaching today?</span>
          </h1>
          <Composer value={text} onChange={setText} textareaRef={taRef} />
          <div className="flex flex-wrap items-center gap-2">
            <span className="t-meta mr-1">Start from</span>
            {TEMPLATE_CHIPS.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setText(c.text);
                  taRef.current?.focus();
                }}
                className="rounded-full border border-[#DEE7F5] bg-white px-3.5 py-1.5 text-[13px] font-medium text-[#2A3B5F] transition hover:-translate-y-px hover:border-[#9DBBF5] hover:text-[#1D4ED8]"
              >
                {c.label}
              </button>
            ))}
          </div>
        </section>

        <div className="lv-surface flex flex-wrap items-center gap-x-8 gap-y-2 px-4 py-2.5 text-[13px]">
          {[
            [decks === null ? "–" : stats.week, "slides this week"],
            [decks === null ? "–" : list.length, list.length === 1 ? "deck" : "decks"],
            [stats.avg != null ? `${stats.avg}` : "–", "avg engagement"],
          ].map(([n, l]) => (
            <span key={l} className="inline-flex items-baseline gap-1.5">
              <b className="font-[Bricolage_Grotesque] text-[17px] tabular-nums text-[#0B1F44]">{n}</b>
              <span className="text-muted-foreground">{l}</span>
            </span>
          ))}
        </div>

        <ErrorNote error={error} />

        {decks === null ? (
          <LoadingGrid count={4} />
        ) : list.length === 0 ? (
          <DashEmpty
            onSample={() => {
              setText(SAMPLE_SYLLABUS);
              taRef.current?.focus();
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          />
        ) : (
          <>
            <section className="flex flex-col gap-3">
              <h2 className="t-h2">Continue where you left off</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {list.slice(0, 2).map((d, i) => (
                  <Link
                    key={deckId(d)}
                    to={`/app/preview/${deckId(d)}`}
                    style={{ animationDelay: `${i * 40}ms` }}
                    className="lv-surface lv-lift lv-in flex items-center gap-4 p-3"
                  >
                    <span className="w-36 shrink-0 overflow-hidden rounded-lg border">
                      <DeckThumb id={deckId(d)} title={deckTitle(d)} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="t-card block truncate">{deckTitle(d)}</span>
                      <span className="t-meta mt-0.5 block">
                        Edited {relativeTime(deckUpdated(d)) || "recently"} · {deckSlides(d)} slides
                      </span>
                      <span className="mt-2 inline-flex items-center gap-1 text-[13px] font-semibold text-[#2563EB]">
                        Resume <ArrowRight className="size-3.5" />
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            </section>

            <section className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h2 className="t-h2">Your decks</h2>
                <Link to="/app/presentations" className="text-[13px] font-semibold text-[#2563EB] hover:underline">
                  See all
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
                {list.slice(0, 8).map((d, i) => (
                  <PresentationCard key={deckId(d)} deck={d} index={i} onDelete={(x) => confirmDelete(x, removeWithUndo)} />
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  );
}
