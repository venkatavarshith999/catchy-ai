import assert from "node:assert/strict";
import {
  BrowserASR,
  HostedASR,
  speakWarning,
  cancelWarning,
} from "../frontend/asr.js";
let recognition;
globalThis.window = {
  SpeechRecognition: class {
    constructor() {
      recognition = this;
    }
    start() {}
    abort() {
      this.aborted = true;
    }
  },
};
const received = [];
const browser = new BrowserASR();
await browser.start({
  language: "te-IN",
  onText: (text, ended) => received.push({ text, ended }),
  onError: () => {
    throw Error("unexpected");
  },
});
assert.equal(recognition.lang, "te-IN");
recognition.onspeechend();
recognition.onspeechstart();
recognition.onresult({
  resultIndex: 0,
  results: [Object.assign([{ transcript: "synthetic" }], { isFinal: true })],
});
assert.equal(
  received[0].ended,
  null,
  "A previous utterance must not supply the next timing",
);
browser.stop();
assert.ok(recognition.aborted);
recognition.onerror({ error: "aborted" });
recognition.onresult({
  resultIndex: 0,
  results: [Object.assign([{ transcript: "late text" }], { isFinal: true })],
});
assert.equal(
  received.length,
  1,
  "Stopped recognition must discard late transcripts and errors",
);
let resolveMic,
  stopped = false;
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: {
    mediaDevices: {
      getUserMedia: () => new Promise((resolve) => (resolveMic = resolve)),
    },
  },
});
const hosted = new HostedASR();
const pending = hosted.start({
  callId: "owned-session",
  language: "en-IN",
  onText() {},
  onError() {},
});
hosted.stop();
resolveMic({
  getTracks: () => [
    {
      stop() {
        stopped = true;
      },
    },
  ],
});
await assert.rejects(pending, /background/);
assert.ok(
  stopped,
  "A late permission result must release the microphone after Stop",
);
console.log(
  "ASR lifecycle: stale timing and late-permission cleanup regressions passed.",
);

let micRequests = 0;
navigator.mediaDevices.getUserMedia = async () => {
  micRequests++;
  return { getTracks: () => [{ stop() {} }] };
};
await assert.rejects(
  new HostedASR().start({ language: "en-IN", onText() {}, onError() {} }),
  /authNeeded/,
);
assert.equal(
  micRequests,
  0,
  "No session means no microphone permission request",
);
let hostedSocket, recorder;
globalThis.location = { protocol: "https:", host: "catchy.test" };
globalThis.WebSocket = class {
  constructor(url) {
    this.url = url;
    this.readyState = 1;
    this.sent = [];
    hostedSocket = this;
    queueMicrotask(() => this.onopen());
  }
  send(data) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
};
globalThis.MediaRecorder = class {
  static isTypeSupported() {
    return true;
  }
  constructor() {
    recorder = this;
  }
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.onstop?.();
  }
};
const connected = new HostedASR();
await connected.start({
  callId: "owned /session",
  language: "te-IN",
  onText() {},
  onError() {},
});
const asrURL = new URL(hostedSocket.url);
assert.equal(asrURL.protocol, "wss:");
assert.equal(asrURL.searchParams.get("call_id"), "owned /session");
assert.equal(asrURL.searchParams.get("language"), "te-IN");
let finishBuffer;
const bufferPending = recorder.ondataavailable({
  data: {
    size: 2,
    arrayBuffer: () =>
      new Promise((resolve) => {
        finishBuffer = resolve;
      }),
  },
});
connected.stop();
finishBuffer(new ArrayBuffer(2));
await bufferPending;
assert.equal(
  hostedSocket.sent.length,
  0,
  "Stopping must discard delayed audio buffers",
);

// Closing during handshake must settle even when the socket sends no close event.
let handshake;
globalThis.WebSocket = class {
  constructor() {
    handshake = this;
  }
  close() {}
};
const opening = new HostedASR();
const openingPromise = opening.start({
  callId: "owned-session",
  language: "en-IN",
  onText() {},
  onError() {},
});
await Promise.resolve();
assert.ok(handshake);
opening.stop();
await assert.rejects(openingPromise, /background/);

let utterance,
  cancelCount = 0;
globalThis.SpeechSynthesisUtterance = class {
  constructor(text) {
    this.text = text;
  }
};
window.speechSynthesis = {
  getVoices: () => [{ lang: "te-IN" }],
  cancel() {
    cancelCount++;
  },
  speak(value) {
    utterance = value;
  },
};
let settled = false;
const playback = speakWarning("test warning", "te-IN").then((value) => {
  settled = true;
  return value;
});
await Promise.resolve();
assert.equal(
  settled,
  false,
  "Queued speech is not evidence of completed playback",
);
assert.equal(utterance.lang, "te-IN");
assert.equal(utterance.rate, 0.85);
utterance.onend();
assert.equal(await playback, true);
const failed = speakWarning("test warning", "te-IN");
await Promise.resolve();
utterance.onerror({ error: "audio-busy" });
assert.equal(
  await failed,
  false,
  "Delayed audio errors must preserve the text fallback",
);
const canceled = speakWarning("test warning", "te-IN");
const lateEnd = utterance.onend;
cancelWarning();
assert.equal(
  await canceled,
  false,
  "Cancel settles even if the engine emits no event",
);
lateEnd();
const controller = new AbortController();
const aborted = speakWarning("test warning", "te-IN", {
  signal: controller.signal,
});
controller.abort();
assert.equal(await aborted, false);
const alreadyAborted = new AbortController();
alreadyAborted.abort();
assert.equal(
  await speakWarning("test warning", "te-IN", {
    signal: alreadyAborted.signal,
  }),
  false,
);
assert.equal(
  await speakWarning("test warning", "hi-IN"),
  false,
  "No matching voice must not claim success",
);
const timedOut = speakWarning("test warning", "te-IN", { timeoutMs: 5 });
assert.equal(
  await timedOut,
  false,
  "Engines emitting no event have a bounded timeout",
);
const superseded = speakWarning("older warning", "te-IN");
const latest = speakWarning("newer warning", "te-IN");
assert.equal(
  await superseded,
  false,
  "A replacement settles the previous warning",
);
utterance.onend();
assert.equal(await latest, true);
window.speechSynthesis.speak = () => {
  throw Error("blocked");
};
assert.equal(await speakWarning("test warning", "te-IN"), false);
assert.ok(cancelCount > 0);
console.log(
  "Session-bound hosted ASR and completion/error/cancel/timeout speech regressions passed.",
);
