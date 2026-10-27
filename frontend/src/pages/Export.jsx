import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CheckCircle2,
  Download,
  ArrowLeft,
  Eye,
  FileDown,
  Globe,
  MonitorPlay,
  PartyPopper,
  Pencil,
  Presentation,
  Share2,
  Sparkles,
} from "lucide-react";
import * as api from "@/api";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CountUp, Stagger, StaggerItem } from "@/components/app/motion";
import SharePanel from "@/components/app/SharePanel";

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
    const t = toast.loading(`Preparing ${artifact === "pptx" ? "PowerPoint" : "web deck"}…`);
    try {
      try {
        await api.downloadArtifact(api.jobDownloadPath(jobId, artifact), name);
      } catch {
        await api.downloadArtifact(api.deckDownloadPath(jobId, artifact), name);
      }
      toast.success("Download started", { id: t });
    } catch (e) {
      setError(e.message);
      toast.error(e.message || "Download failed", { id: t });
    }
  }

  return (
    <div data-learnova-app className="min-h-svh bg-[#FFFAF5] text-[#402B25]">
      <header className="flex h-14 items-center gap-3 border-b bg-white px-4 sm:px-6">
        <Button asChild variant="ghost" size="icon" className="rounded-full">
          <Link to={`/app/preview/${jobId}`} aria-label="Back to the deck"><ArrowLeft /></Link>
        </Button>
        <Link to="/app" className="flex items-center gap-2 rounded-lg" aria-label="Learnova home">
          <span className="grid size-7 place-items-center rounded-lg bg-[#F47B45] text-[#2A1A14]"><Sparkles className="size-4" /></span>
          <span className="font-[Bricolage_Grotesque] text-[17px] font-bold tracking-tight">Learnova</span>
        </Link>
      </header>

      <Stagger className="mx-auto flex max-w-md flex-col items-center gap-6 px-4 pb-16 pt-8 text-center sm:pt-12">
        <StaggerItem className="flex flex-col items-center gap-4">
          <div className="flex size-16 items-center justify-center rounded-3xl bg-[#FCE5D6] text-[#8F3A18]">
            <PartyPopper className="size-8" />
          </div>
          <div>
            <h1 className="t-h1">Your presentation is ready</h1>
            <p className="t-body mt-1 text-muted-foreground">
              {s?.source_name ? `“${s.source_name}”` : "Saved to your library."}
            </p>
          </div>
        </StaggerItem>

        {error ? (
          <Alert variant="destructive" className="rounded-xl bg-[#FBE9E7] text-left">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <StaggerItem className="w-full">
          <div className="lv-surface lv-r-hero grid grid-cols-3 divide-x divide-[#E8D8C9]">
            {deck === null
              ? Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="p-4">
                    <div className="lv-skel mx-auto h-8 w-10" />
                  </div>
                ))
              : [
                  ["Slides", s?.slide_count ?? 0],
                  ["Visuals", visuals],
                  ["Quizzes", s?.quiz_count ?? 0],
                ].map(([label, value]) => (
                  <div key={label} className="p-4">
                    <p className="font-[Bricolage_Grotesque] text-[28px] font-bold leading-8 tabular-nums">
                      <CountUp value={value} />
                    </p>
                    <p className="text-xs text-[#715A4E]">{label}</p>
                  </div>
                ))}
          </div>
        </StaggerItem>

        <StaggerItem className="flex w-full flex-col gap-2.5">
          <Button size="lg" className="h-12 w-full bg-[#F47B45] text-[15px] font-bold text-[#2A1A14] hover:bg-[#FF8A58]" onClick={() => download("pptx")}>
            <FileDown /> Download PowerPoint
          </Button>
          <Button size="lg" variant="outline" className="h-12 w-full text-[15px]" onClick={() => download("html")}>
            <Download /> Download web deck
          </Button>
          <Button asChild size="lg" variant="outline" className="h-12 w-full text-[15px]">
            <Link to={`/app/preview/${jobId}`}>
              <Eye /> Open presentation
            </Link>
          </Button>
        </StaggerItem>

        <StaggerItem className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              try {
                navigator.clipboard?.writeText(`${window.location.origin}/app/preview/${jobId}`);
              } catch {
                /* clipboard blocked */
              }
              setCopied(true);
              toast.success("Link copied");
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? <CheckCircle2 /> : <Share2 />} {copied ? "Link copied" : "Share"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => navigate("/app")}>
            <Pencil /> Make another
          </Button>
        </StaggerItem>

        <StaggerItem className="w-full text-left">
          <h2 className="t-h2 mb-3">What’s in each format</h2>
          <div className="flex flex-col gap-3">
            {[
              [FileDown, "PowerPoint (.pptx)", "Editable slides built with native shapes and text — open in PowerPoint, Keynote or Google Slides. Entrance animations mirror the reveal steps when PPTX animation is enabled."],
              [Globe, "Web deck (.html)", "One standalone file — Reveal.js, images and checkpoint quizzes all inlined. Double-click to open in any browser; no server, no install."],
              [MonitorPlay, "Presenter console", "Not a download — a live dual-screen view with speaker notes, a timer, a next-slide preview and a synced audience window."],
            ].map(([Icon, h, b]) => (
              <div key={h} className="lv-surface lv-lift flex items-start gap-3 p-4">
                <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl bg-[#FCE5D6] text-[#8F3A18]">
                  <Icon className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold">{h}</p>
                  <p className="mt-1 text-xs leading-5 text-[#4F3A31]">{b}</p>
                </div>
              </div>
            ))}
          </div>
        </StaggerItem>

        <StaggerItem className="w-full text-left">
          <h2 className="t-h2 mb-3">Share and study</h2>
          <SharePanel deckId={jobId} name={(s?.source_name || "deck").replace(/[^A-Za-z0-9_-]+/g, "_").slice(0, 40)} />
        </StaggerItem>

        <StaggerItem className="w-full text-left">
          <h2 className="t-h2 mb-3">Next steps</h2>
          <ul className="flex flex-col gap-3 text-sm text-[#4F3A31]">
            <li className="flex items-start gap-2.5">
              <Presentation className="mt-0.5 size-4 shrink-0 text-[#B44A22]" />
              Rehearse with the presenter console before you’re in the room.
            </li>
            <li className="flex items-start gap-2.5">
              <Eye className="mt-0.5 size-4 shrink-0 text-[#B44A22]" />
              <span>
                Review the engagement score in{" "}
                <Link to="/app/analytics" className="font-semibold text-[#8F3A18] underline">Insights</Link> — split any slide below 70.
              </span>
            </li>
            <li className="flex items-start gap-2.5">
              <Pencil className="mt-0.5 size-4 shrink-0 text-[#B44A22]" />
              Tweak the source and regenerate; both exports stay in step.
            </li>
          </ul>
        </StaggerItem>
      </Stagger>
    </div>
  );
}
