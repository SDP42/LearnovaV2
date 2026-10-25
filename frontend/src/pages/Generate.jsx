import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import * as api from "@/api";
import AppLayout from "@/components/app/AppLayout";
import GenerationPipeline from "@/components/app/GenerationPipeline";
import { toast } from "sonner";

const POLL_MS = 800;
const MAX_MS = 25 * 60 * 1000; // matches the backend generation watchdog

/** Default generation options, same shape Create.jsx sends. */
export function defaultGenerateOptions(extra = {}) {
  return {
    theme_id: "auto",
    quiz_frequency: Number(localStorage.getItem("learnova-default-quizfreq") || 4),
    quiz_style: "inline",
    quiz_positions: null,
    enable_vision_ocr: true,
    enable_quizzes: true,
    enable_enhancement: true,
    build_pptx: true,
    build_html: true,
    text_density: localStorage.getItem("learnova-default-density") || "medium",
    ...extra,
  };
}

/**
 * /app/generate/:jobId — polls the job (and, for uploads, kicks off generation
 * as soon as conversion finishes), then shows the assembling-deck screen.
 */
export default function Generate() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const opts = location.state?.options;
  const title = location.state?.title;
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const started = useRef(false);

  const begin = useCallback(
    async (id) => {
      if (started.current) return;
      started.current = true;
      try {
        const md = await api.getMarkdown(id);
        await api.startGenerate(id, defaultGenerateOptions({ ...opts, markdown: md.markdown ?? "" }));
      } catch (e) {
        started.current = false;
        setError(e.message);
        setJob((j) => ({ ...(j || {}), status: "failed" }));
      }
    },
    [opts]
  );

  useEffect(() => {
    let live = true;
    const t0 = Date.now();
    let misses = 0;
    setError("");
    const tick = async () => {
      if (Date.now() - t0 > MAX_MS) {
        setError("This is taking longer than expected. Check My Decks in a minute.");
        setJob((j) => ({ ...(j || {}), status: "failed" }));
        return true;
      }
      try {
        const next = await api.getJob(jobId);
        if (!live) return true;
        misses = 0;
        if (next.status === "awaiting_review") {
          await begin(jobId);
          setJob({ ...next, status: "running", stage: next.stage || "convert" });
          return false;
        }
        setJob(next);
        if (next.status === "failed") {
          setError(next.error || "");
          return true;
        }
        if (next.status === "done") {
          toast.success("Your deck is ready");
          return true;
        }
      } catch (e) {
        if (++misses >= 5) {
          setError(e.message);
          setJob((j) => ({ ...(j || {}), status: "failed" }));
          return true;
        }
      }
      return false;
    };
    let timer;
    const loop = async () => {
      if (!live) return;
      const stop = await tick();
      if (!stop && live) timer = setTimeout(loop, POLL_MS);
    };
    loop();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [jobId, begin, attempt]);

  const retry = async () => {
    started.current = false;
    setJob(null);
    try {
      const md = await api.getMarkdown(jobId);
      await api.startGenerate(jobId, defaultGenerateOptions({ ...opts, markdown: md.markdown ?? "" }));
      started.current = true;
    } catch {
      /* the poll below reports the failure */
    }
    setAttempt((a) => a + 1);
  };

  const status = job?.status === "done" ? "done" : job?.status === "failed" ? "failed" : "running";
  return (
    <AppLayout title="Creating deck">
      <div className="mx-auto max-w-5xl">
        <GenerationPipeline
          stage={job?.stage}
          progress={job?.progress}
          status={status}
          title={title || job?.title || job?.source_name}
          error={error}
          onRetry={retry}
          onOpen={() => navigate(`/app/preview/${jobId}`)}
          onPresent={() => navigate(`/app/present/${jobId}`)}
        />
      </div>
    </AppLayout>
  );
}
