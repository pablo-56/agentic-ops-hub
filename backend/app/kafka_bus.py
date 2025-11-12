# backend/app/kafka_bus.py
import asyncio
import json
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaProducer
from .config import settings
from .events_cache import EVENTS
from .routers.streaming import manager

_producer: Optional[AIOKafkaProducer] = None
_started = False

async def start_kafka() -> None:
    """Start a shared aiokafka producer (best-effort; app still works if Kafka is down)."""
    global _producer, _started
    if _started:
        return
    try:
        _producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP)
        await _producer.start()
        _started = True
        print("[kafka] producer started")
    except Exception as e:
        _producer = None
        _started = False
        print(f"[kafka] WARN: producer not started ({e}); will use local cache only")

async def stop_kafka() -> None:
    global _producer, _started
    if _producer:
        try:
            await _producer.stop()
        except Exception:
            pass
    _producer = None
    _started = False
    print("[kafka] producer stopped")

async def safe_publish(topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Publish to Kafka if available; always mirror to in-memory cache + WS."""
    # 1) Mirror to local cache immediately (fast read path for /events/*)
    rec = EVENTS.add(topic, payload)

    # 2) Broadcast to live WS clients
    await manager.broadcast_json({"topic": topic, "ts": rec.ts.isoformat(), "payload": payload})

    # 3) Try to send to Kafka (best-effort)
    if _producer:
        try:
            data = json.dumps(payload).encode("utf-8")
            await _producer.send_and_wait(topic, data)
        except Exception as e:
            print(f"[kafka] WARN publish failed ({topic}): {e}")
    return {"topic": topic, "payload": payload, "ts": rec.ts.isoformat()}
