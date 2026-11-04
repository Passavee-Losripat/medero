"use client";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { load, postForm } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function Prescription() {
  const [lang, setLang] = useState("en");
  const [res, setRes] = useState<any>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => setLang(load("lang") || "en"), []);
  const s = t(lang);

  async function onFile(f: File | undefined) {
    if (!f) return;
    setPreview(URL.createObjectURL(f)); setBusy(true); setErr(""); setRes(null);
    try { setRes(await postForm("/prescription", { file: f, lang })); }
    catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  }
  return (
    <>
      <Header />
      <main className="stack narrow">
        <h1>{s.prescription}</h1>
        <div className="banner"><strong>{s.confirmPharmacist}.</strong> {s.notAdvice}</div>
        <div className="card">
          <label>{s.upload}</label>
          <input type="file" accept="image/*" capture="environment" onChange={(e) => onFile(e.target.files?.[0])} />
          <p className="muted">Sample MOCK labels: <code>data/mock/prescriptions/rx01.png</code></p>
        </div>
        {preview && <img src={preview} alt="uploaded label" style={{ maxWidth: "100%", borderRadius: 12 }} />}
        {busy && <p className="muted">…</p>}
        {err && <div className="banner">{err}</div>}
        {res && (
          <div className="stack">
            {res.fake_models && <div className="banner">{s.fakeModels}</div>}
            {res.low_confidence && <div className="banner">{s.lowConfidence}</div>}
            {res.items.map((it: any, i: number) => (
              <div key={i} className="card stack">
                <div className="row"><span className="ko-big" lang="ko">{it.drug_name_ko}</span>
                  {it.confidence < 0.7 && <span className="badge warn">{s.lowConfidence}</span>}</div>
                <div className="ko" lang="ko">{[it.dose, it.times_per_day, it.days, it.instructions_ko].filter(Boolean).join(" · ")}</div>
                <div>{it.gloss_patient_lang}</div>
                <span className="badge warn">{s.confirmPharmacist}</span>
              </div>
            ))}
            {!!res.untranslated_terms?.length && <div className="banner">{s.untranslated}: {res.untranslated_terms.join(", ")}</div>}
            <p><strong>{res.notice_patient_lang}</strong></p>
          </div>
        )}
      </main>
    </>
  );
}
