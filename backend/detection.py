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

# These are narrow transcript-context rules, not speaker identification or
# speech quality estimates. Callers must surface transcription uncertainty
# separately: missing negations or ambiguous referents cannot be repaired here.
DISCLOSURE_VERBS = (
    "tell",
    "share",
    "read",
    "give",
    "send",
    "provide",
    "reveal",
    "disclose",
    "बताएं",
    "बताओ",
    "भेजें",
    "भेजो",
    "पढ़ें",
    "बोलें",
    "batao",
    "bataye",
    "bhejo",
    "bheje",
    "padho",
    "చెప్పండి",
    "చెప్పు",
    "పంపండి",
    "పంపు",
    "చదవండి",
    "ఇవ్వండి",
    "cheppandi",
    "cheppu",
    "pampandi",
    "pampu",
    "chadavandi",
    "ivvandi",
)
RECIPIENTS = (
    "to me",
    "to us",
    "tell me",
    "tell us",
    "give me",
    "give us",
    "provide me",
    "provide us",
    "with me",
    "with us",
    "mujhe",
    "hame",
    "hume",
    "मुझे",
    "हमें",
    "naaku",
    "naku",
    "maaku",
    "maku",
    "నాకు",
    "మాకు",
)
REFERENTS = (
    "it",
    "that",
    "this code",
    "the code",
    "use",
    "woh",
    "इसे",
    "वह",
    "అది",
    "దాన్ని",
    "adi",
)


def phrase_spans(text, phrases):
    for phrase in phrases:
        yield from re.finditer(r"(?<![a-z])" + re.escape(normalize(phrase)) + r"(?![a-z])", text)


def protective_spans(value, active):
    spans = list(phrase_spans(value, [p for pack in active for p in pack["protective"]]))
    # Cover negated payment requests without treating a whole turn as protective.
    spans.extend(
        re.finditer(
            r"\b(?:never|do not|don't|must not|should not)\s+"
            r"(?:share|tell|give|read|send|provide|transfer|pay|buy|move|install|download|allow)\b",
            value,
        )
    )
    return spans


def disclosure_request(value, negatives):
    for verb in phrase_spans(value, DISCLOSURE_VERBS):
        if any(span.start() <= verb.start() < span.end() for span in negatives):
            continue
        before = value[max(0, verb.start() - 45) : verb.start()]
        after = value[verb.end() :]
        if re.search(r"(?:\bnot|\bnever|\bmat|मत|न)\s+(?:please\s+)?$", before):
            continue
        if re.match(r"\s+(?:me|us)\s+(?:if|whether|about)\b", after):
            continue
        if negatives:
            # Preserve safety advice, but not an additional request to disclose
            # to the speaker. Contrast clauses are evaluated independently.
            request_window = value[max(0, verb.start() - 35) : verb.end() + 85]
            if not match(request_window, RECIPIENTS):
                continue
            previous = [span for span in negatives if span.end() <= verb.start()]
            if previous and re.search(r"\bor\b", value[previous[-1].end() : verb.start()]):
                continue
        return True
    return False


def official_credential_entry(value, disclosure):
    return (
        not disclosure
        and match(
            value, ("enter", "type", "input", "use", "डालें", "darj", "చేయండి", "చేయాలి", "cheyandi")
        )
        and match(
            value,
            ("official app", "official website", "official portal", "आधिकारिक ऐप", "అధికారిక యాప్"),
        )
    )


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
    credential_context = None
    clause_number = 0
    for i, text in enumerate(turns):
        actual = detect_language(text, language)
        extra = lexicon(actual)
        active = packs + [extra]
        for clause in re.split(
            r"[,.!?;\n।]|\bbut\b|\bhowever\b|\binstead\b|\blekin\b|\bkaani\b|लेकिन|కానీ",
            text,
            flags=re.IGNORECASE,
        ):
            value = normalize(clause).strip()
            if not value:
                continue
            clause_number += 1
            quoted = any(match(value, p.get("reported", [])) for p in active)
            if quoted:
                # Do not reuse an older credential after a reported-example turn.
                credential_context = None
                continue
            negatives = protective_spans(value, active)
            credential = any(match(value, p["signals"]["credential"]) for p in active)
            # A bare 'code' is ambiguous. Resolve it only when described as sent,
            # received, verification, or one-time, never from arbitrary numbers.
            credential_mention = credential or (
                match(value, ("code",))
                and match(value, ("sent", "received", "verification", "one-time"))
            )
            negative = bool(negatives)
            disclosure = disclosure_request(value, negatives)
            protective = protective or negative
            recent = credential_context and (
                i - credential_context[0] <= 1
                and clause_number - credential_context[1] <= 2
                and (not credential_context[3] or i == credential_context[0])
            )
            referenced_request = bool(
                recent and disclosure and match(value, RECIPIENTS) and match(value, REFERENTS)
            )
            entry_only = official_credential_entry(value, disclosure)
            ask = any(match(value, p["ask"]) for p in active)
            for key, weight in WEIGHTS.items():
                signal = any(match(value, p["signals"][key]) for p in active)
                if key == "credential":
                    signal = signal or referenced_request
                    if entry_only:
                        continue
                if key == "remote" and entry_only:
                    # A local-language word for 'app' alone is not a remote
                    # control request. Keep named tools and screen-access asks.
                    signal = any(
                        match(
                            value, [term for term in p["signals"][key] if term not in {"ऐप", "యాప్"}]
                        )
                        for p in active
                    )
                if not signal:
                    continue
                if negative and not disclosure:
                    if key != "secrecy" or credential_mention:
                        continue
                if key in ACTIONS and not (ask or (key == "credential" and disclosure)):
                    continue
                quote = clause.strip()
                if key == "credential" and referenced_request and not credential:
                    quote = credential_context[2][:90] + " → " + quote[:120]
                evidence.setdefault(
                    key,
                    {
                        "key": key,
                        "label": key,
                        "weight": weight,
                        "turn": i + 1,
                        "quote": redact(quote)[:220],
                    },
                )
            if credential_mention:
                # Even safety advice supplies a referent for an immediately
                # contradictory request in the same turn, but not future turns.
                credential_context = (i, clause_number, clause.strip(), negative)
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
