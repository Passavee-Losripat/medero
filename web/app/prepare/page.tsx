"use client";
// "What are you feeling" -> a few quick questions -> what Medero may tell the doctor -> visit.
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import EmergencyCard from "@/components/EmergencyCard";
import Header from "@/components/Header";
import Icon from "@/components/Icon";
import WhereToGo from "@/components/WhereToGo";
import { CaseCard, Fact, allFacts, postJson, save } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Profile, loadProfile } from "@/lib/profile";

const NONE_TEXT: Record<string, { allergy: string; meds: string }> = {
  en: { allergy: "no known allergies", meds: "no regular medication" },
  th: { allergy: "ไม่มีประวัติแพ้", meds: "ไม่ได้ใช้ยาประจำ" },
};
const lines = (x: string) => x.split("\n").map((v) => v.trim()).filter(Boolean);

export default function Prepare() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [feeling, setFeeling] = useState("");
  const [onset, setOnset] = useState("");
  const [severity, setSeverity] = useState("");
  const [site, setSite] = useState("");
  const [tried, setTried] = useState("");
  const [step, setStep] = useState<"ask" | "review">("ask");
  const [card, setCard] = useState<CaseCard | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [emergency, setEmergency] = useState<any>(null);

  useEffect(() => {
    const p = loadProfile();
    if (!p) { router.replace("/"); return; }
    setProfile(p);
    try { setFeeling(sessionStorage.getItem("medero.feeling") || ""); } catch {}
    if (p.mock) { // MOCK demo persona: pre-fill the red-eyes story
      setFeeling((f) => f || "Both eyes are red and itchy");
      setOnset("Saturday morning, the day after swimming at an indoor pool");
      setSeverity("itching 6 out of 10, no strong pain");
      setSite("both eyes, left one is worse");
      setTried("artificial tears from a convenience store, 3 times a day");
    }
  }, [router]);
  if (!profile) return null;
  const s = t(profile.lang);
  const none = NONE_TEXT[profile.lang] || NONE_TEXT.en;

  async function build() {
    setBusy(true); setErr("");
    try {
      const res = await postJson("/intake", {
        patient_language: profile!.lang, alias: profile!.alias || "Patient", chief_complaint: feeling,
        onset, severity, site, duration: null,
        tried: lines(tried), history: lines(profile!.conditions),
        allergies: profile!.allergiesNone ? none.allergy : profile!.allergies || null,
        medications: profile!.medicationsNone ? none.meds : profile!.medications || null,
        insurance_type: profile!.insurance_type,
      });
      if (res.emergency) { setEmergency(res.card); return; }
      save("sid", res.session_id);
      setCard(res.card);
      setChecked(Object.fromEntries(allFacts(res.card).filter((f: Fact) => f.value).map((f: Fact) => [f.id, true])));
      setStep("review");
    } catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  }

  async function approve() {
    setBusy(true); setErr("");
    try {
      const ids = Object.entries(checked).filter(([, v]) => v).map(([k]) => k);
      const res = await postJson(`/sessions/${sessionStorage.getItem("medero.sid")}/approve`, { approved_ids: ids });
      sessionStorage.setItem("medero.card", JSON.stringify(res.card));
      router.push("/visit");
    } catch (e: any) { setErr(String(e.message || e)); setBusy(false); }
  }

  if (emergency) return (<><Header /><main><EmergencyCard card={emergency} lang={profile.lang} /></main></>);

  if (step === "review" && card) return (
    <>
      <Header title={s.reviewTitle} back={null} right={<button className="icon-btn" onClick={() => setStep("ask")} aria-label={s.back}><Icon name="back" /></button>} />
      <main className="fade-in">
        <p className="muted" style={{ marginTop: 0 }}>{s.reviewHelp}</p>
        <div className="card">
          {allFacts(card).map((f) => (
            <label className="fact" key={f.id}>
              <input type="checkbox" disabled={!f.value} checked={!!f.value && !!checked[f.id]}
                onChange={(e) => setChecked({ ...checked, [f.id]: e.target.checked })} aria-label={f.id} />
              <div className="grow">
                <div className="muted" style={{ fontSize: ".85rem" }}>{factLabel(f.id, s)}</div>
                {f.value ? <div>{f.value}</div> : <div className="unknown">{s.willAsk}</div>}
              </div>
            </label>
          ))}
        </div>
        <WhereToGo text={[feeling, site].filter(Boolean).join(" ")} lang={profile.lang} title={s.whereToGo} model />
        {err && <div className="banner">{err}</div>}
        <button className="dark big cta" disabled={busy} onClick={approve}>
          {busy ? s.thinking : s.startTalking}<span className="arrow"><Icon name="arrow" /></span>
        </button>
      </main>
    </>
  );

  const chipRow = (opts: string, value: string, set: (v: string) => void) => (
    <div className="chips">
      {opts.split("|").map((o) => (
        <button key={o} type="button" className={`chip ${value === o ? "on" : ""}`} onClick={() => set(value === o ? "" : o)}>{o}</button>
      ))}
    </div>
  );
  return (
    <>
      <Header title={s.quickTitle} />
      <main className="fade-in">
        <p className="muted" style={{ marginTop: 0 }}>{s.quickHelp}</p>
        <div className="card stack" style={{ background: "var(--mint-soft)" }}>
          <label htmlFor="feel">{s.feeling1} {s.feeling2}</label>
          <input id="feel" type="text" value={feeling} placeholder={s.feelingPh} onChange={(e) => setFeeling(e.target.value)} />
        </div>
        <div className="card stack">
          <div><label>{s.whenQ}</label>{chipRow(s.whenOpts, onset, setOnset)}
            {onset && !s.whenOpts.split("|").includes(onset) && <input type="text" style={{ marginTop: 8 }} value={onset} onChange={(e) => setOnset(e.target.value)} />}
          </div>
          <div><label>{s.severityQ}</label>{chipRow(s.severityOpts, severity, setSeverity)}
            {severity && !s.severityOpts.split("|").includes(severity) && <input type="text" style={{ marginTop: 8 }} value={severity} onChange={(e) => setSeverity(e.target.value)} />}
          </div>
          <div><label htmlFor="site">{s.whereQ}</label><input id="site" type="text" value={site} onChange={(e) => setSite(e.target.value)} /></div>
          <div><label htmlFor="tried">{s.triedQ}</label><input id="tried" type="text" value={tried} onChange={(e) => setTried(e.target.value)} /></div>
        </div>
        {err && <div className="banner">{err}</div>}
        <button className="dark big cta" disabled={busy || !feeling.trim()} onClick={build}>
          {s.next}<span className="arrow"><Icon name="arrow" /></span>
        </button>
      </main>
    </>
  );
}

function factLabel(id: string, s: ReturnType<typeof t>): string {
  const map: Record<string, string> = { cc: s.cc, sym_onset: s.onset, sym_duration: s.duration, sym_site: s.site,
    sym_severity: s.severity, allergy: s.allergies, meds: s.medications };
  if (map[id]) return map[id];
  if (id.startsWith("tried_")) return s.triedQ;
  if (id.startsWith("hx_")) return s.conditionsQ;
  return s.otherSymptoms.split("(")[0];
}
