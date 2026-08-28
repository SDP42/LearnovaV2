import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import * as api from "@/api";

/**
 * The audience-facing deck. Loads the same Reveal.js presentation and follows
 * the presenter console over a BroadcastChannel — every move in Present.jsx
 * posts the Reveal state, which we apply here. No chrome; meant for a second
 * screen / projector.
 */
export default function Audience() {
  const { jobId } = useParams();
  const frameRef = useRef(null);
  const [htmlUrl, setHtmlUrl] = useState(null);
  const pending = useRef(null);

  useEffect(() => {
    let url;
    let dead = false;
    api
      .artifactObjectUrl(api.jobDownloadPath(jobId, "html"))
      .then((u) => {
        if (dead) return URL.revokeObjectURL(u);
        url = u;
        setHtmlUrl(u);
      })
      .catch(() => {});
    return () => {
      dead = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [jobId]);

  const [dark, setDark] = useState(false);

  useEffect(() => {
    const chan = new BroadcastChannel(`learnova-present-${jobId}`);
    const apply = (state) => {
      const R = frameRef.current?.contentWindow?.Reveal;
      if (R && state) {
        try {
          R.setState(state);
        } catch {
          pending.current = state;
        }
      } else {
        pending.current = state;
      }
    };
    chan.onmessage = (e) => {
      if (e.data?.type === "state") apply(e.data.state);
      else if (e.data?.type === "blackout") setDark(!!e.data.on);
    };
    return () => chan.close();
  }, [jobId]);

  return (
    <div className="relative h-svh w-svw bg-black">
      {dark ? <div className="absolute inset-0 z-10 bg-black" /> : null}
      {htmlUrl ? (
        <iframe
          ref={frameRef}
          title="Presentation"
          src={htmlUrl}
          className="h-full w-full border-0"
          onLoad={() => {
            const w = frameRef.current?.contentWindow;
            try {
              w?.__enableBuilds?.();
            } catch {
              /* ignore */
            }
            if (pending.current) {
              try {
                w?.Reveal?.setState(pending.current);
              } catch {
                /* ignore */
              }
              pending.current = null;
            }
          }}
        />
      ) : null}
    </div>
  );
}
