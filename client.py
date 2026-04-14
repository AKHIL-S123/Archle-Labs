"""
client_example.py — Demo client for the WebSocket chat server.

Demonstrates:
  - Joining a topic room
  - Sending and receiving messages concurrently
  - Using the /list command
"""

import asyncio
import json

import websockets

SERVER_URI = "ws://localhost:8000/ws"


async def chat_client(username: str, topic: str, outgoing: list[str], delay: float = 0.0) -> None:
    """
    Connect to the chat server, join a topic, send a sequence of messages,
    and print every incoming message until done.

    :param username:  Desired username (server may append #N if taken).
    :param topic:     Topic room to join.
    :param outgoing:  List of message strings to send (use "/list" for the command).
    :param delay:     Seconds to wait before sending the first message.
    """
    async with websockets.connect(SERVER_URI) as ws:
        # ── Handshake ──────────────────────────────────────────────────────
        await ws.send(json.dumps({"username": username, "topic": topic}))
        ack = json.loads(await ws.recv())
        assigned_name = ack.get("username", username)
        print(f"[{assigned_name}] Joined topic '{ack.get('topic')}' as '{assigned_name}'")

        # ── Concurrent receiver ────────────────────────────────────────────
        async def receive_loop() -> None:
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    event = msg.get("event")

                    if event == "topic_list":
                        print(f"\n[{assigned_name}] /list response:\n{msg['data']}\n")
                    elif event == "user_joined":
                        print(f"[{assigned_name}] -- '{msg['username']}' joined the room --")
                    elif event == "delivered":
                        print(f"[{assigned_name}] ✓ Delivered: {msg['message']!r}")
                    elif "username" in msg and "message" in msg:
                        print(f"[{assigned_name}] {msg['username']}: {msg['message']}")
                    elif "error" in msg:
                        print(f"[{assigned_name}] ERROR: {msg['error']}")
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                pass

        recv_task = asyncio.create_task(receive_loop())

        # ── Send messages ──────────────────────────────────────────────────
        await asyncio.sleep(delay)  # stagger so users don't speak simultaneously
        for text in outgoing:
            await asyncio.sleep(0.8)
            await ws.send(json.dumps({"message": text}))

        await asyncio.sleep(2)  # let final responses arrive
        recv_task.cancel()
        await asyncio.gather(recv_task, return_exceptions=True)

    print(f"[{assigned_name}] Disconnected.")


async def main() -> None:
    print("=" * 60)
    print("  WebSocket Chat Demo")
    print("=" * 60)

    # Run two users concurrently in the same topic
    await asyncio.gather(
        chat_client(
            username="alice",
            topic="sports",
            outgoing=["Hello everyone!", "/list", "Anyone watching the game?"],
            delay=0.0,
        ),
        chat_client(
            username="bob",
            topic="sports",
            outgoing=["Hi Alice!", "Yes, great match!", "/list"],
            delay=0.3,
        ),
    )

    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
