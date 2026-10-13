package com.catchyai.safety;

import android.Manifest;
import android.content.Intent;
import android.os.Bundle;
import android.os.SystemClock;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import java.util.ArrayList;

@CapacitorPlugin(name = "CatchySpeech", permissions = {
    @Permission(alias = "microphone", strings = { Manifest.permission.RECORD_AUDIO })
})
public class CatchySpeechPlugin extends Plugin implements RecognitionListener {
    private SpeechRecognizer recognizer;
    private boolean listening = false;
    private Intent intent;
    private long speechEnded = 0;

    @PluginMethod
    public void start(PluginCall call) {
        if (getPermissionState("microphone") != PermissionState.GRANTED) {
            requestPermissionForAlias("microphone", call, "microphoneCallback");
            return;
        }
        getActivity().runOnUiThread(() -> {
            if (!SpeechRecognizer.isRecognitionAvailable(getContext())) {
                call.reject("unsupported");
                return;
            }
            stopRecognizer();
            recognizer = SpeechRecognizer.createSpeechRecognizer(getContext());
            recognizer.setRecognitionListener(this);
            intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, call.getString("language", "en-IN"));
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false);
            listening = true;
            recognizer.startListening(intent);
            call.resolve();
        });
    }
    @PermissionCallback
    private void microphoneCallback(PluginCall call) {
        if (getPermissionState("microphone") == PermissionState.GRANTED) start(call);
        else call.reject("permissionDenied");
    }
    @PluginMethod
    public void stop(PluginCall call) {
        getActivity().runOnUiThread(() -> { stopRecognizer(); call.resolve(); });
    }
    private void stopRecognizer() {
        listening = false;
        if (recognizer != null) { recognizer.cancel(); recognizer.destroy(); recognizer = null; }
    }
    @Override protected void handleOnPause() { stopRecognizer(); }
    @Override protected void handleOnDestroy() { stopRecognizer(); }
    @Override public void onEndOfSpeech() { speechEnded = SystemClock.elapsedRealtime(); }
    @Override public void onBeginningOfSpeech() { speechEnded = 0; }
    @Override public void onResults(Bundle results) {
        if (!listening) return;
        ArrayList<String> texts = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (texts != null && !texts.isEmpty()) {
            JSObject data = new JSObject();
            data.put("text", texts.get(0));
            data.put("elapsed_ms", speechEnded == 0 ? -1 : SystemClock.elapsedRealtime() - speechEnded);
            notifyListeners("transcript", data);
        }
        if (listening && recognizer != null) recognizer.startListening(intent);
    }
    @Override public void onError(int error) {
        if (!listening) return;
        listening = false;
        JSObject data = new JSObject();
        data.put("error", error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS ? "permissionDenied" : "speechError");
        notifyListeners("speechFailure", data);
    }
    @Override public void onReadyForSpeech(Bundle params) {}
    @Override public void onRmsChanged(float rmsdB) {}
    @Override public void onBufferReceived(byte[] buffer) {}
    @Override public void onPartialResults(Bundle results) {}
    @Override public void onEvent(int eventType, Bundle params) {}
}
