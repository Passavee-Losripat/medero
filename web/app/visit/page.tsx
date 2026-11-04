"use client";
// The visit: a conversation. Medero listens hands-free; Korean speech is the doctor, anything
// else is the patient. Questions only the patient can answer appear as a lilac card.
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import EmergencyCard from "@/components/EmergencyCard";
import Icon from "@/components/Icon";
import { load, wsUrl } from "@/lib/api";
import { HandsFree } from "@/lib/audio";
import SpeakButton from "@/components/SpeakButton";
import { canSpeak, setSpeakHooks, speakKo, stopSpeaking, unlockSpeech } from "@/lib/speech";
import { t } from "@/lib/i18n";

type Ev = Record<string, any>;
type Phase = "off" | "listening" | "hearing";

export default function Visit() {
  const router = useRouter();
  const [lang, setLang] = useState("en");
  const [sid, setSid] = useState<string | null>(null);
  const [closed, setClosed] = useState(false);
  const [disclosure, setDisclosure] = useState("");
  const [consent, setConsent] = useState<Ev | null>(null);
  const [items, setItems] = useState<Ev[]>([]);
  const [ask, setAsk] = useState<Ev | null>(null);
  const [last, setLast] = useState<Ev | null>(null);
  const [emergency, setEmergency] = useState<Ev | null>(null);
  const [phase, setPhase] = useState<Phase>("off");
  const [pending, setPending] = useState(0);
  const [level, setLevel] = useState(0);
  const [typing, setTyping] = useState<null | "doctor" | "me">(null);
  const [text, setText] = useState("");
  const [hood, setHood] = useState(false);
  const [big, setBig] = useState(false);
  const [micError, setMicError] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const hf = useRef<HandsFree | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const [voice, setVoice] = useState(false);
  const voiceRef = useRef(false);   // read inside the socket handler, which keeps the first render's closure
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // while the phone speaks Korean, hands-free listening pauses so the reply is not heard as the doctor
    setSpeakHooks({
      start: () => { if (resumeTimer.current) clearTimeout(resumeTimer.current); if (hf.current) hf.current.paused = true; },
      end: () => { resumeTimer.current = setTimeout(() => { if (hf.current) hf.current.paused = false; }, 500); },
    });
    const on = canSpeak();
    setVoice(on); voiceRef.current = on;
    return () => { setSpeakHooks({}); stopSpeaking(); };
  }, []);

  useEffect(() => {
    setLang(load("lang") || "en");
    const id = load("sid");
    setSid(id);
    if (!id) return;
    const sock = new WebSocket(wsUrl(`/sessions/${id}/visit`));
    ws.current = sock;
    sock.onopen = () => sock.send(JSON.stringify({ type: "start" }));
    // only the live socket counts (React dev mode mounts twice and closes the first one)
    sock.onclose = () => { if (ws.current === sock) setClosed(true); };
    sock.onmessage = (m) => handle(JSON.parse(m.data));
    return () => { sock.close(); hf.current?.stop(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [items, ask, pending]);

  const done = () => setPending((n) => Math.max(0, n - 1));
  function handle(e: Ev) {
    switch (e.type) {
      case "disclosure": setDisclosure(e.text_ko); break;
      case "consent": setConsent(e); break;
      case "transcript": setItems((x) => [...x, { kind: "doctor_raw", ...e }]); break;
      case "patient_heard": setItems((x) => [...x, { kind: "you", text: e.text }]); break;
      case "turn_result":
        done(); setLast(e);
        if (voiceRef.current && e.reply_ko) speakKo(e.reply_ko);
        setItems((x) => [...x, { kind: "result", ...e }]);
        setAsk(e.ask_back ? { ...e.ask_back, said: e.clinician_said_patient_lang } : null);
        break;
      case "relay_result": done(); setAsk(null); if (voiceRef.current && e.reply_ko) speakKo(e.reply_ko); setItems((x) => [...x, { kind: "relay", ...e }]); break;
      case "fallback": setItems((x) => [...x, { kind: "fallback", ...e }]); break;
      case "notice": setItems((x) => [...x, { kind: "note", text: e.text_patient }]); break;
      case "asr_failed": done(); if (!e.silent) setItems((x) => [...x, { kind: "note", text: e.text_patient }]); break;
      case "emergency": done(); setEmergency(e.card); hf.current?.stop(); break;
      case "error": done(); setItems((x) => [...x, { kind: "note", text: e.text_patient || e.code }]); break;
    }
  }
  const send = (m: Ev) => { if (ws.current?.readyState === 1) { ws.current.send(JSON.stringify(m)); return true; } return false; };
  const s = t(lang);

  function toggleVoice() {
    const on = !voice;
    setVoice(on); voiceRef.current = on;
    if (on) unlockSpeech(); else stopSpeaking();
  }
  function consentTap(accepted: boolean) {
    unlockSpeech();
    send({ type: "consent", accepted });
  }

  async function toggleListen() {
    unlockSpeech();
    if (hf.current?.running) { hf.current.stop(); hf.current = null; setPhase("off"); setLevel(0); return; }
    const h = new HandsFree({
      onUtterance: (b64) => { if (send({ type: "utterance", data: b64 })) setPending((n) => n + 1); },
      onLevel: (lv, speaking) => { setLevel(lv); setPhase(speaking ? "hearing" : "listening"); },
      onError: () => setMicError(true),
    });
    if (await h.start()) { hf.current = h; setPhase("listening"); setMicError(false); }
  }
  function sendTyped() {
    const v = text.trim();
    if (!v) return;
    if (typing === "doctor") { if (send({ type: "clinician_text", text: v })) setPending((n) => n + 1); }
    else {
      setItems((x) => [...x, { kind: "you", text: v }]);
      if (ask) { if (send({ type: "answer", ask_id: ask.id, text: v })) setPending((n) => n + 1); }
      else if (send({ type: "patient_text", text: v })) setPending((n) => n + 1);
    }
    setText("");
  }
  function answer(v: string) {
    if (!ask) return;
    setItems((x) => [...x, { kind: "you", text: v }]);
    if (send({ type: "answer", ask_id: ask.id, text: v })) setPending((n) => n + 1);
    setAsk(null);
  }
  function endVisit() { hf.current?.stop(); router.push("/after"); }

  if (!sid) return <main><p>No visit yet. <a href="/">{s.backHome}</a></p></main>;
  if (emergency) return <main className="fade-in"><EmergencyCard card={emergency as any} lang={lang} /></main>;

  // Consent gate (guardrail 5): shown to staff first.
  if (!consent?.accepted) return (
    <main className={`fade-in ${big ? "huge" : ""}`}>
      <div className="bar">
        <button className="icon-btn" onClick={() => router.push("/")} aria-label={s.back}><Icon name="back" /></button>
        <span className="title">{s.staffTitle}</span>
        <button className={`icon-btn ${big ? "on" : ""}`} onClick={() => setBig(!big)} aria-label={s.bigText}><span lang="ko" style={{ fontWeight: 800 }}>가</span></button>
      </div>
      <p className="muted center">{s.showStaff}</p>
      <div className="card stack" style={{ background: "var(--mint)", padding: 24 }}>
        <span className="badge" style={{ background: "var(--surface)" }}>AI · Medero</span>
        <p className="ko-big" lang="ko" style={{ margin: 0 }}>{consent && !consent.accepted ? consent.text_ko : disclosure || "…"}</p>
        {disclosure && <div><SpeakButton text={consent && !consent.accepted ? consent.text_ko : disclosure} label={s.speakKo} /></div>}
        {consent && !consent.accepted ? <p>{consent.text_patient}</p> : (
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <button className="dark big" lang="ko" disabled={!disclosure} onClick={() => consentTap(true)}>네, 괜찮아요</button>
            <button className="big" lang="ko" disabled={!disclosure} onClick={() => consentTap(false)}>아니요</button>
          </div>
        )}
      </div>
      {closed && <div className="banner">Connection closed. Is the API running?</div>}
    </main>
  );

  const label = phase === "off" ? s.tapToStart : pending ? s.thinking : phase === "hearing" ? s.hearing : s.listening;
  return (
    <main className={`fade-in ${big ? "huge" : ""}`} style={{ paddingBottom: 0 }}>
      <div className="bar">
        <button className="icon-btn" onClick={endVisit} aria-label={s.endVisit}><Icon name="back" /></button>
        <span className="title">{s.tileVisit}</span>
        <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
          <button className={`icon-btn ${big ? "on" : ""}`} onClick={() => setBig(!big)} aria-label={s.bigText}><span lang="ko" style={{ fontWeight: 800 }}>가</span></button>
          <button className={`icon-btn ${voice ? "on" : ""}`} onClick={toggleVoice} aria-label={s.voiceToggle} aria-pressed={voice}><Icon name={voice ? "speaker" : "mute"} /></button>
          <button className={`icon-btn ${hood ? "on" : ""}`} onClick={() => setHood(!hood)} aria-label={s.hood}><Icon name="info" /></button>
        </div>
      </div>
      <div className="row" style={{ justifyContent: "center", marginBottom: 8 }}>
        <span className="badge mock">{s.simulated} · MOCK</span>
      </div>

      {hood && <Hood last={last} s={s} />}

      <div className="chat">
        {items.length === 0 && !ask && <div className="msg note">{s.tapToStart} · {s.typeDoctor}</div>}
        {items.map((it, i) => <Bubble key={i} it={it} s={s} />)}
        {ask && (
          <div className="ask-card fade-in">
            <span className="badge lilac" style={{ background: "var(--surface)" }}>{s.askTitle}</span>
            {ask.said && <div className="muted" style={{ marginTop: 8 }}>{s.doctorSaid}: {ask.said}</div>}
            <div className="q">{ask.question_patient_lang}</div>
            <div className="chips">
              {(ask.options || []).map((o: string) => <button key={o} className="chip" onClick={() => answer(o)}>{o}</button>)}
            </div>
            <div className="hint">🎙 {s.orSay}</div>
          </div>
        )}
        {pending > 0 && <div className="msg note">{s.thinking}</div>}
        <div ref={endRef} />
      </div>

      <div className="dock">
        {micError && <div className="banner">{s.micDenied}</div>}
        {typing && (
          <div className="card flat" style={{ margin: "0 0 10px", padding: 12, background: "var(--surface)" }}>
            <div className="seg" style={{ marginBottom: 8 }}>
              <button className={typing === "doctor" ? "on" : ""} onClick={() => setTyping("doctor")}>{s.typeDoctor}</button>
              <button className={typing === "me" ? "on" : ""} onClick={() => setTyping("me")}>{s.typeMe}</button>
            </div>
            <div className="typing">
              <input type="text" autoFocus lang={typing === "doctor" ? "ko" : undefined} value={text}
                placeholder={typing === "doctor" ? "예: 며칠 됐어요?" : s.yourAnswer}
                onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendTyped()} />
              <button className="primary" onClick={sendTyped} disabled={!text.trim()}>{s.send}</button>
            </div>
          </div>
        )}
        <div className="row" style={{ justifyContent: "center", marginBottom: 8 }}>
          <button className="chip" onClick={() => { unlockSpeech(); if (send({ type: "ask_repeat" })) setPending((n) => n + 1); }}>
            🔁 {s.askRepeat}
          </button>
        </div>
        <div className="dock-inner">
          <button className={`icon-btn ${typing ? "on" : ""}`} onClick={() => setTyping(typing ? null : "doctor")} aria-label="Keyboard"><Icon name="keyboard" /></button>
          <button className={`mic-big ${phase === "off" ? "off" : ""}`} onClick={toggleListen} aria-label={label}>
            {phase !== "off" && <span className="mic-ring" style={{ transform: `scale(${1 + level * 0.35})` }} />}
            <Icon name={phase === "off" ? "mic" : "stop"} size={34} />
          </button>
          <button className="icon-btn" onClick={endVisit} aria-label={s.endVisit}><Icon name="check" /></button>
        </div>
        <div className={`dock-label ${phase !== "off" ? "live" : ""}`}>{label}</div>
      </div>
    </main>
  );
}

function Bubble({ it, s }: { it: Ev; s: ReturnType<typeof t> }) {
  if (it.kind === "doctor_raw") return (
    <div className="msg doctor fade-in">
      <div className="who">🩺 {s.doctor}{it.uncertain && <span className="badge warn">uncertain</span>}</div>
      <div className="ko" lang="ko">{it.text_ko}</div>
    </div>
  );
  if (it.kind === "result") return (
    <>
      {it.clinician_said_patient_lang && (
        <div className="msg doctor fade-in">
          <div className="who">{s.doctorSaid}</div>
          <div className="gloss">{it.clinician_said_patient_lang}</div>
          {it.gloss_check?.length > 0 && <div className="badge warn" style={{ marginTop: 6, whiteSpace: "normal" }}>⚠ {s.glossWarn}</div>}
        </div>
      )}
      {it.reply_ko && (
        <div className="msg medero fade-in">
          <div className="who">Medero · {s.toldDoctor}
            {it.evidence?.length > 0 && <span className="badge" style={{ background: "var(--surface)" }}>✓ {s.fromCard}</span>}
            {it.blocked && <span className="badge warn">verifier</span>}
            <SpeakButton small text={it.reply_ko} label={s.speakKo} />
          </div>
          <div className="ko-big" lang="ko">{it.reply_ko}</div>
          {it.reply_patient_lang && <div className="muted" style={{ marginTop: 4 }}>{it.reply_patient_lang}</div>}
        </div>
      )}
    </>
  );
  if (it.kind === "you") return (
    <div className="msg you fade-in"><div className="who">{s.youSaid}</div><div>{it.text}</div></div>
  );
  if (it.kind === "relay") return (
    <div className="msg medero fade-in">
      <div className="who">Medero · {s.toldDoctor}{it.blocked && <span className="badge warn">your own words</span>}<SpeakButton small text={it.reply_ko} label={s.speakKo} /></div>
      <div className="ko-big" lang="ko">{it.reply_ko}</div>
      {it.reply_patient_lang && <div className="muted" style={{ marginTop: 4 }}>{it.reply_patient_lang}</div>}
    </div>
  );
  if (it.kind === "fallback") return (
    <div className="msg note fade-in">
      <div>{it.text_patient}</div>
      <div className="ko" lang="ko">{it.note_ko}</div>
      {it.facts?.map((f: Ev) => <div key={f.id} className="ko-big" lang="ko">{f.value_ko || f.value}</div>)}
    </div>
  );
  return <div className="msg note fade-in">{it.text}</div>;
}

function Hood({ last, s }: { last: Ev | null; s: ReturnType<typeof t> }) {
  return (
    <div className="card hood fade-in">
      <h3>{s.hood}</h3>
      {!last ? <span className="muted">–</span> : (
        <div className="stack">
          <div className="row">
            <span className={`badge ${last.turn_class === "on_card" || last.turn_class === "procedural" ? "" : "warn"}`}>{last.turn_class}</span>
            <span className="muted">router: {last.router}</span>
            {last.blocked && <span className="badge danger">blocked: {last.blocked.reasons.join(", ")}</span>}
          </div>
          {last.evidence?.length > 0 && (
            <div>{last.evidence.map((e: Ev) => <div key={e.id}><span className="badge">{e.id}</span> {e.value} <span className="ko" lang="ko">{e.value_ko}</span></div>)}</div>
          )}
          <table><tbody>
            {["transcribe", "route", "respond", "verify", "total"].map((k) => <tr key={k}><td>{k}</td><td>{last.latency_ms?.[k] ?? "–"} ms</td></tr>)}
            <tr><td>Meta API calls</td><td>{last.spark_calls}</td></tr>
          </tbody></table>
        </div>
      )}
    </div>
  );
}
