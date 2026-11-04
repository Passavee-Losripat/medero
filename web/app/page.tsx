"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Hero from "@/components/Hero";
import Icon from "@/components/Icon";
import { api, save } from "@/lib/api";
import { LANGS, t } from "@/lib/i18n";
import { EMPTY_PROFILE, Profile, SAMPLE_PROFILE, loadProfile, saveProfile } from "@/lib/profile";

export default function Start() {
  const [ready, setReady] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  useEffect(() => {
    // /?demo=1 loads the MOCK persona so a judge can try the flow without filling anything in
    if (new URLSearchParams(window.location.search).get("demo")) saveProfile({ ...SAMPLE_PROFILE });
    setProfile(loadProfile()); setReady(true);
  }, []);
  if (!ready) return null;
  return profile ? <Home profile={profile} /> : <Welcome />;
}

function Welcome() {
  const router = useRouter();
  const [lang, setLang] = useState("en");
  const s = t(lang);
  function go() {
    save("lang", lang);
    saveProfile({ ...EMPTY_PROFILE, lang });
    router.push("/profile?first=1");
  }
  return (
    <main className="welcome fade-in">
      <div>
        <div className="row between" style={{ marginTop: 8 }}>
          <span className="brand"><img src="/logo.png" alt="" />Medero</span>
          <div className="seg" role="group" aria-label={s.language}>
            {LANGS.map((l) => (
              <button key={l.code} className={l.code === lang ? "on" : ""} onClick={() => setLang(l.code)}>{l.label}</button>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 28 }}><Hero /></div>
      </div>
      <div>
        <div className="row" style={{ gap: 14 }}>
          <img src="/logo.png" alt="Medero logo" width={64} height={64} style={{ borderRadius: 16 }} />
          <h1 className="brand-big">Medero</h1>
        </div>
        <p className="tagline" style={{ fontSize: "1.2rem", margin: "6px 0 10px", fontWeight: 650 }}>
          <span>{s.welcome1}</span><br /><span>{s.welcome2}</span>
        </p>
        <p className="muted">{s.welcomeBody}</p>
        <div className="steps-dots" aria-hidden="true"><i className="on" /><i /><i /></div>
        <button className="dark big cta" onClick={go}>
          {s.getStarted}<span className="arrow"><Icon name="arrow" /></span>
        </button>
        <p className="center" style={{ margin: "10px 0 0" }}><a href="/?demo=1">✨ {s.demo}</a></p>
        <p className="muted center" style={{ fontSize: ".85rem" }}>{s.notAdvice}</p>
      </div>
    </main>
  );
}

function Home({ profile }: { profile: Profile }) {
  const router = useRouter();
  const s = t(profile.lang);
  const [feeling, setFeeling] = useState("");
  const [apiDown, setApiDown] = useState(false);
  useEffect(() => {
    save("lang", profile.lang);
    api("/health").catch(() => setApiDown(true));
  }, [profile.lang]);
  const h = new Date().getHours();
  const greet = h < 12 ? s.greetMorning : h < 18 ? s.greetAfternoon : s.greetEvening;

  function startVisit() {
    try { sessionStorage.setItem("medero.feeling", feeling.trim()); } catch {}
    router.push("/prepare");
  }
  return (
    <main className="fade-in">
      <div className="bar">
        <div className="row" style={{ gap: 12 }}>
          <span className="avatar">{(profile.alias || "?").slice(0, 1).toUpperCase()}</span>
          <div>
            <div className="muted" style={{ fontSize: ".9rem" }}>{greet}</div>
            <div style={{ fontWeight: 750, fontSize: "1.1rem" }}>{profile.alias || "—"}{profile.mock && <span className="badge mock" style={{ marginLeft: 6 }}>MOCK</span>}</div>
          </div>
        </div>
        <Link href="/profile" className="icon-btn" aria-label={s.editProfile}><Icon name="user" /></Link>
      </div>

      {apiDown && <div className="banner">API not reachable from this device. On a phone, open https://&lt;mac-ip&gt;:8000/health once and accept the warning.</div>}

      <h1 style={{ fontSize: "2.2rem", marginTop: 18 }}>{s.feeling1}<br /><span className="soft">{s.feeling2}</span></h1>
      <p className="muted" style={{ marginTop: 0 }}>{s.hereToHelp}</p>

      <form className="ask-input" onSubmit={(e) => { e.preventDefault(); startVisit(); }}>
        <input type="text" value={feeling} onChange={(e) => setFeeling(e.target.value)} placeholder={s.feelingPh} aria-label={s.feeling1} />
        <button type="submit" className="primary" style={{ width: 52, height: 52, padding: 0, flex: "none" }} aria-label={s.next}>
          <Icon name="arrow" />
        </button>
      </form>

      <div className="tiles" style={{ marginTop: 22 }}>
        <button className="tile mint" onClick={startVisit}>
          <span className="tile-icon"><Icon name="chat" /></span>
          <strong>{s.tileVisit}</strong><small>{s.tileVisitSub}</small>
          <span className="go"><Icon name="arrow" size={18} /></span>
        </button>
        <Link className="tile lilac" href="/prescription">
          <span className="tile-icon"><Icon name="pill" /></span>
          <strong>{s.tileRx}</strong><small>{s.tileRxSub}</small>
          <span className="go"><Icon name="arrow" size={18} /></span>
        </Link>
        <Link className="tile butter" href="/insurance">
          <span className="tile-icon"><Icon name="doc" /></span>
          <strong>{s.tileIns}</strong><small>{s.tileInsSub}</small>
          <span className="go"><Icon name="arrow" size={18} /></span>
        </Link>
        <div className="tile blush disabled" aria-disabled="true">
          <span className="tile-icon"><Icon name="map" /></span>
          <strong>{s.tileMap}</strong><small>{s.tileMapSub}</small>
        </div>
      </div>

      <p className="muted center" style={{ marginTop: 26, fontSize: ".85rem" }}>
        {s.notAdvice} · <Link href="/results">{s.results}</Link>
      </p>
    </main>
  );
}
