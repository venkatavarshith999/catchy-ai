# Contextual AI adapter

The default engine is deterministic English pattern analysis. Optional Ollama uses /api/chat, JSON output, temperature zero and a five-second timeout.

The model receives redacted turns and instructions treating conversation content as untrusted data. Known signal keys, valid turn numbers and exact quotations are required. Invalid evidence is rejected. Failures preserve baseline analysis and explicitly mark model_status as unavailable.

This additive policy does not calibrate probabilities or remove rule-based false positives. No model weights or credentials are bundled. Install and test your chosen model separately; see the root README.

References: https://docs.ollama.com/api/chat and https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
