# Evaluation protocol

Run `python -m evaluation.multilingual`. The report includes 20 cases per enabled language (10 high-risk scam, 10 genuine), confusion counts, precision, recall, F1, per-case outcomes and text-engine p50/p95 timing. English/Hindi/Telugu cases are authored synthetic development examples. The ten later beta packs use lexicon-derived smoke cases and are labeled accordingly. None is an independent holdout or field-accuracy estimate.

`python scripts/smoke.py` starts a real local HTTP service against an isolated temporary database and measures 12 text request round trips. It verifies readiness and frontend serving. `http-benchmark.json` explicitly leaves audio end-to-end timing null.

During real browser/Android speech use, the UI displays speech-end-to-result latency only when recognition provides a speech-end timestamp. Hosted chunked ASR does not currently provide one. Typed/simulated text is not presented as an audio benchmark. The under-three-second speech target has not been validated.

Build a separately labeled, script-family-disjoint holdout containing unfamiliar wording, multiple speakers, noise, legitimate urgency, quotations, protective statements and prompt-injection attempts. Native speakers should review labels and translations; obtain consent for any real recordings. Benchmark supported phones, speech providers and code-mixing separately. Do not tune exclusively to these tiny fixtures or use their scores as marketing claims.

`cases.json`, `run.py` and `results.json` in this folder preserve the legacy English-only protocol. The current multilingual fixtures live in `data/<lang>/cases.json`.
