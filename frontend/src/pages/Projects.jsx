import { useState } from "react";
import { Link } from "react-router-dom";
import { Download, Eye, FileDown, Play, Sparkles, Trash2 } from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import { deckId, deckTitle, useDecks } from "@/lib/useDecks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer, PageHeader } from "@/components/app/Page";
import { EmptyState, ErrorNote } from "@/components/app/states";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal } from "lucide-react";

function statusVariant(s) {
  return /ready|done/i.test(s) ? "success" : /draft|await/i.test(s) ? "warning" : "secondary";
}

export default function Projects() {
  const { decks, error, remove } = useDecks();
  const [busy, setBusy] = useState("");

  async function download(id, artifact) {
    setBusy(id + artifact);
    try {
      await api.downloadArtifact(api.deckDownloadPath(id, artifact), `Learnova.${artifact}`);
    } catch (e) {
      /* surfaced by the row */
    } finally {
      setBusy("");
    }
  }

  return (
    <AppLayout title="Projects">
      <PageContainer>
        <PageHeader
          title="Projects"
          subtitle={`${decks ? `${decks.length} deck${decks.length === 1 ? "" : "s"}` : "…"} in your library.`}
          actions={
            <Button asChild>
              <Link to="/app/create">
                <Sparkles /> New
              </Link>
            </Button>
          }
        />

        <ErrorNote error={error} />

        {decks && decks.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Decks", decks.length],
              ["Slides", decks.reduce((n, d) => n + (d.slide_count ?? d.slides ?? 0), 0)],
              ["Quiz questions", decks.reduce((n, d) => n + (d.quiz_count ?? d.quizzes ?? 0), 0)],
              [
                "Avg score",
                Math.round(
                  decks.reduce((n, d) => n + (d.overall_score ?? d.engagement ?? 0), 0) /
                    decks.length
                ) || "—",
              ],
            ].map(([label, value]) => (
              <Card key={label} className="lv-wash">
                <CardContent className="p-4">
                  <p className="text-xl font-semibold tabular-nums">{value}</p>
                  <p className="text-xs text-muted-foreground">{label}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : null}

        <Card className="overflow-hidden">
          <CardContent className="p-0">
            {decks === null ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
              </div>
            ) : decks.length === 0 ? (
              <EmptyState
                className="border-0"
                icon={Sparkles}
                title="No projects yet"
                description="Every deck you generate is saved here — with its slide count, engagement score, and one-click open, present, and export."
                action={{ to: "/app/create", label: "Create your first" }}
              />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Title</th>
                    <th className="px-3 py-2 font-medium">Slides</th>
                    <th className="px-3 py-2 font-medium">Score</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {decks.map((d) => {
                    const id = deckId(d);
                    return (
                      <tr key={id} className="border-b last:border-0 hover:bg-muted/40">
                        <td className="max-w-[280px] truncate px-4 py-2.5 font-medium">
                          <Link to={`/app/preview/${id}`} className="hover:underline">
                            {deckTitle(d)}
                          </Link>
                        </td>
                        <td className="px-3 py-2.5 tabular-nums text-muted-foreground">
                          {d.slide_count ?? d.slides ?? 0}
                        </td>
                        <td className="px-3 py-2.5 tabular-nums text-muted-foreground">
                          {d.overall_score ?? d.engagement ?? "—"}
                        </td>
                        <td className="px-3 py-2.5">
                          <Badge variant={statusVariant(d.status ?? "ready")}>{d.status ?? "Ready"}</Badge>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="size-8">
                                <MoreHorizontal />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link to={`/app/preview/${id}`}><Eye /> Open</Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem asChild>
                                <Link to={`/app/present/${id}`}><Play /> Present</Link>
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem disabled={busy === id + "pptx"} onSelect={() => download(id, "pptx")}>
                                <FileDown /> PowerPoint
                              </DropdownMenuItem>
                              <DropdownMenuItem disabled={busy === id + "html"} onSelect={() => download(id, "html")}>
                                <Download /> Web deck
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-destructive"
                                onSelect={() => {
                                  if (confirm(`Delete "${deckTitle(d)}"?`)) remove(id);
                                }}
                              >
                                <Trash2 /> Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </AppLayout>
  );
}
