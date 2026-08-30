import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, LayoutGrid, Loader2, Search, Sparkles, Wand2 } from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { PageContainer, PageHeader } from "@/components/app/Page";
import { EmptyState, ErrorNote } from "@/components/app/states";
import { cn } from "@/lib/utils";

const PAGE = 60;

function scaffold(title, subject) {
  return `## ${title}\n\nTeach ${title} to a student new to ${subject}. Cover the definition, the key ideas, how it works step by step, a worked example, and the common misconceptions.`;
}

export default function Gallery() {
  const navigate = useNavigate();
  const [subject, setSubject] = useState(null);
  const [q, setQ] = useState("");
  const [readyOnly, setReadyOnly] = useState(false);

  const [data, setData] = useState(null); // {entries, total, ready_total, subjects}
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);

  const [preview, setPreview] = useState(null); // {slug,title,...}
  const [previewDeck, setPreviewDeck] = useState(null);
  const [using, setUsing] = useState("");

  const debounce = useRef();

  const load = useCallback(
    async (opts = {}) => {
      const nextOffset = opts.append ? offset + PAGE : 0;
      if (opts.append) setLoadingMore(true);
      else setData((d) => (d ? { ...d, entries: null } : null));
      try {
        const res = await api.galleryList({
          subject,
          q: q.trim() || undefined,
          ready: readyOnly || undefined,
          limit: PAGE,
          offset: nextOffset,
        });
        setError("");
        setOffset(nextOffset);
        setData((prev) =>
          opts.append && prev
            ? { ...res, entries: [...prev.entries, ...res.entries] }
            : res
        );
      } catch (e) {
        setError(e.message);
      } finally {
        setLoadingMore(false);
      }
    },
    [subject, q, readyOnly, offset]
  );

  // initial + filter changes (debounced on search text)
  useEffect(() => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => load(), q ? 250 : 0);
    return () => clearTimeout(debounce.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subject, q, readyOnly]);

  useEffect(() => {
    if (!preview?.has_deck) {
      setPreviewDeck(null);
      return;
    }
    let live = true;
    setPreviewDeck(null);
    api
      .galleryDeck(preview.slug)
      .then((d) => live && setPreviewDeck(d))
      .catch(() => live && setPreviewDeck({ slides: [] }));
    return () => {
      live = false;
    };
  }, [preview]);

  const subjectsByCategory = useMemo(() => {
    const out = {};
    for (const s of data?.subjects || []) {
      (out[s.category] ||= []).push(s);
    }
    return out;
  }, [data]);

  async function useDeck(entry) {
    setUsing(entry.slug);
    try {
      const { deck_id } = await api.galleryUse(entry.slug);
      navigate(`/app/preview/${deck_id}`);
    } catch (e) {
      setError(e.message);
      setUsing("");
    }
  }

  function openTopic(entry) {
    if (entry.has_deck) {
      setPreview(entry);
    } else {
      navigate("/app/create", {
        state: { template: { topic: entry.title, text: scaffold(entry.title, entry.subject) } },
      });
    }
  }

  const entries = data?.entries;
  const shown = entries?.length ?? 0;
  const canLoadMore = data && shown < data.total;

  return (
    <AppLayout title="Gallery">
      <PageContainer>
        <PageHeader
          title="Gallery"
          subtitle={
            data
              ? `${data.total.toLocaleString()} topics across ${data.subjects.length} subjects — ${data.ready_total} ready to open now.`
              : "Ready-made presentations you can open or adapt in one click."
          }
          actions={
            <Button
              variant={readyOnly ? "default" : "outline"}
              size="sm"
              onClick={() => setReadyOnly((v) => !v)}
            >
              <Sparkles /> {readyOnly ? "Showing ready decks" : "Ready decks only"}
            </Button>
          }
        />

        <ErrorNote error={error} />

        <div className="flex flex-col gap-4 lg:flex-row">
          {/* subject rail */}
          <aside className="lg:w-52 lg:shrink-0">
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search topics…"
                className="pl-8"
              />
            </div>
            <div className="flex gap-1.5 overflow-x-auto pb-2 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:pb-0">
              <button
                onClick={() => setSubject(null)}
                className={cn(
                  "shrink-0 rounded-md px-2.5 py-1.5 text-left text-sm transition-colors",
                  !subject ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-muted/60"
                )}
              >
                All subjects
              </button>
              {Object.entries(subjectsByCategory).map(([cat, subs]) => (
                <div key={cat} className="lg:mt-2">
                  <p className="hidden px-2.5 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/60 lg:block">
                    {cat}
                  </p>
                  {subs.map((s) => (
                    <button
                      key={s.subject}
                      onClick={() => setSubject(s.subject)}
                      className={cn(
                        "flex shrink-0 items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-sm transition-colors lg:w-full",
                        subject === s.subject
                          ? "bg-primary/10 font-medium text-primary"
                          : "text-muted-foreground hover:bg-muted/60"
                      )}
                    >
                      <span className="truncate">{s.subject}</span>
                      <span className="text-xs tabular-nums opacity-60">{s.count}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </aside>

          {/* grid */}
          <div className="min-w-0 flex-1">
            {entries === null || entries === undefined ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 9 }).map((_, i) => (
                  <div key={i} className="h-32 animate-pulse rounded-xl bg-muted/50" />
                ))}
              </div>
            ) : entries.length === 0 ? (
              <EmptyState
                icon={LayoutGrid}
                title="No topics match"
                description="Try a different subject or clear the search."
              />
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {entries.map((e) => (
                    <Card
                      key={e.slug}
                      className="lv-card group flex flex-col"
                    >
                      <CardContent className="flex flex-1 flex-col gap-2 p-4">
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {e.subject}
                          </span>
                          {e.has_deck ? (
                            <span className="inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                              <Sparkles className="size-3" /> Ready
                            </span>
                          ) : null}
                        </div>
                        <p className="font-medium leading-snug">{e.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {e.has_deck
                            ? `${e.slide_count} slides · ${e.quiz_count} quizzes · score ${e.overall_score}`
                            : `${e.level} · ~${e.minutes} min`}
                        </p>
                        <div className="mt-auto flex gap-2 pt-1">
                          {e.has_deck ? (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                className="flex-1"
                                onClick={() => setPreview(e)}
                              >
                                Preview
                              </Button>
                              <Button
                                size="sm"
                                className="flex-1"
                                disabled={using === e.slug}
                                onClick={() => useDeck(e)}
                              >
                                {using === e.slug ? <Loader2 className="size-4 animate-spin" /> : "Use"}
                              </Button>
                            </>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              className="flex-1"
                              onClick={() => openTopic(e)}
                            >
                              <Wand2 /> Generate
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {canLoadMore ? (
                  <div className="mt-5 flex justify-center">
                    <Button variant="outline" onClick={() => load({ append: true })} disabled={loadingMore}>
                      {loadingMore ? <Loader2 className="size-4 animate-spin" /> : null}
                      Load more ({(data.total - shown).toLocaleString()} left)
                    </Button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      </PageContainer>

      <Sheet open={!!preview} onOpenChange={(v) => !v && setPreview(null)}>
        <SheetContent className="flex w-full flex-col gap-0 sm:max-w-md">
          <SheetHeader>
            <SheetTitle>{preview?.title}</SheetTitle>
            <SheetDescription>
              {preview?.subject} · {preview?.slide_count} slides · {preview?.quiz_count} quizzes
            </SheetDescription>
          </SheetHeader>

          <div className="flex-1 overflow-y-auto py-4">
            {previewDeck === null ? (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-9 animate-pulse rounded bg-muted/50" />
                ))}
              </div>
            ) : (
              <ol className="space-y-1.5">
                {(previewDeck.slides || []).map((s, i) => (
                  <li key={i} className="flex gap-3 rounded-lg border bg-muted/20 px-3 py-2 text-sm">
                    <span className="tabular-nums text-muted-foreground">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="block truncate font-medium">
                        {s.title || s.question || `Slide ${i + 1}`}
                      </span>
                      {Array.isArray(s.bullets) && s.bullets.length ? (
                        <span className="block text-xs text-muted-foreground">
                          {s.bullets.length} point{s.bullets.length === 1 ? "" : "s"}
                        </span>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="border-t pt-4">
            <Button
              className="w-full"
              disabled={using === preview?.slug}
              onClick={() => preview && useDeck(preview)}
            >
              {using === preview?.slug ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <>
                  Use this deck <ArrowRight />
                </>
              )}
            </Button>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Adds an editable copy to your projects.
            </p>
          </div>
        </SheetContent>
      </Sheet>
    </AppLayout>
  );
}
