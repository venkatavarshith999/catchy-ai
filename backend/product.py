"""FastAPI product service. Run with uvicorn backend.product:app."""

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select, text
from starlette.concurrency import run_in_threadpool

from backend.detection import SIGNALS, analyze, redact
from backend.notifications import (
    alert_available,
    deliver_alert,
    mail_available,
    send_mail,
)
from backend.observability import report_error
from backend.product_store import (
    ROOT,
    Call,
    Contact,
    Counter,
    Delivery,
    LiveStore,
    Login,
    User,
    setup,
)
from backend.server import password_hash
from llms.product import classify, provider_config


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def uid():
    return secrets.token_hex(16)


DEFAULTS = {
    "language": "en",
    "retain_transcript": False,
    "retention_days": 30,
    "spoken_warnings": True,
    "high_contrast": False,
    "large_text": False,
    "analytics": False,
    "alert_opt_in": False,
    "asr": "browser",
}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Input):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(default="User", min_length=2, max_length=80)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", v):
            raise ValueError("email")
        return v.lower()


class ResetEmail(Input):
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        return Credentials.email_valid(value)


class ResetPassword(ResetEmail):
    code: str = Field(pattern=r"^[0-9]{6}$")
    password: str = Field(min_length=10, max_length=128)


class Preferences(Input):
    language: str = Field(default="en", max_length=12)
    retain_transcript: bool = False
    retention_days: int = Field(default=30, ge=1, le=90)
    spoken_warnings: bool = True
    high_contrast: bool = False
    large_text: bool = False
    analytics: bool = False
    alert_opt_in: bool = False
    asr: Literal["browser", "selfhost"] = "browser"


class NewCall(Input):
    title: str = Field(default="Conversation", max_length=100)
    language: str = Field(default="en", max_length=12)
    mode: Literal["demo", "typed", "speaker", "test"] = "typed"
    consent: bool


class Turn(Input):
    text: str = Field(min_length=1, max_length=1500)
    request_id: str = Field(min_length=8, max_length=80)
    speech_elapsed_ms: float | None = Field(default=None, ge=0, le=120000)


class Guest(Input):
    turns: list[str] = Field(min_length=1, max_length=60)
    language: str = Field(default="en", max_length=12)
    consent: bool

    @field_validator("turns")
    @classmethod
    def bounded(cls, values):
        if any(not 1 <= len(v) <= 1500 for v in values):
            raise ValueError("size")
        return values


class Invitation(Input):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        return Credentials.email_valid(v)


class Accept(Input):
    token: str = Field(min_length=20, max_length=150)
    phone: str = Field(min_length=7, max_length=25)
    alerts: bool = False

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        if not re.fullmatch(r"\+?[\d ()-]+", v):
            raise ValueError("phone")
        return v


class Code(Input):
    code: str = Field(min_length=6, max_length=6)


class Toggle(Input):
    enabled: bool


class AlertRequest(Input):
    call_id: str | None = Field(default=None, max_length=40)
    test: bool = False


class Analytics(Input):
    event: Literal["alert_shown", "alert_dismissed", "contact_called"]
    consent: bool


def create_app(database_url=None, redis_url=None):
    origin = os.environ.get("APP_ORIGIN", "http://localhost:8000").rstrip("/")
    production = os.environ.get("APP_ENV") == "production"
    if production and (
        not origin.startswith("https://")
        or not os.environ.get("DATABASE_URL", "").startswith(("postgres", "postgresql"))
        or not os.environ.get("REDIS_URL")
    ):
        raise RuntimeError(
            "Production requires HTTPS APP_ORIGIN, PostgreSQL DATABASE_URL and REDIS_URL"
        )
    if production and os.environ.get("DEV_EMAIL_CODES") == "1":
        raise RuntimeError("Development email codes are forbidden in production")
    engine, Session = setup(database_url)
    live = LiveStore(redis_url if redis_url is not None else os.environ.get("REDIS_URL"))
    speech_languages = {
        row["code"]: row["speech"]
        for row in json.loads(
            (ROOT / "frontend" / "locales" / "languages.json").read_text(encoding="utf-8")
        )
        if row["status"] != "planned"
    }

    async def cleanup():
        while True:
            await asyncio.sleep(30)
            try:

                def prune():
                    with Session.begin() as db:
                        expired = list(
                            db.scalars(select(Call.id).where(Call.expires < time.time()))
                        )
                        for cid in expired:
                            live.delete("call:" + cid)
                        db.execute(delete(Call).where(Call.expires < time.time()))
                        db.execute(delete(Login).where(Login.expires < time.time()))
                    if not live.redis:
                        with live.mutex:
                            live._prune()

                await run_in_threadpool(prune)
            except Exception:
                await report_error("retention_cleanup_failed")

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(cleanup())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        engine.dispose()

    app = FastAPI(
        title="Catchy AI",
        version="2.0.1",
        lifespan=lifespan,
        docs_url=None if production else "/api/docs",
        openapi_url=None if production else "/api/openapi.json",
    )
    app.state.Session = Session
    app.state.live = live
    app.state.engine = engine
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Catchy-Request"],
    )

    @app.middleware("http")
    async def controls(request, call_next):
        if request.url.path.startswith("/api/") and request.method not in (
            "GET",
            "HEAD",
            "OPTIONS",
        ):
            if (
                request.headers.get("origin") != origin
                or request.headers.get("x-catchy-request") != "1"
            ):
                return JSONResponse({"error": "origin_rejected"}, 403)
            total = 0
            chunks = []
            async for chunk in request.stream():
                total += len(chunk)
                if total > 100000:
                    return JSONResponse({"error": "request_too_large"}, 413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            await report_error("request_failed")
            response = JSONResponse({"error": "service_unavailable"}, 503)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self' ws: wss:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
            }
        )
        response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - started) * 1000:.1f}"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"error": "invalid_input"}, 422)

    @app.exception_handler(HTTPException)
    async def api_error(request, error):
        return JSONResponse({"error": error.detail}, error.status_code)

    def limited(key, n=120, seconds=60):
        if live.limited(key, n, seconds):
            raise HTTPException(429, "rate_limited")

    def authenticate(request, db, *, check_rate=True):
        token = request.cookies.get("catchy_v2", "")
        record = db.get(Login, digest(token)) if token else None
        if not record or record.expires < time.time():
            raise HTTPException(401, "sign_in_required")
        user = db.get(User, record.user_id)
        if not user:
            raise HTTPException(401, "sign_in_required")
        if check_rate:
            limited("user:" + user.id)
        return user

    def user_json(user):
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "verified": user.verified,
        }

    def allowed_language(language):
        if (
            not re.fullmatch(r"[a-z]{2,3}", language)
            or not (SIGNALS / f"{language}.yaml").is_file()
        ):
            raise HTTPException(422, "language_unavailable")

    def call_owned(db, cid, user):
        call = db.get(Call, cid)
        if not call or call.user_id != user.id or call.expires < time.time():
            raise HTTPException(404, "session_not_found")
        return call

    def call_json(call):
        return {
            "id": call.id,
            "title": call.title,
            "language": call.language,
            "mode": call.mode,
            "status": call.status,
            "score": call.score,
            "created": call.created,
            "updated": call.updated,
            "retain": call.retain,
            "count": call.count,
        }

    def invite_json(contact, include_link=False):
        return {
            "id": contact.id,
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone if contact.status == "accepted" else "",
            "status": contact.status,
            "alerts_owner": contact.alerts_owner,
            "alerts_recipient": contact.alerts_recipient,
        }

    @app.get("/api/health")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        if live.redis:
            live.redis.ping()
        return {
            "status": "ok",
            "version": "2.0.1",
            "database": "postgresql"
            if engine.dialect.name == "postgresql"
            else "sqlite-development",
            "memory": "redis" if live.redis else "local-development",
            "asr": bool(os.environ.get("ASR_WS_URL")),
            "alerts": alert_available(),
            "email": mail_available(),
            "llm": provider_config(),
        }

    @app.post("/api/v2/auth/{action}")
    def auth(action: str, data: Credentials, request: Request, response: Response):
        limited(
            "auth:" + digest(request.client.host if request.client else "unknown"),
            20,
            600,
        )
        with live.lock("identity:" + digest(data.email)), Session.begin() as db:
            user = db.scalar(select(User).where(User.email == data.email))
            if action == "register":
                if user:
                    raise HTTPException(409, "email_registered")
                admins = os.environ.get("ADMIN_EMAILS", "").lower().split(",")
                user = User(
                    id=uid(),
                    name=data.name,
                    email=data.email,
                    password=password_hash(data.password),
                    role="admin" if data.email in admins else "user",
                    preferences=dict(DEFAULTS),
                )
                db.add(user)
                db.flush()
            elif action == "login":
                encoded = user.password if user else password_hash("dummy-password")
                if (
                    not hmac.compare_digest(
                        password_hash(data.password, encoded.split(":")[0]), encoded
                    )
                    or not user
                ):
                    raise HTTPException(401, "invalid_credentials")
            else:
                raise HTTPException(404, "not_found")
            token = secrets.token_urlsafe(32)
            db.add(Login(token=digest(token), user_id=user.id, expires=time.time() + 28800))
            response.set_cookie(
                "catchy_v2",
                token,
                max_age=28800,
                httponly=True,
                secure=origin.startswith("https://"),
                samesite="strict",
                path="/",
            )
            return {"user": user_json(user), "preferences": user.preferences}

    def send_reset_code(address, code):
        try:
            send_mail(
                address,
                "Reset your Catchy AI password",
                f"Your password reset code is {code}. It expires in 10 minutes. If you did not request this, ignore it.",
            )
        except Exception:
            # A provider failure never reveals whether an account exists.
            pass

    @app.post("/api/v2/password/request")
    def password_request(data: ResetEmail, request: Request, background: BackgroundTasks):
        limited("reset-ip:" + digest(request.client.host if request.client else "unknown"), 10, 600)
        key = "reset:" + digest(data.email)
        limited(key, 3, 600)
        code = f"{secrets.randbelow(1000000):06d}"
        with live.lock("identity:" + digest(data.email)), Session() as db:
            user = db.scalar(select(User).where(User.email == data.email))
            if user:
                live.set(
                    key,
                    {
                        "user_id": user.id,
                        "hash": digest(code),
                        "credential": digest(user.password),
                        "attempts": 0,
                        "expires": time.time() + 600,
                    },
                    600,
                )
                background.add_task(send_reset_code, user.email, code)
        result = {"accepted": True, "email_configured": mail_available()}
        if not production and os.environ.get("DEV_EMAIL_CODES") == "1":
            # Same response shape for absent accounts; the dummy code cannot authorize a reset.
            result["development_code"] = code
        return result

    @app.post("/api/v2/password/confirm")
    def password_confirm(data: ResetPassword, request: Request, response: Response):
        limited(
            "reset-confirm:" + digest(request.client.host if request.client else "unknown"), 30, 600
        )
        key = "reset:" + digest(data.email)
        with live.lock("identity:" + digest(data.email)):
            record = live.get(key)
            if not record or record["attempts"] >= 5 or record["expires"] <= time.time():
                raise HTTPException(400, "invalid_reset_code")
            record["attempts"] += 1
            live.set(key, record, max(1, int(record["expires"] - time.time())))
            if not hmac.compare_digest(record["hash"], digest(data.code)):
                raise HTTPException(400, "invalid_reset_code")
            with live.lock("account:" + record["user_id"]), Session.begin() as db:
                user = db.get(User, record["user_id"])
                if (
                    not user
                    or user.email != data.email
                    or not hmac.compare_digest(record["credential"], digest(user.password))
                ):
                    raise HTTPException(400, "invalid_reset_code")
                user.password = password_hash(data.password)
                user.verified = True
                db.execute(delete(Login).where(Login.user_id == user.id))
                for call in db.scalars(select(Call).where(Call.user_id == user.id)):
                    live.delete("call:" + call.id)
                    if call.status == "active":
                        call.status = "completed"
                        call.updated = time.time()
                live.delete("verify:" + user.id)
            live.delete(key)
        response.delete_cookie("catchy_v2", path="/")
        return {"reset": True}

    @app.get("/api/v2/me")
    def me(request: Request):
        with Session() as db:
            user = authenticate(request, db)
            return {
                "user": user_json(user),
                "preferences": dict(DEFAULTS) | user.preferences,
            }

    @app.post("/api/v2/logout")
    def logout(request: Request, response: Response):
        with Session.begin() as db:
            user = authenticate(request, db)
            db.execute(delete(Login).where(Login.user_id == user.id))
        response.delete_cookie("catchy_v2", path="/")
        return {"ok": True}

    @app.post("/api/v2/preferences")
    def preferences(data: Preferences, request: Request):
        allowed_language(data.language)
        with Session.begin() as db:
            user = authenticate(request, db)
            user.preferences = data.model_dump()
            # Shorter retention applies to old calls too; never silently extend old expiry.
            for call in db.scalars(select(Call).where(Call.user_id == user.id)):
                call.expires = min(call.expires, call.created + data.retention_days * 86400)
            return user.preferences

    @app.post("/api/v2/verify/request")
    def verify_request(request: Request):
        with Session() as db:
            user = authenticate(request, db)
            limited("verify:" + user.id, 3, 600)
            code = f"{secrets.randbelow(1000000):06d}"
            live.set(
                "verify:" + user.id,
                {"hash": digest(code), "attempts": 0, "expires": time.time() + 600},
                600,
            )
            try:
                sent = send_mail(
                    user.email,
                    "Verify your Catchy AI email",
                    f"Your verification code is {code}. It expires in 10 minutes.",
                )
            except Exception:
                sent = False
            result = {"sent": sent}
            if not production and os.environ.get("DEV_EMAIL_CODES") == "1":
                result["development_code"] = code
            elif not sent:
                raise HTTPException(503, "email_not_configured")
            return result

    @app.post("/api/v2/verify/confirm")
    def verify_confirm(data: Code, request: Request):
        with Session.begin() as db:
            user = authenticate(request, db)
            with live.lock("verify:" + user.id):
                record = live.get("verify:" + user.id)
                if not record or record["attempts"] >= 5 or record["expires"] < time.time():
                    raise HTTPException(400, "invalid_code")
                record["attempts"] += 1
                live.set(
                    "verify:" + user.id,
                    record,
                    max(1, int(record["expires"] - time.time())),
                )
                if not hmac.compare_digest(record["hash"], digest(data.code)):
                    raise HTTPException(400, "invalid_code")
                live.delete("verify:" + user.id)
                user.verified = True
            return {"verified": True}

    @app.post("/api/v2/guest/analyze")
    def guest(data: Guest, request: Request):
        if not data.consent:
            raise HTTPException(422, "consent_required")
        allowed_language(data.language)
        limited("guest:" + digest(request.client.host if request.client else "unknown"), 60)
        # Guests have no authenticated provider consent. Never send their text to a model.
        result = analyze([redact(t) for t in data.turns], data.language)
        result["model_status"] = "rules"
        return result

    @app.get("/api/v2/calls")
    def calls(request: Request):
        with Session() as db:
            user = authenticate(request, db)
            return {
                "calls": [
                    call_json(c)
                    for c in db.scalars(
                        select(Call)
                        .where(Call.user_id == user.id, Call.expires > time.time())
                        .order_by(Call.created.desc())
                        .limit(200)
                    )
                ]
            }

    @app.post("/api/v2/calls", status_code=201)
    def new_call(data: NewCall, request: Request):
        if not data.consent:
            raise HTTPException(422, "consent_required")
        allowed_language(data.language)
        with Session() as db:
            owner_id = authenticate(request, db).id
        with live.lock("account:" + owner_id), Session.begin() as db:
            user = authenticate(request, db)
            prefs = dict(DEFAULTS) | user.preferences
            call = Call(
                id=uid(),
                user_id=user.id,
                title=data.title,
                language=data.language,
                mode=data.mode,
                retain=prefs["retain_transcript"],
                expires=time.time() + prefs["retention_days"] * 86400,
            )
            db.add(call)
            db.flush()
            live.set("call:" + call.id, {"turns": [], "requests": {}})
            return call_json(call)

    @app.get("/api/v2/calls/{cid}")
    def details(cid: str, request: Request):
        with Session() as db:
            user = authenticate(request, db)
            call = call_owned(db, cid, user)
            return {
                "call": call_json(call),
                "turns": call.transcript,
                "evidence": call.evidence,
            }

    def process_turn(cid, data, user_id):
        with live.lock("account:" + user_id), live.lock(cid), Session.begin() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(401, "sign_in_required")
            call = call_owned(db, cid, user)
            if call.status != "active":
                raise HTTPException(409, "session_ended")
            memory = live.get("call:" + cid)
            if memory is None:
                raise HTTPException(409, "context_expired")
            if data.request_id in memory["requests"]:
                return memory["requests"][data.request_id]
            if len(memory["turns"]) >= 60:
                raise HTTPException(422, "session_limit")
            turns = memory["turns"] + [redact(data.text)]
            start = time.perf_counter()
            result = classify(turns, call.language)
            result["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            result["turn"] = len(turns)
            result["request_id"] = data.request_id
            result["alert_new"] = result["level"] == "high" and not call.warned
            if result["alert_new"]:
                call.warned = True
            call.count = len(turns)
            call.score = result["score"]
            call.updated = time.time()
            if call.retain:
                call.transcript = list(call.transcript) + [
                    {
                        "text": redact(data.text),
                        "time": time.time(),
                        "level": result["level"],
                        "score": result["score"],
                    }
                ]
                call.evidence = result["signals"]
            memory["turns"] = turns
            memory["requests"][data.request_id] = result
            live.set("call:" + cid, memory)
            return result

    @app.post("/api/v2/calls/{cid}/turns")
    def turn(cid: str, data: Turn, request: Request):
        with Session() as db:
            user = authenticate(request, db)
            user_id = user.id
        return process_turn(cid, data, user_id)

    @app.post("/api/v2/calls/{cid}/finish")
    def finish(cid: str, request: Request):
        with live.lock(cid), Session.begin() as db:
            user = authenticate(request, db)
            call = call_owned(db, cid, user)
            if call.status == "active":
                call.status = "completed"
                call.updated = time.time()
            live.delete("call:" + cid)
            return {"ok": True}

    @app.post("/api/v2/calls/{cid}/withdraw")
    def withdraw(cid: str, request: Request):
        with Session() as db:
            owner_id = authenticate(request, db).id
        # Serialize with turns: once acknowledged, no further turn can begin processing.
        with live.lock("account:" + owner_id), live.lock(cid), Session.begin() as db:
            user = authenticate(request, db)
            call = call_owned(db, cid, user)
            if call.status != "withdrawn":
                call.status = "withdrawn"
                call.updated = time.time()
            live.delete("call:" + cid)
            return {"ok": True, "status": "withdrawn"}

    @app.delete("/api/v2/calls/{cid}")
    def delete_call(cid: str, request: Request):
        with live.lock(cid), Session.begin() as db:
            user = authenticate(request, db)
            call = call_owned(db, cid, user)
            db.delete(call)
            live.delete("call:" + cid)
            return {"ok": True}

    @app.websocket("/api/v2/live/{cid}")
    async def live_socket(socket: WebSocket, cid: str):
        if socket.headers.get("origin") != origin:
            await socket.close(code=1008)
            return
        try:
            with Session() as db:
                user = authenticate(socket, db)
                call_owned(db, cid, user)
                user_id = user.id
        except HTTPException:
            await socket.close(code=1008)
            return
        await socket.accept()
        try:
            while True:
                raw = await asyncio.wait_for(socket.receive_text(), timeout=120)
                if len(raw) > 5000:
                    await socket.send_json({"error": "request_too_large"})
                    continue
                try:
                    limited("ws:" + user_id, 60)
                    # Recheck authorization after logout/account deletion on every message.
                    with Session() as db:
                        authenticate(socket, db)
                    data = Turn.model_validate_json(raw)
                    result = await run_in_threadpool(process_turn, cid, data, user_id)
                    await socket.send_json(result)
                except HTTPException as error:
                    await socket.send_json({"error": error.detail})
                except ValueError:
                    await socket.send_json({"error": "invalid_input"})
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass
        except Exception:
            await report_error("live_channel_failed")
            try:
                await socket.send_json({"error": "service_unavailable"})
            except Exception:
                pass

    @app.get("/api/v2/contacts")
    def contacts(request: Request):
        with Session() as db:
            user = authenticate(request, db)
            outgoing = [
                invite_json(c) for c in db.scalars(select(Contact).where(Contact.owner == user.id))
            ]
            incoming = [
                invite_json(c) | {"owner_name": db.get(User, c.owner).name}
                for c in db.scalars(
                    select(Contact).where(
                        Contact.recipient == user.id, Contact.status == "accepted"
                    )
                )
            ]
            return {"contacts": outgoing, "incoming": incoming}

    @app.post("/api/v2/contacts", status_code=201)
    def invite(data: Invitation, request: Request):
        with Session.begin() as db:
            user = authenticate(request, db)
            if not user.verified:
                raise HTTPException(403, "verify_email_required")
            if data.email == user.email:
                raise HTTPException(422, "cannot_invite_self")
            limited("invite:" + user.id, 5, 3600)
            if (
                db.scalar(select(func.count()).select_from(Contact).where(Contact.owner == user.id))
                >= 5
            ):
                raise HTTPException(422, "contact_limit")
            if db.scalar(
                select(Contact).where(Contact.owner == user.id, Contact.email == data.email)
            ):
                raise HTTPException(409, "contact_exists")
            token = secrets.token_urlsafe(32)
            contact = Contact(
                id=uid(),
                owner=user.id,
                name=data.name,
                email=data.email,
                token=digest(token),
                expires=time.time() + 7 * 86400,
            )
            db.add(contact)
            db.flush()
            return {
                "contact": invite_json(contact),
                "invitation_url": origin + "/#invite=" + token,
                "sent": False,
            }

    @app.post("/api/v2/contacts/accept")
    def accept(data: Accept, request: Request):
        with live.lock("invite:" + digest(data.token)), Session.begin() as db:
            user = authenticate(request, db)
            if not user.verified:
                raise HTTPException(403, "verify_email_required")
            contact = db.scalar(select(Contact).where(Contact.token == digest(data.token)))
            if (
                not contact
                or contact.status != "pending"
                or contact.email != user.email
                or contact.expires < time.time()
            ):
                raise HTTPException(404, "invalid_invitation")
            contact.recipient = user.id
            contact.status = "accepted"
            contact.phone = data.phone
            contact.alerts_recipient = data.alerts
            if user.role == "user":
                user.role = "trusted_contact"
            return {"ok": True}

    @app.post("/api/v2/contacts/{contact_id}/alerts")
    def contact_toggle(contact_id: str, data: Toggle, request: Request):
        with Session.begin() as db:
            user = authenticate(request, db)
            contact = db.get(Contact, contact_id)
            if not contact or user.id not in (contact.owner, contact.recipient):
                raise HTTPException(404, "not_found")
            if contact.status != "accepted":
                raise HTTPException(409, "acceptance_required")
            if user.id == contact.owner:
                contact.alerts_owner = data.enabled
            else:
                contact.alerts_recipient = data.enabled
            return invite_json(contact)

    @app.delete("/api/v2/contacts/{contact_id}")
    def remove_contact(contact_id: str, request: Request):
        with Session.begin() as db:
            user = authenticate(request, db)
            contact = db.get(Contact, contact_id)
            if not contact or user.id not in (contact.owner, contact.recipient):
                raise HTTPException(404, "not_found")
            db.delete(contact)
            return {"ok": True}

    @app.post("/api/v2/contacts/{contact_id}/notify")
    def notify(contact_id: str, data: AlertRequest, request: Request):
        with live.lock("alert:" + contact_id), Session.begin() as db:
            user = authenticate(request, db)
            contact = db.get(Contact, contact_id)
            if not contact or contact.owner != user.id:
                raise HTTPException(404, "not_found")
            if (
                not user.verified
                or contact.status != "accepted"
                or not contact.alerts_owner
                or not contact.alerts_recipient
            ):
                raise HTTPException(403, "alert_consent_required")
            if not user.preferences.get("alert_opt_in", False):
                raise HTTPException(403, "alert_consent_required")
            if not alert_available():
                raise HTTPException(503, "delivery_not_configured")
            language = user.preferences.get("language", "en")
            risk = "TEST"
            if not data.test:
                if not data.call_id:
                    raise HTTPException(422, "session_required")
                call = call_owned(db, data.call_id, user)
                if call.score < 60:
                    raise HTTPException(409, "high_risk_required")
                language = call.language
                risk = "HIGH"
            if live.get("alert:" + contact_id):
                raise HTTPException(429, "alert_cooldown")
            live.set("alert:" + contact_id, True, 300)
            metadata = {
                "risk": risk,
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "language": language,
            }
            try:
                sent = deliver_alert(contact, metadata)
            except Exception:
                sent = False
            db.add(
                Delivery(
                    id=uid(),
                    owner=user.id,
                    contact=contact.id,
                    status="provider_accepted" if sent else "uncertain",
                )
            )
            return {
                "status": "provider_accepted" if sent else "uncertain",
                "delivered": False,
            }

    @app.delete("/api/v2/account")
    def delete_account(request: Request, response: Response):
        with Session() as db:
            owner = authenticate(request, db)
            owner_id, owner_email = owner.id, owner.email
        with (
            live.lock("identity:" + digest(owner_email)),
            live.lock("account:" + owner_id),
            Session.begin() as db,
        ):
            user = authenticate(request, db)
            for call in db.scalars(select(Call).where(Call.user_id == user.id)):
                live.delete("call:" + call.id)
            live.delete("verify:" + user.id)
            live.delete("reset:" + digest(user.email))
            db.delete(user)
        response.delete_cookie("catchy_v2", path="/")
        return {"ok": True}

    @app.post("/api/v2/analytics")
    def analytics(data: Analytics, request: Request):
        if not data.consent:
            return {"recorded": False}
        limited(
            "analytics:" + digest(request.client.host if request.client else "unknown"),
            30,
        )
        key = time.strftime("%Y-%m-%d", time.gmtime()) + ":" + data.event
        with live.lock("analytics"), Session.begin() as db:
            row = db.get(Counter, key)
            if row:
                row.count += 1
            else:
                db.add(Counter(key=key, count=1))
        return {"recorded": True}

    @app.get("/api/v2/evaluation")
    def evaluation(request: Request):
        with Session() as db:
            user = authenticate(request, db)
            if user.role != "admin" or not user.verified:
                raise HTTPException(403, "admin_required")
        path = ROOT / "evaluation" / "multilingual-results.json"
        return (
            json.loads(path.read_text())
            if path.exists()
            else {"languages": [], "status": "not_run"}
        )

    @app.post("/api/v2/evaluation")
    def run_evaluation(request: Request):
        with Session() as db:
            user = authenticate(request, db)
            if user.role != "admin" or not user.verified:
                raise HTTPException(403, "admin_required")
            limited("evaluation:" + user.id, 2, 60)
        from evaluation.multilingual import evaluate

        return evaluate(write=False)

    @app.get("/api/metrics")
    def metrics(request: Request):
        token = os.environ.get("METRICS_TOKEN", "")
        if not token or not hmac.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + token
        ):
            raise HTTPException(403, "forbidden")
        with Session() as db:
            users = db.scalar(select(func.count()).select_from(User))
            calls_count = db.scalar(select(func.count()).select_from(Call))
        return PlainTextResponse(
            f"catchy_users_total {users}\ncatchy_sessions_total {calls_count}\n"
        )

    @app.websocket("/api/v2/asr")
    async def asr(socket: WebSocket):
        if socket.headers.get("origin") != origin:
            await socket.close(1008)
            return
        cid = socket.query_params.get("call_id", "")
        language = socket.query_params.get("language", "")

        def authorized(*, initial=False):
            if not cid or len(cid) > 40:
                raise HTTPException(422, "session_required")
            with Session() as db:
                # Audio is bounded separately; chunks must not consume the HTTP quota.
                user = authenticate(socket, db, check_rate=initial)
                call = call_owned(db, cid, user)
                if call.status != "active" or call.mode != "speaker":
                    raise HTTPException(409, "session_ended")
                if live.get("call:" + cid) is None:
                    raise HTTPException(409, "context_expired")
                if not language or speech_languages.get(call.language) != language:
                    raise HTTPException(422, "language_unavailable")

        try:
            await run_in_threadpool(authorized, initial=True)
        except HTTPException:
            await socket.close(1008)
            return
        await socket.accept()
        url = os.environ.get("ASR_WS_URL")
        if not url:
            await socket.send_json({"error": "asrUnavailable"})
            await socket.close()
            return
        try:
            import websockets

            # Acceptance can yield; recheck before opening the upstream service.
            await run_in_threadpool(authorized)
            async with websockets.connect(
                url,
                max_size=1000000,
                open_timeout=5,
                additional_headers={
                    "Authorization": "Bearer " + os.environ.get("ASR_SERVICE_TOKEN", "")
                },
            ) as upstream:
                await run_in_threadpool(authorized)
                await upstream.send(json.dumps({"language": language}))

                async def upload():
                    total = 0
                    start = time.monotonic()
                    while True:
                        chunk = await asyncio.wait_for(socket.receive_bytes(), timeout=15)
                        total += len(chunk)
                        if len(chunk) > 200000 or total > 5000000 or time.monotonic() - start > 300:
                            raise ValueError("stream_limit")
                        await run_in_threadpool(authorized)
                        await upstream.send(chunk)

                async def receive():
                    async for message in upstream:
                        data = json.loads(message)
                        await run_in_threadpool(authorized)
                        if isinstance(data.get("text"), str) and len(data["text"]) <= 1500:
                            await socket.send_json({"text": redact(data["text"])})
                        elif data.get("error"):
                            await socket.send_json({"error": "speechError"})

                async def watch_authorization():
                    # Also close an idle stream after logout, expiry, or withdrawal.
                    deadline = time.monotonic() + 300
                    while time.monotonic() < deadline:
                        await asyncio.sleep(1)
                        await run_in_threadpool(authorized)
                    raise asyncio.TimeoutError()

                tasks = [
                    asyncio.create_task(upload()),
                    asyncio.create_task(receive()),
                    asyncio.create_task(watch_authorization()),
                ]
                try:
                    done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        except HTTPException:
            await socket.close(1008)
            return
        except WebSocketDisconnect:
            return
        except Exception:
            try:
                await socket.send_json({"error": "speechError"})
            except Exception:
                pass
        try:
            await socket.close()
        except RuntimeError:
            pass

    @app.get("/")
    @app.get("/index.html")
    @app.get("/phone.html")
    @app.get("/dashboard")
    def index():
        return FileResponse(ROOT / "frontend" / "phone.html")

    @app.get("/{path:path}")
    def static(path: str):
        # Resolve against the public frontend directory only; never expose project source or data.
        base = (ROOT / "frontend").resolve()
        target = (base / path).resolve()
        if (
            base not in target.parents
            or not target.is_file()
            or target.suffix
            not in {
                ".js",
                ".css",
                ".html",
                ".json",
                ".svg",
                ".png",
                ".webmanifest",
                ".woff2",
                ".ttf",
                ".webp",
            }
        ):
            raise HTTPException(404, "not_found")
        return FileResponse(
            target,
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"}
            if path == "sw.js"
            else {},
        )

    return app


app = create_app()
