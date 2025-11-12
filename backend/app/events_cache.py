# backend/app/events_cache.py
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Deque, Dict, List, Optional

from .settings import settings

@dataclass
class EventRecord:
    ts: datetime
    topic: str
    payload: Dict[str, Any]

class EventsCache:
    """Ring buffer cache to keep recent events for quick queries & timelines."""
    def __init__(self, maxlen: int = 5000):
        self._buf: Deque[EventRecord] = deque(maxlen=maxlen)
        self._lock = RLock()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def add(self, topic: str, payload: Dict[str, Any]) -> EventRecord:
        rec = EventRecord(ts=self._now(), topic=topic, payload=payload)
        with self._lock:
            self._buf.append(rec)
        return rec

    def _parse_window(self, window: str) -> timedelta:
        if not window:
            return timedelta(minutes=15)
        w = window.strip().lower()
        if w.endswith("ms"):
            return timedelta(milliseconds=int(w[:-2]))
        if w.endswith("s"):
            return timedelta(seconds=int(w[:-1]))
        if w.endswith("m"):
            return timedelta(minutes=int(w[:-1]))
        if w.endswith("h"):
            return timedelta(hours=int(w[:-1]))
        if w.endswith("d"):
            return timedelta(days=int(w[:-1]))
        # default minutes
        try:
            return timedelta(minutes=int(w))
        except Exception:
            return timedelta(minutes=15)

    def query_recent(
        self,
        entity_type: Optional[str],
        entity_id: Optional[str],
        window: str,
    ) -> List[Dict[str, Any]]:
        """Return recent events filtered by entity refs and time window."""
        horizon = self._now() - self._parse_window(window)
        out: List[Dict[str, Any]] = []
        with self._lock:
            for rec in reversed(self._buf):
                if rec.ts < horizon:
                    break
                p = rec.payload
                if entity_type and (p.get("entity_type") != entity_type):
                    continue
                if entity_id and (p.get("entity_id") != entity_id):
                    continue
                item = {
                    "ts": rec.ts.isoformat(),
                    "topic": rec.topic,
                    "payload": p,
                }
                out.append(item)
        return out

    def timeline(
        self,
        incident_id: Optional[str],
        entity_type: Optional[str],
        entity_id: Optional[str],
        window: str,
    ) -> List[Dict[str, Any]]:
        """Merge across topics for a time-ordered incident/entity story."""
        events = self.query_recent(entity_type, entity_id, window)
        if incident_id:
            events = [e for e in events if e["payload"].get("incident_id") == incident_id]
        # Already time-ordered newest→oldest from query_recent; reverse to oldest→newest
        return list(reversed(events))

    def active_alerts(
        self,
        entity_type: Optional[str],
        entity_id: Optional[str],
        severity: Optional[str],
        window: str,
    ) -> List[Dict[str, Any]]:
        horizon = self._now() - self._parse_window(window)
        out: List[Dict[str, Any]] = []
        with self._lock:
            for rec in reversed(self._buf):
                if rec.ts < horizon:
                    break
                if rec.topic != "monitoring.alerts":
                    continue
                p = rec.payload
                if entity_type and p.get("entity_type") != entity_type:
                    continue
                if entity_id and p.get("entity_id") != entity_id:
                    continue
                if severity and p.get("severity") != severity:
                    continue
                if p.get("status", "firing") != "firing":
                    continue
                out.append({"ts": rec.ts.isoformat(), "topic": rec.topic, "payload": p})
        return out

EVENTS = EventsCache(maxlen=settings.EVENTS_CACHE_MAX)

@dataclass
class EventRecord:
    ts: datetime
    topic: str
    payload: Dict[str, Any]

class EventsCache:
    """Ring buffer cache to keep recent events for quick queries & timelines."""
    def __init__(self, maxlen: int = 5000):
        self._buf: Deque[EventRecord] = deque(maxlen=maxlen)
        self._lock = RLock()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def add(self, topic: str, payload: Dict[str, Any]) -> EventRecord:
        rec = EventRecord(ts=self._now(), topic=topic, payload=payload)
        with self._lock:
            self._buf.append(rec)
        return rec

    def _parse_window(self, window: str) -> timedelta:
        if not window:
            return timedelta(minutes=15)
        w = window.strip().lower()
        if w.endswith("ms"):
            return timedelta(milliseconds=int(w[:-2]))
        if w.endswith("s"):
            return timedelta(seconds=int(w[:-1]))
        if w.endswith("m"):
            return timedelta(minutes=int(w[:-1]))
        if w.endswith("h"):
            return timedelta(hours=int(w[:-1]))
        if w.endswith("d"):
            return timedelta(days=int(w[:-1]))
        # default minutes
        try:
            return timedelta(minutes=int(w))
        except Exception:
            return timedelta(minutes=15)

    def query_recent(
        self,
        entity_type: Optional[str],
        entity_id: Optional[str],
        window: str,
    ) -> List[Dict[str, Any]]:
        """Return recent events filtered by entity refs and time window."""
        horizon = self._now() - self._parse_window(window)
        out: List[Dict[str, Any]] = []
        with self._lock:
            for rec in reversed(self._buf):
                if rec.ts < horizon:
                    break
                p = rec.payload
                if entity_type and (p.get("entity_type") != entity_type):
                    continue
                if entity_id and (p.get("entity_id") != entity_id):
                    continue
                item = {
                    "ts": rec.ts.isoformat(),
                    "topic": rec.topic,
                    "payload": p,
                }
                out.append(item)
        return out

    def timeline(
        self,
        incident_id: Optional[str],
        entity_type: Optional[str],
        entity_id: Optional[str],
        window: str,
    ) -> List[Dict[str, Any]]:
        """Merge across topics for a time-ordered incident/entity story."""
        events = self.query_recent(entity_type, entity_id, window)
        if incident_id:
            events = [e for e in events if e["payload"].get("incident_id") == incident_id]
        # Already time-ordered newest→oldest from query_recent; reverse to oldest→newest
        return list(reversed(events))

    def active_alerts(
        self,
        entity_type: Optional[str],
        entity_id: Optional[str],
        severity: Optional[str],
        window: str,
    ) -> List[Dict[str, Any]]:
        horizon = self._now() - self._parse_window(window)
        out: List[Dict[str, Any]] = []
        with self._lock:
            for rec in reversed(self._buf):
                if rec.ts < horizon:
                    break
                if rec.topic != "monitoring.alerts":
                    continue
                p = rec.payload
                if entity_type and p.get("entity_type") != entity_type:
                    continue
                if entity_id and p.get("entity_id") != entity_id:
                    continue
                if severity and p.get("severity") != severity:
                    continue
                if p.get("status", "firing") != "firing":
                    continue
                out.append({"ts": rec.ts.isoformat(), "topic": rec.topic, "payload": p})
        return out

EVENTS = EventsCache(maxlen=settings.EVENTS_CACHE_MAX)
