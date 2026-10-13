"""Data-driven, multilingual pressure detection; severity is not probability."""

import json
import re
import time
import unicodedata
from pathlib import Path

from llms.engine import redact as legacy_redact

SIGNALS = Path(__file__).parent / "signals"
WEIGHTS = {
    "authority": 12,
    "urgency": 13,
    "fear": 18,
    "secrecy": 20,
    "credential": 65,
    "payment": 35,
    "remote": 60,
}
ACTIONS = {"credential", "payment", "remote"}


def normalize(text):
    return unicodedata.normalize("NFKC", text).casefold()


def redact(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(
        r"(?<!\w)[\d\u0966-\u096f\u0c66-\u0c6f][\d\u0966-\u096f\u0c66-\u0c6f ()-]{2,}[\d\u0966-\u096f\u0c66-\u0c6f](?!\w)",
        "[number]",
        text,
    )
    return legacy_redact(text)


def lexicon(code):
    if not re.fullmatch(r"[a-z]{2,3}", code):
        raise ValueError("Invalid language code")
    path = SIGNALS / f"{code}.yaml"
    if not path.exists():
        path = SIGNALS / "en.yaml"
    # JSON is a YAML subset; lexicons need no parser-specific syntax.
    return json.loads(path.read_text(encoding="utf-8"))


def detect_language(text, fallback="en"):
    for code, start, end in [
        ("te", 0x0C00, 0x0C7F),
        ("hi", 0x0900, 0x097F),
        ("ta", 0x0B80, 0x0BFF),
        ("kn", 0x0C80, 0x0CFF),
        ("ml", 0x0D00, 0x0D7F),
        ("bn", 0x0980, 0x09FF),
        ("gu", 0x0A80, 0x0AFF),
        ("pa", 0x0A00, 0x0A7F),
        ("or", 0x0B00, 0x0B7F),
        ("ur", 0x0600, 0x06FF),
    ]:
        if any(start <= ord(c) <= end for c in text):
            return code
    return fallback


def match(text, phrases):
    return any(
        re.search(r"(?<![a-z])" + re.escape(normalize(p)) + r"(?![a-z])", text) for p in phrases
    )


def analyze(turns, language="en"):
    if not re.fullmatch(r"[a-z]{2,3}", language):
        raise ValueError("Invalid language code")
    start = time.perf_counter()
    evidence = {}
    protective = False
    supported = (SIGNALS / f"{language}.yaml").exists()
    packs = [lexicon("en")] + ([lexicon(language)] if language != "en" else [])
    for i, text in enumerate(turns):
        actual = detect_language(text, language)
        extra = lexicon(actual)
        active = packs + [extra]
        for clause in re.split(
            r"[,.!?;\n।]|\bbut\b|\bhowever\b|लेकिन|కానీ", text, flags=re.IGNORECASE
        ):
            value = normalize(clause)
            negative = any(match(value, p["protective"]) for p in active) and not any(
                match(value, p["signals"]["secrecy"]) for p in active
            )
            quoted = any(match(value, p.get("reported", [])) for p in active)
            protective = protective or negative
            if quoted:
                continue
            ask = any(match(value, p["ask"]) for p in active)
            for key, weight in WEIGHTS.items():
                if not any(match(value, p["signals"][key]) for p in active):
                    continue
                if negative and key != "secrecy":
                    continue
                if key in ACTIONS and not ask:
                    continue
                evidence.setdefault(
                    key,
                    {
                        "key": key,
                        "label": key,
                        "weight": weight,
                        "turn": i + 1,
                        "quote": redact(clause.strip())[:220],
                    },
                )
    score = sum(e["weight"] for e in evidence.values()) + (8 if len(evidence) >= 4 else 0)
    if set(evidence).issubset({"authority", "urgency"}):
        score = min(score, 24)
    if not ACTIONS.intersection(evidence):
        score = min(score, 59)
    score = min(score, 98)
    return {
        "score": score,
        "level": "high" if score >= 60 else "caution" if score >= 30 else "low",
        "signals": list(evidence.values()),
        "language": language,
        "detected_language": detect_language(" ".join(turns), language),
        "language_status": "beta" if supported else "unsupported",
        "protective_language": protective,
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        "engine": "multilingual-rules",
        "model_status": "disabled",
    }
