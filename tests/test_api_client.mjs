import assert from "node:assert/strict";
import { ApiError, createApiClient } from "../frontend/api-client.js";

let cases = 0;
async function rejected(fetchImpl, expected, status, options = {}) {
  const states = [];
  const request = createApiClient({
    fetchImpl,
    onConnection: (...args) => states.push(args),
    ...options,
  });
  await assert.rejects(
    request("/api/v2/auth/login", "POST", {
      email: "synthetic@example.test",
      password: "synthetic-only",
    }),
    (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.message, expected);
      assert.equal(error.status, status);
      return true;
    },
  );
  cases++;
  return states.at(-1);
}
for (const [code, status, message] of [
  ["invalid_credentials", 401, "invalidCredentials"],
  ["email_registered", 409, "emailRegistered"],
  ["origin_rejected", 403, "originMismatch"],
  ["invalid_input", 422, "invalidInput"],
  ["rate_limited", 429, "tooManyRequests"],
  ["service_unavailable", 503, "serviceUnavailable"],
]) {
  const state = await rejected(
    async () => Response.json({ error: code }, { status }),
    message,
    status,
  );
  assert.equal(state[0], status >= 500 ? "disconnected" : "connected");
}
assert.equal(
  (
    await rejected(
      async () => new Response("<html>Static preview</html>"),
      "unexpectedResponse",
      200,
    )
  )[0],
  "disconnected",
);
await rejected(
  async () => new Response("Bad gateway", { status: 502 }),
  "serviceUnavailable",
  502,
);
await rejected(
  async () => Response.json({ detail: "Not Found" }, { status: 404 }),
  "unexpectedResponse",
  404,
);
await rejected(
  async () => new Response(null, { status: 204 }),
  "unexpectedResponse",
  204,
);
await rejected(async () => Response.json(null), "unexpectedResponse", 200);
await rejected(
  async () => {
    throw new TypeError("fetch failed");
  },
  "connectionLost",
  0,
);
await rejected(
  async () => {
    throw new TypeError("fetch failed");
  },
  "offline",
  0,
  { isOnline: () => false },
);
await rejected(
  (_path, { signal }) =>
    new Promise((_resolve, reject) =>
      signal.addEventListener(
        "abort",
        () => reject(new DOMException("Aborted", "AbortError")),
        { once: true },
      ),
    ),
  "requestTimeout",
  0,
  { timeoutMs: 5 },
);
await rejected(
  async (_path, { signal }) => ({
    status: 200,
    ok: true,
    json: () =>
      new Promise((_resolve, reject) =>
        signal.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true },
        ),
      ),
  }),
  "requestTimeout",
  0,
  { timeoutMs: 5 },
);
let attempts = 0;
const request = createApiClient({
  fetchImpl: async (path, options) => {
    attempts++;
    assert.equal(path, "/api/v2/auth/login");
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers["X-Catchy-Request"], "1");
    assert.equal(options.method, "POST");
    assert.deepEqual(JSON.parse(options.body), {
      email: "synthetic@example.test",
    });
    return Response.json({ user: { name: "Test" } });
  },
});
assert.deepEqual(
  await request("/api/v2/auth/login", "POST", {
    email: "synthetic@example.test",
  }),
  { user: { name: "Test" } },
);
assert.equal(attempts, 1, "Account writes must never be automatically retried");
console.log(`API client: ${cases + 1} success/error/timeout scenarios passed.`);
