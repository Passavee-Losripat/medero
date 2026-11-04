"use client";
// Find a clinic or pharmacy: the patient's own words -> the department signboard to look for -> a map search.
// The department table is fixed on the server (no model). Medero never ranks or recommends a place.
import { useEffect, useState } from "react";
import EmergencyCard from "@/components/EmergencyCard";
import Header from "@/components/Header";
import Icon from "@/components/Icon";
import { api, load } from "@/lib/api";
import { t } from "@/lib/i18n";

type Dept = { id: string; ko: string; name: string; links: Record<"naver" | "kakao" | "google", string> };
type Res = { emergency: boolean; card?: any; suggested?: Dept[]; all?: Dept[]; matched?: string[] };

export default function Find() {
  const [lang, setLang] = useState("en");
  const [q, setQ] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    const l = load("lang") || "en";
    setLang(l);
    const p = new URLSearchParams(window.location.search);
    let start = p.get("q") || "";
    try { start = start || sessionStorage.getItem("medero.feeling") || ""; } catch {}
    if (p.get("dept") === "pharmacy") start = "pharmacy";
    setQ(start);
    run(start, l);
  }, []);
  const s = t(lang);

  async function run(text: string, l = lang) {
    setErr("");
    try { setRes(await api(`/find?q=${encodeURIComponent(text)}&lang=${l}`)); }
    catch (e: any) { setErr(String(e.message || e)); }
  }

  if (res?.emergency) return <main className="fade-in"><EmergencyCard card={res.card} lang={lang} /></main>;
  const suggested = res?.suggested || [];
  return (
    <>
      <Header title={s.tileMap} />
      <main className="stack narrow fade-in">
        <h1 style={{ marginBottom: 0 }}>{s.findTitle}</h1>
        <p className="muted" style={{ margin: 0 }}>{s.findHelp}</p>
        <form className="ask-input" onSubmit={(e) => { e.preventDefault(); run(q); }}>
          <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder={s.findPh} aria-label={s.findTitle} />
          <button type="submit" className="primary" style={{ width: 52, height: 52, padding: 0, flex: "none" }} aria-label={s.next}><Icon name="arrow" /></button>
        </form>
        {err && <div className="banner">{err}</div>}

        {suggested.length > 0 && <h2 style={{ marginBottom: 0 }}>{s.lookFor}</h2>}
        {suggested.map((d) => <DeptCard key={d.id} d={d} s={s} highlight />)}
        {res && suggested.length === 0 && <div className="card flat" style={{ margin: 0 }}>{s.findNoMatch}</div>}

        <button className="ghost" onClick={() => setShowAll(!showAll)}>{showAll ? "▲" : "▼"} {s.allDepts}</button>
        {showAll && (res?.all || []).map((d) => <DeptCard key={d.id} d={d} s={s} />)}

        <p className="muted" style={{ fontSize: ".85rem" }}>{s.findNotice}</p>
      </main>
    </>
  );
}

function DeptCard({ d, s, highlight }: { d: Dept; s: ReturnType<typeof t>; highlight?: boolean }) {
  return (
    <div className="card stack" style={{ margin: 0, ...(highlight ? { border: "2px solid var(--cyan)" } : {}) }}>
      <div className="row between">
        <div>
          <div className="ko-big" lang="ko" style={{ lineHeight: 1.1 }}>{d.ko}</div>
          <div className="muted">{d.name}</div>
        </div>
        <span className="tile-icon"><Icon name={d.id === "pharmacy" ? "pill" : "map"} /></span>
      </div>
      <div className="map-links">
        <a className="btn dark" href={d.links.naver} target="_blank" rel="noopener noreferrer">Naver Map</a>
        <a className="btn" href={d.links.kakao} target="_blank" rel="noopener noreferrer">Kakao Map</a>
        <a className="btn ghost" href={d.links.google} target="_blank" rel="noopener noreferrer">Google</a>
      </div>
    </div>
  );
}
