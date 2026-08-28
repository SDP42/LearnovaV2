import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CheckCircle2,
  Download,
  Eye,
  FileDown,
  PartyPopper,
  Pencil,
  Share2,
} from "lucide-react";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Export() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [deck, setDeck] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.getDeck(jobId).then(setDeck).catch((e) => setError(e.message));
  }, [jobId]);

  const s = deck?.summary;
  const visuals = (deck?.slides ?? []).filter(
    (x) => x.family && !["TEXT", "MEDIA"].includes(x.family)
  ).length;

  async function download(artifact) {
    const name = `Learnova_${s?.source_name || "deck"}.${artifact}`;
    try {
      await api.downloadArtifact(api.jobDownloadPath(jobId, artifact), name);
    } catch {
      try {
        await api.downloadArtifact(api.deckDownloadPath(jobId, artifact), name);
      } catch (e) {
        setError(e.message);
      }
    }
  }

  return (
    <AppLayout title="Export">
      <div className="mx-auto flex max-w-md flex-col items-center gap-6 pt-6 text-center">
        <div className="flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">
          <PartyPopper className="size-7" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Your presentation is ready</h2>
          <p className="text-sm text-muted-foreground">
            {s?.source_name ? `“${s.source_name}”` : "Saved to your library."}
          </p>
        </div>

        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <Card className="w-full">
          <CardContent className="grid grid-cols-3 divide-x p-0">
            {deck === null
              ? Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="p-4">
                    <Skeleton className="mx-auto h-8 w-10" />
                  </div>
                ))
              : [
                  ["Slides", s?.slide_count ?? 0],
                  ["Visuals", visuals],
                  ["Quizzes", s?.quiz_count ?? 0],
                ].map(([label, value]) => (
                  <div key={label} className="p-4">
                    <p className="text-2xl font-semibold tabular-nums">{value}</p>
                    <p className="text-xs text-muted-foreground">{label}</p>
                  </div>
                ))}
          </CardContent>
        </Card>

        <div className="flex w-full flex-col gap-2">
          <Button className="w-full" onClick={() => download("pptx")}>
            <FileDown /> Download PowerPoint
          </Button>
          <Button variant="outline" className="w-full" onClick={() => download("html")}>
            <Download /> Download web deck
          </Button>
          <Button asChild variant="outline" className="w-full">
            <Link to={`/app/preview/${jobId}`}>
              <Eye /> Open presentation
            </Link>
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              navigator.clipboard?.writeText(`${window.location.origin}/app/preview/${jobId}`);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? <CheckCircle2 /> : <Share2 />} {copied ? "Link copied" : "Share"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => navigate("/app/create")}>
            <Pencil /> Edit again
          </Button>
        </div>
      </div>
    </AppLayout>
  );
}
