"use client";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { API_BASE } from "@/lib/api";

// Minimal markdown renderer for eval/results/latest.md (headings, lists, tables, bold, code).
function inline(s: string): React.ReactNode[] {
  return s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((p, i) =>
    p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : p.startsWith("`") ? <code key={i}>{p.slice(1, -1)}</code> : p);
}
function render(md: string) {
  const out: React.ReactNode[] = [];
  const lines = md.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!/^\|[-| ]+\|$/.test(lines[i])) rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim()));
        i++;
      }
      i--;
      out.push(<div className="md-wrap" key={i}><table className="md"><thead><tr>{rows[0].map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead>
        <tbody>{rows.slice(1).map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody></table></div>);
    } else if (l.startsWith("### ")) out.push(<h3 key={i}>{inline(l.slice(4))}</h3>);
    else if (l.startsWith("## ")) out.push(<h2 key={i}>{inline(l.slice(3))}</h2>);
    else if (l.startsWith("# ")) out.push(<h1 key={i}>{inline(l.slice(2))}</h1>);
    else if (l.startsWith("- ")) out.push(<li key={i}>{inline(l.slice(2))}</li>);
    else if (l.startsWith("> ")) out.push(<div key={i} className="banner">{inline(l.slice(2))}</div>);
    else if (l.trim()) out.push(<p key={i}>{inline(l)}</p>);
  }
  return out;
}

export default function Results() {
  const [md, setMd] = useState<string | null>(null);
  useEffect(() => { fetch(API_BASE + "/eval/latest").then((r) => r.text()).then(setMd).catch(() => setMd("API not reachable.")); }, []);
  return (<><Header right={<span className="badge mock">MOCK DATA</span>} /><main>{md === null ? <p className="muted">…</p> : render(md)}</main></>);
}
