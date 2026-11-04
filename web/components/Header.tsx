import Link from "next/link";
import Icon from "./Icon";

export default function Header({ title, back = "/", right }: { title?: string; back?: string | null; right?: React.ReactNode }) {
  return (
    <div className="bar" style={{ maxWidth: 720, margin: "0 auto", padding: "calc(10px + env(safe-area-inset-top)) 18px 0" }}>
      {back ? <Link href={back} className="icon-btn" aria-label="Back"><Icon name="back" /></Link> : <span className="brand">Medero</span>}
      {title && <span className="title">{title}</span>}
      <div className="top-right" style={{ minWidth: 48, justifyContent: "flex-end" }}>{right}</div>
    </div>
  );
}
