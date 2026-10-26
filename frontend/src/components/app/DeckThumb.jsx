import { useEffect, useState } from "react";
import * as api from "@/api";
import { cn } from "@/lib/utils";

const TONES = [
  ["#C2502A", "#402B25"],
  ["#6B9B72", "#0B3D3A"],
  ["#402B25", "#C2502A"],
  ["#FFC93C", "#B45309"],
];

function toneFor(str = "") {
  let h = 0;
  for (const c of str) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return TONES[h % TONES.length];
}

/**
 * The deck's real first-slide thumbnail (auth'd PNG → blob URL, cached by
 * api.getDeckThumb). Shimmer while loading; themed title card if it fails.
 */
export default function DeckThumb({ id, title = "Untitled deck", className, rounded = "rounded-none" }) {
  const [state, setState] = useState({ id: null, url: null, failed: false });

  useEffect(() => {
    let live = true;
    if (!id) {
      setState({ id, url: null, failed: true });
      return;
    }
    api
      .getDeckThumb(id)
      .then((url) => live && setState({ id, url, failed: false }))
      .catch(() => live && setState({ id, url: null, failed: true }));
    return () => {
      live = false;
    };
  }, [id]);

  const mine = state.id === id;
  const [c1, c2] = toneFor(title);

  return (
    <div className={cn("relative aspect-video w-full overflow-hidden bg-[#EFE1D4]", rounded, className)}>
      {mine && state.url ? (
        <img
          src={state.url}
          alt=""
          loading="lazy"
          draggable={false}
          onError={() => setState({ id, url: null, failed: true })}
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : mine && state.failed ? (
        <div
          className="absolute inset-0 flex flex-col justify-between p-[8%] text-white"
          style={{ background: `linear-gradient(135deg, ${c1}, ${c2})` }}
        >
          <div className="flex gap-1">
            <span className="h-1 w-6 rounded-full bg-white/70" />
            <span className="h-1 w-3 rounded-full bg-white/40" />
          </div>
          <p
            className="line-clamp-3 text-[clamp(11px,1.6vw,17px)] font-semibold leading-tight"
            style={{ fontFamily: '"Bricolage Grotesque", system-ui, sans-serif', color: c1 === "#FFC93C" ? "#402B25" : "#fff" }}
          >
            {title}
          </p>
        </div>
      ) : (
        <div className="lv-skel absolute inset-0 rounded-none" />
      )}
    </div>
  );
}
