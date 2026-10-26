"""Paired synthetic text regressions, not caller or transcription validation."""

import pytest

from backend.detection import analyze


def keys(result):
    return {signal["key"] for signal in result["signals"]}


@pytest.mark.parametrize(
    "language,benign,harmful",
    [
        (
            "en",
            "This is your bank. Enter your OTP in the official app. Never share it with anyone.",
            "This is your bank. Tell me your OTP immediately.",
        ),
        (
            "hi",
            "Bank se bol rahe hain. OTP official app mein enter karo. OTP kabhi mat batao.",
            "Bank se bol rahe hain. OTP mujhe abhi batao.",
        ),
        (
            "te",
            "Bank nunchi. OTP official app lo enter cheyandi. OTP evariki cheppakandi.",
            "Bank nunchi. OTP naaku ippude cheppandi.",
        ),
        (
            "hi",
            "बैंक: अपना ओटीपी आधिकारिक ऐप में डालें। ओटीपी साझा न करें।",
            "बैंक: अपना ओटीपी मुझे तुरंत बताओ।",
        ),
        (
            "te",
            "బ్యాంకు: OTP అధికారిక యాప్ లో enter చేయండి. మీ ఓటీపీ చెప్పకండి.",
            "బ్యాంకు: మీ ఓటీపీ నాకు వెంటనే చెప్పండి.",
        ),
    ],
)
def test_official_app_entry_and_caller_disclosure(language, benign, harmful):
    safe_context = analyze([benign], language)
    risky_context = analyze([harmful], language)
    assert safe_context["level"] == "low"
    assert "credential" not in keys(safe_context)
    assert risky_context["level"] == "high"
    assert "credential" in keys(risky_context)


@pytest.mark.parametrize(
    "turns",
    [
        [
            "This is your bank. Your account will be frozen.",
            "A code was sent to your phone.",
            "Read it to me immediately.",
        ],
        ["Your bank sent a verification code. Read it to me immediately."],
        ["Your OTP has arrived", "Please give it to me"],
    ],
)
def test_recent_credential_reference(turns):
    result = analyze(turns)
    assert result["level"] == "high"
    evidence = next(signal for signal in result["signals"] if signal["key"] == "credential")
    assert evidence["turn"] == len(turns)
    assert "→" in evidence["quote"]


@pytest.mark.parametrize(
    "language,turns",
    [
        ("hi", ["आपके फोन पर OTP आया है।", "इसे मुझे तुरंत बताओ।"]),
        ("te", ["మీకు OTP వచ్చింది.", "దాన్ని నాకు వెంటనే చెప్పండి."]),
        ("hi", ["OTP phone par aaya hai", "woh mujhe abhi batao"]),
        ("te", ["OTP vachindi", "adi naaku ippude cheppandi"]),
    ],
)
def test_mixed_language_reference(language, turns):
    result = analyze(turns, language)
    assert result["level"] == "high"
    assert "credential" in keys(result)


@pytest.mark.parametrize(
    "turns",
    [
        ["Read it to me immediately"],
        ["Your OTP arrived", "How was your day?", "Read it to me"],
        ["Your OTP arrived. Let us discuss lunch. How is the weather? Read it to me."],
        ["Your OTP arrived", "Tell me if it arrived"],
        ["Never share an OTP", "Read it to me"],
        ["The caller yesterday said your OTP has arrived", "Read it to me"],
        ["Your OTP arrived", "The scammer said to call later", "Read it to me"],
    ],
)
def test_reference_is_bounded_and_not_inferred_from_protective_or_reported_text(turns):
    assert "credential" not in keys(analyze(turns))


@pytest.mark.parametrize(
    "text",
    [
        "Never transfer money to a safe account on a caller request",
        "Do not transfer money to a safe account on a caller request",
        "You should not install AnyDesk for a stranger",
        "Never share your OTP or read it to anyone",
        "Do not tell anyone your OTP",
    ],
)
def test_protective_actions_stay_low(text):
    result = analyze([text])
    assert result["level"] == "low"
    assert result["protective_language"]
    assert not keys(result).intersection({"credential", "payment", "remote"})


@pytest.mark.parametrize(
    "language,text",
    [
        ("en", "Never share your OTP with anyone, but tell me your OTP now"),
        ("en", "Never share your OTP with anyone but read it to me immediately"),
        ("en", "Never share your OTP with anyone and tell me your password"),
        ("en", "Enter the OTP in the official app and tell me the OTP"),
        ("en", "Never transfer money but transfer it to our safe account immediately"),
        ("hi", "OTP kabhi mat batao lekin OTP mujhe abhi batao"),
        ("te", "OTP cheppakandi kaani OTP naaku ippude cheppandi"),
        ("hi", "ओटीपी साझा न करें लेकिन अपना ओटीपी मुझे बताओ"),
        ("te", "మీ ఓటీపీ చెప్పకండి కానీ మీ ఓటీపీ నాకు చెప్పండి"),
    ],
)
def test_protective_prefix_cannot_mask_real_request(language, text):
    result = analyze([text], language)
    assert keys(result).intersection({"credential", "payment"})
    if "credential" in keys(result):
        assert result["level"] == "high"


@pytest.mark.parametrize(
    "language,turns",
    [
        (
            "en",
            [
                "Your hospital payment is urgent",
                "You can pay at the hospital reception after checking your invoice",
            ],
        ),
        (
            "hi",
            [
                "Hospital mein urgent bhugtan hai",
                "Published number par verify karo aur reception par pay karo",
            ],
        ),
        ("te", ["Hospital payment urgent", "Invoice verify chesi reception lo payment cheyandi"]),
    ],
)
def test_hospital_payment_discussion_alone_is_not_high(language, turns):
    assert analyze(turns, language)["level"] != "high"


def test_hospital_claim_does_not_exempt_sensitive_request():
    result = analyze(["I am from the hospital. Your payment is urgent. Read your OTP to me."])
    assert result["level"] == "high"


def test_context_evidence_is_redacted():
    result = analyze(["Your OTP 123456 arrived", "Read it to me"])
    assert "123456" not in str(result["signals"])
    assert result["level"] == "high"


def test_unclear_text_is_not_a_speech_confidence_measurement():
    result = analyze(["[unclear speech]"])
    assert result["signals"] == []
    assert result["engine"] == "multilingual-rules"
    assert "confidence" not in result
