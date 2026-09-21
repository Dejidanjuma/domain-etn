import { api } from "./api.js";
import { reduce, createState, Phase, userCopy, isSuccess } from "./flow.js";
import { parseName } from "./names.js";
import { DURATIONS, formatDuration, formatEtn, formatTime, formatRelative, mmss, shortAddr, explorerTx, explorerAddr } from "./format.js";
import { connect, hasWallet, onWalletChange, sendPrepared, switchToElectroneum, getAccounts, chainId as walletChain, isElectroneum } from "./wallet.js";
import { saveSession, sessionFor, clearSession, randomSecret, rememberRecent, loadRecent } from "./storage.js";
import { lifecycleOf, historyRows, relatedAddresses } from "./lifecycle.js";

const main = document.getElementById("main");
const live = document.getElementById("live");
const walletBtn = document.getElementById("wallet-btn");
const netPill = document.getElementById("net-pill");

let state = createState();
let waitTimer = null;
let confirmTimer = null;

function setState(action) {
  state = reduce(state, action);
  persist();
  render();
}

function persist() {
  if (!state.name || !state.intent) return;
  if (state.phase === Phase.IDLE) return;
  saveSession({
    name: state.name,
    label: state.label,
    phase: state.phase,
    intentId: state.intent && state.intent.intent_id,
    secret: state.secret,
    registrant: state.wallet.address,
    duration: state.duration,
    commitTxHash: state.intent && state.intent.commit_tx_hash,
    registerTxHash: state.intent && state.intent.register_tx_hash,
  });
}

function announce(text) {
  if (live) live.textContent = text || "";
}

function setMeta(title, description) {
  document.title = title;
  const meta = document.querySelector('meta[name="description"]');
  if (meta && description) meta.setAttribute("content", description);
  const og = document.querySelector('meta[property="og:title"]');
  if (og) og.setAttribute("content", title);
}

function route() {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  if (path === "/") return { view: "home" };
  if (path === "/me") return { view: "me" };
  if (path === "/discover") return { view: "discover" };
  if (path === "/market") return { view: "market" };
  const domain = path.match(/^\/d\/(.+)$/);
  if (domain) return { view: "domain", name: decodeURIComponent(domain[1]) };
  const owner = path.match(/^\/w\/(0x[a-fA-F0-9]{40})$/);
  if (owner) return { view: "owner", address: owner[1] };
  return { view: "home" };
}

function go(path) {
  if (location.pathname !== path) history.pushState({}, "", path);
  boot();
}

window.addEventListener("popstate", boot);
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-link]");
  if (!a || a.target === "_blank") return;
  const href = a.getAttribute("href") || a.getAttribute("data-link");
  if (!href || href.startsWith("http")) return;
  ev.preventDefault();
  go(href);
});

walletBtn.addEventListener("click", async () => {
  try {
    const w = await connect();
    setState({ type: "WALLET", wallet: w });
    if (!isElectroneum(w.chainId)) {
      setState({ type: "WRONG_NETWORK", chainId: w.chainId });
    }
  } catch (err) {
    setState({ type: "ERROR", error: err.message, phase: Phase.WALLET_DISCONNECTED });
  }
});

onWalletChange(async (evt) => {
  if (evt.type === "accounts") {
    const address = (evt.accounts || [])[0] || null;
    setState({ type: "WALLET", wallet: { address, chainId: state.wallet.chainId } });
  }
  if (evt.type === "chain") {
    setState({ type: "WALLET", wallet: { address: state.wallet.address, chainId: evt.chainId } });
  }
});

async function hydrateWallet() {
  if (!hasWallet()) return;
  try {
    const accounts = await getAccounts();
    const id = await walletChain();
    if (accounts[0]) setState({ type: "WALLET", wallet: { address: accounts[0], chainId: id } });
  } catch {
    /* browsing does not require a wallet */
  }
}

async function boot() {
  const r = route();
  if (r.view !== "domain") {
    clearInterval(waitTimer);
    clearInterval(confirmTimer);
  }
  markNav(r.view);
  if (r.view === "home") {
    if (!state.name) state = { ...state, phase: Phase.IDLE };
    render();
    return;
  }
  if (r.view === "me" || r.view === "discover" || r.view === "market" || r.view === "owner") {
    render();
    return;
  }
  if (r.view === "domain") {
    await openName(r.name);
  }
}

function markNav(view) {
  document.querySelectorAll("[data-nav]").forEach((el) => {
    const on = el.getAttribute("data-nav") === view;
    if (on) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
}

async function openName(raw) {
  const parsed = parseName(raw);
  if (!parsed.ok) {
    setState({ type: "INVALID", error: parsed.message });
    render();
    return;
  }
  setState({ type: "SEARCH_START", query: raw, name: parsed.name, label: parsed.label });
  announce(userCopy(state));
  try {
    const profile = await api.profile(parsed.name);
    if (profile.available) {
      setState({ type: "AVAILABLE", profile });
      await loadQuote(parsed.name, state.duration);
      await maybeResume(parsed.name);
    } else {
      setState({ type: "REGISTERED_PROFILE", profile });
    }
  } catch (err) {
    setState({ type: "ERROR", error: err.message, phase: Phase.BACKEND_ERROR });
  }
}

async function loadQuote(name, duration) {
  setState({ type: "QUOTE_LOADING" });
  try {
    const quote = await api.quote(name, duration);
    setState({ type: "QUOTE", quote });
  } catch (err) {
    if (err.code === "unavailable_domain") {
      const profile = await api.profile(name);
      setState({ type: "REGISTERED_PROFILE", profile });
      return;
    }
    setState({ type: "ERROR", error: err.message, phase: Phase.QUOTE_ERROR });
  }
}

async function maybeResume(name) {
  const saved = sessionFor(name);
  if (!saved || !saved.intentId) return;
  setState({ type: "RECOVERING", name, secret: saved.secret, intent: { intent_id: saved.intentId } });
  try {
    const intent = await api.intent(saved.intentId);
    state = { ...state, intent, secret: saved.secret };
    if (intent.status === "confirmed") {
      setState({ type: "CONFIRMED", intent });
      return;
    }
    if (intent.register_tx_hash) {
      setState({ type: "REGISTER_SUBMITTED", intent });
      pollConfirm();
      return;
    }
    if (intent.commit_tx_hash) {
      setState({ type: "COMMIT_SUBMITTED", intent });
      await waitForCommitment();
      return;
    }
    if (intent.commit_tx) {
      setState({ type: "COMMIT_READY", intent, secret: saved.secret });
    }
  } catch (err) {
    if (err.status === 404) {
      setState({
        type: "ERROR",
        phase: Phase.RECOVERING,
        error: "The previous registration session is no longer on the server. If you already sent a transaction, wait and search the name. A transaction hash is not success by itself.",
      });
      return;
    }
    setState({ type: "ERROR", error: err.message });
  }
}

async function startRegister() {
  if (!state.wallet.address) {
    setState({ type: "ERROR", error: "Connect a wallet to register.", phase: Phase.WALLET_DISCONNECTED });
    return;
  }
  if (!isElectroneum(state.wallet.chainId)) {
    setState({ type: "WRONG_NETWORK", chainId: state.wallet.chainId });
    return;
  }
  if (!state.quote || Date.now() / 1000 > state.quote.expires_at) {
    setState({ type: "QUOTE_EXPIRED" });
    return;
  }
  const secret = state.secret || randomSecret();
  setState({ type: "COMMIT_PREPARING" });
  try {
    const intent = await api.prepareCommit({
      name: state.name,
      quote_token: state.quote.quote_token,
      registrant: state.wallet.address,
      secret,
      duration: state.duration,
    });
    setState({ type: "COMMIT_READY", intent, secret });
    await signCommit();
  } catch (err) {
    setState({ type: "ERROR", error: err.message, phase: Phase.BACKEND_ERROR });
  }
}

async function signCommit() {
  setState({ type: "COMMIT_SIGNING" });
  announce("Waiting for wallet confirmation…");
  try {
    const hash = await sendPrepared(state.intent.commit_tx);
    const intent = await api.submitted(state.intent.intent_id, { kind: "commit", tx_hash: hash });
    setState({ type: "COMMIT_SUBMITTED", intent });
    await waitForCommitment();
  } catch (err) {
    if (err.code === "USER_REJECTED") setState({ type: "USER_REJECTED", error: err.message });
    else if (err.code === "INSUFFICIENT_FUNDS") setState({ type: "INSUFFICIENT", error: err.message });
    else setState({ type: "ERROR", error: err.message, phase: Phase.RPC_ERROR });
  }
}

async function waitForCommitment() {
  clearInterval(waitTimer);
  const tick = async () => {
    try {
      const age = await api.commitment(state.intent.intent_id);
      if (age.expired) {
        clearInterval(waitTimer);
        setState({ type: "FAILED", error: "The reservation expired. Start again." });
        return;
      }
      if (age.ready) {
        clearInterval(waitTimer);
        setState({ type: "WAIT", remaining: 0, total: age.min_commitment_age_sec });
        await prepareRegister();
        return;
      }
      const remaining = age.committed ? age.seconds_remaining : age.min_commitment_age_sec;
      setState({ type: "WAIT", remaining, total: age.min_commitment_age_sec });
    } catch (err) {
      setState({ type: "WAIT", remaining: state.waitRemaining, total: 60 });
      state = { ...state, error: err.message };
      render();
    }
  };
  await tick();
  waitTimer = setInterval(tick, 4000);
}

async function prepareRegister() {
  setState({ type: "REGISTER_PREPARING" });
  try {
    const intent = await api.prepareRegister({ intent_id: state.intent.intent_id, secret: state.secret });
    setState({ type: "REGISTER_READY", intent });
  } catch (err) {
    if (err.code === "commitment_not_mature") {
      setState({ type: "WAIT", remaining: (err.details && err.details.seconds_remaining) || 5, total: 60 });
      waitTimer = setTimeout(waitForCommitment, 3000);
      return;
    }
    setState({ type: "ERROR", error: err.message, phase: Phase.BACKEND_ERROR });
  }
}

async function signRegister() {
  setState({ type: "REGISTER_SIGNING" });
  announce("Confirm payment in your wallet…");
  try {
    const hash = await sendPrepared(state.intent.register_tx);
    const intent = await api.submitted(state.intent.intent_id, { kind: "register", tx_hash: hash });
    setState({ type: "REGISTER_SUBMITTED", intent });
    pollConfirm();
  } catch (err) {
    if (err.code === "USER_REJECTED") setState({ type: "USER_REJECTED", error: err.message });
    else if (err.code === "INSUFFICIENT_FUNDS") setState({ type: "INSUFFICIENT", error: err.message });
    else setState({ type: "ERROR", error: err.message, phase: Phase.RPC_ERROR });
  }
}

async function pollConfirm() {
  clearInterval(confirmTimer);
  setState({ type: "CONFIRMING" });
  const tick = async () => {
    try {
      const intent = await api.confirm(state.intent.intent_id);
      if (intent.status === "confirmed") {
        clearInterval(confirmTimer);
        setState({ type: "CONFIRMED", intent });
        rememberRecent({ name: intent.name, tx: intent.register_tx_hash, owner: intent.registrant });
        clearSession();
        return;
      }
      if (intent.status === "failed") {
        clearInterval(confirmTimer);
        setState({ type: "FAILED", intent, error: intent.note });
        return;
      }
      setState({ type: "REGISTER_SUBMITTED", intent });
    } catch (err) {
      setState({ type: "ERROR", error: err.message, phase: Phase.BACKEND_ERROR });
    }
  };
  await tick();
  confirmTimer = setInterval(tick, 4000);
}

async function startRenew() {
  if (!state.wallet.address) {
    setState({ type: "ERROR", error: "Connect a wallet to renew.", phase: Phase.WALLET_DISCONNECTED });
    return;
  }
  if (!isElectroneum(state.wallet.chainId)) {
    setState({ type: "WRONG_NETWORK", chainId: state.wallet.chainId });
    return;
  }
  try {
    const quote = await api.renewalQuote(state.name, state.duration);
    setState({ type: "RENEW_QUOTE", quote });
    const intent = await api.prepareRenewal({
      name: state.name,
      quote_token: quote.quote_token,
      payer: state.wallet.address,
      duration: state.duration,
    });
    setState({ type: "RENEW_READY", intent });
  } catch (err) {
    setState({ type: "ERROR", error: err.message, phase: Phase.BACKEND_ERROR });
  }
}

async function signRenew() {
  setState({ type: "RENEW_SIGNING" });
  try {
    const hash = await sendPrepared(state.renewal.renew_tx);
    const intent = await api.renewalSubmitted(state.renewal.intent_id, { tx_hash: hash });
    setState({ type: "RENEW_SUBMITTED", intent });
    const tick = async () => {
      const confirmed = await api.renewalConfirm(intent.intent_id);
      if (confirmed.status === "confirmed") {
        setState({ type: "RENEWED", intent: confirmed });
        const profile = await api.profile(state.name);
        setState({ type: "REGISTERED_PROFILE", profile });
        return;
      }
      if (confirmed.status === "failed") {
        setState({ type: "FAILED", error: confirmed.note });
        return;
      }
      setTimeout(tick, 4000);
    };
    tick();
  } catch (err) {
    if (err.code === "USER_REJECTED") setState({ type: "USER_REJECTED", error: err.message });
    else if (err.code === "INSUFFICIENT_FUNDS") setState({ type: "INSUFFICIENT", error: err.message });
    else setState({ type: "ERROR", error: err.message, phase: Phase.RPC_ERROR });
  }
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&")
    .replace(/</g, "<")
    .replace(/>/g, ">")
    .replace(/"/g, """);
}

function domainTitle(name) {
  const [label, tld] = String(name || "").split(".");
  return `<span>${esc(label)}</span><span class="tld">.${esc(tld || "etn")}</span>`;
}

function steps() {
  const order = [
    ["Search", [Phase.IDLE, Phase.CHECKING, Phase.AVAILABLE, Phase.QUOTE_READY, Phase.QUOTE_LOADING]],
    ["Reserve", [Phase.COMMIT_PREPARING, Phase.COMMIT_READY, Phase.COMMIT_SIGNING, Phase.COMMIT_SUBMITTED]],
    ["Wait", [Phase.WAITING_FOR_COMMITMENT]],
    ["Pay", [Phase.REGISTER_PREPARING, Phase.REGISTER_READY, Phase.REGISTER_SIGNING, Phase.REGISTER_SUBMITTED, Phase.CONFIRMING]],
    ["Done", [Phase.REGISTERED_SUCCESSFULLY]],
  ];
  const idx = order.findIndex(([, phases]) => phases.includes(state.phase));
  return `<ol class="steps">${order
    .map(([label], i) => `<li class="${i === idx ? "now" : i < idx ? "done" : ""}">${label}</li>`)
    .join("")}</ol>`;
}

function renderWalletChrome() {
  if (state.wallet.address) {
    walletBtn.textContent = shortAddr(state.wallet.address);
    walletBtn.setAttribute("aria-label", `Connected wallet ${state.wallet.address}`);
    if (!isElectroneum(state.wallet.chainId)) {
      netPill.hidden = false;
      netPill.classList.add("warn");
      netPill.textContent = "Wrong network";
    } else {
      netPill.hidden = false;
      netPill.classList.remove("warn");
      netPill.textContent = "Electroneum";
    }
  } else {
    walletBtn.textContent = "Connect wallet";
    walletBtn.setAttribute("aria-label", "Connect wallet");
    netPill.hidden = true;
  }
}

function searchForm(autofill = "") {
  return `
    <form class="search" id="search-form" role="search">
      <label class="sr-only" for="q">Search a .etn domain</label>
      <input id="q" name="q" value="${esc(autofill)}" placeholder="satoshi.etn" autocomplete="off" spellcheck="false" />
      <button class="btn" type="submit">Search</button>
    </form>
    <div class="examples">
      <button type="button" data-ex="satoshi.etn">satoshi.etn</button>
      <button type="button" data-ex="nakamoto.etn">nakamoto.etn</button>
      <button type="button" data-ex="wallet.etn">wallet.etn</button>
    </div>`;
}

function bindSearch() {
  const form = document.getElementById("search-form");
  if (!form) return;
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const raw = form.q.value;
    const parsed = parseName(raw);
    if (!parsed.ok) {
      setState({ type: "INVALID", error: parsed.message });
      render();
      return;
    }
    go(`/d/${parsed.name}`);
  });
  document.querySelectorAll("[data-ex]").forEach((btn) => {
    btn.addEventListener("click", () => go(`/d/${btn.getAttribute("data-ex")}`));
  });
}

function durationPicker() {
  return `<div class="duration" role="group" aria-label="Registration duration">${DURATIONS.map(
    (d) => `<button type="button" data-dur="${d.seconds}" aria-pressed="${d.seconds === state.duration}">${d.label}</button>`
  ).join("")}</div>`;
}

function errorBox() {
  if (!state.error) return "";
  return `<div class="err" role="alert">${esc(state.error)}</div>`;
}

function homeView() {
  setMeta("DOMAIN.etn — Find your .etn name", "Search, register, and renew .etn names on Electroneum with your own wallet.");
  return `
    <section class="hero">
      <p class="kicker">Electroneum names</p>
      <h1>Find your <span class="tld">.etn</span> name</h1>
      <p class="lede">Search a name, see the live price, then register it with your own wallet. DOMAIN.etn never holds your keys or your ETN.</p>
      ${searchForm()}
      ${errorBox()}
      <p class="note home-links">Looking up a registered name? Open its profile. Or <a href="/discover" data-link>browse indexed names</a>.</p>
    </section>`;
}

function quoteCard() {
  const q = state.quote;
  if (!q) return `<p class="note">${esc(userCopy(state))}</p>`;
  return `
    <div class="card">
      <div class="grid">
        <div class="metric"><label>Duration</label><b>${esc(formatDuration(q.duration))}</b></div>
        <div class="metric"><label>Base</label><b>${esc(formatEtn(q.price.base))}</b></div>
        <div class="metric"><label>Premium</label><b>${esc(formatEtn(q.price.premium))}</b></div>
        <div class="metric"><label>Total</label><b>${esc(formatEtn(q.price.total))}</b></div>
      </div>
      ${durationPicker()}
      <p class="note">Live chain price. Not a reservation. You pay the official Electroneum registrar, not DOMAIN.etn.</p>
      <div class="cta-row">
        <button class="btn" id="register-btn" type="button">Register</button>
      </div>
    </div>`;
}

function availableView() {
  setMeta(`${state.name} is available — DOMAIN.etn`, `Register ${state.name} on Electroneum with your own wallet.`);
  return `
    <section class="domain-hero">
      <p class="kicker">Available</p>
      <h1>${domainTitle(state.name)}</h1>
      <div class="status-row"><span class="status available">Available</span></div>
    </section>
    ${steps()}
    ${errorBox()}
    ${quoteCard()}
    ${wizardExtras()}`;
}

function wizardExtras() {
  const p = state.phase;
  if (p === Phase.WRONG_NETWORK) {
    return `<div class="card" style="margin-top:16px"><p>Your wallet is on the wrong network.</p><button class="btn" id="switch-btn" type="button">Switch to Electroneum</button></div>`;
  }
  if (p === Phase.COMMIT_SIGNING || p === Phase.REGISTER_SIGNING || p === Phase.RENEW_SIGNING) {
    return `<div class="card" style="margin-top:16px"><p>${esc(userCopy(state))}</p></div>`;
  }
  if (p === Phase.WAITING_FOR_COMMITMENT || p === Phase.COMMIT_SUBMITTED) {
    const pct = state.waitTotal ? Math.max(0, Math.min(100, ((state.waitTotal - state.waitRemaining) / state.waitTotal) * 100)) : 0;
    return `<div class="card" style="margin-top:16px">
      <p class="kicker">Reservation submitted</p>
      <p>Your name is reserved for registration. Registration becomes available in</p>
      <div class="countdown" aria-live="polite">${mmss(state.waitRemaining)}</div>
      <div class="progress"><span style="width:${pct}%"></span></div>
      ${state.intent && state.intent.commit_tx_hash ? `<p class="mono tx-box"><a rel="noopener noreferrer" target="_blank" href="${explorerTx(state.intent.commit_tx_hash)}">Reservation transaction</a></p>` : ""}
    </div>`;
  }
  if (p === Phase.REGISTER_READY) {
    const tx = state.intent.register_tx || {};
    return `<div class="card" style="margin-top:16px">
      <p class="kicker">Pay to register</p>
      <p>Registering <b>${esc(state.name)}</b></p>
      <div class="grid">
        <div class="metric"><label>Owner</label><b>${esc(shortAddr(state.intent.registrant))}</b></div>
        <div class="metric"><label>Duration</label><b>${esc(formatDuration(state.intent.duration))}</b></div>
        <div class="metric"><label>Total</label><b>${esc(formatEtn(tx.value || state.intent.price.total))}</b></div>
        <div class="metric"><label>Network</label><b>Electroneum</b></div>
      </div>
      <p class="note">Confirm in your wallet. You send ETN to the official controller, not to DOMAIN.etn.</p>
      <div class="cta-row"><button class="btn" id="pay-btn" type="button">Pay ${esc(formatEtn(tx.value || "0"))}</button></div>
    </div>`;
  }
  if (p === Phase.REGISTER_SUBMITTED || p === Phase.CONFIRMING) {
    return `<div class="card" style="margin-top:16px">
      <p>Transaction submitted. Waiting for blockchain confirmation…</p>
      <p class="note">Submission is not registration. DOMAIN.etn waits for the official NameRegistered event.</p>
      ${state.intent && state.intent.register_tx_hash ? `<p class="mono"><a rel="noopener noreferrer" target="_blank" href="${explorerTx(state.intent.register_tx_hash)}">${esc(state.intent.register_tx_hash)}</a></p>` : ""}
    </div>`;
  }
  if (p === Phase.COMMIT_READY) {
    return `<div class="card" style="margin-top:16px">
      <p>Reservation is ready. Confirm in your wallet. This step costs no ETN.</p>
      <div class="cta-row"><button class="btn" id="commit-btn" type="button">Confirm reservation</button></div>
    </div>`;
  }
  if (p === Phase.USER_REJECTED || p === Phase.INSUFFICIENT_FUNDS || p === Phase.REGISTRATION_FAILED) {
    return `<div class="cta-row"><button class="btn" id="retry-btn" type="button">Try again</button></div>`;
  }
  if (isSuccess(state) || p === Phase.REGISTERED_SUCCESSFULLY) {
    return successCard();
  }
  return "";
}

function successCard() {
  const intent = state.intent || {};
  return `<div class="card" style="margin-top:16px">
    <p class="kicker">Registered successfully</p>
    <h2 style="font-family:var(--serif);font-weight:500">${domainTitle(intent.name || state.name)}</h2>
    <div class="grid">
      <div class="metric"><label>Owner</label><b>${esc(shortAddr(intent.registrant))}</b></div>
      <div class="metric"><label>Duration</label><b>${esc(formatDuration(intent.duration))}</b></div>
      <div class="metric"><label>Network</label><b>Electroneum</b></div>
    </div>
    ${intent.register_tx_hash ? `<p class="mono tx-box"><a rel="noopener noreferrer" target="_blank" href="${explorerTx(intent.register_tx_hash)}">${esc(intent.register_tx_hash)}</a></p>` : ""}
    <div class="cta-row"><button class="btn" id="view-domain" type="button">View domain</button></div>
  </div>`;
}

function profileView() {
  const p = state.profile || {};
  const owner = p.owner;
  const life = lifecycleOf(p);
  const hist = historyRows(p);
  const related = relatedAddresses(p);
  const intel = p.intelligence || {};
  setMeta(`${p.name || state.name} — DOMAIN.etn`, `${p.name || state.name} is ${life.label.toLowerCase()} on Electroneum.`);
  return `
    <section class="domain-hero">
      <p class="kicker">${esc(life.label)}</p>
      <h1>${domainTitle(p.name || state.name)}</h1>
      <div class="status-row"><span class="status ${esc(life.className)}">${esc(life.label)}</span></div>
    </section>
    ${errorBox()}
    <div class="card">
      <div class="grid">
        <div class="metric"><label>Owner</label><b>${
          owner
            ? `<a href="/w/${esc(owner)}" data-link>${esc(shortAddr(owner))}</a>`
            : "Not visible on-chain"
        }</b></div>
        <div class="metric"><label>Expires</label><b>${esc(formatTime(p.expires_at))}</b><span class="hint">${esc(formatRelative(p.expires_at))}</span></div>
        <div class="metric"><label>Network</label><b>Electroneum</b></div>
        <div class="metric"><label>Lifecycle</label><b>${esc(life.label)}</b></div>
      </div>
      <p class="note">${esc(p.note || "Live on-chain facts. EAE intelligence is optional and is not ownership.")}</p>
      ${owner ? `<p class="note">On-chain owner: <a rel="noopener noreferrer" target="_blank" href="${explorerAddr(owner)}">${esc(owner)}</a></p>` : ""}
      ${p.renewable ? `<div class="cta-row"><button class="btn" id="renew-btn" type="button">Renew</button></div>` : ""}
      ${state.phase === Phase.RENEW_QUOTE || state.phase === Phase.RENEW_READY ? renewBox() : ""}
    </div>
    <section class="stack">
      <h2>History</h2>
      <p class="note">Indexed EAE events. Transfer is not a sale. Live registration is the chain, not this list.</p>
      <div id="history">${hist.length ? historyList(hist) : `<div class="empty">${intel.configured ? "No indexed events for this name yet." : "EAE is not configured, so there is no indexed history."}</div>`}</div>
    </section>
    <section class="stack">
      <h2>Related addresses</h2>
      <p class="note">Factual associations from EAE. Not a social graph and not counterparties.</p>
      ${
        related.length
          ? `<ul class="chips">${related
              .map((row) => {
                const addr = row.address || row;
                const role = row.role ? `${esc(row.role)} · ` : "";
                return `<li><a href="/w/${esc(addr)}" data-link>${role}${esc(shortAddr(addr))}</a></li>`;
              })
              .join("")}</ul>`
          : `<div class="empty">${intel.configured ? "No related addresses indexed." : "EAE is not configured."}</div>`
      }
    </section>
    <section class="stack">
      <h2>Related names</h2>
      <p class="note">Other indexed names for the current NFT owner, when EAE has them. Not proof of ownership.</p>
      <div id="related-names">${owner ? "<p class='note'>Loading indexed names…</p>" : "<div class='empty'>Owner is not visible on-chain, so related names cannot be listed.</div>"}</div>
    </section>
    <section class="stack">
      <h2>Marketplace</h2>
      ${marketNote(p)}
    </section>`;
}

function historyList(rows) {
  return `<ol class="timeline">${rows
    .map((row) => {
      const label = row.label || row.event_type || "Event";
      const tx = row.tx_hash
        ? `<a rel="noopener noreferrer" target="_blank" href="${explorerTx(row.tx_hash)}">transaction</a>`
        : "";
      const block = row.block_number != null ? `block ${esc(row.block_number)}` : "";
      return `<li><strong>${esc(label)}</strong><span class="muted">${[block, tx].filter(Boolean).join(" · ")}</span></li>`;
    })
    .join("")}</ol>`;
}

function marketNote(profile) {
  const facts = (profile.intelligence && profile.intelligence.marketplace_facts) || profile.marketplace || {};
  const status = facts.status || (profile.marketplace && profile.marketplace.status) || "not_implemented";
  return `<div class="card">
    <p class="note">Settlement is not live on Electroneum. DOMAIN.etn will not prepare a listing or purchase until a deployed marketplace contract exists.</p>
    <p class="note">Indexed status: <b>${esc(status)}</b>. Offers and auctions are not implemented.</p>
    <p><a href="/market" data-link>Marketplace status</a></p>
  </div>`;
}

function renewBox() {
  const q = state.renewal;
  if (!q) return "";
  const price = q.price || {};
  const tx = q.renew_tx || {};
  return `<div style="margin-top:16px">
    ${durationPicker()}
    <div class="grid">
      <div class="metric"><label>Renewal total</label><b>${esc(formatEtn(price.total || tx.value || "0"))}</b></div>
    </div>
    <p class="note">Renewal pays rentPrice.base in native ETN to the official controller. Anyone may pay to extend a name.</p>
    <div class="cta-row"><button class="btn" id="pay-renew" type="button">Pay to renew</button></div>
  </div>`;
}

function meView() {
  setMeta("My names — DOMAIN.etn", "Indexed .etn names for a connected wallet. DOMAIN.etn does not keep an ownership database.");
  const recent = loadRecent();
  return `
    <section class="hero left">
      <p class="kicker">Wallet</p>
      <h1>My names</h1>
      <p class="lede">DOMAIN.etn does not keep an ownership database. Names below are either indexed by EAE or remembered from this browser after a confirmed registration.</p>
    </section>
    <div id="mine">${state.wallet.address ? `<p class="note">Loading indexed names for ${esc(shortAddr(state.wallet.address))}…</p>` : `<div class="empty">Connect a wallet to look up indexed names.</div>`}</div>
    ${recent.length ? `<h2 class="block-title">Registered in this browser</h2><p class="note">Local reminder only. Not proof of ownership.</p><div class="list">${recent.map((row) => `<a href="/d/${esc(row.name)}" data-link>${esc(row.name)}</a>`).join("")}</div>` : ""}`;
}

function discoverView() {
  setMeta("Discover .etn names — DOMAIN.etn", "Indexed Electroneum name catalog. Not availability and not a ranking.");
  return `
    <section class="hero left">
      <p class="kicker">Indexed catalog</p>
      <h1>Discover</h1>
      <p class="lede">Recent names EAE has indexed. This is not live availability and not a popularity ranking. Search a name to read the chain.</p>
      <form class="search" id="prefix-form" role="search">
        <label class="sr-only" for="prefix">Prefix search indexed names</label>
        <input id="prefix" name="prefix" placeholder="sat" autocomplete="off" spellcheck="false" />
        <button class="btn" type="submit">Find indexed</button>
      </form>
    </section>
    <div id="discover-results"><p class="note">Loading indexed names…</p></div>`;
}

function marketView() {
  setMeta("Marketplace — DOMAIN.etn", "Secondary .etn marketplace settlement is not deployed on Electroneum.");
  return `
    <section class="hero left">
      <p class="kicker">Secondary market</p>
      <h1>Marketplace</h1>
      <p class="lede">Fixed-price listings will settle on a DomainMarketplace contract when a human deployment gate enables it. That contract is not live on Electroneum today.</p>
    </section>
    <div class="card">
      <div class="grid">
        <div class="metric"><label>Settlement</label><b>Not deployed</b></div>
        <div class="metric"><label>Buy now</label><b>Not implemented</b></div>
        <div class="metric"><label>Offers</label><b>Not implemented</b></div>
        <div class="metric"><label>Auctions</label><b>Not implemented</b></div>
      </div>
      <p class="note">DOMAIN.etn will not prepare listing or purchase transactions, will not invent inventory, and will not treat an indexed row as a name you can buy.</p>
    </div>
    <h2 class="block-title">Indexed listings</h2>
    <div id="market-list"><p class="note">Checking EAE for observational listings…</p></div>`;
}

function ownerView(address) {
  setMeta(`${shortAddr(address)} — DOMAIN.etn`, `Indexed .etn names associated with ${address}.`);
  return `
    <section class="hero left">
      <p class="kicker">Address</p>
      <h1 class="addr-title">${esc(shortAddr(address))}</h1>
      <p class="lede">Indexed associations from EAE. Not a person, not a marketplace seller, not live ownership by itself. <a rel="noopener noreferrer" target="_blank" href="${explorerAddr(address)}">View on explorer</a></p>
    </section>
    <div id="owner-box"><p class="note">Loading indexed names…</p></div>`;
}

async function fillMine() {
  const box = document.getElementById("mine");
  if (!box || !state.wallet.address) return;
  try {
    const data = await api.ownerDomains(state.wallet.address);
    const rows = data.domains || [];
    if (!rows.length) {
      box.innerHTML = `<div class="empty">${data.authority === "not_queried" ? "EAE is not configured, so there is no indexed list. Search a name to read live chain state." : "No indexed names for this wallet."}</div>`;
      return;
    }
    box.innerHTML = `<p class="note">Indexed by EAE. Not an ownership table.</p><div class="list">${rows
      .map((row) => `<a href="/d/${esc(row.name)}" data-link>${esc(row.name)}</a>`)
      .join("")}</div>`;
  } catch (err) {
    box.innerHTML = `<div class="err" role="alert">${esc(err.message)}</div>`;
  }
}

async function fillRelated() {
  const box = document.getElementById("related-names");
  const owner = state.profile && state.profile.owner;
  if (!box || !owner) return;
  try {
    const data = await api.ownerDomains(owner);
    const rows = (data.domains || []).filter((row) => row.name && row.name !== (state.profile && state.profile.name));
    if (!rows.length) {
      box.innerHTML = `<div class="empty">${data.authority === "not_queried" ? "EAE is not configured." : "No other indexed names for this owner."}</div>`;
      return;
    }
    box.innerHTML = `<div class="list">${rows.map((row) => `<a href="/d/${esc(row.name)}" data-link>${esc(row.name)}</a>`).join("")}</div>`;
  } catch (err) {
    box.innerHTML = `<div class="err" role="alert">${esc(err.message)}</div>`;
  }
}

async function fillDiscover() {
  const box = document.getElementById("discover-results");
  if (!box) return;
  const form = document.getElementById("prefix-form");
  if (form) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const prefix = (form.prefix.value || "").trim();
      if (!prefix) return;
      box.innerHTML = `<p class="note">Searching indexed catalog…</p>`;
      try {
        const data = await api.catalogSearch(prefix, prefix);
        const rows = data.results || [];
        if (!rows.length) {
          box.innerHTML = `<div class="empty">${data.authority === "not_queried" ? "EAE is not configured, so there is no indexed catalog." : "No indexed names match that prefix."}</div>`;
          return;
        }
        box.innerHTML = `<p class="note">Indexed matches. Open a name to read live chain state.</p><div class="list">${rows
          .map((row) => {
            const name = row.normalized_name || row.name || row;
            return `<a href="/d/${esc(name)}" data-link>${esc(name)}</a>`;
          })
          .join("")}</div>`;
      } catch (err) {
        box.innerHTML = `<div class="err" role="alert">${esc(err.message)}</div>`;
      }
    });
  }
  try {
    const data = await api.discovery();
    const cats = data.categories || {};
    const recent = cats.recently_registered || cats.recently_seen || data.eae && (data.eae.recent_registrations || data.eae.recent) || [];
    if (data.authority === "not_queried") {
      box.innerHTML = `<div class="empty">EAE is not configured. Discovery is indexed catalog data, not live availability. Search a name instead.</div>`;
      return;
    }
    const sections = [
      ["Recently registered", cats.recently_registered || recent],
      ["Recently seen", cats.recently_seen || []],
    ].filter(([, rows]) => Array.isArray(rows) && rows.length);
    if (!sections.length) {
      box.innerHTML = `<div class="empty">EAE has no indexed names to show yet.</div>`;
      return;
    }
    box.innerHTML = sections
      .map(
        ([title, rows]) =>
          `<h2 class="block-title">${esc(title)}</h2><div class="list">${rows
            .map((row) => {
              const name = row.normalized_name || row.name || row;
              return `<a href="/d/${esc(name)}" data-link>${esc(name)}</a>`;
            })
            .join("")}</div>`
      )
      .join("");
  } catch (err) {
    box.innerHTML = `<div class="err" role="alert">${esc(err.message)}</div>`;
  }
}

async function fillMarket() {
  const box = document.getElementById("market-list");
  if (!box) return;
  try {
    const data = await api.marketplaceListings();
    const rows = data.listings || [];
    if (!rows.length) {
      box.innerHTML = `<div class="empty">${
        data.authority === "not_queried"
          ? "EAE is not configured, and no marketplace contract is deployed. There is nothing to buy here."
          : "No indexed listings. Indexed rows would still not be purchasable here."
      }</div>`;
      return;
    }
    box.innerHTML = `<p class="note">Observational EAE rows. Not purchasable. Not live availability.</p><div class="list">${rows
      .map((row) => {
        const name = row.name || "unknown";
        const price = row.price_wei ? formatEtn(row.price_wei) : "price not shown as live";
        return `<div class="name-row"><a href="/d/${esc(name)}" data-link>${esc(name)}</a><span class="muted">${esc(price)} · not for sale here</span></div>`;
      })
      .join("")}</div>`;
  } catch (err) {
    box.innerHTML = `<div class="err" role="alert">${esc(err.message)}</div>`;
  }
}

async function fillOwner(address) {
  const box = document.getElementById("owner-box");
  if (!box) return;
  try {
    const data = await api.owner(address);
    const rows = data.domains || [];
    const list = rows.length
      ? `<div class="list">${rows.map((row) => `<a href="/d/${esc(row.name)}" data-link>${esc(row.name)}</a>`).join("")}</div>`
      : `<div class="empty">${data.authority === "not_queried" ? "EAE is not configured." : "No indexed names for this address."}</div>`;
    box.innerHTML = `<p class="note">${esc(data.note || "Indexed associations only.")}</p>${list}`;
  } catch (err) {
    box.innerHTML = `<div class="err" role="alert">${esc(err.message)}</div>`;
  }
}

function render() {
  renderWalletChrome();
  const r = route();
  if (r.view === "home") main.innerHTML = homeView();
  else if (r.view === "me") main.innerHTML = meView();
  else if (r.view === "discover") main.innerHTML = discoverView();
  else if (r.view === "market") main.innerHTML = marketView();
  else if (r.view === "owner") main.innerHTML = ownerView(r.address);
  else if (state.phase === Phase.REGISTERED_SUCCESSFULLY) {
    setMeta(`${state.name} registered — DOMAIN.etn`, `${state.name} was confirmed on Electroneum.`);
    main.innerHTML = `<section class="domain-hero"><p class="kicker">Registered successfully</p><h1>${domainTitle(state.name)}</h1></section>${successCard()}`;
  } else if (state.available === false && state.profile) main.innerHTML = profileView();
  else if (state.name) main.innerHTML = availableView();
  else main.innerHTML = homeView();
  bindSearch();
  document.querySelectorAll("[data-dur]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      state = { ...state, duration: Number(btn.getAttribute("data-dur")) };
      if (state.available) await loadQuote(state.name, state.duration);
      else render();
    });
  });
  const registerBtn = document.getElementById("register-btn");
  if (registerBtn) registerBtn.addEventListener("click", startRegister);
  const commitBtn = document.getElementById("commit-btn");
  if (commitBtn) commitBtn.addEventListener("click", signCommit);
  const payBtn = document.getElementById("pay-btn");
  if (payBtn) payBtn.addEventListener("click", signRegister);
  const retry = document.getElementById("retry-btn");
  if (retry) retry.addEventListener("click", startRegister);
  const view = document.getElementById("view-domain");
  if (view) view.addEventListener("click", async () => {
    const profile = await api.profile(state.name);
    setState({ type: "REGISTERED_PROFILE", profile });
  });
  const sw = document.getElementById("switch-btn");
  if (sw) sw.addEventListener("click", async () => {
    try {
      await switchToElectroneum();
      const id = await walletChain();
      setState({ type: "WALLET", wallet: { address: state.wallet.address, chainId: id } });
    } catch (err) {
      setState({ type: "ERROR", error: err.message, phase: Phase.WRONG_NETWORK });
    }
  });
  const renewBtn = document.getElementById("renew-btn");
  if (renewBtn) renewBtn.addEventListener("click", startRenew);
  const payRenew = document.getElementById("pay-renew");
  if (payRenew) payRenew.addEventListener("click", signRenew);
  if (r.view === "me") fillMine();
  if (r.view === "discover") fillDiscover();
  if (r.view === "market") fillMarket();
  if (r.view === "owner") fillOwner(r.address);
  if (r.view === "domain" && state.profile && !state.available) fillRelated();
  announce(userCopy(state));
}

hydrateWallet().then(boot);
