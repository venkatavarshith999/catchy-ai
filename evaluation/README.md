# Evaluation protocol

cases.json is a synthetic development regression set, not held-out data. It includes known weaknesses. Run python -m evaluation.run to regenerate results.json with the configured classifier.

Do not use its tiny sample as a marketing accuracy claim. Build a separately labeled, script-family-disjoint set containing unfamiliar wording, multiple speakers, noise, legitimate urgency, quotations, protective statements and adversarial instructions. Test languages separately.

Measure time from a dangerous utterance ending to the visible warning. The app's latency_ms excludes transcription and transport. Compare rules and contextual modes, recording failures, false alerts and missed scams. A low score never guarantees safety.
