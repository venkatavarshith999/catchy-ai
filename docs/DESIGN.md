# Catchy interface system — October 2026

Updated 22 October 2026 using the user-supplied Pool Service HTML template by Spicer Designs. The phone remains the primary interactive layout, with a bottom navigation bar and safe-area padding. Desktop uses the template's horizontal navigation, wide illustrated hero and alternating section bands. Listen, Check text and Practice use the existing consent and analysis pipeline.

## Visual system

- Pale blue `#F4F9FB` canvas, `#E5F1F6` section bands and white cards.
- Ink `#0E1F28`, sky blue `#0284C7` accents and darker `#0369A1` button fills for readable white labels. Amber/red remain reserved for caution/danger.
- The template's Fraunces headings and Inter body fonts are bundled locally with their OFL licenses. Noto fonts continue to cover other scripts.
- Pill buttons, thin borders, 12–16 px cards, numbered guidance and a real FAQ accordion reflect the supplied template. Controls keep 56 px minimum targets; the extra-large setting increases important content to 24 px.
- The supplied water artwork is decorative AI-generated placeholder imagery, not a claim about Catchy or its users. Template credit and license are retained; see TEMPLATE-NOTICE.md.

## Real product states

Idle says “Not listening.” A user must choose a mode and consent before analysis begins. The active state, result evidence, errors, and full-screen warning retain their existing handlers. The sample-warning button uses the selected language's installed speech voice, reports a missing voice, and is disabled during analysis so a sample cannot contaminate microphone input. Text checking is manual, not automatic inbox access. The screen explicitly says that automated phone screening and inbox monitoring are not connected.

The voice card and trusted-person card are secondary to starting a check. History, account, contact, settings, evaluation, and legal screens share the same typography, form, table, dialog, and color system. The Android launcher vector, splash background, PWA icons and browser theme use the same brand.

## Accessibility and release validation

Semantic headings, labelled controls, selected navigation state, pressed mode states, keyboard focus outlines, reduced-motion handling, Urdu RTL spacing, safe-area insets, high contrast and extra-large text are implemented. English, Hindi and Telugu include the new copy; other enabled catalogs retain their documented English fallback. Human review of translated copy and device speech is still required.

The source redesign is not a compiled Android APK. Run the existing build and Capacitor sync steps, then build/test with the Android SDK on a physical device. Browser visual automation was previously blocked in this environment, so there is no claim of completed screenshot, overflow, screen-reader, or WCAG certification. Review at 360/390/760/1440 px, 200% zoom, extra-large text, Urdu, Hindi and Telugu before release. Test native microphone, background pause, spoken alerts and safe-area behavior on actual phones.
