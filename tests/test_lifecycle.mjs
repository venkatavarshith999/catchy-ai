import assert from "node:assert/strict";
import { createCurrentSession } from "../frontend/lifecycle.js";
let generation = 1;
let resolveFirst;
const closed = [];
const first = createCurrentSession(
  () => new Promise((resolve) => (resolveFirst = resolve)),
  () => generation === 1,
  async (call) => closed.push(call.id),
);
generation = 2;
const current = await createCurrentSession(
  async () => ({ id: "second" }),
  () => generation === 2,
  async (call) => closed.push(call.id),
);
resolveFirst({ id: "first" });
assert.equal(await first, null);
assert.equal(current.id, "second");
assert.deepEqual(closed, ["first"]);
const cancelled = await createCurrentSession(
  async () => ({ id: "cancelled" }),
  () => false,
  async () => {
    throw Error("network down");
  },
);
assert.equal(
  cancelled,
  null,
  "A cleanup failure must not reactivate a stale session",
);
console.log(
  "Session lifecycle: out-of-order completion and failed stale cleanup regressions passed.",
);
