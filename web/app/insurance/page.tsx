"use client";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import Icon from "@/components/Icon";
import { api, load, postForm, postJson } from "@/lib/api";
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
  useEffect(() => {
    setLang(load("lang") || "en");
    api("/reader/status").catch(() => {});  // wakes the private reader before the first receipt photo
  }, []);
  const s = t(lang);

  async function run<T>(fn: () => Promise<T>) {
    setBusy(true); setErr("");
    try { return await fn(); } catch (e: any) {
      const m = String(e.message || e);
      setErr(m.includes("private_reader_warming") ? s.privWakingRetry : m);
    } finally { setBusy(false); }
  }
  const parse = (file?: File) => run(async () => setChecklist(await postForm("/insurance/checklist", file ? { file } : { text })));
  const capture = (file?: File) => file && run(async () => {
    const d = await postForm("/insurance/capture", { file });
    setCaptured((c) => [...c, d]);
  });
  const sample = async (path: string, type: string) =>
    new File([await (await fetch(path)).blob()], path.split("/").pop() || "sample", { type });
  // MOCK insurer checklist and receipts bundled with the web app, so the flow can be tried on a phone
  const sampleChecklist = async () => parse(await sample("/samples/insurer-mock.pdf", "application/pdf"));
  const sampleReceipts = () => run(async () => {
    for (const f of ["rc01_receipt", "rc02_itemized", "rc03_pharmacy", "rc04_cardslip"]) {
      const d = await postForm("/insurance/capture", { file: await sample(`/samples/${f}.jpg`, "image/jpeg") });
      setCaptured((c) => [...c, d]);
    }
  });
  useEffect(() => {
    if (!checklist) return;
    postJson("/insurance/pack", { insurer_name: checklist.insurer_name, required_docs: checklist.required_docs, captured, have, lang })
      .then(setPack).catch((e) => setErr(String(e.message || e)));
  }, [checklist, captured, have, lang]);

  return (
    <>
      <Header title={s.insurance} />
      <main className="stack narrow">
        <h1>{s.insurance}</h1>
        <div className="banner">{pack?.notice || s.insurerHelp}</div>
        <div className="card stack">
          <h2>{s.insurerChecklist}</h2>
          <p className="muted">{s.insurerHelp}</p>
          <input type="file" accept="application/pdf,image/*" onChange={(e) => parse(e.target.files?.[0])} />
          <textarea placeholder="Paste the insurer's text…" value={text} onChange={(e) => setText(e.target.value)} />
          <button disabled={busy || !text.trim()} onClick={() => parse()}>{s.parse}</button>
          <button className="ghost" style={{ alignSelf: "center" }} disabled={busy} onClick={sampleChecklist}>✨ {s.sampleChecklist}</button>
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
            <div className="pick">
              <label className="btn dark"><Icon name="camera" size={28} />{s.takePhoto}
                <input type="file" accept="image/*" capture="environment" disabled={busy}
                  onChange={(e) => { capture(e.target.files?.[0]); e.target.value = ""; }} /></label>
              <label className="btn"><Icon name="image" size={28} />{s.fromLibrary}
                <input type="file" accept="image/*" disabled={busy}
                  onChange={(e) => { capture(e.target.files?.[0]); e.target.value = ""; }} /></label>
            </div>
            <button className="ghost" style={{ alignSelf: "center" }} disabled={busy} onClick={sampleReceipts}>✨ {s.sampleReceipts}</button>
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
        {busy && <p className="muted center">{s.thinking}</p>}
        {err && <div className="banner">{err}</div>}
      </main>
    </>
  );
}
