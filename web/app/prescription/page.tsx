"use client";
import { useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import Icon from "@/components/Icon";
import RedactEditor from "@/components/RedactEditor";
import SpeakButton from "@/components/SpeakButton";
import { api, load, postForm } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function Prescription() {
  const [lang, setLang] = useState("en");
  const [res, setRes] = useState<any>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [bigKo, setBigKo] = useState(false);
  // Private reader = Muse Glimmer on our own GPU. It scales to zero, so it may be waking up (~1 min).
  const [priv, setPriv] = useState<{ configured: boolean; ready: boolean } | null>(null);
  const [toCover, setToCover] = useState<File | null>(null);
  const [coverCloud, setCoverCloud] = useState(true);  // true: cloud reader, header box suggested
  const [warmNote, setWarmNote] = useState(false);
  const privRef = useRef(priv);
  privRef.current = priv;
  useEffect(() => {
    setLang(load("lang") || "en");
    let tries = 0, stop = false;
    const poll = () => api("/reader/status").then((r) => {
      if (stop) return;
      setPriv({ configured: r.private_configured, ready: r.private_ready });
      // the status call itself wakes the GPU; check again for up to ~2 minutes
      if (r.private_configured && !r.private_ready && ++tries < 12) setTimeout(poll, 10000);
    }).catch(() => setPriv({ configured: false, ready: false }));
    poll();
    return () => { stop = true; };
  }, []);
  const s = t(lang);

  function onFile(f: File | undefined) {
    if (!f) return;
    setRes(null); setErr(""); setWarmNote(false);
    // every photo passes the cover step: optional with the private reader, suggested with the cloud reader
    const cloud = !privRef.current?.ready;
    setPreview(null); setCoverCloud(cloud); setWarmNote(cloud && !!privRef.current?.configured); setToCover(f);
  }
  async function upload(f: File, cloud: boolean) {
    setToCover(null);
    setPreview(URL.createObjectURL(f)); setBusy(true); setErr(""); setRes(null);
    try { setRes(await postForm("/prescription", { file: f, lang, cloud: cloud ? "true" : "false" })); }
    catch (e: any) {
      if (String(e.message).includes("private_reader_warming")) {  // went to sleep meanwhile: cover, then cloud
        setPriv((p) => p && { ...p, ready: false }); setPreview(null); setCoverCloud(true); setWarmNote(true); setToCover(f);
      } else setErr(String(e.message || e));
    } finally { setBusy(false); }
  }
  async function trySample() {
    // MOCK label bundled with the web app so a phone user can try it without the repo
    const blob = await (await fetch("/samples/rx-form-mock.jpg")).blob();
    onFile(new File([blob], "rx-form-mock.jpg", { type: "image/jpeg" }));
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
        {priv?.configured && (
          <div className="row" style={{ gap: 6 }}>
            <span className={`badge ${priv.ready ? "" : "warn"}`}>🔒 {priv.ready ? s.privReady : s.privWaking}</span>
          </div>
        )}
        {toCover && warmNote && <div className="banner">{s.privWakingCover}</div>}
        {toCover && (
          <RedactEditor key={coverCloud ? "cloud" : "private"} file={toCover} suggest={coverCloud}
            onDone={(f) => upload(f, coverCloud)} onCancel={() => setToCover(null)}
            labels={coverCloud
              ? { title: s.coverTitle, help: s.coverHelp, reset: s.coverReset, send: s.coverSend, cancel: s.cancel }
              : { title: s.coverOptTitle, help: s.coverOptHelp, reset: s.coverReset, send: s.coverOptSend, cancel: s.cancel }} />
        )}
        {preview && <img src={preview} alt="uploaded label" className="rx-preview" />}
        {busy && <p className="muted center">{s.reading}</p>}
        {err && <div className="banner">{err}</div>}
        {res && (
          <div className="stack">
            {res.fake_models && <div className="banner">{s.fakeModels}</div>}
            {res.reader && (
              <div className="row" style={{ gap: 6 }}>
                <span className={`badge ${res.reader.local ? "" : "lilac"}`}>
                  {res.reader.local ? `🔒 ${s.readLocally}` : `☁️ ${s.readCloud}`} · {res.reader.model}
                </span>
              </div>
            )}
            {res.low_confidence && <div className="banner">{s.lowConfidence}</div>}
            {res.notes_patient_lang?.map((n: string, i: number) => (
              <div key={i} className="card flat" style={{ margin: 0 }}><Icon name="info" size={18} /> {n}</div>
            ))}
            {res.request_ko && (
              <div className="card stack" style={{ margin: 0 }}>
                <div className="muted">{s.codeRequest}</div>
                <div className={bigKo ? "ko-big" : "ko"} lang="ko" style={{ fontWeight: 650 }}>{res.request_ko}</div>
                <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                  <button className="ghost" onClick={() => setBigKo(!bigKo)}>가 {s.bigForStaff}</button>
                  <SpeakButton text={res.request_ko} label={s.speakKo} />
                </div>
              </div>
            )}
            {res.items.map((it: any, i: number) => (
              <div key={i} className="card stack">
                <div className="row"><span className="ko-big" lang="ko">{it.drug_name_ko}</span>
                  {it.confidence < 0.7 && <span className="badge warn">{s.lowConfidence}</span>}</div>
                {res.doc_kind === "prescription_form" ? (
                  <div className="rx-cols">
                    <span><small>{s.perDose}</small>{it.dose ?? "—"}</span>
                    <span><small>{s.perDay}</small>{it.times_per_day ?? "—"}</span>
                    <span><small>{s.daysCol}</small>{it.days ?? "—"}</span>
                    <span lang="ko"><small>{s.howCol}</small>{it.instructions_ko ?? "—"}</span>
                  </div>
                ) : (
                  <div className="ko" lang="ko">{[it.dose, it.times_per_day, it.days, it.instructions_ko].filter(Boolean).join(" · ")}</div>
                )}
                <div>{it.gloss_patient_lang}</div>
                {it.flags_patient_lang?.map((f: string, j: number) => <div key={j} className="muted" style={{ fontSize: ".92rem" }}>• {f}</div>)}
                <span className="badge warn">{s.confirmPharmacist}</span>
              </div>
            ))}
            {!!res.untranslated_terms?.length && <div className="banner">{s.untranslated}: {res.untranslated_terms.join(", ")}</div>}
            <p><strong>{res.notice_patient_lang}</strong></p>
            <a className="btn dark" href="/find?dept=pharmacy"><Icon name="map" size={18} /> {s.findPharmacy}</a>
          </div>
        )}
      </main>
    </>
  );
}
