import Link from "next/link";
export default function Header({ right }: { right?: React.ReactNode }) {
  return (
    <header className="top">
      <Link href="/" className="brand">Medero</Link>
      <div className="top-right">{right}</div>
    </header>
  );
}
