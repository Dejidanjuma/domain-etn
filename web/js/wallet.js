const CHAIN_ID = 52014;
const CHAIN_HEX = "0xcb2e";

export const ELECTRONEUM = {
  chainId: CHAIN_HEX,
  chainName: "Electroneum Mainnet",
  nativeCurrency: { name: "Electroneum", symbol: "ETN", decimals: 18 },
  rpcUrls: ["https://rpc.electroneum.com"],
  blockExplorerUrls: ["https://blockexplorer.electroneum.com"],
};

function provider() {
  return window.ethereum || null;
}

export function hasWallet() {
  return Boolean(provider());
}

export async function getAccounts() {
  const eth = provider();
  if (!eth) return [];
  const accounts = await eth.request({ method: "eth_accounts" });
  return accounts || [];
}

export async function connect() {
  const eth = provider();
  if (!eth) {
    const err = new Error("No wallet found. Install a browser wallet that supports Electroneum.");
    err.code = "WALLET_DISCONNECTED";
    throw err;
  }
  const accounts = await eth.request({ method: "eth_requestAccounts" });
  const chainId = await eth.request({ method: "eth_chainId" });
  return { address: accounts[0], chainId: Number.parseInt(chainId, 16) };
}

export async function chainId() {
  const eth = provider();
  if (!eth) return null;
  const raw = await eth.request({ method: "eth_chainId" });
  return Number.parseInt(raw, 16);
}

export function isElectroneum(id) {
  return Number(id) === CHAIN_ID;
}

export async function switchToElectroneum() {
  const eth = provider();
  if (!eth) throw new Error("No wallet found.");
  try {
    await eth.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
  } catch (err) {
    if (err && (err.code === 4902 || String(err.message || "").includes("Unrecognized chain"))) {
      await eth.request({ method: "wallet_addEthereumChain", params: [ELECTRONEUM] });
      return;
    }
    throw err;
  }
}

export async function sendPrepared(tx) {
  const eth = provider();
  if (!eth) {
    const err = new Error("No wallet found.");
    err.code = "WALLET_DISCONNECTED";
    throw err;
  }
  const live = await chainId();
  if (!isElectroneum(live)) {
    const err = new Error("Wallet is not on Electroneum (chain 52014).");
    err.code = "WRONG_NETWORK";
    throw err;
  }
  const params = {
    from: tx.from,
    to: tx.to,
    data: tx.data,
    value: hexValue(tx.value),
    chainId: CHAIN_HEX,
  };
  try {
    return await eth.request({ method: "eth_sendTransaction", params: [params] });
  } catch (err) {
    const mapped = mapWalletError(err);
    throw mapped;
  }
}

export function onWalletChange(handler) {
  const eth = provider();
  if (!eth || !eth.on) return () => {};
  const accounts = (accs) => handler({ type: "accounts", accounts: accs || [] });
  const chain = (id) => handler({ type: "chain", chainId: Number.parseInt(id, 16) });
  eth.on("accountsChanged", accounts);
  eth.on("chainChanged", chain);
  return () => {
    if (eth.removeListener) {
      eth.removeListener("accountsChanged", accounts);
      eth.removeListener("chainChanged", chain);
    }
  };
}

function hexValue(wei) {
  const n = BigInt(wei || "0");
  return "0x" + n.toString(16);
}

export function mapWalletError(err) {
  const code = err && err.code;
  const message = String((err && err.message) || err || "Wallet error");
  const out = new Error(message);
  if (code === 4001 || /user rejected|denied/i.test(message)) {
    out.code = "USER_REJECTED";
    out.message = "Wallet request was rejected.";
  } else if (/insufficient/i.test(message)) {
    out.code = "INSUFFICIENT_FUNDS";
    out.message = "Not enough ETN to pay for this transaction.";
  } else if (code === "WRONG_NETWORK") {
    out.code = "WRONG_NETWORK";
  } else {
    out.code = "RPC_ERROR";
  }
  return out;
}

export { CHAIN_ID };
