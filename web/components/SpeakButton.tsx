"use client";
import { useEffect, useState } from "react";
import { canSpeak, speakKo } from "@/lib/speech";
import Icon from "./Icon";

export default function SpeakButton({ text, label, small }: { text: string; label: string; small?: boolean }) {
  const [ok, setOk] = useState(false);
  useEffect(() => setOk(canSpeak()), []); // checked after mount so server and client render match
  if (!ok) return null;
  return small ? (
    <button className="icon-btn speak" onClick={() => speakKo(text)} aria-label={label} title={label}><Icon name="speaker" size={18} /></button>
  ) : (
    <button className="ghost" onClick={() => speakKo(text)}><Icon name="speaker" size={18} /> {label}</button>
  );
}
