"use strict";
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
const scenarios = [
  {
    id: "bank",
    title: "The “safe account” scam",
    tag: "SCAM SIMULATION",
    icon: "◈",
    desc: "An official-sounding caller. A little pressure. Then a request that changes everything.",
    turns: [
      "Hello, I am calling from your bank security team about your account.",
      "Your account will be frozen. You need to act right now.",
      "Keep this confidential. Do not tell your family and stay on the line.",
      "Read the six-digit verification code to me, then transfer your money to our safe account.",
    ],
  },
  {
    id: "hospital",
    title: "A genuinely urgent call",
    tag: "LEGITIMATE SIMULATION",
    icon: "✚",
    desc: "An urgent appointment reminder shows why urgency alone should not trigger a high-risk alert.",
    turns: [
      "Hello, this is the hospital appointment desk calling about your visit.",
      "Your appointment is today. Please arrive within twenty minutes if possible.",
      "You can call the hospital number on your appointment letter to confirm.",
      "Never share your OTP or password with anyone. We do not ask for payment on this call.",
    ],
  },
  {
    id: "support",
    title: "The helpful stranger",
    tag: "SCAM SIMULATION",
    icon: "◇",
    desc: "A familiar support story becomes a remote-access request. See exactly when the risk changes.",
    turns: [
      "This is technical support. We noticed a problem with your computer.",
      "Your files could be blocked unless we fix this immediately.",
      "Please install AnyDesk so that I can get remote access.",
      "Do not tell anyone about this investigation. Send money to complete the repair.",
    ],
  },
];
const state = {
  user: null,
  page: "overview",
  calls: [],
  contacts: [],
  settings: { retain_transcript: false, spoken_warnings: false },
  authMode: "register",
  mode: "demo",
  scenario: scenarios[0],
  session: null,
  turns: [],
  analysis: null,
  running: false,
  busy: false,
  timer: null,
  recognition: null,
  heard: [],
  generation: 0,
  guestHistory: [],
  provider: "rules",
};
let toastTimer;
function toast(m) {
  $("#toast").textContent = m;
  $("#toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 4500);
}
async function api(path, method = "GET", body) {
  const o = {
    method,
    credentials: "same-origin",
    headers: { "X-Catchy-Request": "1" },
  };
  if (body !== undefined) {
    o.headers["Content-Type"] = "application/json";
    o.body = JSON.stringify(body);
  }
  const controller = new AbortController();
  o.signal = controller.signal;
  const timer = setTimeout(() => controller.abort(), 12000);
  let r, data;
  try {
    r = await fetch("/api" + path, o);
    data = await r.json();
  } catch {
    throw Error(
      "Connection interrupted. Check the server and session history before retrying.",
    );
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) throw Error(data.error || "Please try again.");
  return data;
}
const date = (v) =>
    new Date(v).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    }),
  level = (s) => (s >= 60 ? "high" : s >= 30 ? "caution" : "low"),
  label = (s) => (s >= 60 ? "High risk" : s >= 30 ? "Caution" : "Low signals");
const badge = (s) =>
    `<span class="badge ${level(s)}">${s >= 60 ? "!" : "·"} ${label(s)}</span>`,
  initials = (n) =>
    n
      .split(/\s+/)
      .map((n) => n[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();
function heading(e, t, d, a = "") {
  return `<div class="page-heading"><div><span class="eyebrow">${e}</span><h1>${t}</h1><p>${d}</p></div>${a}</div>`;
}
function empty(t, c, a = "") {
  return `<div class="empty"><span class="empty-symbol">◈</span><strong>${t}</strong>${c}${a ? "<br><br>" + a : ""}</div>`;
}
function updateAccount() {
  const u = state.user;
  $("#account-name").textContent = u ? u.name : "Guest workspace";
  $("#account-detail").textContent = u
    ? "Personal account"
    : "Sign in to save your sessions";
  $("#avatar").textContent = $("#top-avatar").textContent = u
    ? initials(u.name)
    : "G";
}
async function refresh() {
  if (!state.user) return;
  const [c, t, s] = await Promise.all([
    api("/calls"),
    api("/contacts"),
    api("/settings"),
  ]);
  state.calls = c.calls;
  state.contacts = t.contacts;
  state.settings = s;
}
const allCalls = () => (state.user ? state.calls : state.guestHistory);
function navigate(p) {
  if (
    !["overview", "monitor", "history", "contacts", "lab", "settings"].includes(
      p,
    )
  )
    p = "overview";
  state.page = p;
  location.hash = p;
  $(".sidebar").classList.remove("open");
  $$(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.page === p),
  );
  $("#page-label").textContent = {
    overview: "Overview",
    monitor: "Live protection",
    history: "Session history",
    contacts: "Trusted circle",
    lab: "Demo studio",
    settings: "Preferences",
  }[p];
  render();
  window.scrollTo({ top: 0 });
}
function render() {
  ({
    overview: renderOverview,
    monitor: renderMonitor,
    history: renderHistory,
    contacts: renderContacts,
    lab: renderLab,
    settings: renderSettings,
  })[state.page]();
}
function renderOverview() {
  const calls = allCalls(),
    completed = calls.filter((c) => c.status === "completed"),
    flags = calls.filter((c) => c.score >= 60);
  $("#page").innerHTML =
    heading(
      "A LITTLE CLARITY. A LOT MORE PEACE OF MIND.",
      state.user
        ? `Good to have you here, ${esc(state.user.name.split(" ")[0])}.`
        : "Welcome to Catchy.",
      "Your space for safer conversations and the people who matter.",
      `<span class="date-tag">◷ &nbsp; ${new Date().toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}</span>`,
    ) +
    `
<section class="hero"><div class="hero-copy"><span class="hero-pill"><i></i> A SECOND PAIR OF EARS</span><h2>Stay connected.<br><em>Stay one step ahead.</em></h2><p>Catchy helps you recognize pressure and suspicious requests, so you can focus on the conversation.</p><div class="hero-actions"><button class="btn primary" data-page="monitor">◉ &nbsp; Start protection <span>↗</span></button><button class="btn ghost" data-page="lab">Explore the demo &nbsp; →</button></div></div><div class="hero-art" aria-hidden="true"><div class="orbit three"></div><div class="orbit two"></div><div class="orbit"></div><div class="shield">✓</div><div class="art-label a"><span>✓</span><div>A little more confidence<small>Every conversation matters</small></div></div><div class="art-label b"><span>◈</span><div>Privacy comes first<small>No raw audio stored</small></div></div></div></section>
<section class="stats" aria-label="Your session statistics"><div class="stat"><div><span class="stat-label">Sessions completed</span><strong class="stat-value">${String(completed.length).padStart(2, "0")}</strong><span class="stat-note">${state.user ? "From your saved history" : "Your demos this visit"}</span></div><span class="stat-icon">◷</span></div><div class="stat"><div><span class="stat-label">High-risk sessions</span><strong class="stat-value">${String(flags.length).padStart(2, "0")}</strong><span class="stat-note">${flags.length ? "<b>Review your warnings</b>" : "No warnings in your history"}</span></div><span class="stat-icon">◇</span></div><div class="stat"><div><span class="stat-label">Trusted connections</span><strong class="stat-value">${String(state.contacts.length).padStart(2, "0")}</strong><span class="stat-note">${state.contacts.length ? "<b>Your circle is here</b>" : "Add someone you trust"}</span></div><span class="stat-icon">♧</span></div></section>
<div class="grid-two"><section class="card"><div class="card-header"><div><h3>Recent conversations</h3><p>A little context for every call.</p></div><button class="text-button" data-page="history">View all &nbsp; ↗</button></div><div class="activity">${
      calls.length
        ? calls
            .slice(0, 3)
            .map(
              (c) =>
                `<div class="activity-row"><span class="activity-icon">${c.score >= 60 ? "!" : "◷"}</span><div><strong>${esc(c.title)}</strong><small>${date(c.created_at)} · ${esc(c.mode)} · ${esc(c.status)}</small></div>${badge(c.score)}</div>`,
            )
            .join("")
        : empty(
            "Your story starts here.",
            "Try a guided demo to see Catchy in action.",
            '<button class="text-button" data-page="lab">Choose a scenario →</button>',
          )
    }</div></section><section class="card"><div class="card-header"><div><h3>Better, together.</h3><p>Your trusted circle</p></div><span>♧</span></div><div class="circle-content"><div class="circle-people">${
      state.contacts
        .slice(0, 3)
        .map(
          (c) =>
            `<span class="person" title="${esc(c.name)}">${esc(initials(c.name))}</span>`,
        )
        .join("") ||
      '<span class="person">♡</span><span class="person">♧</span>'
    }<button class="person plus" data-page="contacts" aria-label="Add trusted contact">+</button></div><p>When something feels off, a familiar voice can make all the difference. Keep your people close.</p><button class="btn secondary" data-page="contacts">Manage your circle &nbsp; ↗</button></div></section></div><div class="bottom-note"><span>☼</span><div><strong>A simple habit. A powerful safeguard.</strong><p>A real bank will never need you to share a secret code on a call. Pause, hang up, and verify independently.</p></div><button class="text-button" id="learn-safety">A little more guidance ↗</button></div>`;
}
function renderLab() {
  $("#page").innerHTML =
    heading(
      "SEE THE SIGNALS. UNDERSTAND THE STORY.",
      "A safe space to try it.",
      "Three scripted conversations. Real analysis. No phone call needed.",
      '<span class="badge neutral">SIMULATED TEXT</span>',
    ) +
    `<div class="notice">These are illustrative scenarios, not real incidents or proof of accuracy. Guest demos run a local rules engine; sign in to use the backend and optional contextual AI.</div><div class="lab-grid">${scenarios.map((s) => `<section class="card scenario"><span class="scenario-icon">${s.icon}</span><span class="eyebrow">${s.tag}</span><h3>${s.title}</h3><p>${s.desc}</p><button class="btn secondary" data-scenario="${s.id}">Play this scenario <span>→</span></button></section>`).join("")}</div><div class="card lab-info"><h3>Look beyond a single word.</h3><p>Watch evidence accumulate across turns: a claimed role, an urgent deadline, isolation, and then a request for money or a secret code. The baseline detects specific patterns; optional contextual AI adds evidence-backed signals. Neither guarantees safety.</p><hr class="divider"><div class="actions"><span class="badge neutral">01 · Claim</span><span>→</span><span class="badge caution">02 · Pressure</span><span>→</span><span class="badge high">03 · Sensitive request</span></div></div>`;
}
function renderMonitor() {
  const a = state.analysis;
  $("#page").innerHTML =
    heading(
      "AWARENESS, IN THE MOMENT.",
      "A clearer conversation.",
      "Listen for the signals. Take the next step with confidence.",
      `<span class="badge ${state.running ? "live" : "neutral"}">${state.running ? '<i class="live-dot"></i> Session active' : "Ready when you are"}</span>`,
    ) +
    `<div id="risk-alert"></div><div class="monitor-tools"><div class="segmented" role="group" aria-label="Input mode">${["demo", "manual", "microphone"].map((m) => `<button data-mode="${m}" class="${m === state.mode ? "selected" : ""}" ${state.running ? "disabled" : ""}>${{ demo: "▷ Demo playback", manual: "⌨ Type a conversation", microphone: "◉ Microphone" }[m]}</button>`).join("")}</div>${state.running ? '<button class="btn secondary" id="stop-session">End session □</button>' : `<button class="btn primary" id="start-session">${state.turns.length ? "Start a new session" : "Start session"} →</button>`}</div><div class="monitor-grid"><section class="card"><div class="card-header"><div><h3>${state.mode === "demo" ? esc(state.scenario.title) : "Conversation transcript"}</h3><p>${state.mode === "demo" ? "Scripted demonstration · one turn at a time" : state.mode === "microphone" ? "Browser speech recognition · permission required" : "Paste or type what the caller says"}</p></div><span class="badge neutral">${state.mode === "demo" ? "SIMULATION" : state.mode.toUpperCase()}</span></div><div id="transcript" class="transcript" aria-live="polite"></div>${state.mode === "manual" ? `<form id="turn-form" class="composer"><textarea id="turn-input" maxlength="1500" aria-label="Caller statement" placeholder="What did the caller say?" ${!state.running ? "disabled" : ""} required></textarea><button class="btn primary" type="submit" ${!state.running || state.busy ? "disabled" : ""}>Analyze →</button></form>` : ""}<div class="monitor-status"><span id="engine-name">${a ? esc(a.engine) : state.user ? "Backend analysis" : "Guest · local rules"}</span><span id="latency-label">${a ? `${a.latency_ms} ms analysis` : "No audio stored"}</span></div></section><section class="card risk-panel"><span class="section-label">Conversation risk</span><div class="risk-ring"><svg viewBox="0 0 174 174" aria-hidden="true"><circle cx="87" cy="87" r="74"/><circle class="progress" id="risk-progress" cx="87" cy="87" r="74"/></svg><div class="risk-number"><strong id="risk-score">0</strong><span>OF 100 · SEVERITY INDEX</span></div></div><div id="risk-badge">${badge(0)}</div><p class="risk-advice" id="risk-advice">Start a session to see the signals. Scores indicate heuristic severity, not a probability of fraud.</p><div class="signals"><span class="section-label">What we noticed</span><div id="signal-list"><div class="empty">Evidence will appear here.</div></div></div></section></div><p class="session-note">${state.user ? (state.settings.retain_transcript ? "Redacted transcript retention is enabled for new sessions." : "Transcript retention is off. Only session metadata is saved.") : "Guest sessions stay in memory for this visit. Sign in to save history."} Catchy cannot intercept cellular calls or verify who a caller really is.</p>`;
  updateMonitor();
}
function updateMonitor() {
  if (state.page !== "monitor") return;
  $("#transcript").innerHTML = state.turns.length
    ? state.turns
        .map(
          (t, i) =>
            `<div class="turn"><div class="turn-meta"><span>CALLER · TURN ${i + 1}</span><span>${esc(t.time)}</span></div><p>${esc(t.text)}</p></div>`,
        )
        .join("")
    : empty(
        state.running
          ? "Listening for the first signal…"
          : "The conversation will appear here.",
        state.mode === "demo"
          ? "Start playback to watch the analysis unfold."
          : state.mode === "manual"
            ? "Start a session, then enter a caller statement."
            : "Start a session and allow microphone access.",
      );
  $("#transcript").scrollTop = $("#transcript").scrollHeight;
  const a = state.analysis;
  if (!a) return;
  $("#risk-score").textContent = a.score;
  $("#risk-progress").style.strokeDashoffset = String(
    465 * (1 - a.score / 100),
  );
  $("#risk-progress").classList.toggle("high", a.level === "high");
  $("#risk-progress").classList.toggle("caution", a.level === "caution");
  $("#risk-badge").innerHTML = badge(a.score);
  $("#risk-advice").textContent = a.advice;
  $("#engine-name").textContent = a.engine;
  $("#latency-label").textContent = `${a.latency_ms} ms analysis`;
  $("#signal-list").innerHTML = a.signals.length
    ? a.signals
        .map(
          (s) =>
            `<div class="signal"><strong>${esc(s.label)}<span>Turn ${s.turn}</span></strong><blockquote>“${esc(s.quote)}”</blockquote></div>`,
        )
        .join("")
    : '<div class="empty">No suspicious pattern detected so far.</div>';
  $("#risk-alert").innerHTML =
    a.level === "high"
      ? `<div class="alert-box" role="alert"><strong>Pause. This conversation contains high-risk requests.</strong><p>${esc(a.advice)}</p><div class="actions"><button class="btn secondary" id="read-warning">Read warning aloud ♬</button><button class="btn secondary" id="contact-help">Contact someone you trust ↗</button></div></div>`
      : a.model_status === "unavailable"
        ? '<div class="notice warning">Contextual AI is unavailable. Rules-only analysis is active; interpretation may be limited.</div>'
        : "";
}
// Explicit local baseline for guest demos. No LLM request occurs in guest mode.
function localAnalyze(turns) {
  const start = performance.now();
  const definitions = [
    [
      "authority",
      "Authority claim",
      12,
      /\b(bank|police|officer|government|tax department|technical support|fraud department|investigation|security team)\b/i,
    ],
    [
      "urgency",
      "Artificial urgency",
      13,
      /\b(immediately|right now|within.{0,15}minutes|last chance|act now|today only|urgent|expires?)\b/i,
    ],
    [
      "fear",
      "Threat or intimidation",
      18,
      /\b(arrest|warrant|freeze|frozen|suspend|blocked|legal action|criminal|lose your money)\b/i,
    ],
    [
      "secrecy",
      "Isolation or secrecy",
      20,
      /\b(don.t tell|do not tell|keep.{0,18}(secret|confidential)|stay on.{0,10}line|tell no one|alone|do not contact|don.t call)\b/i,
    ],
    [
      "credential",
      "Secret code requested",
      65,
      /\b(otp|one[ -]time.{0,8}(password|code)|pin|password|verification code|security code|six[ -]digit|6[ -]digit|digits.{0,20}(text|message))\b/i,
    ],
    [
      "payment",
      "Money transfer requested",
      22,
      /\b(transfer|send money|pay.{0,15}(fee|fine)|safe account|gift card|crypto|payment|move.{0,20}(funds|money|savings))\b/i,
    ],
    [
      "remote",
      "Remote access requested",
      60,
      /\b(anydesk|teamviewer|screen.?share|remote access|install.{0,20}(app|software))\b/i,
    ],
  ];
  const found = new Map();
  for (const [i, text] of turns.entries()) {
    for (const clause of text.split(/[.!?;\n]|\bbut\b|\bhowever\b/i)) {
      const negative =
        /\b(never|do not|don.t|must not|should not|won.t|will not|not to)\s+(?:ever\s+)?(?:ask\s+(?:you\s+)?(?:for|to)\s+)?(?:share|disclose|give|tell|send|read|provide|install|enter|pay|transfer|reveal|request)\b/i.test(
          clause,
        );
      for (const [key, name, weight, pattern] of definitions) {
        if (negative && key !== "secrecy") continue;
        if (!pattern.test(clause) || found.has(key)) continue;
        if (
          key === "credential" &&
          !/\b(tell|share|read|give|send|provide|confirm|say|enter|type|repeat|what is|what.s)\b/i.test(
            clause,
          )
        )
          continue;
        if (
          key === "payment" &&
          !/\b(transfer|send|pay|move|buy|purchase)\b/i.test(clause)
        )
          continue;
        found.set(key, {
          key,
          label: name,
          weight,
          turn: i + 1,
          quote: clause
            .trim()
            .replace(/\b\d[\d ()-]{3,}\d\b/g, "[number]")
            .slice(0, 180),
        });
      }
    }
  }
  let score = Math.min(
    98,
    [...found.values()].reduce((a, b) => a + b.weight, 0) +
      (found.size >= 4 ? 8 : 0),
  );
  if ([...found.keys()].every((k) => ["authority", "urgency"].includes(k)))
    score = Math.min(score, 24);
  return {
    score,
    level: level(score),
    signals: [...found.values()],
    engine: "Guest · local rules",
    model_status: "disabled",
    latency_ms: Math.round(performance.now() - start),
    advice:
      score >= 60
        ? "Pause the conversation. Do not share codes, install software, or move money. Verify using a trusted contact number."
        : score >= 30
          ? "Take your time. Verify who is calling through an independent, trusted channel before acting."
          : "No high-risk pattern detected so far. This is not a guarantee that the call is safe.",
  };
}
function requestStart() {
  if (state.mode !== "demo" && !state.user) {
    toast("Create an account to use live input and save your sessions.");
    openAuth();
    return;
  }
  if (
    state.mode === "microphone" &&
    !(window.SpeechRecognition || window.webkitSpeechRecognition)
  ) {
    toast(
      "Speech recognition is unavailable in this browser. Use typed input or a demo.",
    );
    return;
  }
  $("#consent-check").checked = false;
  $("#consent-dialog").showModal();
}
async function startSession() {
  if (!$("#consent-check").checked) {
    toast("Please confirm consent before starting.");
    return;
  }
  $("#consent-start").disabled = true;
  try {
    const title =
      state.mode === "demo"
        ? state.scenario.title
        : state.mode === "manual"
          ? "Typed conversation"
          : "Microphone session";
    const session = state.user
      ? await api("/calls", "POST", { title, mode: state.mode, consent: true })
      : { id: crypto.randomUUID() };
    state.session = {
      ...session,
      title,
      mode: state.mode,
      created_at: new Date().toISOString(),
    };
    state.turns = [];
    state.analysis = null;
    state.running = true;
    state.generation++;
    state.heard = [];
    $("#consent-dialog").close();
    navigate("monitor");
    if (state.mode === "demo") playTurn(0, state.generation);
    if (state.mode === "microphone") startMicrophone();
  } catch (e) {
    toast(e.message);
  } finally {
    $("#consent-start").disabled = false;
  }
}
async function analyzeTurn(text) {
  if (!state.running || state.busy) return false;
  state.busy = true;
  const generation = state.generation;
  try {
    const a = state.user
      ? await api(`/calls/${state.session.id}/turns`, "POST", { text })
      : localAnalyze([...state.turns.map((t) => t.text), text]);
    if (generation !== state.generation) return false;
    state.turns.push({
      text,
      time: new Date().toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      }),
    });
    const prior = state.analysis?.level;
    state.analysis = a;
    updateMonitor();
    if (
      a.level === "high" &&
      prior !== "high" &&
      state.settings.spoken_warnings
    )
      readWarning();
    return true;
  } catch (e) {
    toast(e.message);
    state.busy = false;
    await endSession(false);
    return false;
  } finally {
    state.busy = false;
  }
}
async function playTurn(index, generation) {
  if (!state.running || generation !== state.generation) return;
  if (index >= state.scenario.turns.length) {
    await endSession();
    return;
  }
  const ok = await analyzeTurn(state.scenario.turns[index]);
  if (ok && state.running && generation === state.generation)
    state.timer = setTimeout(() => playTurn(index + 1, generation), 2400);
}
async function endSession(showToast = true) {
  if (!state.running) return;
  state.running = false;
  clearTimeout(state.timer);
  if (state.recognition) {
    state.recognition.onend = null;
    state.recognition.stop();
    state.recognition = null;
  }
  state.heard = [];
  if (state.busy)
    await new Promise((resolve) => {
      const timer = setInterval(() => {
        if (!state.busy) {
          clearInterval(timer);
          resolve();
        }
      }, 30);
    });
  state.generation++;
  try {
    if (state.user) {
      await api(`/calls/${state.session.id}/finish`, "POST", {});
      await refresh();
    } else
      state.guestHistory.unshift({
        ...state.session,
        score: state.analysis?.score || 0,
        status: "completed",
        turns: [...state.turns],
      });
    if (showToast) toast("Session ended. You are in control.");
  } catch (e) {
    toast(e.message);
  }
  if (state.page === "monitor") renderMonitor();
}
function startMicrophone() {
  const Recognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  const r = new Recognition();
  state.recognition = r;
  r.lang = "en-IN";
  r.continuous = true;
  r.interimResults = false;
  r.onresult = (e) => {
    for (let i = e.resultIndex; i < e.results.length; i++)
      if (e.results[i].isFinal) state.heard.push(e.results[i][0].transcript);
    drainSpeech();
  };
  r.onerror = (e) => {
    toast(`Microphone stopped: ${e.error}. You can switch to typed input.`);
    endSession(false);
  };
  r.onend = () => {
    if (state.running) {
      toast("Speech recognition ended. Start a new session to continue.");
      endSession(false);
    }
  };
  try {
    r.start();
  } catch {
    toast("Could not start speech recognition. Try typed input.");
    endSession(false);
  }
}
async function drainSpeech() {
  if (state.busy || !state.running) return;
  while (state.heard.length && state.running)
    if (!(await analyzeTurn(state.heard.shift()))) break;
}
function readWarning() {
  if (!("speechSynthesis" in window)) {
    toast("Spoken warnings are unavailable in this browser.");
    return;
  }
  speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance(
    state.analysis?.advice ||
      "Do not share secret codes. Verify the caller independently.",
  );
  speech.rate = 0.87;
  speechSynthesis.speak(speech);
}
function renderHistory() {
  const calls = allCalls();
  $("#page").innerHTML =
    heading(
      "A LITTLE PERSPECTIVE.",
      "Your conversations, revisited.",
      "Review the signals and decide what you want to keep.",
      '<button class="btn secondary" id="export-history">Export metadata ↓</button>',
    ) +
    (!state.user
      ? '<div class="notice">Guest history is temporary and disappears when you reload. Sign in for persistent, account-private session metadata.</div>'
      : "") +
    `<div class="toolbar"><input id="history-search" type="search" placeholder="Search conversations…" aria-label="Search conversations"><select id="history-filter" aria-label="Filter by risk"><option value="all">All risk levels</option><option value="high">High risk</option><option value="caution">Caution</option><option value="low">Low signals</option></select></div><section class="card"><div class="table-wrap"><table><thead><tr><th>Conversation</th><th>Risk signals</th><th>Status</th><th>Actions</th></tr></thead><tbody id="history-rows"></tbody></table></div><div id="history-empty" ${calls.length ? "hidden" : ""}>${empty("Nothing to revisit yet.", "Start with a demo or a protected session.")}</div></section>`;
  filterHistory();
}
function filterHistory() {
  const q = $("#history-search").value.toLowerCase(),
    f = $("#history-filter").value;
  const calls = allCalls().filter(
    (c) =>
      c.title.toLowerCase().includes(q) &&
      (f === "all" || level(c.score) === f),
  );
  $("#history-rows").innerHTML = calls
    .map(
      (c) =>
        `<tr><td>${esc(c.title)}<small>${date(c.created_at)} · ${esc(c.mode)}</small></td><td>${badge(c.score)}<small>Severity ${c.score}/100</small></td><td><span class="badge neutral">${esc(c.status)}</span></td><td><div class="row-actions"><button class="text-button" data-detail="${c.id}">View</button><button class="text-button danger-text" data-delete="${c.id}">Delete</button></div></td></tr>`,
    )
    .join("");
  $("#history-empty").hidden = !!calls.length;
}
async function showDetail(id) {
  try {
    const r = state.user
      ? await api(`/calls/${id}`)
      : {
          call: state.guestHistory.find((c) => c.id === id),
          turns: state.guestHistory.find((c) => c.id === id)?.turns || [],
        };
    $("#detail-content").innerHTML =
      `<span class="eyebrow">SESSION SUMMARY</span><h2>${esc(r.call.title)}</h2><p>${date(r.call.created_at)} · ${esc(r.call.mode)} · ${esc(r.call.status)}</p>${badge(r.call.score)}<hr class="divider">${r.turns.length ? r.turns.map((t, i) => `<div class="detail-turn"><small class="muted">TURN ${i + 1}</small><p>${esc(t.text)}</p>${t.score !== undefined ? badge(t.score) : ""}</div>`).join("") : '<div class="notice">No transcript was retained. Your session metadata and final risk score are available.</div>'}`;
    $("#detail-dialog").showModal();
  } catch (e) {
    toast(e.message);
  }
}
async function deleteCall(id) {
  if (state.running && state.session?.id === id) {
    toast("End this active session before deleting it.");
    return;
  }
  if (
    !confirm(
      "Delete this session and any retained transcript? This cannot be undone.",
    )
  )
    return;
  try {
    if (state.user) {
      await api(`/calls/${id}`, "DELETE");
      await refresh();
    } else state.guestHistory = state.guestHistory.filter((c) => c.id !== id);
    renderHistory();
    toast("Session deleted.");
  } catch (e) {
    toast(e.message);
  }
}
function renderContacts() {
  $("#page").innerHTML =
    heading(
      "YOUR PEOPLE. ONE TAP CLOSER.",
      "Build your circle.",
      "Keep the people you trust close, especially when something feels off.",
    ) +
    `<div class="notice">Contacts are saved privately to your account. “Call” opens your device’s dialer. Catchy does not send automatic messages, verify contacts, or notify anyone in the background.</div>${state.user ? `<section class="card"><form id="contact-form" class="contact-form"><label>Name<input name="name" required minlength="2" maxlength="80" placeholder="Someone you trust"></label><label>Phone number<input name="phone" type="tel" required minlength="7" maxlength="25" placeholder="+91 …"></label><label>Relationship<select name="relationship"><option>Family</option><option>Friend</option><option>Caregiver</option></select></label><button class="btn primary" type="submit">Add to circle +</button></form></section><div class="contact-grid">${state.contacts.map((c) => `<section class="card contact-card"><span class="avatar">${esc(initials(c.name))}</span><h3>${esc(c.name)}</h3><p>${esc(c.relationship)} · ${esc(c.phone)}</p><div class="actions"><a class="btn secondary" href="tel:${esc(c.phone.replace(/[^+\d]/g, ""))}">Call ↗</a><button class="text-button danger-text" data-remove-contact="${c.id}">Remove</button></div></section>`).join("")}</div>${!state.contacts.length ? empty("Your circle is ready to grow.", "Add up to five people you feel comfortable contacting.") : ""}` : `<section class="card">${empty("A familiar voice makes a difference.", "Sign in to save and manage your trusted contacts.", '<button class="btn primary" data-auth>Create your workspace →</button>')}</section>`}`;
}
function renderSettings() {
  $("#page").innerHTML =
    heading(
      "PRIVACY IS A CHOICE. YOURS.",
      "Make yourself comfortable.",
      "A few thoughtful preferences for your peace of mind.",
    ) +
    `<section class="card settings-card"><h3>Privacy & listening</h3><form id="settings-form"><div class="setting-row"><div><strong>Retain redacted transcripts</strong><p>Off by default. When enabled, new sessions retain redacted text and evidence. Redaction is best effort; do not enter real secrets. Existing retained sessions can be deleted from history.</p></div><input class="switch" type="checkbox" name="retain_transcript" aria-label="Retain redacted transcripts" ${state.settings.retain_transcript ? "checked" : ""}></div><div class="setting-row"><div><strong>Read high-risk warnings aloud</strong><p>Use browser speech synthesis when a session first reaches high risk. Keep your sound on; anyone nearby may hear the warning.</p></div><input class="switch" type="checkbox" name="spoken_warnings" aria-label="Read warnings aloud" ${state.settings.spoken_warnings ? "checked" : ""}></div><div class="setting-footer"><button class="btn primary" type="submit">Save preferences</button><span class="muted">${state.user ? "Saved to your account" : "Guest preferences last this visit"}</span></div></form></section><section class="card settings-card"><h3>What happens to your data?</h3><p>Raw audio is never stored by Catchy. Browser microphone recognition may use the browser vendor’s servers. Text is processed by the Catchy server and, if configured, the operator’s Ollama model. Active conversation memory expires after 30 minutes of inactivity or when you end the session.</p><p>Session metadata is retained until you delete it. The app stores names and phone numbers you add to your trusted circle. It does not sell or send these details to contacts.</p><hr class="divider"><span class="badge neutral">${state.user ? "Server provider: " + esc(state.provider) : "Guest · local rules"}</span></section><section class="card settings-card"><h3>Your account</h3><p>${state.user ? "Signed in as " + esc(state.user.email) + "." : "You are using a temporary guest workspace."}</p><div class="setting-footer">${state.user ? '<button class="btn secondary" id="logout">Sign out</button>' : '<button class="btn primary" data-auth>Create an account →</button>'}</div></section>`;
}
function openAuth() {
  if (state.user) {
    navigate("settings");
    return;
  }
  $("#auth-error").textContent = "";
  $("#auth-name").required = state.authMode === "register";
  $("#auth-dialog").showModal();
}
function switchAuth() {
  state.authMode = state.authMode === "register" ? "login" : "register";
  const r = state.authMode === "register";
  $("#auth-title").textContent = r
    ? "Welcome to peace of mind."
    : "Good to have you back.";
  $("#name-label").hidden = !r;
  $("#auth-name").required = r;
  $("#auth-password").autocomplete = r ? "new-password" : "current-password";
  $("#auth-submit").textContent = r ? "Create account →" : "Sign in →";
  $("#auth-switch").textContent = r
    ? "Already have an account? Sign in"
    : "New to Catchy? Create an account";
  $("#auth-error").textContent = "";
}
function safetyInfo() {
  $("#detail-content").innerHTML =
    '<span class="eyebrow">A MOMENT TO PAUSE</span><h2>Pressure is a reason to slow down.</h2><p>Do not share OTPs, passwords, or PINs with callers. Do not install remote-access software at a stranger’s request. If asked to move money to a “safe account,” end the conversation and verify independently.</p><div class="notice">Use a number you already trust, such as the one printed on your bank card. Catchy detects patterns; it cannot confirm identity or guarantee a safe call.</div><p>For a suspected incident, contact your bank promptly using its official support channel.</p>';
  $("#detail-dialog").showModal();
}
$("#auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#auth-submit").disabled = true;
  $("#auth-error").textContent = "";
  try {
    if (state.running) await endSession();
    const r = await api("/auth/" + state.authMode, "POST", {
      name: $("#auth-name").value,
      email: $("#auth-email").value,
      password: $("#auth-password").value,
    });
    state.user = r.user;
    $("#auth-password").value = "";
    $("#auth-dialog").close();
    updateAccount();
    await refresh();
    state.provider = (await api("/me")).llm_provider;
    render();
    toast("Your workspace is ready.");
  } catch (e) {
    $("#auth-error").textContent = e.message;
  } finally {
    $("#auth-submit").disabled = false;
  }
});
$("#auth-switch").addEventListener("click", switchAuth);
$("#account-button").addEventListener("click", openAuth);
$("#consent-start").addEventListener("click", startSession);
$("#menu-button").addEventListener("click", () =>
  $(".sidebar").classList.toggle("open"),
);
$("#help-button").addEventListener("click", safetyInfo);
$("#footer-privacy").addEventListener("click", () => navigate("settings"));
document.addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.page) navigate(b.dataset.page);
  if (b.hasAttribute("data-auth")) openAuth();
  if (b.dataset.close) $("#" + b.dataset.close).close();
  if (b.dataset.scenario) {
    if (state.running) {
      toast("End your current session before choosing another scenario.");
      navigate("monitor");
      return;
    }
    state.scenario = scenarios.find((s) => s.id === b.dataset.scenario);
    state.mode = "demo";
    state.turns = [];
    state.analysis = null;
    navigate("monitor");
    requestStart();
  }
  if (b.dataset.mode && !state.running) {
    state.mode = b.dataset.mode;
    renderMonitor();
  }
  if (b.id === "start-session") requestStart();
  if (b.id === "stop-session") endSession();
  if (b.id === "read-warning") readWarning();
  if (b.id === "contact-help") navigate("contacts");
  if (b.id === "learn-safety") safetyInfo();
  if (b.dataset.detail) showDetail(b.dataset.detail);
  if (b.dataset.delete) deleteCall(b.dataset.delete);
  if (b.dataset.removeContact) {
    try {
      await api("/contacts/" + b.dataset.removeContact, "DELETE");
      await refresh();
      renderContacts();
      toast("Contact removed.");
    } catch (e) {
      toast(e.message);
    }
  }
  if (b.id === "logout") {
    if (state.running) await endSession();
    try {
      await api("/auth/logout", "POST", {});
      state.user = null;
      state.calls = [];
      state.contacts = [];
      state.settings = { retain_transcript: false, spoken_warnings: false };
      state.session = null;
      state.turns = [];
      state.analysis = null;
      updateAccount();
      navigate("overview");
      toast("Signed out.");
    } catch (e) {
      toast(e.message);
    }
  }
  if (b.id === "export-history") {
    const data = JSON.stringify(
      allCalls().map(({ id, title, mode, score, status, created_at }) => ({
        id,
        title,
        mode,
        score,
        status,
        created_at,
      })),
      null,
      2,
    );
    const url = URL.createObjectURL(
      new Blob([data], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "catchy-session-metadata.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
});
document.addEventListener("submit", async (e) => {
  if (e.target.id === "turn-form") {
    e.preventDefault();
    const input = $("#turn-input"),
      text = input.value.trim();
    if (!text || state.busy) return;
    const button = $("button", e.target);
    button.disabled = true;
    await analyzeTurn(text);
    input.value = "";
    button.disabled = !state.running;
    input.focus();
  }
  if (e.target.id === "contact-form") {
    e.preventDefault();
    const form = e.target,
      button = $("button", form);
    button.disabled = true;
    try {
      await api("/contacts", "POST", Object.fromEntries(new FormData(form)));
      await refresh();
      renderContacts();
      toast("Added to your trusted circle.");
    } catch (e) {
      toast(e.message);
      button.disabled = false;
    }
  }
  if (e.target.id === "settings-form") {
    e.preventDefault();
    const form = e.target,
      s = {
        retain_transcript: form.elements.retain_transcript.checked,
        spoken_warnings: form.elements.spoken_warnings.checked,
      };
    try {
      if (state.user) await api("/settings", "POST", s);
      state.settings = s;
      toast("Preferences saved.");
    } catch (e) {
      toast(e.message);
    }
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "history-search") filterHistory();
});
document.addEventListener("change", (e) => {
  if (e.target.id === "history-filter") filterHistory();
});
window.addEventListener("hashchange", () => {
  const p = location.hash.slice(1);
  if (p !== state.page) navigate(p);
});
window.addEventListener("beforeunload", () => {
  state.recognition?.stop();
  if (window.speechSynthesis) speechSynthesis.cancel();
});
async function boot() {
  navigate(location.hash.slice(1) || "overview");
  try {
    await api("/health");
    $("#connection-label").textContent = "Server connected";
    try {
      const r = await api("/me");
      state.user = r.user;
      state.provider = r.llm_provider;
      await refresh();
      updateAccount();
      render();
    } catch {
      /* Guest mode is intentional. */
    }
  } catch {
    $("#connection-label").textContent = "Guest demo mode";
  }
}
boot();
