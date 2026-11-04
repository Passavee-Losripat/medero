"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { save } from "@/lib/api";
import { t } from "@/lib/i18n";
import { EMPTY_PROFILE, Profile, SAMPLE_PROFILE, clearProfile, loadProfile, saveProfile } from "@/lib/profile";

type Tri = "none" | "unsure" | "yes";

export default function ProfilePage() {
  const router = useRouter();
  const [p, setP] = useState<Profile>(EMPTY_PROFILE);
  const [allergy, setAllergy] = useState<Tri>("unsure");
  const [meds, setMeds] = useState<Tri>("unsure");
  useEffect(() => {
    const cur = loadProfile() || EMPTY_PROFILE;
    setP(cur);
    setAllergy(cur.allergiesNone ? "none" : cur.allergies ? "yes" : "unsure");
    setMeds(cur.medicationsNone ? "none" : cur.medications ? "yes" : "unsure");
  }, []);
  const s = t(p.lang);

  function fillSample() {
    const sample = { ...SAMPLE_PROFILE, lang: p.lang };
    setP(sample); setAllergy("unsure"); setMeds("none");
  }
  function submit() {
    const out: Profile = {
      ...p,
      allergiesNone: allergy === "none", allergies: allergy === "yes" ? p.allergies : "",
      medicationsNone: meds === "none", medications: meds === "yes" ? p.medications : "",
    };
    saveProfile(out); save("lang", out.lang);
    router.push("/");
  }
  const tri = (value: Tri, set: (v: Tri) => void, name: string) => (
    <div className="chips" role="radiogroup">
      {(["none", "unsure", "yes"] as Tri[]).map((v) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} className={`chip ${value === v ? "on" : ""}`}
          onClick={() => set(v)} name={name}>
          {v === "none" ? s.optNone : v === "unsure" ? s.optUnsure : s.optYes}
        </button>
      ))}
    </div>
  );

  return (
    <>
      <Header title={s.profileTitle} />
      <main className="fade-in">
        <p className="muted" style={{ marginTop: 0 }}>{s.profileHelp}</p>
        <button className="ghost" onClick={fillSample}>✨ {s.sample}</button>

        <div className="card stack">
          <div>
            <label htmlFor="alias">{s.nameQ}</label>
            <input id="alias" type="text" value={p.alias} placeholder={s.namePh} onChange={(e) => setP({ ...p, alias: e.target.value })} />
          </div>
          <div>
            <label>{s.allergyQ}</label>
            {tri(allergy, setAllergy, "allergy")}
            {allergy === "yes" && <input type="text" style={{ marginTop: 8 }} value={p.allergies} onChange={(e) => setP({ ...p, allergies: e.target.value })} />}
            {allergy === "unsure" && <p className="muted" style={{ margin: "6px 0 0" }}>{s.willAsk}</p>}
          </div>
          <div>
            <label>{s.medsQ}</label>
            {tri(meds, setMeds, "meds")}
            {meds === "yes" && <input type="text" style={{ marginTop: 8 }} value={p.medications} onChange={(e) => setP({ ...p, medications: e.target.value })} />}
          </div>
          <div>
            <label htmlFor="cond">{s.conditionsQ}</label>
            <textarea id="cond" value={p.conditions} placeholder={s.conditionsPh} onChange={(e) => setP({ ...p, conditions: e.target.value })} />
          </div>
        </div>

        <div className="card">
          <label id="ins-label">{s.insuranceType}</label>
          <div className="choices" role="radiogroup" aria-labelledby="ins-label">
            {Object.entries(s.ins).map(([k, v]) => (
              <label key={k} className="choice">
                <input type="radio" name="insurance_type" value={k} checked={p.insurance_type === k}
                  onChange={() => setP({ ...p, insurance_type: k })} />
                <span className="dot" aria-hidden="true" />{v}
              </label>
            ))}
          </div>
        </div>

        <button className="dark big" onClick={submit} disabled={!p.alias.trim()}>{s.saveContinue}</button>
        <p className="center"><button className="ghost danger" style={{ marginTop: 14 }} onClick={() => { clearProfile(); router.push("/"); }}>{s.deleteProfile}</button></p>
      </main>
    </>
  );
}
