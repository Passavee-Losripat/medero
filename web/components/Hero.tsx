// Original welcome illustration: two speech bubbles (Korean and the patient's language)
// joined by a care heart, with soft sparkles.
export default function Hero() {
  return (
    <svg viewBox="0 0 320 240" width="100%" style={{ maxWidth: 360, display: "block", margin: "0 auto" }} role="img"
      aria-label="Two speech bubbles, one Korean and one English, with a heart">
      <defs>
        <linearGradient id="hb1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#8b7cf6" /><stop offset="1" stopColor="#5b4bdb" /></linearGradient>
        <linearGradient id="hb2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#7fe0b8" /><stop offset="1" stopColor="#2fae84" /></linearGradient>
        <linearGradient id="hh" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ff9fb6" /><stop offset="1" stopColor="#e8507a" /></linearGradient>
      </defs>
      <ellipse cx="160" cy="150" rx="140" ry="44" fill="none" stroke="#c9c0fb" strokeWidth="5" opacity=".7" />
      <path d="M58 52h104a26 26 0 0 1 26 26v38a26 26 0 0 1-26 26H98l-26 22 4-22h-18a26 26 0 0 1-26-26V78a26 26 0 0 1 26-26z" fill="url(#hb1)" />
      <text x="110" y="112" textAnchor="middle" fontSize="40" fontWeight="800" fill="#fff" fontFamily="Apple SD Gothic Neo, Noto Sans KR, sans-serif">안녕</text>
      <path d="M262 92H164a26 26 0 0 0-26 26v34a26 26 0 0 0 26 26h56l26 20-4-20h20a26 26 0 0 0 26-26v-34a26 26 0 0 0-26-26z" fill="url(#hb2)" />
      <text x="216" y="148" textAnchor="middle" fontSize="36" fontWeight="800" fill="#fff" fontFamily="ui-rounded, system-ui, sans-serif">Hi!</text>
      <path d="M160 214s-22-13-22-29a12 12 0 0 1 22-7 12 12 0 0 1 22 7c0 16-22 29-22 29z" fill="url(#hh)" />
      <g fill="#f6c445">
        <path d="M262 34l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" />
        <path d="M36 168l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" />
        <path d="M288 196l2.5 6 6 2.5-6 2.5-2.5 6-2.5-6-6-2.5 6-2.5z" opacity=".8" />
      </g>
      <path d="M232 40c-20 2-30 14-32 30" fill="none" stroke="#b8aef7" strokeWidth="3" strokeDasharray="4 7" strokeLinecap="round" />
    </svg>
  );
}
