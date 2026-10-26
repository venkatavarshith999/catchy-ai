# Template UI update — 22 October 2026

The existing Catchy app now adapts the user-supplied Pool Service HTML template: pale blue surfaces, sky-blue accents, locally bundled Fraunces and Inter fonts, pill buttons, a wide water-image hero, alternating section bands and bordered white panels. The image is decorative AI-generated template artwork. Spicer Designs attribution and the supplied license are retained.

The hero shortcuts select Listen or Check text and focus the actual session button. Consent is still required. Existing account, history, contacts, settings, LLM, evidence and warning flows remain connected. Native details elements provide the FAQ. Hindi and Telugu cover the new copy; other enabled catalogs continue their documented English fallback. Large-text controls and keyboard focus were reviewed and corrected. The old service-worker cache is replaced on activation.

## Verification

- Backend suite: 79 passed, 1 external PostgreSQL/Redis test skipped locally. Used bundled Python 3.12 with the installed project packages because the environment could not start the existing venv executable.
- Existing JavaScript regressions passed. Added `tests/test_product_ui.mjs` to `npm run check`: 78 localized mode/state combinations plus consent, focus visibility targets, escaping and active-session guards. These are executable handler/rendering checks, not browser layout tests.
- All new public asset URLs and all enabled locale key sets passed the backend asset test after the manifest was regenerated.
- Formatting checks passed.
- Browser screenshot and physical-device checks remain outstanding. Earlier automatic approval review blocked local preview access; no alternate browser route was used.

## Android assets and build limitation

Full esbuild bundling failed in this Windows sandbox while traversing an inaccessible ancestor directory. The unchanged prebuilt bridge was reused explicitly via `node scripts/build-mobile.mjs --assets-only`, producing the new public manifest and `mobile/web` assets. This option is only appropriate when native bridge source and dependencies have not changed; normal `npm run build` still rebuilds the bridge.

Capacitor CLI then failed in `os.userInfo()` (`uv_os_get_passwd`). With the bridge confirmed byte-identical, the public UI assets were copied into the existing Android public-assets directory and checked byte-for-byte. Native plugins were not regenerated and no APK was compiled. On a normal developer machine or CI, use the standard `npm run android:sync` and Android build workflow before device testing. Source ZIPs omit generated mobile/Android public-assets directories and regenerate them through the normal build.

Automatic call screening, interception of cellular audio and SMS inbox monitoring remain outside this implementation. This update replaces the interface, not those platform integrations.
