import { useCallback, useEffect, useRef, useState } from "react";
import { Crop, Loader2, Redo2, Square, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Crop + highlight a slide figure on a canvas, then save the result back to the
 * deck. `src` is an object URL for the current figure; `onSaved(blob)` fires
 * after a successful PUT so the caller can re-render.
 */
export default function ImageEditor({ src, onSave, onClose }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [tool, setTool] = useState("crop"); // "crop" | "box"
  const [rect, setRect] = useState(null); // {x,y,w,h} in canvas px
  const [boxes, setBoxes] = useState([]); // committed highlight rects
  const [drag, setDrag] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // Base image drawn each frame; starts as the full image, shrinks after a crop.
  const [crop, setCrop] = useState(null); // {sx,sy,sw,sh} source px

  const CW = 720;

  const redraw = useCallback(() => {
    const cv = canvasRef.current;
    const im = imgRef.current;
    if (!cv || !im) return;
    const ctx = cv.getContext("2d");
    const s = crop || { sx: 0, sy: 0, sw: im.naturalWidth, sh: im.naturalHeight };
    const scale = CW / s.sw;
    cv.width = CW;
    cv.height = Math.round(s.sh * scale);
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.drawImage(im, s.sx, s.sy, s.sw, s.sh, 0, 0, cv.width, cv.height);

    // committed highlights
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#8b7bf5";
    ctx.fillStyle = "rgba(139,123,245,0.12)";
    boxes.forEach((b) => {
      ctx.fillRect(b.x, b.y, b.w, b.h);
      ctx.strokeRect(b.x, b.y, b.w, b.h);
    });

    // live rectangle
    if (rect) {
      if (tool === "crop") {
        ctx.save();
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.fillRect(0, 0, cv.width, cv.height);
        ctx.clearRect(rect.x, rect.y, rect.w, rect.h);
        ctx.drawImage(
          im,
          s.sx + (rect.x / scale),
          s.sy + (rect.y / scale),
          rect.w / scale,
          rect.h / scale,
          rect.x,
          rect.y,
          rect.w,
          rect.h
        );
        ctx.strokeStyle = "#fff";
        ctx.setLineDash([6, 4]);
        ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
        ctx.restore();
      } else {
        ctx.strokeStyle = "#8b7bf5";
        ctx.fillStyle = "rgba(139,123,245,0.12)";
        ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
        ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
      }
    }
  }, [crop, boxes, rect, tool]);

  useEffect(() => {
    const im = new Image();
    im.crossOrigin = "anonymous";
    im.onload = () => {
      imgRef.current = im;
      setReady(true);
    };
    im.onerror = () => setErr("Could not load the figure.");
    im.src = src;
  }, [src]);

  useEffect(() => {
    if (ready) redraw();
  }, [ready, redraw]);

  function pos(e) {
    const r = canvasRef.current.getBoundingClientRect();
    return {
      x: ((e.clientX - r.left) / r.width) * canvasRef.current.width,
      y: ((e.clientY - r.top) / r.height) * canvasRef.current.height,
    };
  }
  function down(e) {
    const p = pos(e);
    setDrag(p);
    setRect({ x: p.x, y: p.y, w: 0, h: 0 });
  }
  function move(e) {
    if (!drag) return;
    const p = pos(e);
    setRect({
      x: Math.min(drag.x, p.x),
      y: Math.min(drag.y, p.y),
      w: Math.abs(p.x - drag.x),
      h: Math.abs(p.y - drag.y),
    });
  }
  function up() {
    if (!drag || !rect || rect.w < 5 || rect.h < 5) {
      setDrag(null);
      setRect(null);
      return;
    }
    if (tool === "box") {
      setBoxes((b) => [...b, rect]);
      setRect(null);
    }
    setDrag(null);
  }

  function applyCrop() {
    const im = imgRef.current;
    if (!rect || !im) return;
    const s = crop || { sx: 0, sy: 0, sw: im.naturalWidth, sh: im.naturalHeight };
    const scale = CW / s.sw;
    setCrop({
      sx: s.sx + rect.x / scale,
      sy: s.sy + rect.y / scale,
      sw: rect.w / scale,
      sh: rect.h / scale,
    });
    setBoxes([]);
    setRect(null);
  }

  function reset() {
    setCrop(null);
    setBoxes([]);
    setRect(null);
  }

  async function save() {
    setBusy(true);
    setErr("");
    // Redraw once clean (no live rect) then export.
    setRect(null);
    await new Promise((r) => setTimeout(r, 30));
    redraw();
    canvasRef.current.toBlob(async (blob) => {
      try {
        await onSave(blob);
        onClose();
      } catch (e) {
        setErr(e.message || "Save failed");
      } finally {
        setBusy(false);
      }
    }, "image/png");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="lv-frost flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <p className="text-sm font-medium">Edit figure</p>
          <Button size="icon" variant="ghost" onClick={onClose}><X /></Button>
        </div>

        <div className="flex items-center gap-2 border-b px-4 py-2">
          <Button
            size="sm"
            variant={tool === "crop" ? "default" : "outline"}
            onClick={() => { setTool("crop"); setRect(null); }}
          >
            <Crop /> Crop
          </Button>
          <Button
            size="sm"
            variant={tool === "box" ? "default" : "outline"}
            onClick={() => { setTool("box"); setRect(null); }}
          >
            <Square /> Highlight
          </Button>
          {tool === "crop" && rect ? (
            <Button size="sm" onClick={applyCrop}>Apply crop</Button>
          ) : null}
          <Button size="sm" variant="ghost" onClick={reset} className="ml-auto">
            <Redo2 /> Reset
          </Button>
        </div>

        <div className="flex-1 overflow-auto bg-muted/30 p-4">
          {err ? <p className="mb-2 text-sm text-destructive">{err}</p> : null}
          {ready ? (
            <canvas
              ref={canvasRef}
              onMouseDown={down}
              onMouseMove={move}
              onMouseUp={up}
              onMouseLeave={up}
              className={cn(
                "mx-auto max-w-full rounded-lg border bg-white",
                tool === "crop" ? "cursor-crosshair" : "cursor-copy"
              )}
            />
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="mr-2 animate-spin" /> Loading figure…
            </div>
          )}
          <p className="mx-auto mt-2 max-w-md text-center text-xs text-muted-foreground">
            Drag to {tool === "crop" ? "select an area, then Apply crop" : "draw a highlight box"}.
            Saving replaces the figure and re-renders the deck.
          </p>
        </div>

        <div className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy || !ready}>
            {busy ? <Loader2 className="animate-spin" /> : null}
            {busy ? "Saving…" : "Save figure"}
          </Button>
        </div>
      </div>
    </div>
  );
}
