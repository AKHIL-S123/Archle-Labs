import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Dict, List


from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# topic -> {username -> WebSocket}
topics: Dict[str, Dict[str, WebSocket]] = {}

# topic -> list of in-memory messages (cleared on expiry)
messages: Dict[str, List[dict]] = defaultdict(list)


def get_unique_username(topic: str, requested: str) -> str:
    """Return username, appending #N suffix if already taken in the topic."""
    print("topic", "-" * 60 ,topics)

    existing = topics.get(topic, {})
    if requested not in existing:
        return requested
    counter = 2
    while f"{requested}#{counter}" in existing:
        counter += 1
    return f"{requested}#{counter}"


async def expire_message(topic: str, msg: dict) -> None:
    """Remove a message from the in-memory store after 30 seconds."""
    await asyncio.sleep(30)
    bucket = messages.get(topic)
    if bucket and msg in bucket:
        bucket.remove(msg)
        logger.info("Message expired in topic '%s': %.40s", topic, msg.get("message", ""))


async def broadcast(topic: str, payload: dict, exclude: str | None = None) -> None:
    """Send payload to all users in the topic except the excluded username."""
    if topic not in topics:
        return
    dead: List[str] = []
    for uname, ws in list(topics[topic].items()):
        if uname == exclude:
            continue
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(uname)
    for uname in dead:
        topics[topic].pop(uname, None)


def build_topic_list() -> str:
    lines = ["Active Topics:"]
    for t, users in topics.items():
        count = len(users)
        lines.append(f"  {t} ({count} user{'s' if count != 1 else ''})")
    return "\n".join(lines)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    username: str | None = None
    topic: str | None = None

    try:
        # ── Step 1: handshake ──────────────────────────────────────────────
        raw = await websocket.receive_text()
        try:
            init = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"error": "Invalid JSON in handshake"})
            await websocket.close(code=1003)
            return

        username = str(init.get("username", "")).strip()
        topic = str(init.get("topic", "")).strip()

        if not username or not topic:
            await websocket.send_json({"error": "'username' and 'topic' are required"})
            await websocket.close(code=1003)
            return

        # ── Step 2: register user ─────────────────────────────────────────
        if topic not in topics:
            topics[topic] = {}

        username = get_unique_username(topic, username)
        topics[topic][username] = websocket

        logger.info("'%s' joined topic '%s'", username, topic)

        await websocket.send_json({"event": "joined", "username": username, "topic": topic})
        await broadcast(topic, {"event": "user_joined", "username": username}, exclude=username)

        # ── Step 3: message loop ──────────────────────────────────────────
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON payload"})
                continue

            msg_text = str(data.get("message", "")).strip()
            if not msg_text:
                await websocket.send_json({"error": "'message' field is required"})
                continue

            # /list command – respond only to sender
            if msg_text == "/list":
                await websocket.send_json({"event": "topic_list", "data": build_topic_list()})
                continue

            # Normal message
            msg: dict = {
                "username": username,
                "message": msg_text,
                "timestamp": int(time.time()),
            }

            messages[topic].append(msg)
            asyncio.create_task(expire_message(topic, msg))

            await broadcast(topic, msg, exclude=username)
            await websocket.send_json(
                {"event": "delivered", "message": msg_text, "timestamp": msg["timestamp"]}
            )

    except WebSocketDisconnect:
        logger.info("'%s' disconnected from topic '%s'", username, topic)
    except Exception as exc:
        logger.error("Unexpected error for '%s' in '%s': %s", username, topic, exc)
    finally:
        if topic and username:
            topics.get(topic, {}).pop(username, None)
            if topic in topics and not topics[topic]:
                del topics[topic]
                messages.pop(topic, None)
                logger.info("Topic '%s' removed (empty)", topic)

