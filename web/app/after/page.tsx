"use client";
// After the visit: what the doctor said (their words only) and a short checklist.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import Icon from "@/components/Icon";
import SpeakButton from "@/components/SpeakButton";
import { api, load } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function After() {
  const router = useRouter();
  const [lang, setLang] = useState("en");
  const [summary, setSummary] = useState<any>(null);
  const [leaving, setLeaving] = useState<any>(null);
  const [bigKo, setBigKo] = useState(false);
  const [done, setDone] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState("");
  useEffect(() => {
    setLang(load("lang") || "en");
    const sid = load("sid");
    if (!sid) return;
    api(`/sessions/${sid}`).then((r) => { setSummary(r.summary); setLeaving(r.before_leaving); }).catch((e) => setErr(String(e.message || e)));
  }, []);
  const s = t(lang);
  const tick = (k: string) => setDone({ ...done, [k]: !done[k] });

  async function deleteVisit() {
    const sid = load("sid");
    if (sid) await api(`/sessions/${sid}`, { method: "DELETE" }).catch(() => {});
    try { sessionStorage.removeItem("medero.sid"); sessionStorage.removeItem("medero.card"); } catch {}
    setDone({ ...done, delete: true });
    setSummary(null);
  }

  const said: any[] = summary?.record?.doctor_said || [];
  return (
    <>
      <Header title={s.afterTitle} back="/" />
      <main className="fade-in">
        <p className="muted" style={{ marginTop: 0 }}>{s.afterHelp}</p>
        <div className="card" style={{ background: "var(--sky-soft)" }}>
          <h3>🩺 {s.doctorSaid}</h3>
          {said.length ? <ol style={{ paddingLeft: 20, margin: "8px 0 0" }}>{said.map((st, i) => <li key={i} style={{ margin: "6px 0" }}>{st.text_patient_lang}</li>)}</ol>
            : <p className="muted">{done.delete ? s.deleted : "–"}</p>}
          {summary?.notice_patient && <p className="muted" style={{ fontSize: ".85rem" }}>{summary.notice_patient}</p>}
        </div>
        {err && <div className="banner">{err}</div>}

        {leaving && !done.delete && (
          <div className="card stack" style={{ background: "var(--butter-soft, #fff7e0)" }}>
            <h3 style={{ margin: 0 }}>🧾 {s.beforeLeaving}</h3>
            <p style={{ margin: 0 }}>{s.beforeLeavingHelp}</p>
            <div className={bigKo ? "ko-big" : "ko"} lang="ko" style={{ fontWeight: 650 }}>{leaving.request_ko}</div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button className="ghost" onClick={() => setBigKo(!bigKo)}>가 {s.bigForStaff}</button>
              <SpeakButton text={leaving.request_ko} label={s.speakKo} />
            </div>
            <p className="muted" style={{ margin: 0, fontSize: ".85rem" }}>{s.yourChoice}</p>
          </div>
        )}

        <h2>✅ Checklist</h2>
        <button className={`check ${done.summary ? "done" : ""}`} onClick={() => tick("summary")}>
          <span className="box">{done.summary && <Icon name="check" size={18} />}</span><span className="label">{s.checkSummary}</span>
        </button>
        {leaving && (
          <button className={`check ${done.code ? "done" : ""}`} onClick={() => tick("code")}>
            <span className="box">{done.code && <Icon name="check" size={18} />}</span><span className="label">{s.checkCode}</span>
          </button>
        )}
        <Link className={`check ${done.rx ? "done" : ""}`} href="/prescription" onClick={() => tick("rx")}>
          <span className="box">{done.rx && <Icon name="check" size={18} />}</span><span className="label grow">{s.checkPharmacy}</span><Icon name="arrow" />
        </Link>
        <Link className={`check ${done.ins ? "done" : ""}`} href="/insurance" onClick={() => tick("ins")}>
          <span className="box">{done.ins && <Icon name="check" size={18} />}</span><span className="label grow">{s.checkInsurance}</span><Icon name="arrow" />
        </Link>
        <button className={`check ${done.delete ? "done" : ""}`} onClick={deleteVisit} disabled={done.delete}>
          <span className="box">{done.delete && <Icon name="check" size={18} />}</span><span className="label">{s.checkDelete}</span>
        </button>

        <button className="dark big" style={{ marginTop: 16 }} onClick={() => router.push("/")}>{s.backHome}</button>
      </main>
    </>
  );
}
