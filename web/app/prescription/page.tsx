"use client";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import Icon from "@/components/Icon";
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
  async function trySample() {
    // MOCK label bundled with the web app so a phone user can try it without the repo
    const blob = await (await fetch("/samples/rx-mock.jpg")).blob();
    onFile(new File([blob], "rx-mock.jpg", { type: "image/jpeg" }));
  }
  return (
    <>
      <Header title={s.prescription} />
      <main className="stack narrow">
        <h1>{s.prescription}</h1>
        <div className="banner"><strong>{s.confirmPharmacist}.</strong> {s.notAdvice}</div>
        <p className="muted" style={{ margin: 0 }}>{s.rxHow}</p>
        <div className="pick">
          <label className="btn dark">
            <Icon name="camera" size={28} />{s.takePhoto}
            <input type="file" accept="image/*" capture="environment" disabled={busy}
              onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
          </label>
          <label className="btn">
            <Icon name="image" size={28} />{s.fromLibrary}
            <input type="file" accept="image/*" disabled={busy}
              onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
          </label>
        </div>
        <button className="ghost" style={{ alignSelf: "center" }} disabled={busy} onClick={trySample}>✨ {s.trySample}</button>
        {preview && <img src={preview} alt="uploaded label" className="rx-preview" />}
        {busy && <p className="muted center">{s.reading}</p>}
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
