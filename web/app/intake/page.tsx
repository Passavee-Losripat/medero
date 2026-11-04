"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import EmergencyCard from "@/components/EmergencyCard";
import Header from "@/components/Header";
import { api, load, postJson, save } from "@/lib/api";
import { t } from "@/lib/i18n";

type Form = {
  alias: string; chief_complaint: string; onset: string; duration: string; site: string; severity: string;
  other_symptoms: string; tried: string; history: string; allergies: string; medications: string;
  allergiesNone: boolean; medicationsNone: boolean; insurance_type: string;
};
const EMPTY: Form = {
  alias: "", chief_complaint: "", onset: "", duration: "", site: "", severity: "", other_symptoms: "", tried: "",
  history: "", allergies: "", medications: "", allergiesNone: false, medicationsNone: false, insurance_type: "unknown",
};
const NONE_TEXT: Record<string, { allergy: string; meds: string }> = {
  en: { allergy: "no known allergies", meds: "no regular medication" },
  th: { allergy: "ไม่มีประวัติแพ้", meds: "ไม่ได้ใช้ยาประจำ" },
};
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

export default function Intake() {
  const router = useRouter();
  const [lang, setLang] = useState("en");
  const [f, setF] = useState<Form>(EMPTY);
  const [demo, setDemo] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [emergency, setEmergency] = useState<any>(null);

  useEffect(() => {
    const l = load("lang") || "en";
    setLang(l);
    if (new URLSearchParams(window.location.search).get("demo")) {
      setDemo(true);
      api("/demo/case").then((d) => {
        setLang(d.patient_language); save("lang", d.patient_language);
        setF({
          ...EMPTY, alias: d.alias, chief_complaint: d.chief_complaint, onset: d.onset || "", duration: d.duration || "",
          site: d.site || "", severity: d.severity || "", other_symptoms: (d.other_symptoms || []).join("\n"),
          tried: (d.tried || []).join("\n"), history: (d.history || []).join("\n"), allergies: d.allergies || "",
          medications: d.medications || "", insurance_type: d.insurance_type || "unknown",
        });
      }).catch((e) => setErr(String(e.message || e)));
    }
  }, []);
  const s = t(lang);
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });

  async function submit() {
    setBusy(true); setErr("");
    const none = NONE_TEXT[lang] || NONE_TEXT.en;
    try {
      const res = await postJson("/intake", {
        patient_language: lang, alias: f.alias || "Patient", chief_complaint: f.chief_complaint,
        onset: f.onset, duration: f.duration, site: f.site, severity: f.severity,
        other_symptoms: lines(f.other_symptoms), tried: lines(f.tried), history: lines(f.history),
        allergies: f.allergiesNone ? none.allergy : f.allergies || null,
        medications: f.medicationsNone ? none.meds : f.medications || null,
        insurance_type: f.insurance_type,
      });
      if (res.emergency) { setEmergency(res.card); return; }
      save("sid", res.session_id); save("lang", lang);
      sessionStorage.setItem("medero.card", JSON.stringify(res.card));
      router.push("/card");
    } catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  }

  if (emergency) return (<><Header /><main><EmergencyCard card={emergency} lang={lang} /></main></>);

  const text = (k: keyof Form, label: string, hint = true) => (
    <div>
      <label>{label} {hint && <span className="muted">({s.unknownHint})</span>}</label>
      <input type="text" value={f[k] as string} onChange={set(k)} />
    </div>
  );
  return (
    <>
      <Header right={demo ? <span className="badge mock">DEMO · MOCK</span> : null} />
      <main className="stack narrow">
        <h1>{s.intakeTitle}</h1>
        <p className="muted">{s.intakeHelp}</p>
        <div className="card stack">
          {text("alias", s.alias, false)}
          <div><label>{s.cc}</label><input type="text" value={f.chief_complaint} onChange={set("chief_complaint")} /></div>
          {text("onset", s.onset)}{text("duration", s.duration)}{text("site", s.site)}{text("severity", s.severity)}
          <div><label>{s.otherSymptoms}</label><textarea value={f.other_symptoms} onChange={set("other_symptoms")} /></div>
          <div><label>{s.tried}</label><textarea value={f.tried} onChange={set("tried")} /></div>
          <div><label>{s.history}</label><textarea value={f.history} onChange={set("history")} /></div>
          <div>
            <label>{s.allergies} <span className="muted">({s.unknownHint})</span></label>
            <input type="text" value={f.allergies} onChange={set("allergies")} disabled={f.allergiesNone} />
            <label className="row muted"><input type="checkbox" checked={f.allergiesNone} onChange={set("allergiesNone")} /> {s.noneKnown}</label>
          </div>
          <div>
            <label>{s.medications} <span className="muted">({s.unknownHint})</span></label>
            <input type="text" value={f.medications} onChange={set("medications")} disabled={f.medicationsNone} />
            <label className="row muted"><input type="checkbox" checked={f.medicationsNone} onChange={set("medicationsNone")} /> {s.noneKnown}</label>
          </div>
          <div>
            <label id="ins-label">{s.insuranceType}</label>
            <div className="choices" role="radiogroup" aria-labelledby="ins-label">
              {Object.entries(s.ins).map(([k, v]) => (
                <label key={k} className="choice">
                  <input type="radio" name="insurance_type" value={k} checked={f.insurance_type === k}
                    onChange={() => setF({ ...f, insurance_type: k })} />
                  <span className="dot" aria-hidden="true" />{v}
                </label>
              ))}
            </div>
          </div>
        </div>
        {err && <div className="banner">{err}</div>}
        <button className="primary big" disabled={busy || !f.chief_complaint.trim()} onClick={submit}>{s.next}</button>
      </main>
    </>
  );
}
