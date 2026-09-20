import test from "node:test";
import assert from "node:assert/strict";
import { createState, reduce, Phase, isSuccess, canRegister, userCopy } from "../../web/js/flow.js";
import { parseName } from "../../web/js/names.js";
import { formatEtn, mmss } from "../../web/js/format.js";

test("empty search is invalid", () => {
  assert.equal(parseName("").ok, false);
  assert.equal(parseName("   ").code, "empty");
});

test("invalid domains", () => {
  assert.equal(parseName("ab").ok, false);
  assert.equal(parseName("a.b.etn").ok, false);
  assert.equal(parseName("alice.eth").ok, false);
  assert.equal(parseName("ALICE.etn").ok, true);
  assert.equal(parseName("ALICE.etn").name, "alice.etn");
});

test("valid domain", () => {
  const parsed = parseName("satoshi");
  assert.equal(parsed.ok, true);
  assert.equal(parsed.name, "satoshi.etn");
});

test("search loading then available", () => {
  let s = createState();
  s = reduce(s, { type: "SEARCH_START", query: "alice", name: "alice.etn", label: "alice" });
  assert.equal(s.phase, Phase.CHECKING);
  s = reduce(s, { type: "AVAILABLE", profile: { name: "alice.etn", label: "alice", available: true } });
  assert.equal(s.phase, Phase.AVAILABLE);
  s = reduce(s, { type: "QUOTE", quote: { duration: 1, price: { total: "1" } } });
  assert.equal(s.phase, Phase.QUOTE_READY);
});

test("registered search does not offer success", () => {
  let s = reduce(createState(), { type: "REGISTERED_PROFILE", profile: { name: "wallet.etn", available: false } });
  assert.equal(s.phase, Phase.REGISTERED);
  assert.equal(s.success, false);
});

test("quote expiry", () => {
  let s = reduce(createState(), { type: "QUOTE_EXPIRED" });
  assert.equal(s.phase, Phase.QUOTE_EXPIRED);
});

test("wallet states", () => {
  let s = reduce(createState(), { type: "WALLET", wallet: { address: null, chainId: null } });
  assert.equal(s.phase, Phase.WALLET_DISCONNECTED);
  s = reduce(createState({ phase: Phase.QUOTE_READY }), { type: "WALLET", wallet: { address: "0x1", chainId: 1 } });
  assert.equal(s.phase, Phase.WRONG_NETWORK);
  s = reduce(createState({ phase: Phase.QUOTE_READY, quote: { duration: 1 } }), { type: "WALLET", wallet: { address: "0x1", chainId: 52014 } });
  assert.equal(s.phase, Phase.QUOTE_READY);
  assert.equal(canRegister(s), true);
});

test("commit wait register confirm", () => {
  let s = createState({ name: "alice.etn" });
  s = reduce(s, { type: "COMMIT_PREPARING" });
  s = reduce(s, { type: "COMMIT_READY", intent: { intent_id: "1" }, secret: "0x22" });
  s = reduce(s, { type: "COMMIT_SIGNING" });
  s = reduce(s, { type: "COMMIT_SUBMITTED", intent: { intent_id: "1", commit_tx_hash: "0xab" } });
  assert.equal(s.success, false);
  s = reduce(s, { type: "WAIT", remaining: 47, total: 60 });
  assert.equal(s.phase, Phase.WAITING_FOR_COMMITMENT);
  s = reduce(s, { type: "REGISTER_READY", intent: { intent_id: "1", status: "prepared" } });
  s = reduce(s, { type: "REGISTER_SUBMITTED", intent: { intent_id: "1", status: "submitted" } });
  assert.equal(s.success, false);
  s = reduce(s, { type: "CONFIRMING" });
  s = reduce(s, { type: "CONFIRMED", intent: { intent_id: "1", status: "confirmed" } });
  assert.equal(s.phase, Phase.REGISTERED_SUCCESSFULLY);
  assert.equal(isSuccess(s), true);
});

test("user rejection and insufficient funds", () => {
  let s = reduce(createState(), { type: "USER_REJECTED" });
  assert.equal(s.phase, Phase.USER_REJECTED);
  s = reduce(createState(), { type: "INSUFFICIENT" });
  assert.match(userCopy(s), /ETN/);
});

test("confirmation failure is not success", () => {
  let s = reduce(createState(), { type: "FAILED", error: "reverted" });
  assert.equal(s.success, false);
  assert.equal(isSuccess(s), false);
});

test("format helpers", () => {
  assert.equal(formatEtn("1000000000000000000"), "1 ETN");
  assert.equal(mmss(47), "00:47");
});
