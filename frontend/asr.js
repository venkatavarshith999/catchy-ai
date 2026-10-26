export class ASRProvider {
  async start() {
    throw Error("unsupported");
  }
  stop() {}
}
export class BrowserASR extends ASRProvider {
  async start({ language, onText, onError }) {
    const Recognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) throw Error("unsupported");
    this.stopping = false;
    this.recognition = new Recognition();
    this.recognition.lang = language;
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.started = performance.now();
    this.speechEnd = null;
    this.recognition.onspeechstart = () => {
      this.speechEnd = null;
    };
    this.recognition.onspeechend = () => {
      this.speechEnd = performance.now();
    };
    this.recognition.onresult = (e) => {
      if (this.stopping) return;
      for (let i = e.resultIndex; i < e.results.length; i++)
        if (e.results[i].isFinal)
          onText(e.results[i][0].transcript, this.speechEnd);
    };
    this.recognition.onerror = (e) => {
      if (!this.stopping)
        onError(e.error === "not-allowed" ? "permissionDenied" : "speechError");
    };
    this.recognition.onend = () => {
      if (!this.stopping) onError("speechError");
    };
    this.recognition.start();
  }
  stop() {
    this.stopping = true;
    this.recognition?.abort();
  }
}
export class HostedASR extends ASRProvider {
  async start({ callId, language, onText, onError }) {
    // Capture requires the application's authenticated, consented session.
    if (!callId) throw Error("authNeeded");
    this.stopping = false;
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (this.stopping) {
      this.stream.getTracks().forEach((track) => track.stop());
      throw Error("background");
    }
    this.socket = new WebSocket(
      `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v2/asr?call_id=${encodeURIComponent(callId)}&language=${encodeURIComponent(language)}`,
    );
    await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        this.cancelStart = null;
        if (error) {
          this.stop();
          reject(error);
        } else resolve();
      };
      const timeout = setTimeout(() => finish(Error("asrUnavailable")), 10000);
      this.cancelStart = () => finish(Error("background"));
      this.socket.onopen = () => finish();
      this.socket.onerror = this.socket.onclose = () =>
        finish(Error("asrUnavailable"));
    });
    if (this.stopping) throw Error("background");
    this.socket.onmessage = (e) => {
      if (this.stopping) return;
      try {
        const m = JSON.parse(e.data);
        if (m.error) onError(m.error);
        else if (m.text) onText(m.text, null);
      } catch {
        onError("speechError");
      }
    };
    this.socket.onclose = () => {
      if (!this.stopping) onError("speechError");
    };
    if (!MediaRecorder.isTypeSupported("audio/webm;codecs=opus"))
      throw Error("unsupported");
    this.recorder = new MediaRecorder(this.stream, {
      mimeType: "audio/webm;codecs=opus",
    });
    this.recorder.onerror = () => onError("speechError");
    this.recorder.ondataavailable = async (e) => {
      if (!this.stopping && e.data.size && this.socket.readyState === 1) {
        const buffer = await e.data.arrayBuffer();
        if (!this.stopping && this.socket.readyState === 1)
          this.socket.send(buffer);
      }
    };
    this.recorder.onstop = () => {
      if (!this.stopping) {
        this.recorder.start();
        this.chunkTimer = setTimeout(() => {
          if (this.recorder.state === "recording") this.recorder.stop();
        }, 2000);
      }
    };
    this.recorder.start();
    this.chunkTimer = setTimeout(() => {
      if (this.recorder.state === "recording") this.recorder.stop();
    }, 2000);
  }
  stop() {
    this.stopping = true;
    this.cancelStart?.();
    clearTimeout(this.chunkTimer);
    if (this.recorder?.state === "recording") this.recorder.stop();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.socket?.close();
  }
}
let pendingWarning;
export function cancelWarning() {
  // Some engines emit no event after cancel(). Always settle the pending promise.
  pendingWarning?.(false);
  try {
    window.speechSynthesis?.cancel();
  } catch {}
}
export function speakWarning(
  text,
  language,
  { signal, timeoutMs = 15000 } = {},
) {
  cancelWarning();
  const synthesis = window.speechSynthesis;
  if (!synthesis || signal?.aborted) return Promise.resolve(false);
  let voice;
  try {
    voice = synthesis
      .getVoices()
      .find((candidate) =>
        candidate.lang
          .toLowerCase()
          .startsWith(language.split("-")[0].toLowerCase()),
      );
  } catch {
    return Promise.resolve(false);
  }
  if (!voice) return Promise.resolve(false);
  return new Promise((resolve) => {
    let settled = false,
      timer,
      utterance;
    const finish = (spoken) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      if (utterance) utterance.onend = utterance.onerror = null;
      if (pendingWarning === finish) pendingWarning = null;
      resolve(spoken);
    };
    const abort = () => {
      finish(false);
      try {
        synthesis.cancel();
      } catch {}
    };
    pendingWarning = finish;
    signal?.addEventListener("abort", abort, { once: true });
    timer = setTimeout(abort, Math.min(30000, Math.max(1, timeoutMs)));
    try {
      utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = language;
      utterance.rate = 0.85;
      utterance.onend = () => finish(true);
      utterance.onerror = () => finish(false);
      synthesis.speak(utterance);
    } catch {
      abort();
    }
  });
}
export class NativeASR extends ASRProvider {
  async start({ language, onText, onError }) {
    this.native = await import("./native.js");
    try {
      await this.native.speechStart(language, onText, onError);
    } catch (error) {
      throw Error(
        error.message === "permissionDenied"
          ? "permissionDenied"
          : "unsupported",
      );
    }
  }
  stop() {
    this.native?.speechStop().catch(() => {});
  }
}
export async function chooseASR(provider) {
  if (provider === "selfhost") return new HostedASR();
  try {
    const native = await import("./native.js");
    if (native.isNative()) return new NativeASR();
  } catch {}
  return new BrowserASR();
}
