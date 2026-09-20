const KEY = "domain-etn.session.v1";
const RECENT_KEY = "domain-etn.recent.v1";

export function loadSession() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  localStorage.setItem(KEY, JSON.stringify({ ...session, savedAt: Date.now() }));
}

export function clearSession() {
  localStorage.removeItem(KEY);
}

export function sessionFor(name) {
  const rec = loadSession();
  if (!rec || rec.name !== name) return null;
  return rec;
}

export function rememberRecent(entry) {
  const rows = loadRecent().filter((row) => row.name !== entry.name);
  rows.unshift({ ...entry, at: Date.now() });
  localStorage.setItem(RECENT_KEY, JSON.stringify(rows.slice(0, 12)));
}

export function loadRecent() {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function randomSecret() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return "0x" + [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}
