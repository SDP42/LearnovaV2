import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useUser } from "@/auth";
import { toast } from "sonner";
import { fetchSampleFile } from "@/api";
import AppLayout from "@/components/app/AppLayout";
import Composer, { SAMPLE_SYLLABUS, TEMPLATE_CHIPS } from "@/components/app/Composer";
import DashEmpty from "@/components/app/DashEmpty";
import DeckThumb from "@/components/app/DeckThumb";
import PresentationCard, { confirmDelete } from "@/components/app/PresentationCard";
import { ErrorNote, LoadingGrid } from "@/components/app/states";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import { deckSlides, deckUpdated, greeting, relativeTime } from "@/lib/format";
import { ArrowRight, Gauge, Layers, Presentation } from "lucide-react";
import { CountUp, Stagger, StaggerItem } from "@/components/app/motion";

export default function Dashboard() {
  const { user } = useUser();
  const location = useLocation();
  const { decks, error, removeWithUndo } = useDecks();
  const taRef = useRef(null);
  const tpl = location.state?.template;
  const sample = location.state?.sample;
  const [text, setText] = useState(tpl?.text ?? "");
  const [sampleFile, setSampleFile] = useState(null);

  // Templates → Sample decks: load the real lecture file and attach it to the composer
  useEffect(() => {
    if (!sample?.url) return;
    let alive = true;
    fetchSampleFile(sample)
      .then((f) => alive && setSampleFile(f))
      .catch(() => toast.error("Could not load the sample file"));
    return () => { alive = false; };
  }, [sample?.url]);

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
            <br className="sm:hidden" /> <span className="text-[#B44A22]">What are we teaching today?</span>
          </h1>
          <Composer value={text} onChange={setText} textareaRef={taRef} initialFile={sampleFile} />
          <div className="flex flex-wrap items-center gap-2">
            <span className="t-meta mr-1">Start from</span>
            {TEMPLATE_CHIPS.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setText(c.text);
                  taRef.current?.focus();
                }}
                className="lv-chip min-h-10 px-4 font-medium hover:text-[#8F3A18] sm:min-h-9"
              >
                {c.label}
              </button>
            ))}
          </div>
        </section>

        <Stagger className="grid grid-cols-3 gap-2.5 sm:gap-4" aria-label="Your numbers">
          {[
            [Layers, decks === null ? "–" : stats.week, "slides this week"],
            [Presentation, decks === null ? "–" : list.length, list.length === 1 ? "deck" : "decks"],
            [Gauge, stats.avg != null ? stats.avg : "–", "avg engagement"],
          ].map(([Icon, n, l]) => (
            <StaggerItem key={l}>
              <div className="lv-surface lv-lift flex h-full flex-col gap-1.5 p-3 sm:flex-row sm:items-center sm:gap-3 sm:p-4">
                <span className="hidden size-10 shrink-0 place-items-center rounded-xl bg-[#FCE5D6] text-[#8F3A18] sm:grid">
                  <Icon className="size-5" />
                </span>
                <span className="min-w-0">
                  <CountUp value={n} className="block font-[Bricolage_Grotesque] text-[26px] font-bold leading-8 tabular-nums text-[#402B25]" />
                  <span className="block truncate text-[12.5px] text-[#715A4E]">{l}</span>
                </span>
              </div>
            </StaggerItem>
          ))}
        </Stagger>

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
              <Stagger className="grid gap-3 sm:grid-cols-2">
                {list.slice(0, 2).map((d) => (
                  <StaggerItem key={deckId(d)}>
                    <Link
                      to={`/app/preview/${deckId(d)}`}
                      className="lv-surface lv-lift flex items-center gap-4 p-3"
                    >
                      <span className="w-28 shrink-0 overflow-hidden rounded-lg border sm:w-36">
                        <DeckThumb id={deckId(d)} title={deckTitle(d)} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="t-card block truncate">{deckTitle(d)}</span>
                        <span className="t-meta mt-0.5 block">
                          Edited {relativeTime(deckUpdated(d)) || "recently"} · {deckSlides(d)} slides
                        </span>
                        <span className="mt-2 inline-flex min-h-6 items-center gap-1 text-[13px] font-semibold text-[#B44A22]">
                          Resume <ArrowRight className="size-3.5" />
                        </span>
                      </span>
                    </Link>
                  </StaggerItem>
                ))}
              </Stagger>
            </section>

            <section className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h2 className="t-h2">Your decks</h2>
                <Link to="/app/presentations" className="inline-flex min-h-10 items-center text-[13px] font-semibold text-[#B44A22] hover:underline">
                  See all
                </Link>
              </div>
              <Stagger className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
                {list.slice(0, 8).map((d) => (
                  <StaggerItem key={deckId(d)}>
                    <PresentationCard deck={d} onDelete={(x) => confirmDelete(x, removeWithUndo)} />
                  </StaggerItem>
                ))}
              </Stagger>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  );
}
