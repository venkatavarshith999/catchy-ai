"""Content-free operational events. Never pass request data to this module."""

import json
import logging
import os
import time

import httpx

logger = logging.getLogger("catchy.events")
EVENTS = {"request_failed", "retention_cleanup_failed", "live_channel_failed"}


def log_event(event, **fields):
    safe = {key: value for key, value in fields.items() if key in {"status", "duration_ms"}}
    logger.warning(
        json.dumps(
            {
                "event": event if event in EVENTS else "request_complete",
                "time": int(time.time()),
                **safe,
            }
        )
    )


async def report_error(event):
    event = event if event in EVENTS else "request_failed"
    log_event(event)
    url = os.environ.get("ERROR_WEBHOOK_URL", "")
    if not url.startswith("https://"):
        return
    try:
        async with httpx.AsyncClient(timeout=0.5, follow_redirects=False) as client:
            await client.post(
                url,
                json={"service": "catchy", "event": event, "time": int(time.time())},
                headers={"Authorization": "Bearer " + os.environ.get("ERROR_WEBHOOK_TOKEN", "")},
            )
    except httpx.HTTPError:
        logger.warning(json.dumps({"event": "monitor_unavailable"}))
