"""Explicitly configured delivery adapters. Never log addresses or message content."""

import os
import smtplib
import ssl
from email.message import EmailMessage

import httpx


def mail_available():
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"))


def send_mail(address, subject, body):
    if not mail_available():
        return False
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = address
    message["Subject"] = subject
    message.set_content(body)
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=6)
    else:
        server = smtplib.SMTP(host, port, timeout=6)
        server.starttls(context=ssl.create_default_context())
    with server:
        if os.environ.get("SMTP_USER"):
            server.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        server.send_message(message)
    return True


def alert_available():
    return bool(os.environ.get("ALERT_WEBHOOK_URL")) or mail_available()


def deliver_alert(contact, metadata):
    url = os.environ.get("ALERT_WEBHOOK_URL")
    if url:
        if not url.startswith("https://"):
            raise ValueError("Webhook requires HTTPS")
        # Recipient routing is necessary for delivery; the incident payload has only allowed metadata.
        response = httpx.post(
            url,
            json={
                "recipient": {"email": contact.email, "phone": contact.phone},
                "incident": metadata,
            },
            headers={"Authorization": "Bearer " + os.environ.get("ALERT_WEBHOOK_TOKEN", "")},
            timeout=6,
        )
        response.raise_for_status()
        return True
    return send_mail(
        contact.email,
        "Catchy AI safety notification",
        "\n".join(f"{key}: {value}" for key, value in metadata.items()),
    )
