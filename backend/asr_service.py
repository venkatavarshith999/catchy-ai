"""Optional in-memory ASR worker. Audio is never written to disk.

Run on a private network: uvicorn backend.asr_service:app --port 9001.
Install requirements-asr.txt and provision model weights before use.
"""

import asyncio
import io
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

model = None
lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app):
    global model
    from faster_whisper import WhisperModel

    model = WhisperModel(
        os.environ.get("WHISPER_MODEL", "small"),
        device=os.environ.get("WHISPER_DEVICE", "cpu"),
        compute_type=os.environ.get("WHISPER_COMPUTE", "int8"),
    )
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, openapi_url=None)


@app.websocket("/stream")
async def stream(ws: WebSocket):
    token = os.environ.get("ASR_SERVICE_TOKEN")
    if token and ws.headers.get("authorization") != "Bearer " + token:
        await ws.close(1008)
        return
    await ws.accept()
    try:
        config = await asyncio.wait_for(ws.receive_json(), 10)
        language = str(config.get("language", "en")).split("-")[0]

        def transcribe(audio):
            segments, _ = model.transcribe(
                io.BytesIO(audio), language=language, vad_filter=True, beam_size=1
            )
            return " ".join(segment.text.strip() for segment in segments)[:1500]

        while True:
            audio = await asyncio.wait_for(ws.receive_bytes(), 20)
            if len(audio) > 250000:
                await ws.send_json({"error": "chunk_too_large"})
                break
            if model is None:
                await ws.send_json({"error": "model_unavailable"})
                break
            try:
                async with lock:
                    text = await run_in_threadpool(transcribe, audio)
                if text:
                    await ws.send_json({"text": text})
            except Exception:
                await ws.send_json({"error": "transcription_failed"})
            finally:
                audio = b""
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
