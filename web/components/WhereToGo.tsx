"use client";
// "Look for this sign": the department to search for, from the patient's own words, with a map hand-off.
// Uses the fixed server table (/find); no model, no ranking. Debounced so it can follow typing.
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import Icon from "./Icon";

type Dept = { id: string; ko: string; name: string; links: Record<string, string> };

export default function WhereToGo({ text, lang, title, model }: { text: string; lang: string; title?: string; model?: boolean }) {
  const [depts, setDepts] = useState<Dept[]>([]);
  const [urgent, setUrgent] = useState(false);
  const [byModel, setByModel] = useState(false);
  const s = t(lang);
  useEffect(() => {
    const q = text.trim();
    if (q.length < 3) { setDepts([]); setUrgent(false); return; }
    const id = setTimeout(() => {
      api(`/find?q=${encodeURIComponent(q)}&lang=${lang}${model ? "&model=1" : ""}`)
        .then((r) => { setUrgent(!!r.emergency); setByModel(String(r.source || "").startsWith("model")); setDepts(r.emergency ? [] : (r.suggested || []).slice(0, 2)); })
        .catch(() => {});
    }, 450);
    return () => clearTimeout(id);
  }, [text, lang, model]);

  if (urgent) return (
    <a className="where urgent fade-in" href="tel:119">🚨 {s.urgentCall}</a>
  );
  if (!depts.length) return null;
  return (
    <div className="where fade-in">
      {title && <div className="muted" style={{ fontSize: ".85rem", fontWeight: 650 }}>{title}</div>}
      {depts.map((d) => (
        <div className="where-row" key={d.id}>
          <span className="where-ko" lang="ko">{d.ko}</span>
          <span className="where-name grow">{d.name}</span>
          <a className="btn dark where-map" href={d.links.naver} target="_blank" rel="noopener noreferrer"
            aria-label={`${s.openMap}: ${d.ko}`}><Icon name="map" size={18} /> {s.openMap}</a>
        </div>
      ))}
      {byModel && <div className="muted" style={{ fontSize: ".8rem" }}>✨ {s.byModel}</div>}
      <Link href={`/find?q=${encodeURIComponent(text.trim())}`} className="muted" style={{ fontSize: ".85rem" }}>{s.moreMaps} →</Link>
    </div>
  );
}
