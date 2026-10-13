import { Capacitor, registerPlugin } from "@capacitor/core";
import { Haptics, ImpactStyle } from "@capacitor/haptics";
import { App } from "@capacitor/app";
const Screen = registerPlugin("CatchyScreen");
export async function haptic() {
  if (Capacitor.isNativePlatform())
    await Haptics.impact({ style: ImpactStyle.Heavy });
}
export async function keepAwake() {
  if (Capacitor.isNativePlatform()) await Screen.keepAwake();
}
export async function allowSleep() {
  if (Capacitor.isNativePlatform()) await Screen.allowSleep();
}
if (Capacitor.isNativePlatform())
  App.addListener("appStateChange", (state) => {
    if (!state.isActive) window.dispatchEvent(new Event("catchy-background"));
  });
const Speech = registerPlugin("CatchySpeech");
export const isNative = () => Capacitor.isNativePlatform();
let speechListeners = [];
export async function speechStart(language, onText, onError) {
  speechListeners.push(
    await Speech.addListener("transcript", (data) =>
      onText(
        data.text,
        data.elapsed_ms >= 0 ? performance.now() - data.elapsed_ms : null,
      ),
    ),
  );
  speechListeners.push(
    await Speech.addListener("speechFailure", (data) => onError(data.error)),
  );
  await Speech.start({ language });
}
export async function speechStop() {
  await Speech.stop();
  for (const listener of speechListeners) await listener.remove();
  speechListeners = [];
}
