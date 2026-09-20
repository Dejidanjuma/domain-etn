export const Phase = {
  IDLE: "IDLE",
  CHECKING: "CHECKING",
  AVAILABLE: "AVAILABLE",
  REGISTERED: "REGISTERED",
  QUOTE_LOADING: "QUOTE_LOADING",
  QUOTE_READY: "QUOTE_READY",
  QUOTE_EXPIRED: "QUOTE_EXPIRED",
  QUOTE_ERROR: "QUOTE_ERROR",
  WALLET_DISCONNECTED: "WALLET_DISCONNECTED",
  WALLET_CONNECTED: "WALLET_CONNECTED",
  WRONG_NETWORK: "WRONG_NETWORK",
  COMMIT_PREPARING: "COMMIT_PREPARING",
  COMMIT_READY: "COMMIT_READY",
  COMMIT_SIGNING: "COMMIT_SIGNING",
  COMMIT_SUBMITTED: "COMMIT_SUBMITTED",
  WAITING_FOR_COMMITMENT: "WAITING_FOR_COMMITMENT",
  REGISTER_PREPARING: "REGISTER_PREPARING",
  REGISTER_READY: "REGISTER_READY",
  REGISTER_SIGNING: "REGISTER_SIGNING",
  REGISTER_SUBMITTED: "REGISTER_SUBMITTED",
  CONFIRMING: "CONFIRMING",
  REGISTERED_SUCCESSFULLY: "REGISTERED_SUCCESSFULLY",
  REGISTRATION_FAILED: "REGISTRATION_FAILED",
  USER_REJECTED: "USER_REJECTED",
  INSUFFICIENT_FUNDS: "INSUFFICIENT_FUNDS",
  RPC_ERROR: "RPC_ERROR",
  BACKEND_ERROR: "BACKEND_ERROR",
  RECOVERING: "RECOVERING",
  RENEW_QUOTE: "RENEW_QUOTE",
  RENEW_READY: "RENEW_READY",
  RENEW_SIGNING: "RENEW_SIGNING",
  RENEW_SUBMITTED: "RENEW_SUBMITTED",
  RENEW_CONFIRMING: "RENEW_CONFIRMING",
  RENEWED: "RENEWED",
};

export const COPY = {
  [Phase.CHECKING]: "Checking that name…",
  [Phase.AVAILABLE]: "This name is available.",
  [Phase.REGISTERED]: "This name is already registered.",
  [Phase.QUOTE_LOADING]: "Fetching a live price…",
  [Phase.QUOTE_READY]: "Live price ready. Registering does not reserve the name until the chain confirms.",
  [Phase.QUOTE_EXPIRED]: "That price expired. Get a fresh quote.",
  [Phase.WALLET_DISCONNECTED]: "Connect a wallet to continue. DOMAIN.etn never asks for wallet secrets.",
  [Phase.WRONG_NETWORK]: "Switch your wallet to Electroneum (chain 52014).",
  [Phase.COMMIT_PREPARING]: "Preparing the reservation transaction…",
  [Phase.COMMIT_READY]: "Confirm the reservation in your wallet. This costs no ETN.",
  [Phase.COMMIT_SIGNING]: "Waiting for wallet confirmation…",
  [Phase.COMMIT_SUBMITTED]: "Reservation submitted. Waiting for the network…",
  [Phase.WAITING_FOR_COMMITMENT]: "Your name is reserved for registration.",
  [Phase.REGISTER_PREPARING]: "Preparing the registration payment…",
  [Phase.REGISTER_READY]: "Confirm payment in your wallet. You pay native ETN to the official registrar.",
  [Phase.REGISTER_SIGNING]: "Waiting for wallet confirmation…",
  [Phase.REGISTER_SUBMITTED]: "Transaction submitted. Waiting for blockchain confirmation…",
  [Phase.CONFIRMING]: "Checking the official NameRegistered event…",
  [Phase.REGISTERED_SUCCESSFULLY]: "Registered successfully.",
  [Phase.REGISTRATION_FAILED]: "Registration did not complete.",
  [Phase.USER_REJECTED]: "Wallet request was rejected.",
  [Phase.INSUFFICIENT_FUNDS]: "Not enough ETN to pay for this registration.",
  [Phase.RECOVERING]: "Checking the previous registration attempt…",
};

export function createState(overrides = {}) {
  return {
    phase: Phase.IDLE,
    query: "",
    name: null,
    label: null,
    available: null,
    profile: null,
    quote: null,
    duration: 365 * 24 * 3600,
    wallet: { address: null, chainId: null },
    intent: null,
    secret: null,
    waitRemaining: 60,
    waitTotal: 60,
    error: null,
    success: false,
    renewal: null,
    ...overrides,
  };
}

export function reduce(state, action) {
  const next = { ...state, error: action.type === "ERROR" ? action.error : state.error };
  switch (action.type) {
    case "RESET":
      return createState({ wallet: state.wallet, duration: state.duration });
    case "SEARCH_START":
      return { ...createState({ wallet: state.wallet, duration: state.duration }), phase: Phase.CHECKING, query: action.query, name: action.name, label: action.label };
    case "INVALID":
      return { ...state, phase: Phase.IDLE, error: action.error, name: null };
    case "AVAILABLE":
      return { ...state, phase: Phase.AVAILABLE, available: true, profile: action.profile, name: action.profile.name, label: action.profile.label, success: false };
    case "REGISTERED_PROFILE":
      return { ...state, phase: Phase.REGISTERED, available: false, profile: action.profile, name: action.profile.name, success: false };
    case "QUOTE_LOADING":
      return { ...state, phase: Phase.QUOTE_LOADING, error: null };
    case "QUOTE":
      return { ...state, phase: Phase.QUOTE_READY, quote: action.quote, duration: action.quote.duration, error: null };
    case "QUOTE_EXPIRED":
      return { ...state, phase: Phase.QUOTE_EXPIRED, error: action.error || "Quote expired." };
    case "WALLET":
      return { ...state, wallet: action.wallet, phase: action.wallet.address ? (Number(action.wallet.chainId) === 52014 ? state.phase : Phase.WRONG_NETWORK) : Phase.WALLET_DISCONNECTED };
    case "WRONG_NETWORK":
      return { ...state, phase: Phase.WRONG_NETWORK, wallet: { ...state.wallet, chainId: action.chainId } };
    case "COMMIT_PREPARING":
      return { ...state, phase: Phase.COMMIT_PREPARING, error: null };
    case "COMMIT_READY":
      return { ...state, phase: Phase.COMMIT_READY, intent: action.intent, secret: action.secret || state.secret, error: null };
    case "COMMIT_SIGNING":
      return { ...state, phase: Phase.COMMIT_SIGNING, error: null };
    case "COMMIT_SUBMITTED":
      return { ...state, phase: Phase.COMMIT_SUBMITTED, intent: action.intent, success: false };
    case "WAIT":
      return { ...state, phase: Phase.WAITING_FOR_COMMITMENT, waitRemaining: action.remaining, waitTotal: action.total || state.waitTotal, success: false };
    case "REGISTER_PREPARING":
      return { ...state, phase: Phase.REGISTER_PREPARING, error: null };
    case "REGISTER_READY":
      return { ...state, phase: Phase.REGISTER_READY, intent: action.intent, error: null };
    case "REGISTER_SIGNING":
      return { ...state, phase: Phase.REGISTER_SIGNING, error: null };
    case "REGISTER_SUBMITTED":
      return { ...state, phase: Phase.REGISTER_SUBMITTED, intent: action.intent, success: false };
    case "CONFIRMING":
      return { ...state, phase: Phase.CONFIRMING, success: false };
    case "CONFIRMED":
      return { ...state, phase: Phase.REGISTERED_SUCCESSFULLY, intent: action.intent, success: true, error: null };
    case "FAILED":
      return { ...state, phase: Phase.REGISTRATION_FAILED, intent: action.intent || state.intent, success: false, error: action.error };
    case "USER_REJECTED":
      return { ...state, phase: Phase.USER_REJECTED, error: action.error || COPY[Phase.USER_REJECTED] };
    case "INSUFFICIENT":
      return { ...state, phase: Phase.INSUFFICIENT_FUNDS, error: action.error || COPY[Phase.INSUFFICIENT_FUNDS] };
    case "ERROR":
      return { ...state, phase: action.phase || Phase.BACKEND_ERROR, error: action.error, success: false };
    case "RECOVERING":
      return { ...state, phase: Phase.RECOVERING, name: action.name, intent: action.intent || null, secret: action.secret || null };
    case "RENEW_QUOTE":
      return { ...state, phase: Phase.RENEW_QUOTE, renewal: action.quote };
    case "RENEW_READY":
      return { ...state, phase: Phase.RENEW_READY, renewal: action.intent };
    case "RENEW_SIGNING":
      return { ...state, phase: Phase.RENEW_SIGNING };
    case "RENEW_SUBMITTED":
      return { ...state, phase: Phase.RENEW_SUBMITTED, renewal: action.intent, success: false };
    case "RENEWED":
      return { ...state, phase: Phase.RENEWED, renewal: action.intent, success: true };
    default:
      return next;
  }
}

export function userCopy(state) {
  if (state.error) return state.error;
  return COPY[state.phase] || "";
}

export function canRegister(state) {
  return Boolean(
    state.phase === Phase.QUOTE_READY &&
      state.quote &&
      state.wallet.address &&
      Number(state.wallet.chainId) === 52014
  );
}

export function isSuccess(state) {
  return state.phase === Phase.REGISTERED_SUCCESSFULLY && state.success === true && state.intent && state.intent.status === "confirmed";
}
