const YEAR = 365 * 24 * 3600;
const DAY = 24 * 3600;

export const DURATIONS = [
  { label: "28 days", seconds: 28 * DAY },
  { label: "1 year", seconds: YEAR },
  { label: "2 years", seconds: 2 * YEAR },
  { label: "5 years", seconds: 5 * YEAR },
];

export function formatEtn(wei) {
  try {
    const value = BigInt(wei || "0");
    const whole = value / 10n ** 18n;
    const frac = (value % 10n ** 18n).toString().padStart(18, "0").replace(/0+$/, "");
    if (!frac) return `${whole.toString()} ETN`;
    const short = frac.slice(0, 6).replace(/0+$/, "");
    return `${whole.toString()}.${short} ETN`;
  } catch {
    return "—";
  }
}

export function formatDuration(seconds) {
  const n = Number(seconds);
  if (!Number.isFinite(n) || n <= 0) return "—";
  if (n % YEAR === 0) {
    const y = n / YEAR;
    return y === 1 ? "1 year" : `${y} years`;
  }
  const days = Math.round(n / DAY);
  return days === 1 ? "1 day" : `${days} days`;
}

export function shortAddr(addr) {
  if (!addr) return "—";
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export function explorerTx(hash) {
  return `https://blockexplorer.electroneum.com/tx/${hash}`;
}

export function explorerAddr(addr) {
  return `https://blockexplorer.electroneum.com/address/${addr}`;
}

export function formatTime(unix) {
  if (!unix) return "—";
  return new Date(Number(unix) * 1000).toLocaleString();
}

export function formatRelative(unix, now = Date.now() / 1000) {
  if (!unix) return "—";
  const delta = Number(unix) - Number(now);
  const abs = Math.abs(delta);
  const days = Math.round(abs / DAY);
  if (days < 1) {
    const hours = Math.max(1, Math.round(abs / 3600));
    return delta >= 0 ? `in ${hours}h` : `${hours}h ago`;
  }
  if (days < 60) return delta >= 0 ? `in ${days} days` : `${days} days ago`;
  const years = (days / 365).toFixed(1).replace(/\.0$/, "");
  return delta >= 0 ? `in ${years} years` : `${years} years ago`;
}

export function mmss(total) {
  const s = Math.max(0, Math.ceil(Number(total) || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

export function toHexValue(wei) {
  const n = BigInt(wei || "0");
  return "0x" + n.toString(16);
}

export { YEAR };
