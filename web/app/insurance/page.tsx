"use client";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { load, postForm, postJson } from "@/lib/api";
import { t } from "@/lib/i18n";

type Doc = { type: string; date?: string | null; amount?: string | null; disease_code?: string | null; confidence?: number };

export default function Insurance() {
  const [lang, setLang] = useState("en");
  const [text, setText] = useState("");
  const [checklist, setChecklist] = useState<{ insurer_name: string | null; required_docs: string[]; fake_models?: boolean; error?: string } | null>(null);
  const [captured, setCaptured] = useState<Doc[]>([]);
  const [have, setHave] = useState<string[]>([]);
  const [pack, setPack] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => setLang(load("lang") || "en"), []);
  const s = t(lang);

  async function run<T>(fn: () => Promise<T>) {
    setBusy(true); setErr("");
    try { return await fn(); } catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  }
  const parse = (file?: File) => run(async () => setChecklist(await postForm("/insurance/checklist", file ? { file } : { text })));
  const capture = (file?: File) => file && run(async () => {
    const d = await postForm("/insurance/capture", { file });
    setCaptured((c) => [...c, d]);
  });
  useEffect(() => {
    if (!checklist) return;
    postJson("/insurance/pack", { insurer_name: checklist.insurer_name, required_docs: checklist.required_docs, captured, have, lang })
      .then(setPack).catch((e) => setErr(String(e.message || e)));
  }, [checklist, captured, have, lang]);

  return (
    <>
      <Header />
      <main className="stack">
        <h1>{s.insurance}</h1>
        <div className="banner">{pack?.notice || s.insurerHelp}</div>
        <div className="card stack">
          <h2>{s.insurerChecklist}</h2>
          <p className="muted">{s.insurerHelp}</p>
          <input type="file" accept="application/pdf,image/*" onChange={(e) => parse(e.target.files?.[0])} />
          <textarea placeholder="Paste the insurer's text…" value={text} onChange={(e) => setText(e.target.value)} />
          <button disabled={busy || !text.trim()} onClick={() => parse()}>{s.parse}</button>
          <p className="muted">MOCK samples: <code>data/mock/insurers/ins_a.txt</code>, <code>ins_b.txt</code></p>
        </div>
        {checklist?.fake_models && <div className="banner">{s.fakeModels}</div>}
        {checklist?.error && <div className="banner">{checklist.error}</div>}
        {checklist && (
          <div className="card stack">
            <h2>{checklist.insurer_name || "Insurer"}</h2>
            {checklist.required_docs.map((d) => (
              <label key={d} className="row" style={{ fontWeight: 400 }}>
                <input type="checkbox" checked={have.includes(d)}
                  onChange={(e) => setHave(e.target.checked ? [...have, d] : have.filter((x) => x !== d))} />
                {d} <span className="muted">({s.have})</span>
              </label>
            ))}
          </div>
        )}
        {checklist && (
          <div className="card stack">
            <h2>{s.captureDocs}</h2>
            <input type="file" accept="image/*" capture="environment" onChange={(e) => capture(e.target.files?.[0])} />
            {captured.map((c, i) => (
              <div key={i} className="fact"><span className="badge">{c.type}</span>
                <div className="grow muted">{[c.date, c.amount, c.disease_code].filter(Boolean).join(" · ") || "–"}
                  {(c.confidence ?? 1) < 0.7 && <span className="badge warn"> {s.lowConfidence}</span>}</div></div>
            ))}
          </div>
        )}
        {pack && (
          <div className="card stack">
            <h2>{s.missing}</h2>
            {pack.missing.length ? <ul>{pack.missing.map((m: string) => <li key={m}>{m}</li>)}</ul> : <p>{s.allSet}</p>}
            <h2>{s.draft}</h2>
            <pre className="draft">{pack.draft_message}</pre>
            <button onClick={() => navigator.clipboard?.writeText(pack.draft_message)}>{s.copy}</button>
          </div>
        )}
        {busy && <p className="muted">…</p>}
        {err && <div className="banner">{err}</div>}
      </main>
    </>
  );
}
