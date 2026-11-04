// Korean speech output with the phone's built-in voice (Web Speech API). On-device, no model call,
// no audio stored. Muse has no text-to-speech, so this is the default TTS for the demo.
// Any speech pauses hands-free listening (see setSpeakHooks) so Medero never hears itself.

let hooks: { start?: () => void; end?: () => void } = {};
export function setSpeakHooks(h: typeof hooks) { hooks = h; }

export function canSpeak() {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function koVoice(): SpeechSynthesisVoice | undefined {
  const vs = window.speechSynthesis.getVoices();
  return vs.find((v) => v.lang === "ko-KR" && v.localService) || vs.find((v) => v.lang.toLowerCase().startsWith("ko"));
}

// iOS only allows speech after a user gesture; call this from a tap before speaking programmatically.
export function unlockSpeech() {
  if (!canSpeak()) return;
  const u = new SpeechSynthesisUtterance(" ");
  u.volume = 0;
  window.speechSynthesis.speak(u);
}

export function speakKo(text: string) {
  if (!canSpeak() || !text.trim()) return false;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "ko-KR";
  const v = koVoice();
  if (v) u.voice = v;
  u.rate = 0.95;
  u.onstart = () => hooks.start?.();
  u.onend = u.onerror = () => hooks.end?.();
  synth.speak(u);
  return true;
}

export function stopSpeaking() {
  if (canSpeak()) window.speechSynthesis.cancel();
  hooks.end?.();
}
