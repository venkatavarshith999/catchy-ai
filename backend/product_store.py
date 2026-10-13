"""Product persistence. SQLite for local use, PostgreSQL for deployment."""

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
Base = declarative_base()


class User(Base):
    __tablename__ = "product_users"
    id = Column(String(40), primary_key=True)
    name = Column(String(80), nullable=False)
    email = Column(String(254), unique=True, nullable=False, index=True)
    password = Column(String(256), nullable=False)
    role = Column(String(24), default="user", nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    created = Column(Float, default=time.time, nullable=False)
    preferences = Column(JSON, default=dict, nullable=False)


class Login(Base):
    __tablename__ = "product_logins"
    token = Column(String(64), primary_key=True)
    user_id = Column(
        String(40),
        ForeignKey("product_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    expires = Column(Float, nullable=False)


class Call(Base):
    __tablename__ = "product_calls"
    id = Column(String(40), primary_key=True)
    user_id = Column(
        String(40),
        ForeignKey("product_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title = Column(String(100), nullable=False)
    language = Column(String(12), nullable=False)
    mode = Column(String(20), nullable=False)
    status = Column(String(20), default="active", nullable=False)
    score = Column(Integer, default=0, nullable=False)
    created = Column(Float, default=time.time, nullable=False, index=True)
    updated = Column(Float, default=time.time, nullable=False)
    retain = Column(Boolean, default=False, nullable=False)
    expires = Column(Float, nullable=False, index=True)
    count = Column(Integer, default=0, nullable=False)
    transcript = Column(JSON, default=list, nullable=False)
    evidence = Column(JSON, default=list, nullable=False)
    warned = Column(Boolean, default=False, nullable=False)


class Contact(Base):
    __tablename__ = "product_contacts"
    id = Column(String(40), primary_key=True)
    owner = Column(
        String(40),
        ForeignKey("product_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    recipient = Column(
        String(40),
        ForeignKey("product_users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(80), nullable=False)
    email = Column(String(254), nullable=False)
    phone = Column(String(25), default="", nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    expires = Column(Float, nullable=False)
    alerts_owner = Column(Boolean, default=False, nullable=False)
    alerts_recipient = Column(Boolean, default=False, nullable=False)


class Delivery(Base):
    __tablename__ = "product_deliveries"
    id = Column(String(40), primary_key=True)
    owner = Column(
        String(40),
        ForeignKey("product_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    contact = Column(
        String(40),
        ForeignKey("product_contacts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created = Column(Float, default=time.time, nullable=False)
    status = Column(String(24), nullable=False)


class Counter(Base):
    __tablename__ = "product_counters"
    key = Column(String(80), primary_key=True)
    count = Column(Integer, default=0, nullable=False)


class LiveStore:
    def __init__(self, url=None):
        self.redis = None
        if url:
            import redis

            self.redis = redis.Redis.from_url(
                url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3
            )
            self.redis.ping()
        self.local = {}
        self.mutex = threading.RLock()
        self.locks = [threading.RLock() for _ in range(128)]

    def get(self, key):
        if self.redis:
            raw = self.redis.get("catchy:" + key)
            return json.loads(raw) if raw else None
        with self.mutex:
            self._prune()
            value = self.local.get(key)
            return value[1] if value else None

    def _prune(self):
        now = time.time()
        for key in list(self.local):
            if self.local[key][0] <= now:
                self.local.pop(key, None)

    def set(self, key, value, ttl=1800):
        if self.redis:
            self.redis.setex("catchy:" + key, ttl, json.dumps(value))
            return
        with self.mutex:
            self._prune()
            if len(self.local) >= 5000 and key not in self.local:
                raise RuntimeError("capacity")
            self.local[key] = (time.time() + ttl, value)

    def delete(self, key):
        if self.redis:
            self.redis.delete("catchy:" + key)
            return
        with self.mutex:
            self.local.pop(key, None)

    def limited(self, key, maximum, seconds=60):
        key = "rate:" + key
        if self.redis:
            script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"
            return self.redis.eval(script, 1, "catchy:" + key, seconds) > maximum
        with self.mutex:
            current = self.get(key) or 0
            if current == 0:
                self.set(key, 1, seconds)
            else:
                self.local[key] = (self.local[key][0], current + 1)
            return current + 1 > maximum

    @contextmanager
    def lock(self, key):
        if self.redis:
            with self.redis.lock("catchy:lock:" + key, timeout=30, blocking_timeout=5):
                yield
        else:
            with self.locks[hash(key) % len(self.locks)]:
                yield


def setup(url=None):
    url = url or os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + str(ROOT / "data" / "product.db").replace("\\", "/"),
    )
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    (ROOT / "data").mkdir(exist_ok=True)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def pragma(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
