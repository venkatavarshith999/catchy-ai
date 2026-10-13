import { createCurrentSession } from "./lifecycle.js";
import {
  loadLanguage,
  t,
  translate,
  language,
  languageInfo,
  languages,
} from "./i18n.js";
import { chooseASR, speakWarning } from "./asr.js";
const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const defaultPreferences = () => ({
  spoken_warnings: true,
  retain_transcript: false,
  retention_days: 30,
  high_contrast: false,
  large_text: false,
  analytics: false,
  alert_opt_in: false,
  asr: "browser",
});
const S = {
  user: null,
  page: "home",
  mode: "speaker",
  running: false,
  call: null,
  turns: [],
  result: null,
  asr: null,
  queue: [],
  busy: false,
  preferences: {
    spoken_warnings: true,
    retain_transcript: false,
    retention_days: 30,
    high_contrast: false,
    large_text: false,
    analytics: false,
    alert_opt_in: false,
    asr: "browser",
  },
  contacts: [],
  calls: [],
  generation: 0,
  timer: null,
  silence: null,
  wake: null,
  latency: null,
  health: null,
  error: null,
  alertShown: false,
  invitation: null,
  socket: null,
  pending: new Map(),
};
let toastTimer, installEvent;
function notice(key, literal = false) {
  if ($("#danger").open) {
    $("#danger-feedback").hidden = false;
    $("#danger-feedback").textContent = literal ? key : t(key);
  }
  if ($("#modal").open) {
    let status = $("#modal-notice");
    if (!status) {
      status = document.createElement("p");
      status.id = "modal-notice";
      status.setAttribute("role", "status");
      $("#modal-body").append(status);
    }
    status.textContent = literal ? key : t(key);
  }
  $("#notice").textContent = literal ? key : t(key);
  $("#notice").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#notice").classList.remove("show"), 6500);
}
const errors = {
  invalid_reset_code: "resetInvalid",
  rate_limited: "tooManyRequests",
  verify_email_required: "verificationNeeded",
  delivery_not_configured: "providerUnavailable",
  email_not_configured: "providerUnavailable",
  alert_cooldown: "cooldown",
  invalid_invitation: "inviteInvalid",
  admin_required: "adminOnly",
  language_unavailable: "planned",
  sign_in_required: "authNeeded",
};
async function api(path, method = "GET", body) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch("/api/v2" + path, {
      method,
      credentials: "same-origin",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", "X-Catchy-Request": "1" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      const error = Error(errors[result.error] || "error");
      error.code = result.error;
      throw error;
    }
    return result;
  } catch (error) {
    if (!error.code) throw Error(navigator.onLine ? "serverError" : "offline");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
function button(key, action, kind = "secondary", attributes = "") {
  return `<button class="${kind}" data-action="${action}" ${attributes}>${esc(t(key))}</button>`;
}
function field(key, name, type = "text", value = "", attributes = "") {
  return `<label>${esc(t(key))}<input name="${name}" type="${type}" value="${esc(value)}" ${attributes}></label>`;
}
function checkbox(key, name, checked) {
  return `<label class="check"><input name="${name}" type="checkbox" ${checked ? "checked" : ""}>${esc(t(key))}</label>`;
}
const levelLabel = (level) =>
  t(level === "high" ? "danger" : level === "caution" ? "careful" : "low");
function heading(title, description, action = "") {
  return `<div class="heading"><div><h1>${esc(t(title))}</h1><p>${esc(t(description))}</p></div>${action}</div>`;
}
function modal(html) {
  $("#modal-body").innerHTML = html;
  translate($("#modal"));
  if (!$("#modal").open) $("#modal").showModal();
}
function nav() {
  const pages = ["home", "history", "circle", "settings"];
  if (S.user?.role === "admin") pages.push("evaluation");
  $("#navigation").innerHTML = pages
    .map(
      (p) =>
        `<a href="#${p}" class="${S.page === p ? "current" : ""}">${esc(t(p))}</a>`,
    )
    .join("");
  $("#account").textContent = S.user ? S.user.name : t("signIn");
  $("#language").innerHTML = languages
    .map(
      (l) =>
        `<option value="${l.code}" ${l.code === language ? "selected" : ""} ${l.status === "planned" ? "disabled" : ""}>${esc(l.name)}${l.status === "preview" ? " · " + t("preview") : ""}</option>`,
    )
    .join("");
  document.body.classList.toggle("contrast", !!S.preferences.high_contrast);
  document.body.classList.toggle("large", !!S.preferences.large_text);
  translate();
}
function go(page) {
  if (S.running && page !== "home") {
    notice("phoneNote");
    location.hash = "home";
    return;
  }
  S.page = [
    "home",
    "history",
    "circle",
    "settings",
    "evaluation",
    "privacy",
    "terms",
  ].includes(page)
    ? page
    : "home";
  nav();
  render();
  window.scrollTo({ top: 0 });
}
function render() {
  ({
    home: home,
    history: history,
    circle: circle,
    settings: settings,
    evaluation: evaluation,
    privacy: legal,
    terms: legal,
  })[S.page]();
  translate();
}
function icon(name) {
  const paths = {
    speaker: "M5 9h4l5-4v14l-5-4H5z M18 8c3 2 3 6 0 8",
    typed: "M4 5h16v14H4z M7 9h10 M7 13h7",
    demo: "M8 5l11 7-11 7z",
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="${paths[name]}"/></svg>`;
}
function home() {
  const status = S.running ? "listening" : S.error ? "stopped" : "ready";
  $("#content").innerHTML =
    `${S.error ? `<div class="banner error" role="alert">${esc(t(S.error))}</div>` : ""}<div class="home-grid"><section class="intro"><p class="eyebrow">${esc(t("caption"))}</p><h1>${esc(t("tagline"))}</h1><p>${esc(t("intro"))}</p><div class="trust-line"><span aria-hidden="true">✓</span>${esc(t("secure"))}</div></section><section class="protection-card" aria-label="${esc(t("home"))}"><div class="card-top"><strong>${esc(t("home"))}</strong><span class="chip">${esc(t(languageInfo().status === "preview" ? "preview" : "beta"))}</span></div><div class="status-orb ${S.running ? "listening" : ""}" aria-hidden="true">${S.running ? "◉" : "✓"}</div><h2 id="live-status" class="status-title center" role="status">${esc(t(status))}</h2>${S.running ? button("stop", "stop", "primary start-button wide") : button("start", "start", "primary start-button wide")}<div class="mode-grid" role="group" aria-label="${esc(t("mode"))}">${["speaker", "typed", "demo"].map((m) => `<button data-mode="${m}" class="${S.mode === m ? "selected" : ""}" ${S.running ? "disabled" : ""}>${icon(m)}${esc(t(m))}</button>`).join("")}</div>${S.mode === "demo" ? `${!demos[language] ? `<p class="support">${esc(t("englishDemo"))}</p>` : ""}<div class="actions">${button("demoScam", "scam")}${button("demoGenuine", "genuine")}</div>` : ""}${S.mode === "typed" ? `<form id="turn-form"><label>${esc(t("message"))}<textarea name="text" maxlength="1500" required ${!S.running ? "disabled" : ""}></textarea></label><button class="primary wide" ${!S.running ? "disabled" : ""}>${esc(t("analyze"))}</button></form>` : ""}<p class="support">${esc(t("phoneNote"))}</p>${!S.user ? `<p class="support">${esc(t("guestNotice"))}</p>` : ""}<div id="live-result" aria-live="polite"></div></section></div><div id="session-details"></div><section class="steps">${[1, 2, 3].map((i) => `<article class="step"><span>0${i}</span><h3>${esc(t("step" + i))}</h3><p>${esc(t("step" + i + "Text"))}</p></article>`).join("")}</section>`;
  updateResults();
}
function updateResults() {
  if (S.page !== "home") return;
  const result = S.result;
  if (!result) return;
  $("#live-result").innerHTML =
    `<p class="banner risk-${result.level}">${esc(levelLabel(result.level))}</p><p class="support">${esc(t("endToEnd"))}: ${S.latency === null ? esc(t("notMeasured")) : Math.round(S.latency) + " " + t("ms")}</p>${result.model_status === "unavailable" ? `<p class="support">${esc(t("modelFallback"))}</p>` : ""}`;
  $("#session-details").innerHTML =
    `<section class="panel"><h2>${esc(t("signals"))}</h2>${result.signals.map((s) => `<div class="evidence"><strong>${esc(t("signal_" + s.key))}</strong><p>“${esc(s.quote)}”</p></div>`).join("") || `<p>${esc(t("low"))}</p>`}<p class="support">${esc(t("supportNote"))}</p>${!S.running && S.user && S.result?.level === "high" && S.preferences.alert_opt_in ? button("sendAlert", "sendAlert", "primary") : ""}<div class="transcript">${S.turns.map((turn) => `<div class="turn"><p>${esc(turn)}</p></div>`).join("")}</div></section>`;
}
function askConsent() {
  if (languageInfo().status === "preview") {
    notice("preview");
    return;
  }
  if (!navigator.onLine) {
    S.error = "offline";
    render();
    return;
  }
  modal(
    `<h2>${esc(t("consentTitle"))}</h2><p>${esc(t("consentText"))}</p>${checkbox("consentCheck", "consent", false)}<div class="actions">${button("continue", "consent", "primary")}${button("cancel", "close")}</div>`,
  );
}
async function start() {
  if (!$("[name=consent]")?.checked) {
    notice("consentCheck");
    return;
  }
  $("#modal").close();
  S.error = null;
  S.turns = [];
  S.result = null;
  S.latency = null;
  S.alertShown = false;
  S.generation++;
  const generation = S.generation;
  S.queue = [];
  try {
    if (S.mode === "speaker" && S.preferences.asr === "selfhost" && !S.user)
      throw Error("authNeeded");
    const call = S.user
      ? await createCurrentSession(
          () =>
            api("/calls", "POST", {
              title: t("sessionTitle"),
              language,
              mode: S.mode,
              consent: true,
            }),
          () => generation === S.generation,
          (stale) => api(`/calls/${stale.id}/finish`, "POST", {}),
        )
      : null;
    if (generation !== S.generation) return;
    S.call = call;
    S.running = true;
    location.hash = "home";
    go("home");
    if (navigator.wakeLock)
      try {
        const wake = await navigator.wakeLock.request("screen");
        if (generation !== S.generation) {
          await wake.release();
          return;
        }
        S.wake = wake;
      } catch {
        notice("phoneNote");
      }
    try {
      const native = await import("./native.js");
      await native.keepAwake();
      if (generation !== S.generation && !S.running) await native.allowSleep();
    } catch {}
    if (generation !== S.generation || !S.running) return;
    if (S.mode === "speaker") {
      const provider = await chooseASR(S.preferences.asr);
      if (generation !== S.generation || !S.running) return;
      S.asr = provider;
      await provider.start({
        language: languageInfo().speech,
        onText: (text, ended) => {
          if (generation === S.generation) enqueue(text, ended);
        },
        onError: (key) => {
          if (generation === S.generation) fail(key);
        },
      });
      if (generation !== S.generation || !S.running) {
        provider.stop();
        return;
      }
      resetSilence();
    }
    if (S.mode === "demo") playDemo(0, S.generation);
    if (S.user && S.mode !== "demo") connectLive();
  } catch (error) {
    if (generation !== S.generation) return;
    await fail(
      error.name === "NotAllowedError" ? "permissionDenied" : error.message,
    );
  }
}
function resetSilence() {
  clearTimeout(S.silence);
  S.silence = setTimeout(() => {
    if (S.running && S.mode === "speaker") fail("silence");
  }, 25000);
}
async function fail(key) {
  await stop(false);
  S.error = [
    "permissionDenied",
    "offline",
    "serverError",
    "speechError",
    "unsupported",
    "background",
    "silence",
    "authNeeded",
    "asrUnavailable",
  ].includes(key)
    ? key
    : "serverError";
  if (S.page === "home") home();
  notice(S.error);
}
async function stop(show = true) {
  const call = S.call;
  S.running = false;
  clearTimeout(S.timer);
  clearTimeout(S.silence);
  S.asr?.stop();
  S.asr = null;
  S.queue = [];
  S.generation++;
  S.socket?.close();
  S.socket = null;
  for (const job of S.pending.values()) job.reject(Error("serverError"));
  S.pending.clear();
  try {
    await S.wake?.release();
  } catch {}
  S.wake = null;
  try {
    const native = await import("./native.js");
    await native.allowSleep();
  } catch {}
  window.speechSynthesis?.cancel();
  if ($("#danger").open) $("#danger").close();
  if (call && S.user)
    try {
      await api(`/calls/${call.id}/finish`, "POST", {});
    } catch {
      S.error = "serverError";
    }
  if (S.page === "home") home();
  if (show) notice("stopped");
}
function connectLive() {
  if (!S.call) return;
  const ws = new WebSocket(
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v2/live/${S.call.id}`,
  );
  S.socket = ws;
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.error) {
      for (const job of S.pending.values()) job.reject(Error("serverError"));
      S.pending.clear();
      fail("serverError");
      return;
    }
    const job = S.pending.get(data.request_id);
    if (job) {
      S.pending.delete(data.request_id);
      job.resolve(data);
    }
  };
  ws.onclose = () => {
    if (S.running && S.socket === ws) {
      S.socket = null;
      if (S.pending.size) fail("serverError");
    }
  };
}
function enqueue(text, ended = null) {
  if (!S.running) return;
  resetSilence();
  if (S.queue.length >= 10) {
    fail("speechError");
    return;
  }
  S.queue.push({ text, ended });
  drain();
}
async function drain() {
  if (S.busy) return;
  S.busy = true;
  try {
    while (S.running && S.queue.length) {
      const item = S.queue.shift(),
        generation = S.generation,
        request_id = crypto.randomUUID();
      let result;
      const payload = { text: item.text, request_id };
      if (S.user) {
        if (S.socket?.readyState === 1) {
          result = await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
              S.pending.delete(request_id);
              reject(Error("serverError"));
            }, 10000);
            S.pending.set(request_id, {
              resolve: (v) => {
                clearTimeout(timeout);
                resolve(v);
              },
              reject: (e) => {
                clearTimeout(timeout);
                reject(e);
              },
            });
            S.socket.send(JSON.stringify(payload));
          });
        } else result = await api(`/calls/${S.call.id}/turns`, "POST", payload);
      } else
        result = await api("/guest/analyze", "POST", {
          turns: [...S.turns, item.text],
          language,
          consent: true,
        });
      if (generation !== S.generation) break;
      S.turns.push(item.text);
      S.result = result;
      S.latency = item.ended === null ? null : performance.now() - item.ended;
      updateResults();
      if (result.level === "high" && !S.alertShown) await warn();
    }
  } catch (error) {
    await fail(error.message);
  } finally {
    S.busy = false;
  }
}
async function warn() {
  $("#danger-feedback").hidden = true;
  S.alertShown = true;
  $("#danger").showModal();
  navigator.vibrate?.([180, 90, 180]);
  try {
    const native = await import("./native.js");
    await native.haptic();
  } catch {}
  if (S.preferences.spoken_warnings) {
    const spoken = await speakWarning(t("warning"), languageInfo().speech);
    $("#voice-fallback").hidden = spoken;
  }
  eventCount("alert_shown");
}
async function eventCount(event) {
  if (!S.preferences.analytics) return;
  try {
    await api("/analytics", "POST", { event, consent: true });
  } catch {}
}
const demos = {
  en: {
    scam: [
      "I am from the bank security team.",
      "Your account is frozen. Act right now.",
      "Keep this secret. Read your OTP to me.",
    ],
    genuine: [
      "This is your hospital appointment reminder.",
      "Please arrive today.",
      "Never share your OTP or password.",
    ],
  },
  hi: {
    scam: [
      "मैं बैंक अधिकारी हूँ।",
      "आपका खाता बंद हो जाएगा। तुरंत जवाब दें।",
      "किसी को मत बताना। अपना ओटीपी बताएं।",
    ],
    genuine: [
      "यह अस्पताल से आपकी मुलाकात का संदेश है।",
      "कृपया आज समय पर आएं।",
      "ओटीपी साझा न करें।",
    ],
  },
  te: {
    scam: [
      "నేను బ్యాంకు అధికారి.",
      "మీ ఖాతా బ్లాక్ అవుతుంది. వెంటనే మాట్లాడండి.",
      "ఎవరికీ చెప్పవద్దు. మీ ఓటీపీ చెప్పండి.",
    ],
    genuine: [
      "ఇది ఆసుపత్రి అపాయింట్‌మెంట్ గుర్తు.",
      "దయచేసి ఈరోజు సమయానికి రండి.",
      "మీ ఓటీపీ చెప్పకండి.",
    ],
  },
};
S.demoType = "scam";
function playDemo(index, generation) {
  if (!S.running || generation !== S.generation) return;
  const lines = (demos[language] || demos.en)[S.demoType];
  if (index >= lines.length) return;
  enqueue(lines[index]);
  S.timer = setTimeout(() => playDemo(index + 1, generation), 3000);
}
async function history() {
  if (!S.user) {
    $("#content").innerHTML = heading(
      "history",
      "authNeeded",
      button("signIn", "account", "primary"),
    );
    return;
  }
  $("#content").innerHTML =
    heading("history", "review") + `<p>${esc(t("loading"))}</p>`;
  try {
    const data = await api("/calls");
    if (S.page !== "history") return;
    S.calls = data.calls;
    $("#content").innerHTML =
      heading("history", "review", button("export", "export")) +
      `<div class="toolbar"><input id="search" aria-label="${esc(t("search"))}" placeholder="${esc(t("search"))}"><select id="risk-filter" aria-label="${esc(t("risk"))}"><option value="all">${esc(t("all"))}</option><option value="high">${esc(t("danger"))}</option><option value="caution">${esc(t("careful"))}</option><option value="low">${esc(t("low"))}</option></select></div><section class="panel table-wrap"><table><thead><tr><th>${esc(t("session"))}</th><th>${esc(t("date"))}</th><th>${esc(t("risk"))}</th><th>${esc(t("details"))}</th></tr></thead><tbody id="calls"></tbody></table><p id="empty-history" hidden>${esc(t("emptyHistory"))}</p></section>`;
    filterHistory();
  } catch (error) {
    notice(error.message);
  }
}
function filterHistory() {
  const q = $("#search").value.toLowerCase(),
    filter = $("#risk-filter").value;
  const calls = S.calls.filter(
    (c) =>
      c.title.toLowerCase().includes(q) &&
      (filter === "all" ||
        (c.score >= 60 ? "high" : c.score >= 30 ? "caution" : "low") ===
          filter),
  );
  $("#calls").innerHTML = calls
    .map(
      (c) =>
        `<tr><td>${esc(c.title)}<p>${esc(languages.find((l) => l.code === c.language)?.name || c.language)}</p></td><td>${new Date(c.created * 1000).toLocaleString(language)}</td><td>${esc(levelLabel(c.score >= 60 ? "high" : c.score >= 30 ? "caution" : "low"))}</td><td><div class="actions">${button("details", "detail", "secondary", `data-id="${c.id}"`)}${button("delete", "deleteCall", "secondary danger-text", `data-id="${c.id}"`)}</div></td></tr>`,
    )
    .join("");
  $("#empty-history").hidden = !!calls.length;
}
async function detail(id) {
  try {
    const data = await api("/calls/" + id);
    modal(
      `<h2>${esc(data.call.title)}</h2><p>${esc(levelLabel(data.call.score >= 60 ? "high" : data.call.score >= 30 ? "caution" : "low"))}</p>${data.turns.length ? data.turns.map((turn) => `<div class="turn"><p>${esc(turn.text)}</p></div>`).join("") : `<p>${esc(t("noTranscript"))}</p>`}${data.evidence.map((e) => `<div class="evidence"><strong>${esc(t("signal_" + e.key))}</strong><p>${esc(e.quote)}</p></div>`).join("")}<div class="actions">${button("back", "close")}</div>`,
    );
  } catch (error) {
    notice(error.message);
  }
}
async function circle() {
  if (!S.user) {
    $("#content").innerHTML = heading(
      "circle",
      "authNeeded",
      button("signIn", "account", "primary"),
    );
    return;
  }
  $("#content").innerHTML = heading("circle", "trustedHelp");
  try {
    const data = await api("/contacts");
    if (S.page !== "circle") return;
    S.contacts = data.contacts;
    $("#content").innerHTML =
      heading("circle", "trustedHelp") +
      (!S.user.verified
        ? `<div class="banner">${esc(t("verificationNeeded"))} ${button("verifyEmail", "verifyEmail")}</div>`
        : "") +
      `<section class="panel"><h2>${esc(t("invite"))}</h2><p>${esc(t("inviteNotice"))}</p><form id="invite-form" class="form-grid">${field("name", "name", "text", "", 'required minlength="2" maxlength="80"')}${field("contactEmail", "email", "email", "", 'required maxlength="254"')}<button class="primary span2" ${!S.user.verified ? "disabled" : ""}>${esc(t("sendInvite"))}</button></form></section><section class="panel">${S.contacts.map((c) => `<article class="contact"><div><h3>${esc(c.name)}</h3><p>${esc(c.email)}</p><span class="chip">${esc(t(c.status === "accepted" ? "accepted" : "pending"))}</span>${c.phone ? `<p>${esc(c.phone)}</p>` : ""}</div><div class="actions">${c.status === "accepted" ? `${button("alerts", "toggleOwner", "secondary", `data-id="${c.id}" data-enabled="${!c.alerts_owner}" aria-pressed="${c.alerts_owner}"`)}${button("testAlert", "testAlert", "secondary", `data-id="${c.id}"`)}` : ""}${button("delete", "removeContact", "secondary danger-text", `data-id="${c.id}"`)}</div></article>`).join("") || `<p>${esc(t("invite"))}</p>`}</section>${data.incoming.length ? `<section class="panel"><h2>${esc(t("incoming"))}</h2>${data.incoming.map((c) => `<article class="contact"><div><h3>${esc(c.owner_name)}</h3><p>${esc(t("accepted"))}</p></div><div class="actions">${button("alerts", "toggleOwner", "secondary", `data-id="${c.id}" data-enabled="${!c.alerts_recipient}" aria-pressed="${c.alerts_recipient}"`)}${button("delete", "removeContact", "secondary danger-text", `data-id="${c.id}"`)}</div></article>`).join("")}</section>` : ""}`;
    if (S.invitation) showInvitation();
  } catch (error) {
    notice(error.message);
  }
}
function showInvitation() {
  if (!S.user) {
    authForm();
    return;
  }
  modal(
    `<h2>${esc(t("incoming"))}</h2><p>${esc(t("inviteNotice"))}</p>${!S.user.verified ? `<p>${esc(t("verificationNeeded"))}</p>${button("verifyEmail", "verifyEmail")}` : `<form id="accept-form">${field("phone", "phone", "tel", "", 'required minlength="7" maxlength="25"')}${checkbox("alerts", "alerts", false)}<div class="actions"><button class="primary">${esc(t("acceptInvite"))}</button>${button("declineInvite", "declineInvite")}</div></form>`}`,
  );
}
function settings() {
  const p = S.preferences;
  $("#content").innerHTML =
    heading("settings", "humanReview") +
    `<form id="preferences-form"><section class="panel"><h2>${esc(t("privacy"))}</h2>${[
      ["retention", "retain_transcript", "retentionHelp"],
      ["spoken", "spoken_warnings", ""],
      ["contrast", "high_contrast", ""],
      ["large", "large_text", ""],
      ["alertOptIn", "alert_opt_in", "trustedHelp"],
      ["analytics", "analytics", "analyticsHelp"],
    ]
      .map(
        ([key, name, help]) =>
          `<div class="setting-row"><div><label for="${name}">${esc(t(key))}</label>${help ? `<p>${esc(t(help))}</p>` : ""}</div><input id="${name}" name="${name}" type="checkbox" ${p[name] ? "checked" : ""}></div>`,
      )
      .join(
        "",
      )}<label>${esc(t("retentionDays"))}<input type="number" name="retention_days" min="1" max="90" value="${p.retention_days}"></label><label>${esc(t("provider"))}<select name="asr"><option value="browser" ${p.asr === "browser" ? "selected" : ""}>${esc(t("browserAsr"))}</option><option value="selfhost" ${p.asr === "selfhost" ? "selected" : ""}>${esc(t("selfhostAsr"))}</option></select></label><p>${esc(t("asrNotice"))}</p><div class="toolbar"><button class="primary">${esc(t("save"))}</button></div></section></form><section class="panel"><h2>${esc(t("account"))}</h2><p>${esc(S.user?.email || t("guest"))}</p><p>${esc(t(S.user?.verified ? "verified" : "notVerified"))}</p><div class="toolbar">${S.user ? button("verifyEmail", "verifyEmail") + button("signOut", "logout") + button("deleteAll", "deleteAccount", "secondary danger-text") : button("signIn", "account", "primary")}</div></section><section class="panel"><h2>${esc(t("languageSupport"))}</h2><p>${esc(t("humanReview"))}</p><div class="toolbar">${languages.map((l) => `<span class="chip">${esc(l.name)} · ${esc(t(l.status === "beta" ? "beta" : l.status === "preview" ? "preview" : "planned"))}</span>`).join("")}</div></section>`;
}
function authForm(register = false) {
  modal(
    `<h2>${esc(t(register ? "register" : "signIn"))}</h2><p>${esc(t("signinPrivacy"))}</p><form id="auth-form" data-register="${register}">${register ? field("name", "name", "text", "", 'required minlength="2" maxlength="80" autocomplete="name"') : ""}${field("email", "email", "email", "", 'required autocomplete="email"')}${field("password", "password", "password", "", 'required minlength="10" maxlength="128" autocomplete="' + (register ? "new-password" : "current-password") + '"')}<p id="form-error" class="form-error" role="alert"></p><button class="primary wide">${esc(t(register ? "register" : "signIn"))}</button></form><div class="actions">${button(register ? "signIn" : "register", register ? "loginForm" : "registerForm")}${button("guest", "close")}${!register ? button("forgotPassword", "forgotPassword") : ""}</div><p class="support">${esc(t("accountLocal"))}</p>`,
  );
}
function resetForm(email = "", requested = false, code = null) {
  modal(
    `<h2>${esc(t("resetPassword"))}</h2><p>${esc(t(requested ? "resetRequested" : "resetHelp"))}</p>${code ? `<p>${esc(t("developmentCode"))}: ${esc(code)}</p>` : ""}<form id="${requested ? "reset-confirm-form" : "reset-request-form"}">${field("email", "email", "email", email, 'required autocomplete="email"')}${requested ? field("verificationCode", "code", "text", "", 'required pattern="[0-9]{6}" maxlength="6" inputmode="numeric" autocomplete="one-time-code"') + field("newPassword", "password", "password", "", 'required minlength="10" maxlength="128" autocomplete="new-password"') : ""}<p id="form-error" class="form-error" role="alert"></p><button class="primary wide">${esc(t(requested ? "resetPassword" : "sendCode"))}</button></form><div class="actions">${button("signIn", "loginForm")}${button("cancel", "close")}</div>`,
  );
}
function verifyForm() {
  modal(
    `<h2>${esc(t("verifyEmail"))}</h2><p>${esc(t("accountLocal"))}</p>${button("sendCode", "sendCode", "primary")}<form id="verify-form">${field("verificationCode", "code", "text", "", 'required pattern="[0-9]{6}" maxlength="6" inputmode="numeric"')}<button class="primary">${esc(t("verify"))}</button></form><div class="actions">${button("back", "close")}</div>`,
  );
}
async function evaluation() {
  if (S.user?.role !== "admin") {
    $("#content").innerHTML = heading("evaluation", "adminOnly");
    return;
  }
  $("#content").innerHTML =
    heading(
      "evaluation",
      "synthetic",
      button("runEvaluation", "runEvaluation", "primary"),
    ) + '<div id="evaluation-report"></div>';
  try {
    showEvaluation(await api("/evaluation"));
  } catch (error) {
    notice(error.message);
  }
}
function showEvaluation(report) {
  if (S.page !== "evaluation") return;
  $("#evaluation-report").innerHTML = (report.languages || [])
    .map(
      (row) =>
        `<section class="panel"><h2>${esc(languages.find((l) => l.code === row.language)?.name || row.language)}</h2><p>${esc(t(row.dataset_kind === "lexicon-derived-smoke" ? "smokeDataset" : "synthetic"))}</p><div class="metrics">${["precision", "recall", "f1"].map((metric) => `<div class="metric">${esc(t(metric))}<strong>${(row[metric] * 100).toFixed(1)}%</strong></div>`).join("")}</div><p>${esc(t("latency"))}: p95 ${row.p95_ms} ${esc(t("ms"))}</p><p>${esc(t("endToEnd"))}: ${esc(t("notMeasured"))}</p></section>`,
    )
    .join("");
}
async function legal() {
  const key = S.page;
  $("#content").innerHTML = heading(key, "privacy");
  try {
    const document = await fetch(
      `/locales/legal-${["en", "hi", "te"].includes(language) ? language : "en"}.json`,
    ).then((r) => r.json());
    if (S.page !== key) return;
    $("#content").innerHTML =
      `<article class="panel legal">${!["en", "hi", "te"].includes(language) ? `<p>${esc(t("englishFallback"))}</p>` : ""}<h1>${esc(t(key))}</h1>${document[key].map((section) => `<h2>${esc(section.title)}</h2><p>${esc(section.text)}</p>`).join("")}</article>`;
  } catch {
    notice("serverError");
  }
}
async function refreshUser() {
  const data = await api("/me");
  S.user = data.user;
  S.preferences = { ...S.preferences, ...data.preferences };
  localStorage.setItem("catchy-preferences", JSON.stringify(S.preferences));
  nav();
}
async function callTrusted() {
  if (!S.user) {
    notice("noContact");
    return;
  }
  try {
    const { contacts } = await api("/contacts");
    const contact = contacts.find((c) => c.status === "accepted" && c.phone);
    if (!contact) {
      notice("noContact");
      return;
    }
    await stop(false);
    eventCount("contact_called");
    location.href = "tel:" + contact.phone.replace(/[^+\d]/g, "");
  } catch (error) {
    notice(error.message);
  }
}
async function requestAlert(id, test = false) {
  try {
    const result = await api(`/contacts/${id}/notify`, "POST", {
      test,
      call_id: test ? null : S.call?.id,
    });
    notice(
      result.status === "provider_accepted" ? "alertSent" : "deliveryUncertain",
    );
  } catch (error) {
    notice(error.message);
  }
}
document.addEventListener("click", async (event) => {
  const element = event.target.closest("[data-action],[data-mode]");
  if (!element) return;
  const action = element.dataset.action,
    id = element.dataset.id;
  try {
    if (element.dataset.mode) {
      if (!S.running) {
        S.mode = element.dataset.mode;
        home();
      }
      return;
    }
    if (action === "start") askConsent();
    if (action === "consent") await start();
    if (action === "stop") await stop();
    if (action === "close") $("#modal").close();
    if (action === "account" || action === "loginForm") authForm();
    if (action === "registerForm") authForm(true);
    if (action === "forgotPassword") resetForm();
    if (action === "scam" || action === "genuine") {
      if (S.running) return;
      S.demoType = action;
      S.mode = "demo";
      askConsent();
    }
    if (action === "verifyEmail") verifyForm();
    if (action === "sendCode") {
      element.disabled = true;
      const response = await api("/verify/request", "POST", {});
      notice(
        response.development_code
          ? t("developmentCode") + ": " + response.development_code
          : "verificationSent",
        !!response.development_code,
      );
      element.disabled = false;
    }
    if (action === "detail") await detail(id);
    if (action === "deleteCall" && confirm(t("deleteConfirm"))) {
      await api("/calls/" + id, "DELETE");
      history();
    }
    if (action === "export") {
      const data = S.calls.map(
        ({ id, title, language, mode, status, score, created }) => ({
          id,
          title,
          language,
          mode,
          status,
          score,
          created,
        }),
      );
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "catchy-metadata.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    if (action === "copyLink") {
      try {
        await navigator.clipboard.writeText($("#invitation-url").value);
        notice("saved");
      } catch {
        $("#invitation-url").select();
      }
    }
    if (action === "toggleOwner") {
      await api("/contacts/" + id + "/alerts", "POST", {
        enabled: element.dataset.enabled === "true",
      });
      circle();
    }
    if (action === "removeContact" && confirm(t("deleteConfirm"))) {
      await api("/contacts/" + id, "DELETE");
      circle();
    }
    if (action === "testAlert") await requestAlert(id, true);
    if (action === "sendAlert") {
      const data = await api("/contacts");
      const contact = data.contacts.find(
        (c) => c.status === "accepted" && c.alerts_owner && c.alerts_recipient,
      );
      if (contact) await requestAlert(contact.id);
      else notice("noContact");
    }
    if (action === "declineInvite") {
      S.invitation = null;
      sessionStorage.removeItem("catchy-invitation");
      $("#modal").close();
      location.hash = "circle";
    }
    if (action === "logout") {
      await stop(false);
      await api("/logout", "POST", {});
      S.user = null;
      S.contacts = [];
      S.calls = [];
      S.turns = [];
      S.result = null;
      S.call = null;
      localStorage.removeItem("catchy-preferences");
      S.preferences = defaultPreferences();
      location.hash = "home";
      go("home");
    }
    if (action === "deleteAccount" && confirm(t("deleteAllConfirm"))) {
      await stop(false);
      await api("/account", "DELETE");
      S.user = null;
      S.calls = [];
      S.contacts = [];
      S.turns = [];
      S.result = null;
      localStorage.removeItem("catchy-preferences");
      S.preferences = defaultPreferences();
      notice("saved");
      go("home");
    }
    if (action === "runEvaluation") {
      element.disabled = true;
      showEvaluation(await api("/evaluation", "POST", {}));
      element.disabled = false;
    }
  } catch (error) {
    element.disabled = false;
    notice(error.message);
  }
});
document.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target,
    values = Object.fromEntries(new FormData(form)),
    submit = $("button[type=submit],button.primary", form);
  if (submit) submit.disabled = true;
  try {
    if (form.id === "auth-form") {
      const result = await api(
        "/auth/" + (form.dataset.register === "true" ? "register" : "login"),
        "POST",
        values,
      );
      S.user = result.user;
      S.preferences = { ...S.preferences, ...result.preferences };
      $("#modal").close();
      nav();
      render();
      if (S.invitation) showInvitation();
    }
    if (form.id === "reset-request-form") {
      const result = await api("/password/request", "POST", values);
      resetForm(values.email, true, result.development_code);
      if (!result.email_configured && !result.development_code)
        notice("providerUnavailable");
    }
    if (form.id === "reset-confirm-form") {
      await api("/password/confirm", "POST", values);
      await stop(false);
      S.user = null;
      S.call = null;
      S.calls = [];
      S.contacts = [];
      S.turns = [];
      S.result = null;
      S.preferences = defaultPreferences();
      localStorage.removeItem("catchy-preferences");
      go("home");
      authForm();
      notice("resetSuccess");
    }
    if (form.id === "turn-form") {
      enqueue(values.text);
      form.reset();
    }
    if (form.id === "invite-form") {
      const result = await api("/contacts", "POST", values);
      modal(
        `<h2>${esc(t("invitationLink"))}</h2><p>${esc(t("inviteNotice"))}</p><input id="invitation-url" aria-label="${esc(t("invitationLink"))}" readonly value="${esc(result.invitation_url)}"><div class="actions">${button("copyLink", "copyLink", "primary")}${button("back", "close")}</div>`,
      );
      await circle();
    }
    if (form.id === "accept-form") {
      await api("/contacts/accept", "POST", {
        token: S.invitation,
        phone: values.phone,
        alerts: !!values.alerts,
      });
      S.invitation = null;
      sessionStorage.removeItem("catchy-invitation");
      $("#modal").close();
      notice("inviteAccepted");
      await refreshUser();
      location.hash = "circle";
      go("circle");
    }
    if (form.id === "verify-form") {
      await api("/verify/confirm", "POST", values);
      await refreshUser();
      $("#modal").close();
      notice("verified");
      render();
      if (S.invitation) showInvitation();
    }
    if (form.id === "preferences-form") {
      const preferences = {
        language,
        retention_days: Number(values.retention_days),
        asr: values.asr,
      };
      for (const key of [
        "retain_transcript",
        "spoken_warnings",
        "high_contrast",
        "large_text",
        "analytics",
        "alert_opt_in",
      ])
        preferences[key] = !!values[key];
      if (S.user) await api("/preferences", "POST", preferences);
      S.preferences = { ...S.preferences, ...preferences };
      localStorage.setItem("catchy-preferences", JSON.stringify(S.preferences));
      nav();
      notice("saved");
    }
  } catch (error) {
    if ($("#form-error")) $("#form-error").textContent = t(error.message);
    else notice(error.message);
  } finally {
    if (submit) submit.disabled = false;
  }
});
$("#account").addEventListener("click", () =>
  S.user ? (location.hash = "settings") : authForm(),
);
$("#language").addEventListener("change", async (event) => {
  if (S.running) await stop(false);
  await loadLanguage(event.target.value);
  nav();
  render();
  if (languageInfo().status === "preview") notice("preview");
});
$("#danger-stop").addEventListener("click", async () => {
  eventCount("alert_dismissed");
  await stop();
});
$("#danger-call").addEventListener("click", callTrusted);
$("#danger").addEventListener("cancel", (event) => event.preventDefault());
document.addEventListener("input", (event) => {
  if (event.target.id === "search") filterHistory();
});
document.addEventListener("change", (event) => {
  if (event.target.id === "risk-filter") filterHistory();
});
window.addEventListener("hashchange", () => {
  const hash = location.hash.slice(1);
  if (hash.startsWith("invite=")) {
    S.invitation = hash.slice(7);
    sessionStorage.setItem("catchy-invitation", S.invitation);
    location.hash = "circle";
    showInvitation();
  } else go(hash || "home");
});
window.addEventListener("catchy-background", () => {
  if (S.running) fail("background");
});
window.addEventListener("offline", () => {
  if (S.running) fail("offline");
  else {
    S.error = "offline";
    render();
  }
});
window.addEventListener("online", () => {
  S.error = null;
  if (S.page === "home") home();
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden && S.running) fail("background");
});
window.addEventListener("pagehide", () => {
  S.asr?.stop();
  S.wake?.release();
  window.speechSynthesis?.cancel();
});
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installEvent = event;
});
$("#install").addEventListener("click", async () => {
  if (installEvent) {
    await installEvent.prompt();
    installEvent = null;
  } else notice("installHelp");
});
async function boot() {
  try {
    const first = !localStorage.getItem("catchy-language");
    await loadLanguage();
    try {
      S.preferences = {
        ...S.preferences,
        ...JSON.parse(localStorage.getItem("catchy-preferences") || "{}"),
      };
    } catch {}
    S.invitation = sessionStorage.getItem("catchy-invitation");
    try {
      S.health = await fetch("/api/health").then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      });
      try {
        await refreshUser();
      } catch (error) {
        if (error.code !== "sign_in_required") throw error;
      }
    } catch {
      S.error = "serverError";
    }
    const hash = location.hash.slice(1);
    if (hash.startsWith("invite=")) {
      S.invitation = hash.slice(7);
      sessionStorage.setItem("catchy-invitation", S.invitation);
      go("circle");
      showInvitation();
    } else go(hash || "home");
    if (first && !S.invitation)
      modal(
        `<h2>${esc(t("chooseLanguage"))}</h2><div class="actions">${languages
          .filter((l) => l.status === "beta")
          .map(
            (l) =>
              `<button class="secondary" data-language="${l.code}">${esc(l.name)}</button>`,
          )
          .join("")}</div><p class="support">${esc(t("humanReview"))}</p>`,
      );
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    window.speechSynthesis?.getVoices();
  } catch {
    document.getElementById("content").textContent =
      "Catchy could not load. Restart the server and reload.";
  }
}
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-language]");
  if (button) {
    await loadLanguage(button.dataset.language);
    $("#modal").close();
    nav();
    render();
  }
});
boot();
