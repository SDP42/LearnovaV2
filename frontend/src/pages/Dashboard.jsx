import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useUser } from "@/auth";
import {
  FileStack,
  Images,
  ListChecks,
  Presentation,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import StatCard from "@/components/app/StatCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function statusVariant(status) {
  if (/ready|done|complete/i.test(status)) return "success";
  if (/draft|await/i.test(status)) return "warning";
  return "secondary";
}

export default function Dashboard() {
  const { user } = useUser();
  const [decks, setDecks] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listMyDecks()
      .then((rows) => setDecks(Array.isArray(rows) ? rows : rows?.decks ?? []))
      .catch((e) => {
        setError(e.message);
        setDecks([]);
      });
  }, []);

  const slideCount = (decks ?? []).reduce((n, d) => n + (d.slide_count ?? d.slides ?? 0), 0);
  const quizCount = (decks ?? []).reduce((n, d) => n + (d.quiz_count ?? d.quizzes ?? 0), 0);
  const avgScore =
    decks && decks.length
      ? Math.round(
          decks.reduce((n, d) => n + (d.overall_score ?? d.engagement ?? 0), 0) / decks.length
        )
      : 0;

  return (
    <AppLayout title="Dashboard">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">
              Welcome back{user?.firstName ? `, ${user.firstName}` : ""} 👋
            </h2>
            <p className="text-sm text-muted-foreground">
              Turn a syllabus or document into an engaging, structured deck.
            </p>
          </div>
          <Button asChild>
            <Link to="/app/create">
              <Sparkles /> New presentation
            </Link>
          </Button>
        </div>

        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {decks === null ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)
          ) : (
            <>
              <StatCard label="Projects" value={decks.length} icon={FileStack} hint="all time" />
              <StatCard label="Slides generated" value={slideCount} icon={Presentation} />
              <StatCard label="Quiz questions" value={quizCount} icon={ListChecks} />
              <StatCard
                label="Avg engagement"
                value={`${avgScore}`}
                icon={TrendingUp}
                hint="/ 100 (PSF)"
              />
            </>
          )}
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Recent projects</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link to="/app/projects">View all</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {decks === null ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : decks.length === 0 ? (
              <div className="flex flex-col items-center gap-3 p-10 text-center">
                <Images className="size-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  No projects yet. Create your first learning experience.
                </p>
                <Button asChild size="sm">
                  <Link to="/app/create">
                    <Sparkles /> Create presentation
                  </Link>
                </Button>
              </div>
            ) : (
              <ul className="divide-y">
                {decks.slice(0, 8).map((d) => (
                  <li
                    key={d.id ?? d.deck_id}
                    className="flex items-center justify-between gap-3 px-4 py-3 text-sm"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {d.title ?? d.source_name ?? "Untitled deck"}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {d.slide_count ?? d.slides ?? 0} slides
                        {d.updated_at ? ` · ${new Date(d.updated_at).toLocaleDateString()}` : ""}
                      </p>
                    </div>
                    <Badge variant={statusVariant(d.status ?? "ready")}>
                      {d.status ?? "Ready"}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
