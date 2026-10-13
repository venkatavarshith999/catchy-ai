import assert from "node:assert/strict";
import { BrowserASR, HostedASR } from "../frontend/asr.js";
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
const pending = hosted.start({ language: "en-IN", onText() {}, onError() {} });
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
