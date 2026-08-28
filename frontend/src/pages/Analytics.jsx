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
import { Gauge, PieChart, Presentation, Target } from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import StatCard from "@/components/app/StatCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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

  return (
    <AppLayout title="Analytics">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Learning analytics</h2>
          <p className="text-sm text-muted-foreground">
            Engagement (Pedagogical Slide Fitness) and deck composition across your projects.
          </p>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

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
      </div>
    </AppLayout>
  );
}
