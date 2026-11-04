// Small inline icon set (original strokes), sized by font-size.
type Name = "mic" | "keyboard" | "arrow" | "back" | "pill" | "doc" | "map" | "chat" | "heart" | "check" | "info" | "user" | "stop" | "trash" | "home" | "camera" | "image";

const PATHS: Record<Name, React.ReactNode> = {
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></>,
  keyboard: <><rect x="3" y="6" width="18" height="12" rx="3" /><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10" /></>,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  back: <path d="M19 12H5M11 6l-6 6 6 6" />,
  pill: <><rect x="3" y="8" width="18" height="8" rx="4" transform="rotate(-35 12 12)" /><path d="M9.5 8.5l5 7" /></>,
  doc: <><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></>,
  map: <><path d="M12 21s-6-5.3-6-11a6 6 0 0 1 12 0c0 5.7-6 11-6 11z" /><circle cx="12" cy="10" r="2.2" /></>,
  chat: <><path d="M4 5h16v10H9l-5 4z" /><path d="M8 9h8M8 12h5" /></>,
  heart: <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />,
  check: <path d="M5 12.5l4.5 4.5L19 7" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  stop: <rect x="7" y="7" width="10" height="10" rx="2" />,
  trash: <path d="M4 7h16M10 7V4h4v3M6 7l1 13h10l1-13" />,
  home: <path d="M4 11l8-7 8 7v9h-5v-6H9v6H4z" />,
  camera: <><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="3" /><circle cx="9" cy="9.5" r="1.8" /><path d="M21 16l-5-5-9 9" /></>,
};

export default function Icon({ name, size = 22 }: { name: Name; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{PATHS[name]}</svg>
  );
}
