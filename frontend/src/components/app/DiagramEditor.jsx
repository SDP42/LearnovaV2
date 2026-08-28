import { useCallback, useEffect, useRef, useState } from "react";
import {
  Code2,
  Copy,
  Check,
  Download,
  Maximize2,
  Minus,
  Plus,
  RefreshCw,
  Scan,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useTheme } from "@/components/theme.jsx";
import { cn } from "@/lib/utils";

let _seq = 0;

/**
 * A pan / zoom / fullscreen shell around a Mermaid diagram.
 *
 * Props: `code` (mermaid source), `title`. The source panel is editable and
 * re-renders live. Export to SVG or PNG works because this runs on a real
 * origin (not a sandboxed artifact).
 */
export default function DiagramEditor({ code = "", title = "Diagram", className }) {
  const { theme } = useTheme();
  const wrapRef = useRef(null);
  const stageRef = useRef(null);
  const [src, setSrc] = useState(code);
  const [svg, setSvg] = useState("");
  const [err, setErr] = useState("");
  const [showSrc, setShowSrc] = useState(false);
  const [copied, setCopied] = useState(false);

  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const drag = useRef(null);

  useEffect(() => setSrc(code), [code]);

  const render = useCallback(async (text) => {
    if (!text.trim()) {
      setSvg("");
      setErr("");
      return;
    }
    try {
      const mermaid = (await import("mermaid")).default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        theme: theme === "dark" ? "dark" : "neutral",
        flowchart: { curve: "basis", htmlLabels: true },
      });
      const { svg: out } = await mermaid.render(`lv-dg-${_seq++}`, text);
      setSvg(out);
      setErr("");
    } catch (e) {
      setErr(String(e?.message || e).split("\n")[0]);
    }
  }, [theme]);

  useEffect(() => {
    const t = setTimeout(() => render(src), 200);
    return () => clearTimeout(t);
  }, [src, render]);

  // ── pan / zoom ────────────────────────────────────────────────────────────
  function onWheel(e) {
    e.preventDefault();
    const rect = stageRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    setView((v) => {
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const k = Math.min(6, Math.max(0.2, v.k * factor));
      const ratio = k / v.k;
      return { k, x: mx - (mx - v.x) * ratio, y: my - (my - v.y) * ratio };
    });
  }
  function onDown(e) {
    drag.current = { sx: e.clientX, sy: e.clientY, ox: view.x, oy: view.y };
  }
  function onMove(e) {
    if (!drag.current) return;
    setView((v) => ({
      ...v,
      x: drag.current.ox + (e.clientX - drag.current.sx),
      y: drag.current.oy + (e.clientY - drag.current.sy),
    }));
  }
  function onUp() {
    drag.current = null;
  }

  const zoom = (f) =>
    setView((v) => ({ ...v, k: Math.min(6, Math.max(0.2, v.k * f)) }));
  const reset = () => setView({ x: 0, y: 0, k: 1 });

  function fit() {
    const stage = stageRef.current;
    const g = stage?.querySelector("svg");
    if (!stage || !g) return reset();
    const sb = stage.getBoundingClientRect();
    const gb = g.getBoundingClientRect();
    const k = Math.min(sb.width / (gb.width / view.k), sb.height / (gb.height / view.k)) * 0.9;
    setView({ k, x: (sb.width - (gb.width / view.k) * k) / 2, y: (sb.height - (gb.height / view.k) * k) / 2 });
  }

  function fullscreen() {
    const el = wrapRef.current;
    if (!document.fullscreenElement) el?.requestFullscreen?.();
    else document.exitFullscreen?.();
  }

  function download(kind) {
    const stage = stageRef.current?.querySelector("svg");
    if (!stage) return;
    const clone = stage.cloneNode(true);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const markup = new XMLSerializer().serializeToString(clone);
    const safe = title.replace(/[^\w-]+/g, "_").slice(0, 40) || "diagram";

    if (kind === "svg") {
      const url = URL.createObjectURL(new Blob([markup], { type: "image/svg+xml" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${safe}.svg`;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }
    const img = new Image();
    img.onload = () => {
      const scale = 2;
      const c = document.createElement("canvas");
      c.width = img.width * scale;
      c.height = img.height * scale;
      const ctx = c.getContext("2d");
      ctx.fillStyle = theme === "dark" ? "#17162b" : "#ffffff";
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0);
      c.toBlob((b) => {
        const url = URL.createObjectURL(b);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${safe}.png`;
        a.click();
        URL.revokeObjectURL(url);
      });
    };
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(markup)));
  }

  const nodeCount = (src.match(/-->/g) || []).length + 1;

  return (
    <div
      ref={wrapRef}
      className={cn("flex min-h-0 flex-col overflow-hidden rounded-xl border bg-card", className)}
    >
      <div className="flex flex-wrap items-center gap-1 border-b bg-muted/30 px-2 py-1.5">
        <span className="mr-1 truncate px-1.5 text-sm font-medium">{title}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {nodeCount} nodes
        </span>
        <div className="ml-auto flex items-center gap-0.5">
          <Button variant="ghost" size="icon" className="size-8" onClick={() => zoom(1 / 1.2)} title="Zoom out">
            <Minus />
          </Button>
          <span className="w-11 text-center text-xs tabular-nums text-muted-foreground">
            {Math.round(view.k * 100)}%
          </span>
          <Button variant="ghost" size="icon" className="size-8" onClick={() => zoom(1.2)} title="Zoom in">
            <Plus />
          </Button>
          <Button variant="ghost" size="icon" className="size-8" onClick={fit} title="Fit to view">
            <Scan />
          </Button>
          <Button variant="ghost" size="icon" className="size-8" onClick={reset} title="Reset">
            <RefreshCw />
          </Button>
          <Separator orientation="vertical" className="mx-1 h-5" />
          <Button variant="ghost" size="icon" className="size-8" onClick={() => setShowSrc((s) => !s)} title="Source">
            <Code2 className={showSrc ? "text-primary" : ""} />
          </Button>
          <Button variant="ghost" size="icon" className="size-8" onClick={() => download("png")} title="Download PNG">
            <Download />
          </Button>
          <Button variant="ghost" size="icon" className="size-8" onClick={() => download("svg")} title="Download SVG">
            <span className="text-[10px] font-bold">SVG</span>
          </Button>
          <Button variant="ghost" size="icon" className="size-8" onClick={fullscreen} title="Fullscreen">
            <Maximize2 />
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <div
          ref={stageRef}
          onWheel={onWheel}
          onMouseDown={onDown}
          onMouseMove={onMove}
          onMouseUp={onUp}
          onMouseLeave={onUp}
          className="relative min-h-[320px] flex-1 cursor-grab overflow-hidden bg-[radial-gradient(circle,var(--color-border)_1px,transparent_1px)] [background-size:22px_22px] active:cursor-grabbing"
        >
          {err ? (
            <p className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-destructive">
              {err}
            </p>
          ) : null}
          <div
            className="absolute left-0 top-0 origin-top-left"
            style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})` }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        </div>

        {showSrc && (
          <div className="flex w-72 shrink-0 flex-col border-l">
            <div className="flex items-center justify-between border-b px-3 py-1.5 text-xs font-medium">
              Mermaid source
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                onClick={() => {
                  navigator.clipboard?.writeText(src);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1200);
                }}
              >
                {copied ? <Check /> : <Copy />}
              </Button>
            </div>
            <textarea
              value={src}
              onChange={(e) => setSrc(e.target.value)}
              spellCheck={false}
              className="min-h-0 flex-1 resize-none bg-transparent p-3 font-mono text-xs outline-none"
            />
          </div>
        )}
      </div>
    </div>
  );
}
