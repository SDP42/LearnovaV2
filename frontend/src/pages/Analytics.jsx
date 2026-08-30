import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Gauge,
  Layers,
  PieChart,
  Presentation,
  Sparkles,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import StatCard from "@/components/app/StatCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer, PageHeader } from "@/components/app/Page";
import { EmptyState, ErrorNote } from "@/components/app/states";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

export default function Analytics() {
  const [decks, setDecks] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listMyDecks()
      .then((r) => setDecks(Array.isArray(r) ? r : r?.decks ?? []))
      .catch((e) => {
        setError(e.message);
        setDecks([]);
      });
  }, []);

  const engagementSeries = useMemo(
    () =>
      (decks ?? [])
        .slice()
        .reverse()
        .map((d, i) => ({
          name: (d.title ?? d.source_name ?? `Deck ${i + 1}`).slice(0, 14),
          score: d.overall_score ?? d.engagement ?? 0,
        })),
    [decks]
  );

  const sizeSeries = useMemo(
    () =>
      (decks ?? []).slice(0, 8).map((d, i) => ({
        name: (d.title ?? d.source_name ?? `Deck ${i + 1}`).slice(0, 12),
        slides: d.slide_count ?? d.slides ?? 0,
        quizzes: d.quiz_count ?? d.quizzes ?? 0,
      })),
    [decks]
  );

  const avg = engagementSeries.length
    ? Math.round(engagementSeries.reduce((n, x) => n + x.score, 0) / engagementSeries.length)
    : 0;
  const totalSlides = sizeSeries.reduce((n, x) => n + x.slides, 0);
  const totalQuizzes = sizeSeries.reduce((n, x) => n + x.quizzes, 0);

  const best = useMemo(
    () =>
      (decks ?? []).reduce(
        (top, d) =>
          (d.overall_score ?? 0) > (top?.overall_score ?? -1) ? d : top,
        null
      ),
    [decks]
  );
  const weakest = useMemo(
    () =>
      (decks ?? [])
        .filter((d) => (d.overall_score ?? 0) > 0)
        .reduce(
          (low, d) =>
            (d.overall_score ?? 100) < (low?.overall_score ?? 101) ? d : low,
          null
        ),
    [decks]
  );
  const trend = useMemo(() => {
    if (engagementSeries.length < 2) return 0;
    return engagementSeries.at(-1).score - engagementSeries[0].score;
  }, [engagementSeries]);

  const avgSlides = sizeSeries.length ? Math.round(totalSlides / sizeSeries.length) : 0;
  const quizCoverage =
    totalSlides > 0 ? Math.round((totalQuizzes / totalSlides) * 100) : 0;

  const insights = useMemo(() => {
    const out = [];
    if (!decks || decks.length === 0) return out;
    if (avg >= 80) out.push(["Strong average", "Your decks score in the 80s — source material is well structured. Keep headings and ordered lists in your inputs."]);
    else if (avg >= 65) out.push(["Room to tighten", `Average engagement is ${avg}. Slides scoring below 70 are usually still text-heavy — split them into one idea each.`]);
    else out.push(["Text-heavy decks", `Average engagement is ${avg}. Try the "low" density default and add more structure (## headings, numbered steps) to your source.`]);
    if (trend > 3) out.push(["Improving", `Engagement is up ${trend} points from your first deck to your latest.`]);
    else if (trend < -3) out.push(["Slipping", `Latest deck scored ${Math.abs(trend)} points below your first. Compare their structure.`]);
    if (quizCoverage < 15 && totalSlides > 6) out.push(["Few checkpoints", `Only ${quizCoverage}% quiz coverage. Lower "Quiz every N" in Settings to drive more active recall.`]);
    if (avgSlides > 24) out.push(["Long decks", `Averaging ${avgSlides} slides. Consider splitting a topic across two sessions — attention drops past ~20 slides.`]);
    return out;
  }, [decks, avg, trend, quizCoverage, totalSlides, avgSlides]);

  return (
    <AppLayout title="Analytics">
      <PageContainer>
        <PageHeader
          title="Learning analytics"
          subtitle="Engagement (Pedagogical Slide Fitness) and deck composition across your projects."
        />

        <ErrorNote error={error} />

        {decks && decks.length === 0 ? (
          <EmptyState
            icon={BarChart3}
            title="No analytics yet"
            description="Generate a deck — its engagement score, slide mix and quiz coverage will show up here."
            action={{ to: "/app/create", label: "Create a presentation" }}
          />
        ) : (
        <>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {decks === null ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)
          ) : (
            <>
              <StatCard label="Avg engagement" value={`${avg}`} icon={Gauge} hint="/ 100" />
              <StatCard label="Decks" value={decks.length} icon={Presentation} />
              <StatCard label="Slides" value={totalSlides} icon={Target} />
              <StatCard label="Quiz questions" value={totalQuizzes} icon={PieChart} />
            </>
          )}
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Engagement over time</CardTitle>
          </CardHeader>
          <CardContent>
            {decks === null ? (
              <Skeleton className="aspect-video w-full" />
            ) : engagementSeries.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">No decks yet.</p>
            ) : (
              <ChartContainer
                className="h-[260px] w-full"
                config={{ score: { label: "Engagement", color: "var(--chart-1)" } }}
              >
                <AreaChart data={engagementSeries} margin={{ left: -18, right: 8, top: 8 }}>
                  <defs>
                    <linearGradient id="fillScore" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-score)" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="var(--color-score)" stopOpacity={0.03} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} />
                  <YAxis domain={[0, 100]} tickLine={false} axisLine={false} width={36} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Area
                    dataKey="score"
                    type="monotone"
                    stroke="var(--color-score)"
                    strokeWidth={2}
                    fill="url(#fillScore)"
                  />
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Deck composition</CardTitle>
          </CardHeader>
          <CardContent>
            {decks === null ? (
              <Skeleton className="aspect-video w-full" />
            ) : sizeSeries.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">No decks yet.</p>
            ) : (
              <ChartContainer
                className="h-[260px] w-full"
                config={{
                  slides: { label: "Slides", color: "var(--chart-1)" },
                  quizzes: { label: "Quiz questions", color: "var(--chart-3)" },
                }}
              >
                <BarChart data={sizeSeries} margin={{ left: -18, right: 8, top: 8 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} />
                  <YAxis tickLine={false} axisLine={false} width={36} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="slides" fill="var(--color-slides)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="quizzes" fill="var(--color-quizzes)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        {decks && decks.length > 0 ? (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="lv-card">
                <CardHeader>
                  <CardTitle className="text-base">Highest scoring</CardTitle>
                </CardHeader>
                <CardContent>
                  {best ? (
                    <>
                      <p className="truncate font-medium">
                        {best.title ?? best.source_name ?? "Untitled"}
                      </p>
                      <p className="mt-1 flex items-center gap-1 text-sm text-emerald-600 dark:text-emerald-400">
                        <ArrowUpRight className="size-4" />
                        {best.overall_score ?? 0} / 100 PSF
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {best.slide_count ?? best.slides ?? 0} slides ·{" "}
                        {best.quiz_count ?? best.quizzes ?? 0} quiz questions
                      </p>
                      <Button asChild size="sm" variant="outline" className="mt-3">
                        <Link to={`/app/preview/${best.id ?? best.deck_id}`}>Open</Link>
                      </Button>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">Not scored yet.</p>
                  )}
                </CardContent>
              </Card>
              <Card className="lv-card">
                <CardHeader>
                  <CardTitle className="text-base">Needs the most work</CardTitle>
                </CardHeader>
                <CardContent>
                  {weakest ? (
                    <>
                      <p className="truncate font-medium">
                        {weakest.title ?? weakest.source_name ?? "Untitled"}
                      </p>
                      <p className="mt-1 flex items-center gap-1 text-sm text-rose-600 dark:text-rose-400">
                        <ArrowDownRight className="size-4" />
                        {weakest.overall_score ?? 0} / 100 PSF
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        Split its densest slides into one idea each and regenerate.
                      </p>
                      <Button asChild size="sm" variant="outline" className="mt-3">
                        <Link to={`/app/preview/${weakest.id ?? weakest.deck_id}`}>Open</Link>
                      </Button>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">Nothing flagged.</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {insights.length > 0 ? (
              <Card className="lv-card">
                <CardHeader className="flex flex-row items-center gap-2">
                  <Sparkles className="size-4 text-primary" />
                  <CardTitle className="text-base">Insights</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="flex flex-col gap-3 text-sm">
                    {insights.map(([h, b]) => (
                      <li key={h} className="flex gap-3">
                        <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                        <span>
                          <span className="font-medium text-foreground">{h}</span>{" "}
                          <span className="text-muted-foreground">— {b}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ) : null}
          </>
        ) : null}
        </>
        )}

        <Card className="lv-card">
          <CardHeader className="flex flex-row items-center gap-2">
            <Layers className="size-4 text-primary" />
            <CardTitle className="text-base">How to read the engagement score</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            {[
              ["Information efficiency", "Meaningful content per unit of slide space. Wordy paragraphs and redundant bullets pull this down."],
              ["Cognitive load", "How much the slide asks working memory to hold at once. More than ~4 parallel ideas is penalised."],
              ["Multimedia coherence", "Whether the visual and the text reinforce the same point. A decorative image that adds nothing lowers this."],
            ].map(([h, b]) => (
              <div key={h}>
                <p className="text-sm font-medium">{h}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{b}</p>
              </div>
            ))}
          </CardContent>
          <CardContent className="pt-0 text-xs text-muted-foreground">
            The three terms are combined multiplicatively — a slide that fails one
            dimension can't be rescued by the other two. The same model paginates
            your slides (CLASS), so the metric and the builder agree.
          </CardContent>
        </Card>
      </PageContainer>
    </AppLayout>
  );
}
