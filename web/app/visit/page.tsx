"use client";
import { useEffect, useRef, useState } from "react";
import EmergencyCard from "@/components/EmergencyCard";
import Header from "@/components/Header";
import { api, load, wsUrl } from "@/lib/api";
import { t } from "@/lib/i18n";

type Ev = Record<string, any>;
const CLASS_COLORS: Record<string, string> = {
  on_card: "", needs_fact: "warn", needs_decision: "warn", unclear: "danger", procedural: "",
};

export default function Visit() {
  const [lang, setLang] = useState("en");
  const [sid, setSid] = useState<string | null>(null);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [disclosure, setDisclosure] = useState<string>("");
  const [consent, setConsent] = useState<Ev | null>(null);
  const [items, setItems] = useState<Ev[]>([]);
  const [ask, setAsk] = useState<Ev | null>(null);
  const [last, setLast] = useState<Ev | null>(null);
  const [emergency, setEmergency] = useState<Ev | null>(null);
  const [summary, setSummary] = useState<Ev | null>(null);
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [big, setBig] = useState(false);
  const [simulated, setSimulated] = useState(true);
  const [recording, setRecording] = useState(false);
  const [fake, setFake] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const l = load("lang") || "en";
    const id = load("sid");
    setLang(l); setSid(id);
    api("/health").then((h) => setFake(!!h.fake_models)).catch(() => {});
    if (!id) { setStatus("closed"); return; }
    const sock = new WebSocket(wsUrl(`/sessions/${id}/visit`));
    ws.current = sock;
    sock.onopen = () => { setStatus("open"); sock.send(JSON.stringify({ type: "start" })); };
    sock.onclose = () => setStatus("closed");
    sock.onmessage = (m) => handle(JSON.parse(m.data));
    return () => sock.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [items, ask]);

  function handle(e: Ev) {
    switch (e.type) {
      case "disclosure": setDisclosure(e.text_ko); break;
      case "consent": setConsent(e); break;
      case "transcript": setItems((x) => [...x, { kind: "clinician", ...e }]); break;
      case "turn_result":
        setBusy(false); setLast(e);
        setItems((x) => [...x, { kind: "result", ...e }]);
        if (e.ask_back) setAsk({ ...e.ask_back, said: e.clinician_said_patient_lang });
        break;
      case "relay_result": setBusy(false); setItems((x) => [...x, { kind: "relay", ...e }]); break;
      case "fallback": setItems((x) => [...x, { kind: "fallback", ...e }]); break;
      case "notice": setItems((x) => [...x, { kind: "notice", ...e }]); break;
      case "asr_failed": setBusy(false); setItems((x) => [...x, { kind: "notice", text_patient: e.text_patient, error: e.error }]); break;
      case "emergency": setBusy(false); setEmergency(e.card); setAsk(null); break;
      case "summary": setSummary(e); break;
      case "error": setBusy(false); setItems((x) => [...x, { kind: "notice", text_patient: e.text_patient || e.code }]); break;
    }
  }
  const send = (m: Ev) => ws.current?.readyState === 1 && ws.current.send(JSON.stringify(m));
  const s = t(lang);

  function sendText() {
    if (!text.trim()) return;
    setBusy(true); send({ type: "clinician_text", text }); setText("");
  }
  function sendAnswer(v: string) {
    if (!ask || !v.trim()) return;
    setItems((x) => [...x, { kind: "patient", text: v, question: ask.question_patient_lang }]);
    setBusy(true); send({ type: "answer", ask_id: ask.id, text: v }); setAsk(null); setAnswer("");
  }

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (ev) => ev.data.size && chunks.current.push(ev.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        const blob = new Blob(chunks.current, { type: mr.mimeType || "audio/webm" });
        chunks.current = []; // audio is sent once and not kept
        const b64 = await blobToB64(blob);
        setBusy(true); send({ type: "audio_turn", mime: blob.type, data: b64 });
      };
      rec.current = mr; mr.start(); setRecording(true);
    } catch {
      setItems((x) => [...x, { kind: "notice", text_patient: s.typeHere }]);
    }
  }
  function stopRec() { rec.current?.state === "recording" && rec.current.stop(); setRecording(false); }

  async function del() {
    if (!sid) return;
    await api(`/sessions/${sid}`, { method: "DELETE" }).catch(() => {});
    try { sessionStorage.clear(); } catch {}
    ws.current?.close(); setDeleted(true);
  }

  const header = (
    <Header right={<>
      {simulated && <span className="badge mock">{s.simulated}</span>}
      {fake && <span className="badge danger">FAKE</span>}
      <label className="row muted" style={{ margin: 0 }}><input type="checkbox" checked={big} onChange={(e) => setBig(e.target.checked)} /> {s.bigText}</label>
      <label className="row muted" style={{ margin: 0 }}><input type="checkbox" checked={simulated} onChange={(e) => setSimulated(e.target.checked)} /> {s.simulated}</label>
    </>} />
  );

  if (deleted) return (<>{header}<main><p>{s.deleted}</p><a href="/">Medero</a></main></>);
  if (!sid) return (<>{header}<main><p>No session. <a href="/intake">{s.start}</a></p></main></>);
  if (emergency) return (<>{header}<main><EmergencyCard card={emergency as any} lang={lang} /></main></>);

  // Consent gate (guardrail 5)
  if (!consent?.accepted) {
    return (
      <>{header}
        <main className={big ? "huge stack" : "stack"}>
          <p className="muted">{s.showStaff}</p>
          {consent && !consent.accepted ? (
            <div className="card stack">
              <span className="badge warn">{s.declined}</span>
              <p className="ko-big" lang="ko">{consent.text_ko}</p>
              <p>{consent.text_patient}</p>
            </div>
          ) : (
            <div className="card stack">
              <p className="ko-big" lang="ko">{disclosure || "…"}</p>
              <div className="row">
                <button className="primary big" lang="ko" disabled={!disclosure} onClick={() => send({ type: "consent", accepted: true })}>네, 괜찮아요</button>
                <button className="big" lang="ko" disabled={!disclosure} onClick={() => send({ type: "consent", accepted: false })}>아니요</button>
              </div>
              {status === "closed" && <div className="banner">Connection closed. Is the API running?</div>}
            </div>
          )}
        </main>
      </>
    );
  }

  if (summary) {
    const record = summary.record;
    return (
      <>{header}
        <main className="stack">
          <h1>{s.summary}</h1>
          <p className="muted">{summary.notice_patient}</p>
          <div className="card">
            <ol>{record.doctor_said.map((st: Ev, i: number) => <li key={i}>{st.text_patient_lang} <span className="muted">({st.source_turn_id})</span></li>)}</ol>
          </div>
          <div className="row">
            <button className="primary" disabled={record.patient_confirmed} onClick={() => send({ type: "confirm_summary" })}>{record.patient_confirmed ? "✓" : ""} {s.confirmSummary}</button>
            <button onClick={() => setSummary(null)}>{s.back}</button>
            <a className="btn" href="/prescription">{s.prescription}</a>
            <a className="btn" href="/insurance">{s.insurance}</a>
            <button className="danger" onClick={del}>{s.deleteSession}</button>
          </div>
        </main>
      </>
    );
  }

  return (
    <>{header}
      <main className={big ? "huge" : ""}>
        <div className="visit">
          <section>
            {items.map((it, i) => <Item key={i} it={it} s={s} />)}
            {busy && <div className="muted">…</div>}
            {ask && (
              <div className="ask stack">
                <strong>{s.askTitle}</strong>
                {ask.said && <div className="muted">{s.doctorSaid}: {ask.said}</div>}
                <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>{ask.question_patient_lang}</div>
                <div className="options">
                  {(ask.options || []).map((o: string) => <button key={o} onClick={() => sendAnswer(o)}>{o}</button>)}
                </div>
                <label>{s.yourAnswer}</label>
                <div className="row">
                  <input className="grow" type="text" value={answer} onChange={(e) => setAnswer(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendAnswer(answer)} style={{ flex: 1 }} />
                  <button className="primary" onClick={() => sendAnswer(answer)}>{s.answer}</button>
                </div>
              </div>
            )}
            <div ref={endRef} />
            <div className="card stack">
              <label>{s.clinicianLine}</label>
              <div className="row">
                <input type="text" lang="ko" placeholder={s.typeHere} value={text} style={{ flex: 1 }}
                  onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendText()} />
                <button className="primary" disabled={busy || !text.trim()} onClick={sendText}>{s.send}</button>
              </div>
              <button className={`mic big ${recording ? "on" : ""}`} disabled={busy && !recording}
                onPointerDown={startRec} onPointerUp={stopRec} onPointerLeave={() => recording && stopRec()}>
                {recording ? s.recording : s.holdToTalk}
              </button>
              <button onClick={() => send({ type: "summary" })}>{s.summaryEnd}</button>
            </div>
          </section>
          <aside className="panel stack">
            <div className="card">
              <h3>Turn</h3>
              {last ? <>
                <span className={`badge ${CLASS_COLORS[last.turn_class] || ""}`}>{last.turn_class}</span>{" "}
                <span className="muted">router: {last.router}</span>
                {last.blocked && <div className="banner">{s.blocked}<br /><span className="lat">{last.blocked.reasons.join(", ")}</span></div>}
              </> : <span className="muted">–</span>}
            </div>
            <div className="card">
              <h3>{s.evidence}</h3>
              {last?.evidence?.length ? last.evidence.map((e: Ev) => (
                <div key={e.id} className="fact"><span className="badge">{e.id}</span><div className="grow">{e.value}<div className="ko" lang="ko">{e.value_ko}</div></div></div>
              )) : <span className="muted">–</span>}
            </div>
            <div className="card">
              <h3>{s.latency} (ms)</h3>
              {last?.latency_ms ? (
                <table className="lat"><tbody>
                  {["transcribe", "route", "respond", "verify", "total"].map((k) => (
                    <tr key={k}><td>{k}</td><td>{last.latency_ms[k] ?? "–"}</td></tr>
                  ))}
                  <tr><td>Meta API calls</td><td>{last.spark_calls}</td></tr>
                </tbody></table>
              ) : <span className="muted">–</span>}
            </div>
          </aside>
        </div>
      </main>
    </>
  );
}

function Item({ it, s }: { it: Ev; s: ReturnType<typeof t> }) {
  if (it.kind === "clinician") return (
    <div className="turn clinician">
      <div className="who">Clinician {it.uncertain && <span className="badge warn">uncertain</span>}</div>
      <div className="ko" lang="ko">{it.text_ko}</div>
    </div>
  );
  if (it.kind === "result") return (
    <div className="turn agent">
      {it.clinician_said_patient_lang && <div><span className="who">{s.doctorSaid}</span><div>{it.clinician_said_patient_lang}</div></div>}
      {it.reply_ko && <div style={{ marginTop: 8 }}>
        <span className="who">{s.agentSaid}</span>
        <div className="ko-big" lang="ko">{it.reply_ko}</div>
        {it.reply_patient_lang && <div className="muted">{it.reply_patient_lang}</div>}
      </div>}
      <div className="row" style={{ marginTop: 6 }}>
        <span className={`badge ${CLASS_COLORS[it.turn_class] || ""}`}>{it.turn_class}</span>
        {it.evidence?.map((e: Ev) => <span key={e.id} className="badge">{e.id}</span>)}
        {it.blocked && <span className="badge danger">blocked</span>}
        {it.confidence < 0.6 && <span className="badge warn">low confidence</span>}
        <span className="muted lat">{it.latency_ms?.total} ms</span>
      </div>
    </div>
  );
  if (it.kind === "patient") return (
    <div className="turn patient"><div className="who">Patient</div><div>{it.text}</div></div>
  );
  if (it.kind === "relay") return (
    <div className="turn agent">
      <span className="who">{s.agentSaid}</span>
      <div className="ko-big" lang="ko">{it.reply_ko}</div>
      <div className="muted">{it.reply_patient_lang}</div>
      {it.blocked && <span className="badge danger">verifier: showing your own words</span>}
    </div>
  );
  if (it.kind === "fallback") return (
    <div className="turn agent">
      <div className="banner">{it.text_patient}</div>
      <div className="ko" lang="ko">{it.note_ko}</div>
      {it.facts?.map((f: Ev) => <div key={f.id} className="ko-big" lang="ko">{f.value_ko || f.value}</div>)}
    </div>
  );
  return <div className="banner">{it.text_patient}{it.error ? ` (${it.error})` : ""}</div>;
}

function blobToB64(b: Blob): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1] || "");
    r.onerror = rej;
    r.readAsDataURL(b);
  });
}
