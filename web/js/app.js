import { api } from "./api.js";
import { reduce, createState, Phase, userCopy, isSuccess } from "./flow.js";
import { parseName } from "./names.js";
import { DURATIONS, formatDuration, formatEtn, formatTime, mmss, shortAddr, explorerTx, explorerAddr, YEAR } from "./format.js";
import { connect, hasWallet, onWalletChange, sendPrepared, switchToElectroneum, getAccounts, chainId as walletChain, isElectroneum } from "./wallet.js";
import { saveSession, sessionFor, clearSession, randomSecret, rememberRecent, loadRecent } from "./storage.js";

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

function route() {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  if (path === "/") return { view: "home" };
  if (path === "/me") return { view: "me" };
  const domain = path.match(/^\/d\/(.+)$/);
  if (domain) return { view: "domain", name: decodeURIComponent(domain[1]) };
  return { view: "home" };
}

function go(path) {
  if (location.pathname !== path) history.pushState({}, "", path);
  boot();
}

window.addEventListener("popstate", boot);
document.querySelectorAll("[data-link]").forEach((el) => {
  el.addEventListener("click", (ev) => {
    ev.preventDefault();
    go(el.getAttribute("href"));
  });
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
  if (r.view === "home") {
    if (!state.name) state = { ...state, phase: Phase.IDLE };
    render();
    return;
  }
  if (r.view === "me") {
    render();
    return;
  }
  if (r.view === "domain") {
    await openName(r.name);
  }
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
    netPill.hidden = true;
  }
}

function searchForm(autofill = "") {
  return `
    <form class="search" id="search-form">
      <label class="sr-only" for="q">Search a .etn domain</label>
      <input id="q" name="q" value="${esc(autofill)}" placeholder="satoshi.etn" autocomplete="off" spellcheck="false" />
      <button class="btn" type="submit">Search</button>
    </form>
    <div class="examples">
      <button type="button" data-ex="satoshi.etn">satoshi.etn</button>
      <button type="button" data-ex="nakamoto.etn">nakamoto.etn</button>
      <button type="button" data-ex="example.etn">example.etn</button>
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
  return `
    <section class="hero">
      <p class="kicker">Electroneum names</p>
      <h1>Find your <span class="tld">.etn</span> name</h1>
      <p class="lede">Search a name, see the live price, then register it with your own wallet. DOMAIN.etn never holds your keys or your ETN.</p>
      ${searchForm()}
      ${errorBox()}
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
      ${state.intent && state.intent.commit_tx_hash ? `<p class="mono tx-box"><a href="${explorerTx(state.intent.commit_tx_hash)}">Reservation transaction</a></p>` : ""}
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
      ${state.intent && state.intent.register_tx_hash ? `<p class="mono"><a href="${explorerTx(state.intent.register_tx_hash)}">${esc(state.intent.register_tx_hash)}</a></p>` : ""}
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
    ${intent.register_tx_hash ? `<p class="mono tx-box"><a href="${explorerTx(intent.register_tx_hash)}">${esc(intent.register_tx_hash)}</a></p>` : ""}
    <div class="cta-row"><button class="btn" id="view-domain" type="button">View domain</button></div>
  </div>`;
}

function profileView() {
  const p = state.profile || {};
  const owner = p.owner;
  return `
    <section class="domain-hero">
      <p class="kicker">${p.in_grace ? "In grace period" : "Registered"}</p>
      <h1>${domainTitle(p.name || state.name)}</h1>
      <div class="status-row"><span class="status registered">${p.in_grace ? "Expired · renewable" : "Registered"}</span></div>
    </section>
    ${errorBox()}
    <div class="card">
      <div class="grid">
        <div class="metric"><label>Owner</label><b>${owner ? `<a href="${explorerAddr(owner)}">${esc(shortAddr(owner))}</a>` : "Not visible on-chain"}</b></div>
        <div class="metric"><label>Expires</label><b>${esc(formatTime(p.expires_at))}</b></div>
        <div class="metric"><label>Network</label><b>Electroneum</b></div>
        <div class="metric"><label>Status</label><b>${p.in_grace ? "Grace period" : "Active"}</b></div>
      </div>
      <p class="note">${esc(p.note || "Live on-chain facts. EAE intelligence is optional and is not ownership.")}</p>
      ${p.renewable ? `<div class="cta-row"><button class="btn" id="renew-btn" type="button">Renew</button></div>` : ""}
      ${state.phase === Phase.RENEW_QUOTE || state.phase === Phase.RENEW_READY ? renewBox() : ""}
      ${p.eae ? `<div class="tx-box"><p class="kicker">Intelligence</p><p class="note">Indexed EAE facts are shown when configured. Absence from EAE is not absence on-chain.</p></div>` : `<p class="note">No EAE intelligence is configured for this process.</p>`}
      <p class="note">Marketplace listing is not implemented.</p>
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
  const recent = loadRecent();
  return `
    <section class="hero" style="text-align:left">
      <p class="kicker">Wallet</p>
      <h1>My names</h1>
      <p class="lede">DOMAIN.etn does not keep an ownership database. Names below are either indexed by EAE or remembered from this browser after a confirmed registration.</p>
    </section>
    <div id="mine">${state.wallet.address ? `<p class="note">Loading indexed names for ${esc(shortAddr(state.wallet.address))}…</p>` : `<div class="empty">Connect a wallet to look up indexed names.</div>`}</div>
    ${recent.length ? `<h2 style="margin-top:32px">Registered in this browser</h2><p class="note">Local reminder only. Not proof of ownership.</p><div class="list">${recent.map((row) => `<a href="/d/${esc(row.name)}" data-link="/d/${esc(row.name)}">${esc(row.name)}</a>`).join("")}</div>` : ""}`;
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
      .map((row) => `<a href="/d/${esc(row.name)}" data-link="/d/${esc(row.name)}">${esc(row.name)}</a>`)
      .join("")}</div>`;
    box.querySelectorAll("[data-link]").forEach((a) => a.addEventListener("click", (ev) => { ev.preventDefault(); go(a.getAttribute("data-link")); }));
  } catch (err) {
    box.innerHTML = `<div class="err">${esc(err.message)}</div>`;
  }
}

function render() {
  renderWalletChrome();
  const r = route();
  if (r.view === "home") main.innerHTML = homeView();
  else if (r.view === "me") main.innerHTML = meView();
  else if (state.phase === Phase.REGISTERED_SUCCESSFULLY) main.innerHTML = `<section class="domain-hero"><p class="kicker">Registered successfully</p><h1>${domainTitle(state.name)}</h1></section>${successCard()}`;
  else if (state.available === false && state.profile) main.innerHTML = profileView();
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
  announce(userCopy(state));
}

hydrateWallet().then(boot);
