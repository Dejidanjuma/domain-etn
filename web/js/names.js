const LABEL_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export function parseName(raw) {
  const text = (raw || "").trim();
  if (!text) return { ok: false, code: "empty", message: "Enter a .etn name." };
  if (/\s/.test(text)) return { ok: false, code: "invalid_domain", message: "Names cannot contain spaces." };
  if ([...text].some((ch) => ch.charCodeAt(0) > 127)) {
    return { ok: false, code: "invalid_domain", message: "Non-ASCII names are not supported." };
  }
  const lowered = text.toLowerCase();
  let label;
  if (lowered.endsWith(".etn")) {
    const parts = lowered.split(".");
    if (parts.length !== 2) {
      return { ok: false, code: "invalid_domain", message: "Only 2LD names like example.etn can be registered here." };
    }
    label = parts[0];
  } else if (lowered.includes(".")) {
    return { ok: false, code: "invalid_domain", message: "Only .etn names can be registered here." };
  } else {
    label = lowered;
  }
  if (!LABEL_RE.test(label)) {
    return { ok: false, code: "invalid_domain", message: "Use lowercase letters, numbers, and inner hyphens." };
  }
  if (label.length < 3) {
    return { ok: false, code: "invalid_domain", message: "Names need at least 3 characters." };
  }
  if (label.length > 63) {
    return { ok: false, code: "invalid_domain", message: "That label is too long." };
  }
  return { ok: true, label, name: `${label}.etn`, display: `${label}.etn` };
}
