"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { CaseCard, FACT_LABELS, allFacts, load, postJson } from "@/lib/api";
import { t } from "@/lib/i18n";

function labelFor(id: string, s: ReturnType<typeof t>): string {
  const key = FACT_LABELS[id] as keyof typeof s | undefined;
  if (key && typeof s[key] === "string") return s[key] as string;
  if (id.startsWith("sym_")) return s.otherSymptoms.split("(")[0].trim();
  if (id.startsWith("tried_")) return s.tried.split("(")[0].trim();
  if (id.startsWith("hx_")) return s.history.split("(")[0].trim();
  return id;
}

export default function CardPage() {
  const router = useRouter();
  const [lang, setLang] = useState("en");
  const [card, setCard] = useState<CaseCard | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [approved, setApproved] = useState<{ card: CaseCard; untranslated_terms: string[]; error?: string; fake_models?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    setLang(load("lang") || "en");
    try {
      const c = JSON.parse(sessionStorage.getItem("medero.card") || "null") as CaseCard | null;
      if (c) {
        setCard(c);
        setChecked(Object.fromEntries(allFacts(c).filter((f) => f.value).map((f) => [f.id, true])));
      }
    } catch {}
  }, []);
  const s = t(lang);
  if (!card) return (<><Header /><main><p>No case card. <a href="/intake">{s.start}</a></p></main></>);

  async function approve() {
    setBusy(true); setErr("");
    try {
      const ids = Object.entries(checked).filter(([, v]) => v).map(([k]) => k);
      const res = await postJson(`/sessions/${load("sid")}/approve`, { approved_ids: ids });
      setApproved(res);
      sessionStorage.setItem("medero.card", JSON.stringify(res.card));
    } catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  }

  const facts = allFacts(approved?.card || card);
  return (
    <>
      <Header right={<span className="badge">{card.alias}</span>} />
      <main className="stack narrow">
        <h1>{s.cardTitle}</h1>
        <p className="muted">{s.cardHelp}</p>
        <div className="card">
          {facts.map((f) => (
            <label className="fact" key={f.id} style={{ fontWeight: 400, margin: 0 }}>
              <input type="checkbox" aria-label={f.id} disabled={!f.value || !!approved}
                checked={!!f.value && !!checked[f.id]} onChange={(e) => setChecked({ ...checked, [f.id]: e.target.checked })} />
              <div className="grow">
                <div className="muted">{labelFor(f.id, s)}</div>
                {f.value ? <div>{f.value}</div> : <div className="unknown">{s.willAsk}</div>}
                {approved && f.approved && f.value_ko && (
                  <div className="ko" lang="ko">{f.value_ko}</div>
                )}
              </div>
            </label>
          ))}
        </div>
        <div className="card">
          <div className="muted">{s.insuranceType}</div>
          <div>{s.ins[card.insurance_type] || card.insurance_type}</div>
          <div className="muted" style={{ marginTop: 8 }}>Always asked to you: {card.must_ask.join(", ")}</div>
        </div>
        {approved?.fake_models && <div className="banner">{s.fakeModels}</div>}
        {approved?.error && <div className="banner">Korean rendering failed ({approved.error}). Facts will be relayed after you confirm them in the visit.</div>}
        {!!approved?.untranslated_terms?.length && (
          <div className="banner">{s.untranslated}: {approved.untranslated_terms.join(", ")}</div>
        )}
        {err && <div className="banner">{err}</div>}
        {!approved
          ? <button className="primary big" disabled={busy} onClick={approve}>{s.approve}</button>
          : <button className="primary big" onClick={() => router.push("/visit")}>{s.startVisit}</button>}
      </main>
    </>
  );
}
