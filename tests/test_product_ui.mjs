// Run the real UI handlers without a browser. Layout/device QA is separate.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { createCurrentSession } from "../frontend/lifecycle.js";
import { createApiClient, ApiError } from "../frontend/api-client.js";

const source = readFileSync("frontend/product.js", "utf8")
  .replace(/^import[\s\S]*?from "[^"\n]+";\s*/gm, "")
  .replace(/\nboot\(\);\s*$/, "\n");
const registry = JSON.parse(
  readFileSync("frontend/locales/languages.json", "utf8"),
);
let combinations = 0;
for (const locale of registry.filter((item) => item.status !== "planned")) {
  const catalog = JSON.parse(
    readFileSync(`frontend/locales/${locale.code}.json`, "utf8"),
  );
  const nodes = new Map(),
    events = new Map(),
    speech = [];
  let server = "down",
    deferSpeech = false,
    analysisLevel = "low",
    asrStarts = 0;
  const deferredSpeech = [],
    asrOptions = [];
  let identityResponse = null,
    identityRequested;
  const requests = [];
  const node = (selector) => {
    if (!nodes.has(selector))
      nodes.set(selector, {
        innerHTML: "",
        textContent: "",
        open: false,
        checked: false,
        classList: { toggle() {}, add() {}, remove() {} },
        addEventListener() {},
        showModal() {
          this.open = true;
        },
        close() {
          this.open = false;
        },
        focus() {
          this.focused = true;
        },
        scrollIntoView(options) {
          this.scrolled = options;
        },
      });
    return nodes.get(selector);
  };
  const context = vm.createContext({
    createApiClient: (options) =>
      createApiClient({
        ...options,
        fetchImpl: async (path, options) => {
          requests.push({ path, method: options.method });
          if (server === "down") throw new TypeError("Connection refused");
          if (path === "/api/health")
            return Response.json(
              server === "invalid"
                ? { status: "ok", version: "1.0.0" }
                : { status: "ok", database: "sqlite-development" },
            );
          if (path === "/api/v2/guest/analyze")
            return Response.json({ level: analysisLevel, signals: [] });
          if (path.endsWith("/withdraw") || path.endsWith("/finish"))
            return Response.json({ ok: true });
          if (path === "/api/v2/calls")
            return Response.json({ id: "owned-session" });
          if (identityResponse) {
            identityRequested();
            return identityResponse;
          }
          return Response.json({ error: "sign_in_required" }, { status: 401 });
        },
      }),
    ApiError,
    AbortController,
    crypto: { randomUUID: () => "synthetic-request" },
    WebSocket: class {
      close() {}
    },
    chooseASR: async () => ({
      start: async (options) => {
        asrStarts++;
        asrOptions.push(options);
      },
      stop() {},
    }),
    createCurrentSession,
    cancelWarning() {},
    document: {
      querySelector: node,
      querySelectorAll: () => [],
      body: node("body"),
      addEventListener(name, fn) {
        if (!events.has(name)) events.set(name, []);
        events.get(name).push(fn);
      },
    },
    window: {
      addEventListener(name, fn) {
        if (!events.has(name)) events.set(name, []);
        events.get(name).push(fn);
      },
      scrollTo() {},
    },
    navigator: { onLine: true },
    location: { hash: "", hostname: "127.0.0.1" },
    t(key) {
      assert.ok(Object.hasOwn(catalog, key), `${locale.code}: missing ${key}`);
      return catalog[key];
    },
    language: locale.code,
    languages: registry,
    languageInfo: () => ({ ...locale, name: "<script>untrusted</script>" }),
    translate() {},
    loadLanguage: async () => {},
    localStorage: {
      getItem: (key) => (key === "catchy-language" ? locale.code : null),
      setItem() {},
    },
    sessionStorage: { getItem: () => null },
    speakWarning: async (...args) => {
      speech.push(args);
      if (deferSpeech)
        return new Promise((resolve) => deferredSpeech.push(resolve));
      return true;
    },
    setTimeout: () => 1,
    clearTimeout() {},
    setInterval: () => 1,
  });
  vm.runInContext(source, context);
  const click = async (dataset) => {
    for (const handler of events.get("click") || []) {
      await handler({
        target: {
          closest: (selector) =>
            selector.includes("data-action") ? { dataset } : null,
        },
      });
    }
  };
  server = "up";
  let finishIdentity;
  identityResponse = new Promise((resolve) => {
    finishIdentity = resolve;
  });
  const pendingIdentity = new Promise((resolve) => {
    identityRequested = resolve;
  });
  const booting = vm.runInContext("boot()", context);
  await pendingIdentity;
  assert.equal(vm.runInContext("S.initializing", context), true);
  assert.ok(
    node("#content").innerHTML.match(
      /<button[^>]*data-action="start"[^>]*disabled/,
    ),
  );
  await click({ action: "start" });
  await click({ action: "account" });
  await vm.runInContext("start()", context);
  for (const handler of events.get("submit"))
    await handler({ preventDefault() {}, target: { id: "auth-form" } });
  assert.equal(
    node("#modal").open,
    false,
    "slow account restoration must block starting and account changes",
  );
  assert.equal(vm.runInContext("S.running", context), false);
  assert.ok(requests.every(({ method }) => method === "GET"));
  finishIdentity(
    Response.json({ user: { name: "Restored account" }, preferences: {} }),
  );
  await booting;
  assert.equal(vm.runInContext("S.initializing", context), false);
  assert.equal(vm.runInContext("S.user.name", context), "Restored account");
  identityResponse = null;
  server = "down";
  requests.length = 0;
  vm.runInContext("S.user=null;", context);
  for (const mode of ["speaker", "typed", "demo"])
    for (const running of [false, true]) {
      vm.runInContext(
        `S.mode=${JSON.stringify(mode)}; S.running=${running}; nav(); home();`,
        context,
      );
      const html = node("#content").innerHTML;
      assert.ok(
        !html.includes("<script>untrusted</script>"),
        "dynamic text must be escaped",
      );
      assert.ok(html.includes("&lt;script&gt;untrusted&lt;/script&gt;"));
      assert.ok(
        html.includes(running ? 'data-action="stop"' : 'data-action="start"'),
      );
      assert.equal(
        html
          .match(/<button[^>]*data-action="previewVoice"[^>]*>/)[0]
          .includes("disabled"),
        running,
      );
      if (mode === "typed")
        assert.equal(
          html.match(/<textarea[^>]*>/)[0].includes("disabled"),
          !running,
        );
      const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(
        (match) => match[1],
      );
      assert.equal(
        new Set(ids).size,
        ids.length,
        "result targets must not be duplicated",
      );
      for (const id of ["live-result", "live-status", "session-details"])
        assert.ok(ids.includes(id));
      combinations++;
    }
  vm.runInContext('S.running=false; S.mode="speaker";', context);
  await click({ openMode: "typed" });
  assert.equal(vm.runInContext("S.mode", context), "typed");
  assert.equal(
    vm.runInContext("S.running", context),
    false,
    "hero shortcut must not bypass consent",
  );
  assert.equal(node(".start-button").focused, true);
  assert.equal(node(".start-button").scrolled.block, "center");
  if (locale.status !== "preview") {
    await click({ action: "start" });
    assert.equal(node("#modal").open, true, "starting still asks for consent");
    assert.equal(vm.runInContext("S.running", context), false);
  }
  vm.runInContext('S.running=true; S.mode="speaker";', context);
  await click({ openMode: "typed" });
  await click({ mode: "demo" });
  await click({ action: "previewVoice" });
  assert.equal(
    vm.runInContext("S.mode", context),
    "speaker",
    "active session cannot switch modes",
  );
  assert.equal(
    speech.length,
    0,
    "sample voice must not contaminate live input",
  );
  vm.runInContext(
    'S.running=false; S.error="connectionLost"; authForm();',
    context,
  );
  assert.ok(node("#modal-body").innerHTML.includes('id="form-retry"'));
  assert.equal(await vm.runInContext("checkConnection()", context), false);
  assert.equal(node("#connection-status").hidden, false);
  assert.equal(node("#connection-message").textContent, catalog.connectionLost);
  assert.equal(node("#connection-local-help").hidden, false);
  // The browser's online event alone must not claim that a stopped API is reachable.
  for (const handler of events.get("online")) handler();
  assert.equal(await vm.runInContext("checkConnection()", context), false);
  assert.equal(vm.runInContext("S.connection", context), "disconnected");
  server = "invalid";
  node("#form-retry").hidden = false;
  node("#form-error").textContent = catalog.requestTimeout;
  assert.equal(await vm.runInContext("checkConnection()", context), false);
  assert.equal(
    node("#connection-message").textContent,
    catalog.unexpectedResponse,
  );
  assert.equal(node("#form-retry").hidden, false);
  assert.equal(node("#form-error").textContent, catalog.requestTimeout);
  server = "up";
  await vm.runInContext("checkConnection({quiet:true})", context);
  assert.equal(
    node("#form-retry").hidden,
    false,
    "health polling must not clear an uncertain submission",
  );
  assert.equal(node("#form-error").textContent, catalog.requestTimeout);
  node("#form-retry").hidden = false;
  node("#form-error").textContent = catalog.connectionLost;
  await click({ action: "retryConnection" });
  assert.equal(node("#connection-status").hidden, true);
  assert.equal(node("#form-error").textContent, "");
  assert.equal(node("#form-retry").hidden, true);
  assert.equal(vm.runInContext("S.error", context), null);
  assert.equal(
    vm.runInContext("S.running", context),
    false,
    "recovery must not restart listening",
  );
  assert.ok(
    requests.every(({ method }) => method === "GET"),
    "retry must not repeat form submissions",
  );
  node("#form-error").textContent = catalog.invalidCredentials;
  await vm.runInContext("checkConnection()", context);
  assert.equal(
    node("#form-error").textContent,
    catalog.invalidCredentials,
    "health polling must preserve credential errors",
  );
  // Guest text and demonstrations stay available, while every microphone path
  // requires a signed-in user before consent, session creation or capture.
  requests.length = 0;
  vm.runInContext('S.user=null; S.mode="speaker"; S.running=false;', context);
  node("[name=consent]").checked = true;
  for (const provider of ["browser", "selfhost"]) {
    vm.runInContext("S.preferences.asr=" + JSON.stringify(provider), context);
    await click({ action: "start" });
    assert.ok(node("#modal-body").innerHTML.includes('id="auth-form"'));
    assert.equal(node("#modal-notice").textContent, catalog.microphoneSignIn);
    await vm.runInContext("start()", context);
    assert.equal(vm.runInContext("S.running", context), false);
  }
  assert.equal(
    requests.length,
    0,
    "Guest microphone denial must make no API request",
  );
  assert.equal(
    asrStarts,
    0,
    "Guest microphone denial must never acquire audio",
  );
  for (const mode of ["typed", "demo"]) {
    vm.runInContext("S.mode=" + JSON.stringify(mode), context);
    await vm.runInContext("start()", context);
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(
      vm.runInContext("S.running", context),
      true,
      mode + " guests remain allowed",
    );
    await vm.runInContext("stop(false)", context);
  }
  assert.equal(
    asrStarts,
    0,
    "Text and demonstration sessions must never acquire audio",
  );
  assert.ok(requests.some(({ path }) => path === "/api/v2/guest/analyze"));
  vm.runInContext('S.user={id:"owner"}; S.mode="speaker";', context);
  await vm.runInContext("start()", context);
  assert.equal(
    asrStarts,
    1,
    "Signed-in consented microphone sessions can start",
  );
  assert.equal(asrOptions[0].callId, "owned-session");
  assert.equal(asrOptions[0].language, locale.speech);
  await click({ action: "stop" });
  assert.ok(
    requests.some(
      ({ path }) => path === "/api/v2/calls/owned-session/withdraw",
    ),
  );
  assert.equal(vm.runInContext("S.running", context), false);
  vm.runInContext(
    "S.user=null; S.call=null; S.running=true; S.voiceMuted=false; S.preferences.spoken_warnings=true;",
    context,
  );
  deferSpeech = true;
  analysisLevel = "high";
  vm.runInContext(
    'S.alertShown=false; S.queue=[{text:"Read the code",ended:null},{text:"Transfer money",ended:null}];',
    context,
  );
  const draining = vm.runInContext("drain()", context);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(deferredSpeech.length, 1);
  assert.equal(
    vm.runInContext("S.queue.length", context),
    0,
    "Speech playback must not block subsequent analysis",
  );
  assert.equal(vm.runInContext("S.busy", context), false);
  deferredSpeech.shift()(true);
  await draining;
  analysisLevel = "low";
  let warning = vm.runInContext("warn()", context);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(
    node("#voice-fallback").hidden,
    false,
    "Text fallback stays visible during pending audio",
  );
  assert.equal(deferredSpeech.length, 1);
  deferredSpeech.shift()(false);
  await warning;
  assert.equal(node("#voice-fallback").hidden, false);
  assert.equal(node("#voice-fallback").textContent, catalog.noVoice);
  warning = vm.runInContext("warn()", context);
  await new Promise((resolve) => setImmediate(resolve));
  deferredSpeech.shift()(true);
  await warning;
  assert.equal(
    node("#voice-fallback").hidden,
    true,
    "Only successful playback may hide the fallback",
  );
  warning = vm.runInContext("warn()", context);
  await new Promise((resolve) => setImmediate(resolve));
  await click({ action: "muteWarning" });
  assert.equal(vm.runInContext("S.voiceMuted", context), true);
  assert.equal(node("#voice-fallback").textContent, catalog.voiceMuted);
  deferredSpeech.shift()(true);
  await warning;
  assert.equal(
    node("#voice-fallback").hidden,
    false,
    "Late playback success cannot hide muted guidance",
  );
  vm.runInContext("S.voiceMuted=false;", context);
  warning = vm.runInContext("warn()", context);
  await new Promise((resolve) => setImmediate(resolve));
  await vm.runInContext("stop(false)", context);
  vm.runInContext("S.running=true; S.generation++;", context);
  node("#voice-fallback").textContent = "new session guidance";
  deferredSpeech.shift()(false);
  await warning;
  assert.equal(
    node("#voice-fallback").textContent,
    "new session guidance",
    "Old speech failures cannot affect a new session",
  );
  assert.equal(
    node("#danger").open,
    false,
    "Stopped warnings cannot reopen the danger dialog",
  );
  await vm.runInContext("stop(false)", context);
}
console.log(
  `Product UI: ${combinations} localized states plus consent, focus, escaping, active-session guards and connection recovery passed.`,
);
