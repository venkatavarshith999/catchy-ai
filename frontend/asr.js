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
      for (let i = e.resultIndex; i < e.results.length; i++)
        if (e.results[i].isFinal)
          onText(e.results[i][0].transcript, this.speechEnd);
    };
    this.recognition.onerror = (e) =>
      onError(e.error === "not-allowed" ? "permissionDenied" : "speechError");
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
  async start({ language, onText, onError }) {
    this.stopping = false;
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (this.stopping) {
      this.stream.getTracks().forEach((track) => track.stop());
      throw Error("background");
    }
    this.socket = new WebSocket(
      `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v2/asr?language=${encodeURIComponent(language)}`,
    );
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.stop();
        reject(Error("asrUnavailable"));
      }, 10000);
      this.socket.onopen = () => {
        clearTimeout(timeout);
        resolve();
      };
      this.socket.onerror = () => {
        clearTimeout(timeout);
        reject(Error("asrUnavailable"));
      };
      this.socket.onclose = () => {
        clearTimeout(timeout);
        reject(Error("asrUnavailable"));
      };
    });
    this.socket.onmessage = (e) => {
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
      if (e.data.size && this.socket.readyState === 1)
        this.socket.send(await e.data.arrayBuffer());
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
    clearTimeout(this.chunkTimer);
    if (this.recorder?.state === "recording") this.recorder.stop();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.socket?.close();
  }
}
export async function speakWarning(text, language) {
  if (!window.speechSynthesis) return false;
  const voices = speechSynthesis.getVoices();
  const voice = voices.find((v) =>
    v.lang.toLowerCase().startsWith(language.split("-")[0].toLowerCase()),
  );
  if (!voice) return false;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.voice = voice;
  utterance.lang = language;
  utterance.rate = 0.85;
  speechSynthesis.speak(utterance);
  return true;
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
