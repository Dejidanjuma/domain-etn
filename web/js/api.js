async function req(path, opts = {}) {
  const res = await fetch(path, {
    cache: "no-store",
    headers: { Accept: "application/json", ...(opts.body ? { "Content-Type": "application/json" } : {}), ...opts.headers },
    ...opts,
  });
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const err = new Error((body && body.message) || `Request failed (${res.status})`);
    err.code = body && body.error;
    err.details = body && body.details;
    err.status = res.status;
    throw err;
  }
  return body;
}

export const api = {
  contract: () => req("/api/v1/contract"),
  availability: (name) => req(`/api/v1/domains/availability?name=${encodeURIComponent(name)}`),
  quote: (name, duration) => req(`/api/v1/domains/quote?name=${encodeURIComponent(name)}&duration=${duration}`),
  profile: (name) => req(`/api/v1/domains/profile?name=${encodeURIComponent(name)}`),
  history: (name) => req(`/api/v1/domains/history?name=${encodeURIComponent(name)}`),
  discovery: () => req("/api/v1/domains/discovery"),
  catalogSearch: (q, prefix) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (prefix) params.set("prefix", prefix);
    return req(`/api/v1/domains/search?${params.toString()}`);
  },
  prepareCommit: (body) => req("/api/v1/registration/prepare-commit", { method: "POST", body: JSON.stringify(body) }),
  prepareRegister: (body) => req("/api/v1/registration/prepare-register", { method: "POST", body: JSON.stringify(body) }),
  intent: (id) => req(`/api/v1/registration/${id}`),
  commitment: (id) => req(`/api/v1/registration/${id}/commitment`),
  submitted: (id, body) => req(`/api/v1/registration/${id}/submitted`, { method: "POST", body: JSON.stringify(body) }),
  confirm: (id) => req(`/api/v1/registration/${id}/confirm`, { method: "POST" }),
  owner: (addr) => req(`/api/v1/owners/${addr}`),
  ownerDomains: (addr) => req(`/api/v1/owners/${addr}/domains`),
  renewalQuote: (name, duration) => req(`/api/v1/renewal/quote?name=${encodeURIComponent(name)}&duration=${duration}`),
  prepareRenewal: (body) => req("/api/v1/renewal/prepare", { method: "POST", body: JSON.stringify(body) }),
  renewal: (id) => req(`/api/v1/renewal/${id}`),
  renewalSubmitted: (id, body) => req(`/api/v1/renewal/${id}/submitted`, { method: "POST", body: JSON.stringify(body) }),
  renewalConfirm: (id) => req(`/api/v1/renewal/${id}/confirm`, { method: "POST" }),
  marketplace: () => req("/api/v1/marketplace"),
  marketplaceListings: () => req("/api/v1/marketplace/listings"),
  marketplaceActivity: () => req("/api/v1/marketplace/activity"),
};
