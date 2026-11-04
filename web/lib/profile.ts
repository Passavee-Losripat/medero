// Health basics, filled once. Kept only on this device (localStorage) and sent to the API
// only when a visit starts. Never a real name: the display name is an alias.

export type Profile = {
  alias: string;
  lang: string;
  allergies: string;        // "" = unknown (will be asked)
  allergiesNone: boolean;   // patient says "I have none"
  medications: string;
  medicationsNone: boolean;
  conditions: string;       // one per line
  insurance_type: string;
  mock?: boolean;
};

export const EMPTY_PROFILE: Profile = {
  alias: "", lang: "en", allergies: "", allergiesNone: false, medications: "", medicationsNone: false,
  conditions: "", insurance_type: "unknown",
};

export const SAMPLE_PROFILE: Profile = {
  alias: "Mali", lang: "en", allergies: "", allergiesNone: false, medications: "", medicationsNone: true,
  conditions: "wears soft contact lenses daily", insurance_type: "travel", mock: true,
};

const KEY = "medero.profile";

export function loadProfile(): Profile | null {
  try {
    const v = localStorage.getItem(KEY);
    return v ? { ...EMPTY_PROFILE, ...JSON.parse(v) } : null;
  } catch { return null; }
}

export function saveProfile(p: Profile) {
  try { localStorage.setItem(KEY, JSON.stringify(p)); } catch {}
}

export function clearProfile() {
  try { localStorage.removeItem(KEY); } catch {}
}

export function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}
