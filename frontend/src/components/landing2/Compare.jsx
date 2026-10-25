import { useRef, useState } from "react";
import { MoveHorizontal } from "lucide-react";
import { RawFace, VisualFace } from "./Faces";

/** Draggable before/after ("Image Comparison"). */
export default function Compare() {
  const ref = useRef(null);
  const [pos, setPos] = useState(50);
  const move = (e) => {
    const r = ref.current.getBoundingClientRect();
    setPos(Math.min(100, Math.max(0, ((e.clientX - r.left) / r.width) * 100)));
  };
  return (
    <div
      ref={ref}
      className="cmp"
      onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); move(e); }}
      onPointerMove={(e) => e.buttons && move(e)}
      role="slider" aria-label="Compare before and after" aria-valuenow={Math.round(pos)} tabIndex={0}
      onKeyDown={(e) => { if (e.key === "ArrowLeft") setPos((p) => Math.max(0, p - 5)); if (e.key === "ArrowRight") setPos((p) => Math.min(100, p + 5)); }}
    >
      <div className="cmp-layer"><VisualFace kind={1} /></div>
      <div className="cmp-layer" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}><RawFace title="Order fulfilment process" /></div>
      <span className="cmp-tag l">Before</span><span className="cmp-tag r">With Learnova</span>
      <div className="cmp-bar" style={{ left: `${pos}%` }}><span><MoveHorizontal size={18} /></span></div>
    </div>
  );
}
