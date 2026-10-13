# Hackathon demo: calm guidance at the moment of pressure

## Pitch

Scam calls exploit urgency, authority and isolation. Catchy gives a person time to pause: it examines the request being made, explains the risk simply, and offers a path to someone they trust. Its differentiators are language-aware evidence, accessible warnings, explicit contact consent and a privacy-first data lifecycle.

## Four-minute walkthrough

1. Start the server, open the app, select Telugu (or Hindi/English), and explain the foreground microphone limitation and consent.
2. Choose the scam simulation. It begins with an authority claim, adds urgency, then requests an OTP. The final request triggers the red warning and two clear actions. If a matching voice is installed, the warning is spoken; otherwise the onscreen fallback explains that.
3. Stop, choose the genuine-call simulation, and show protective advice does not trigger the same warning. Type a different synthetic request to demonstrate the live API rather than only scripted visuals.
4. Sign in and show history. Explain why transcript evidence is empty with retention off. Opt in for a new synthetic session to demonstrate redacted evidence and deletion.
5. Show an accepted trusted-contact relationship and mutual alert settings using two prepared, verified test accounts. Send only an explicitly requested test alert if a provider is configured; otherwise demonstrate the honest unavailable state.
6. Show the admin evaluation page or the report: 260 synthetic cases across 13 beta lexicons, with separate authored versus lexicon-derived labels. Highlight misses and explain that these numbers do not measure real-world speech accuracy.

## Prepare

Use dummy content only. Verify localhost startup before presenting. Use a deployed HTTPS URL for a phone, not the laptop's localhost URL. Prepare language voices, two test accounts and accepted invitation in advance. Guest demos work without email delivery or an LLM. Keep typed mode ready when a browser/device lacks speech recognition.

## Answer honestly

No APK is prebuilt in this ZIP. No universal cellular capture, sub-three-second audio guarantee, flawless accuracy, complete translation of all scheduled languages, or live SMS delivery is claimed. WebRTC/telephony integration and field validation are next product milestones. CI/CD configuration is included; a remote deployment requires the team's hosting and provider accounts.
