"use client";
// Static emergency card (guardrail 6). Text comes from the server's fixed copy or this fixed fallback.
type Num = { number: string; label_ko: string; label_en: string; label_th?: string };
export type EmergencyData = { title_ko: string; body_ko: string; numbers: Num[]; patient: Record<string, string> };

const FALLBACK: EmergencyData = {
  title_ko: "응급 상황입니다",
  body_ko: "이 환자는 응급 증상을 말했습니다. 바로 도와주세요.",
  numbers: [
    { number: "119", label_ko: "구급차 (통역 가능)", label_en: "Ambulance (interpretation available)", label_th: "รถพยาบาล (มีล่าม)" },
    { number: "1339", label_ko: "의료 정보 상담", label_en: "Medical information line", label_th: "สายข้อมูลทางการแพทย์" },
  ],
  patient: {
    en: "This may be an emergency. Call 119 now (ambulance, interpretation available), or show this screen to anyone nearby.",
    th: "นี่อาจเป็นเหตุฉุกเฉิน โทร 119 ทันที (รถพยาบาล มีล่าม) หรือแสดงหน้าจอนี้ให้คนใกล้ตัวดู",
  },
};

export default function EmergencyCard({ card, lang }: { card?: EmergencyData | null; lang: string }) {
  const c = card || FALLBACK;
  return (
    <div className="emergency" role="alert">
      <h1 lang="ko">{c.title_ko}</h1>
      <p lang="ko" className="ko-big">{c.body_ko}</p>
      <p>{c.patient[lang] || c.patient.en}</p>
      <div className="em-numbers">
        {c.numbers.map((n) => (
          <a key={n.number} href={`tel:${n.number}`} className="em-call">
            <strong>{n.number}</strong>
            <span lang="ko">{n.label_ko}</span>
            <span>{lang === "th" ? n.label_th || n.label_en : n.label_en}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
