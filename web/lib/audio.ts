// Hands-free listening: an energy-based voice activity detector cuts the mic stream into
// utterances and hands each one over as a 16 kHz mono 16-bit WAV (the format Meta's
// transcription endpoint accepts). Audio lives only in memory until it is sent.

export type HandsFreeEvents = {
  onUtterance: (wavBase64: string, ms: number) => void;
  onLevel?: (level: number, speaking: boolean) => void;
  onError?: (message: string) => void;
};

const TARGET_RATE = 16000;
const END_SILENCE_MS = 900;
const MIN_SPEECH_MS = 350;
const MAX_UTTERANCE_MS = 15000;
const PREROLL_FRAMES = 3;

export class HandsFree {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private proc: ScriptProcessorNode | null = null;
  private src: MediaStreamAudioSourceNode | null = null;
  private frames: Float32Array[] = [];
  private preroll: Float32Array[] = [];
  private speaking = false;
  private silenceMs = 0;
  private speechMs = 0;
  private noise = 0.01;
  paused = false;

  constructor(private ev: HandsFreeEvents) {}

  get running() { return !!this.ctx; }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
    } catch {
      this.ev.onError?.("mic_denied");
      return false;
    }
    const Ctx = window.AudioContext || (window as any).webkitAudioContext;
    this.ctx = new Ctx();
    await this.ctx.resume();
    this.src = this.ctx.createMediaStreamSource(this.stream);
    this.proc = this.ctx.createScriptProcessor(2048, 1, 1);
    this.proc.onaudioprocess = (e) => this.process(e.inputBuffer.getChannelData(0));
    this.src.connect(this.proc);
    this.proc.connect(this.ctx.destination); // output stays silent; needed for the node to run
    return true;
  }

  stop() {
    this.proc?.disconnect(); this.src?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close().catch(() => {});
    this.ctx = null; this.proc = null; this.src = null; this.stream = null;
    this.frames = []; this.preroll = []; this.speaking = false;
  }

  private process(data: Float32Array) {
    if (!this.ctx) return;
    const frameMs = (data.length / this.ctx.sampleRate) * 1000;
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    const rms = Math.sqrt(sum / data.length);
    if (!this.speaking) this.noise = this.noise * 0.95 + rms * 0.05; // adapt to the room
    const threshold = Math.max(0.015, this.noise * 3);
    const loud = rms > threshold;
    this.ev.onLevel?.(Math.min(1, rms / (threshold * 3)), this.speaking);
    if (this.paused) return;

    const copy = new Float32Array(data);
    if (!this.speaking) {
      this.preroll.push(copy);
      if (this.preroll.length > PREROLL_FRAMES) this.preroll.shift();
      if (loud) {
        this.speaking = true; this.speechMs = 0; this.silenceMs = 0;
        this.frames = [...this.preroll];
      }
      return;
    }
    this.frames.push(copy);
    this.speechMs += frameMs;
    this.silenceMs = loud ? 0 : this.silenceMs + frameMs;
    if (this.silenceMs >= END_SILENCE_MS || this.speechMs >= MAX_UTTERANCE_MS) this.finish();
  }

  private finish() {
    const frames = this.frames, ms = this.speechMs - this.silenceMs, rate = this.ctx!.sampleRate;
    this.frames = []; this.preroll = []; this.speaking = false; this.silenceMs = 0; this.speechMs = 0;
    if (ms < MIN_SPEECH_MS) return;
    const wav = encodeWav(downsample(concat(frames), rate, TARGET_RATE), TARGET_RATE);
    this.ev.onUtterance(bytesToBase64(wav), ms);
  }
}

function concat(chunks: Float32Array[]): Float32Array {
  const out = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
  let o = 0;
  for (const c of chunks) { out.set(c, o); o += c.length; }
  return out;
}

function downsample(input: Float32Array, from: number, to: number): Float32Array {
  if (from === to) return input;
  const ratio = from / to, len = Math.floor(input.length / ratio), out = new Float32Array(len);
  for (let i = 0; i < len; i++) {
    const start = Math.floor(i * ratio), end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let s = 0;
    for (let j = start; j < end; j++) s += input[j];
    out[i] = s / Math.max(1, end - start);
  }
  return out;
}

export function encodeWav(samples: Float32Array, rate: number): Uint8Array {
  const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
  const str = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE"); str(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const x = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
  }
  return new Uint8Array(buf);
}

function bytesToBase64(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}
