"use client";
// Cover parts of a photo on the phone before it is read (guardrail 10).
// Drag on the photo to draw a box; drag a box to move it; drag its corner to resize; ✕ removes it.
// Covering is a solid fill done on the device, so covered pixels are never uploaded.
// With the cloud reader a box over the form header (name, ID number, clinic) is suggested; with the
// private reader covering is optional and starts empty.
import { useEffect, useRef, useState } from "react";

type Box = { x: number; y: number; w: number; h: number }; // fractions of the image, 0..1
const HEADER: Box[] = [{ x: 0, y: 0, w: 1, h: 0.36 }];
const MAX_SIDE = 2000;
const MIN = 0.04;
type Drag = { mode: "draw" | "move" | "resize"; i: number; sx: number; sy: number; orig: Box } | null;

export default function RedactEditor({ file, suggest, labels, onDone, onCancel }: {
  file: File;
  suggest: boolean;
  labels: { title: string; help: string; reset: string; send: string; cancel: string };
  onDone: (f: File) => void;
  onCancel: () => void;
}) {
  const start = suggest ? HEADER : [];
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [boxes, setBoxes] = useState<Box[]>(start);
  const drag = useRef<Drag>(null);
  const wrap = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    const i = new Image();
    i.onload = () => setImg(i);
    i.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const clamp = (v: number) => Math.min(1, Math.max(0, v));
  function pos(e: React.PointerEvent) {
    const r = wrap.current!.getBoundingClientRect();
    return { x: clamp((e.clientX - r.left) / r.width), y: clamp((e.clientY - r.top) / r.height) };
  }
  function begin(e: React.PointerEvent, mode: "draw" | "move" | "resize", i = -1) {
    e.preventDefault(); e.stopPropagation();
    wrap.current?.setPointerCapture(e.pointerId);
    const p = pos(e);
    if (mode === "draw") {
      setBoxes((b) => [...b, { x: p.x, y: p.y, w: 0, h: 0 }]);
      i = boxes.length;
    }
    drag.current = { mode, i, sx: p.x, sy: p.y, orig: mode === "draw" ? { x: p.x, y: p.y, w: 0, h: 0 } : boxes[i] };
  }
  function move(e: React.PointerEvent) {
    const d = drag.current;
    if (!d) return;
    const p = pos(e), dx = p.x - d.sx, dy = p.y - d.sy, o = d.orig;
    let nb: Box;
    if (d.mode === "draw") nb = { x: Math.min(d.sx, p.x), y: Math.min(d.sy, p.y), w: Math.abs(dx), h: Math.abs(dy) };
    else if (d.mode === "move") nb = { ...o, x: clamp(Math.min(o.x + dx, 1 - o.w)), y: clamp(Math.min(o.y + dy, 1 - o.h)) };
    else nb = { ...o, w: Math.max(MIN, Math.min(o.w + dx, 1 - o.x)), h: Math.max(MIN, Math.min(o.h + dy, 1 - o.y)) };
    setBoxes((b) => b.map((x, j) => (j === d.i ? nb : x)));
  }
  function end() {
    const d = drag.current;
    drag.current = null;
    if (d?.mode === "draw") setBoxes((b) => b.filter((x, j) => j !== d.i || (x.w > MIN && x.h > 0.02)));
  }

  function apply() {
    if (!img) return;
    const k = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
    const c = document.createElement("canvas");
    c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
    const g = c.getContext("2d")!;
    g.drawImage(img, 0, 0, c.width, c.height);
    g.fillStyle = "#000";
    for (const b of boxes) g.fillRect(b.x * c.width, b.y * c.height, b.w * c.width, b.h * c.height);
    c.toBlob((blob) => blob && onDone(new File([blob], "covered.jpg", { type: "image/jpeg" })), "image/jpeg", 0.9);
  }

  const style = (b: Box) => ({ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` });
  return (
    <div className="card stack" style={{ margin: 0 }}>
      <h3 style={{ margin: 0 }}>🔒 {labels.title}</h3>
      <p className="muted" style={{ margin: 0 }}>{labels.help}</p>
      {img && (
        <div ref={wrap} className="redact" onPointerDown={(e) => begin(e, "draw")} onPointerMove={move}
          onPointerUp={end} onPointerCancel={end}>
          <img src={img.src} alt="" draggable={false} />
          {boxes.map((b, i) => (
            <div key={i} className="redact-box" style={style(b)} onPointerDown={(e) => begin(e, "move", i)}>
              <button className="redact-x" aria-label="remove cover" onPointerDown={(e) => e.stopPropagation()}
                onClick={() => setBoxes(boxes.filter((_, j) => j !== i))}>✕</button>
              <span className="redact-handle" aria-hidden="true" onPointerDown={(e) => begin(e, "resize", i)} />
            </div>
          ))}
        </div>
      )}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button className="dark" onClick={apply} disabled={!img}>{labels.send}</button>
        <button className="ghost" onClick={() => setBoxes(suggest ? HEADER : [])}>{labels.reset}</button>
        <button className="ghost" onClick={onCancel}>{labels.cancel}</button>
      </div>
    </div>
  );
}
