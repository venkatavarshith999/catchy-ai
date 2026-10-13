# Android and PWA

## PWA first

Deploy over HTTPS and open the site on the phone. Use **Install Catchy** or the browser's **Add to Home screen** command. `localhost` on your phone refers to the phone itself, not the PC. The service worker caches public UI/catalog/font files only; APIs, identities and conversations are excluded. Offline UI does not imply offline protection.

## Android source build

Requirements: Node 22+, JDK 21, Android SDK platform/build tools 36 and Android Studio or the included Gradle wrapper. The generated project has minimum SDK 24. The current build environment has no Android SDK, so an APK/AAB was not compiled or device-tested here.

1. Deploy the Catchy backend/frontend over HTTPS.
2. Run `npm ci` and `npm run build` in the project root.
3. Set `CATCHY_APP_URL` to your deployed HTTPS origin, then run `node scripts/configure-mobile.mjs`.
4. Run `npx cap sync android`.
5. From `android/`, run `gradlew.bat assembleDebug` on Windows or `./gradlew assembleDebug` on Linux/macOS.
6. Install `android/app/build/outputs/apk/debug/app-debug.apk` on a test phone.

Or run the repository's **Build Android test APK** workflow with that HTTPS origin. It provisions JDK/SDK and uploads a debug APK. This workflow definition is provided; it has not executed in this workspace.

The wrapper loads your deployed site as the app's same-origin server. This avoids cross-origin cookie workarounds but requires a reachable HTTPS deployment. A default unconfigured wrapper cannot perform analysis. Only point it at an origin you control: that site's scripts can use the registered native bridges. Deploy matching `frontend/native.js` along with the rest of the release.

## Native bridges

`CatchySpeechPlugin` uses Android SpeechRecognizer after microphone permission, emits recognized text and speech-end timing, and stops on pause/destroy. Android recognition may use a platform vendor's network service. `CatchyScreenPlugin` applies/clears the screen-awake flag. Capacitor Haptics supplies a warning vibration; app background events stop active protection. There is no call-log, accessibility-service or cellular-audio interception permission.

Test English/Hindi/Telugu voice availability, permission denial, microphone contention, airplane mode, background/foreground transitions, notification interruption, battery saver, RTL and very large system fonts on representative phones. A normal cellular call may prevent microphone capture on the same phone. Use a consented second-device scenario when necessary.

For a release AAB, configure signing in Android Studio or your secure CI secret store, run `bundleRelease`, and complete store/device review. No signing keys or production credentials belong in source. The package includes neither a release signing identity nor an assertion of Play Store approval.
