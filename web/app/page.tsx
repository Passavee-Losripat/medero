"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { api, load, save } from "@/lib/api";
import { LANGS, t } from "@/lib/i18n";

export default function Home() {
  const [lang, setLang] = useState("en");
  const [health, setHealth] = useState<any>(null);
  useEffect(() => {
    setLang(load("lang") || "en");
    api("/health").then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);
  const s = t(lang);
  const choose = (l: string) => { setLang(l); save("lang", l); };
  return (
    <>
      <Header />
      <main className="stack">
        <h1>{s.tagline}</h1>
        <p className="muted">{s.notAdvice}</p>
        {health && !health.ok && <div className="banner">API not reachable. Start it with <code>make api</code>.</div>}
        {health?.fake_models && <div className="banner">{s.fakeModels}</div>}
        <div className="card">
          <label>{s.language}</label>
          <div className="row">
            {LANGS.map((l) => (
              <button key={l.code} className={l.code === lang ? "primary" : ""} onClick={() => choose(l.code)}>{l.label}</button>
            ))}
          </div>
        </div>
        <div className="home-grid">
          <Link className="btn primary big" href="/intake">{s.start}</Link>
          <Link className="btn big" href="/intake?demo=1">{s.demo}</Link>
          <Link className="btn big" href="/prescription">{s.prescription}</Link>
          <Link className="btn big" href="/insurance">{s.insurance}</Link>
        </div>
        <p><Link href="/results">{s.results}</Link></p>
      </main>
    </>
  );
}
