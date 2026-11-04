"use client";
// Cover identifiers on the phone before a photo goes to a cloud model (guardrail 10 fallback).
// A suggested box covers the top of the form, where the Korean prescription form prints the patient's
// name, ID number and clinic. Drag to draw more boxes; tap a box to remove it. Covering is a solid fill
// done on the device, so the covered pixels are never uploaded.
import { useEffect, useRef, useState } from "react";

type Box = { x: number; y: number; w: number; h: number }; // fractions of the image, 0..1
const SUGGESTED: Box[] = [{ x: 0, y: 0, w: 1, h: 0.36 }];
const MAX_SIDE = 2000;

export default function RedactEditor({ file, labels, onDone, onCancel }: {
  file: File;
  labels: { title: string; help: string; reset: string; send: string; cancel: string };
  onDone: (f: File) => void;
  onCancel: () => void;
}) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [boxes, setBoxes] = useState<Box[]>(SUGGESTED);
  const [draft, setDraft] = useState<Box | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const wrap = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    const i = new Image();
    i.onload = () => setImg(i);
    i.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function pos(e: React.PointerEvent) {
    const r = wrap.current!.getBoundingClientRect();
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) };
  }
  function down(e: React.PointerEvent) {
    if ((e.target as HTMLElement).dataset.box) return;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    start.current = pos(e);
  }
  function move(e: React.PointerEvent) {
    if (!start.current) return;
    const p = pos(e), s = start.current;
    setDraft({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) });
  }
  function up() {
    if (draft && draft.w > 0.02 && draft.h > 0.01) setBoxes((b) => [...b, draft]);
    setDraft(null); start.current = null;
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
        <div ref={wrap} className="redact" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
          <img src={img.src} alt="" draggable={false} />
          {boxes.map((b, i) => (
            <button key={i} data-box="1" className="redact-box" style={style(b)} aria-label="remove cover"
              onClick={() => setBoxes(boxes.filter((_, j) => j !== i))}>×</button>
          ))}
          {draft && <span className="redact-box draft" style={style(draft)} />}
        </div>
      )}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button className="dark" onClick={apply} disabled={!img}>{labels.send}</button>
        <button className="ghost" onClick={() => setBoxes(SUGGESTED)}>{labels.reset}</button>
        <button className="ghost" onClick={onCancel}>{labels.cancel}</button>
      </div>
    </div>
  );
}
