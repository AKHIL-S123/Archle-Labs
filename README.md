# Real-Time WebSocket Chat Server

FastAPI WebSocket chat server with topic-based rooms, message expiry, and live user listing.

---

## Requirements

- Python 3.11.9
- pip

---

## Setup

```bash
# 1. Create and activate a virtual environment (optional but recommended)
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Running the Server

```bash
python main.py
```

The server starts at `ws://localhost:8000/ws`.

---

## Running the Demo Client

In a **second terminal** (with the venv activated):

```bash
python client.py
```

This connects two users (`alice` and `bob`) to the `sports` topic, exchanges messages, and calls `/list`.

---

## WebSocket Protocol

### 1. Connect & Handshake

Send a JSON object immediately after connecting:

```json
{"username": "alice", "topic": "sports"}
```

Server responds with:

```json
{"event": "joined", "username": "alice", "topic": "sports"}
```

> If `alice` is already taken in the topic, the server assigns `alice#2`, etc.

### 2. Send a Message

```json
{"message": "Hello World"}
```

Other users in the same topic receive:

```json
{"username": "alice", "message": "Hello World", "timestamp": 1690000000}
```

The sender receives a delivery acknowledgment:

```json
{"event": "delivered", "message": "Hello World", "timestamp": 1690000000}
```

Messages are automatically removed from the in-memory store after **30 seconds**.

### 3. List Active Topics

```json
{"message": "/list"}
```

Server responds **only to the requesting user**:

```json
{
  "event": "topic_list",
  "data": "Active Topics:\n  sports (2 users)\n  movies (1 user)"
}
```

### 4. Disconnect

When a client disconnects:
- They are removed from the topic.
- If the topic has no remaining users it is deleted.
- Other users in the topic are unaffected.

---

## Testing Scenarios

| Scenario | How to test |
|---|---|
| Two users exchange messages | Run `client.py` — alice and bob chat in `sports` |
| `/list` shows accurate counts | Both clients send `/list` during the demo |
| Messages expire after 30 s | Check server logs after 30 s for "Message expired" entries |
| Topic removed when empty | All clients disconnect; server logs "Topic removed (empty)" |
| Invalid JSON handled | Send malformed text — server returns `{"error": "Invalid JSON payload"}` without crashing |

---

## Project Structure

```
.
├── main.py             # FastAPI WebSocket server
├── client.py   # Demo client
├── requirements.txt    # Python dependencies
└── README.md           # This file
```
