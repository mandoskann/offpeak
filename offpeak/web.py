"""Simulated Alexa+ experience: a browser "Echo Show" for OffPeak.

    Browser (voice in via Web Speech API, voice out via speech synthesis)
        -> this web app
             /api/ask      -> OffPeak agent (Claude + Agent Skill) -> MCP tools
             watcher       -> MCP tool check_for_price_spike every few seconds,
                              so the autopilot acts on its own and the UI
                              announces it without being asked
        -> OffPeak MCP server (must be running: python -m offpeak.server)

Run:  python -m offpeak.web      then open http://127.0.0.1:8080 in Chrome
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from strands.tools.mcp import MCPClient

from offpeak import agent as offpeak_agent
from offpeak import home

# Strands logs a long traceback when the MCP server isn't up yet; we handle that ourselves
logging.getLogger("strands.tools.mcp.mcp_client").setLevel(logging.CRITICAL)

STATIC = Path(__file__).resolve().parent / "static"
WATCH_SECONDS = float(os.getenv("OFFPEAK_WATCH_SECONDS", "60"))
REPLAY_WATCH_SECONDS = float(os.getenv("OFFPEAK_REPLAY_WATCH_SECONDS", "5"))


mcp: MCPClient | None = None
_mcp_lock = threading.RLock()
_agent = None
_agent_lock = threading.Lock()
_events: list[dict] = []  # autopilot notifications for the UI, newest last
_events_lock = threading.Lock()


def ensure_mcp() -> MCPClient:
    """Connect (or reconnect) to the OffPeak MCP server.

    If the server was restarted, the old session is dead; start a fresh one
    and drop the agent so it's rebuilt with tools bound to the new session.
    """
    global mcp, _agent
    with _mcp_lock:
        if mcp is not None and mcp._is_session_active():
            return mcp
        if mcp is not None:
            try:
                mcp.stop(None, None, None)
            except Exception:
                pass
        client = MCPClient(url=offpeak_agent.MCP_URL)
        client.start()  # raises if the server isn't running
        mcp = client
        _agent = None
        print(f"[web] connected to MCP server at {offpeak_agent.MCP_URL}")
        return mcp


def call_tool(name: str, args: dict | None = None) -> dict:
    """Call an OffPeak MCP tool and return its JSON result."""
    try:
        result = ensure_mcp().call_tool_sync(str(uuid.uuid4()), name, args or {})
    except Exception:
        reset_mcp()
        result = ensure_mcp().call_tool_sync(str(uuid.uuid4()), name, args or {})
    if result.get("structuredContent"):
        data = result["structuredContent"]
        return data.get("result", data) if isinstance(data, dict) else data
    for item in result.get("content", []):
        text = item.get("text") if isinstance(item, dict) else None
        if text:
            try:
                return json.loads(text)
            except ValueError:
                return {"text": text}
    return {}


def reset_mcp() -> None:
    """Force a reconnect on the next call."""
    global mcp, _agent
    with _mcp_lock:
        if mcp is not None:
            try:
                mcp.stop(None, None, None)
            except Exception:
                pass
        mcp = None
        _agent = None


def get_agent():
    global _agent
    client = ensure_mcp()
    if _agent is None:
        _agent = offpeak_agent.build_agent(client)
    return _agent


def push_event(event: dict) -> None:
    with _events_lock:
        event["id"] = len(_events) + 1
        event["at"] = time.time()
        _events.append(event)
        del _events[:-30]


# ---------------------------------------------------------------- watcher
def watcher() -> None:
    """The autopilot's eyes: checks for price spikes on its own, forever."""
    last_check = 0.0
    while True:
        time.sleep(1)
        replay = home.load().get("demo") is not None
        interval = REPLAY_WATCH_SECONDS if replay else WATCH_SECONDS
        if time.time() - last_check < interval:
            continue
        last_check = time.time()
        try:
            result = call_tool("check_for_price_spike")
        except Exception as exc:  # keep watching even if one check fails
            print(f"[watcher] check failed: {exc}")
            continue
        if result.get("spike"):
            push_event({"kind": "spike", "spoken": result.get("spoken", ""),
                        "price_cents": result.get("price_cents"),
                        "actions": result.get("actions", []),
                        "saved_dollars": result.get("saved_dollars", 0)})


def startup() -> None:
    try:
        ensure_mcp()
    except Exception as exc:
        print(f"[web] MCP server not reachable yet ({exc}). Start it with: python -m offpeak.server")
    threading.Thread(target=watcher, daemon=True).start()
    print(f"OffPeak web ready ({offpeak_agent.model_label()}). Open http://127.0.0.1:{PORT}")


def shutdown() -> None:
    reset_mcp()


@asynccontextmanager
async def lifespan(_app):
    startup()
    yield
    shutdown()


app = FastAPI(title="OffPeak: simulated Alexa+", lifespan=lifespan)


# ---------------------------------------------------------------- API
class Ask(BaseModel):
    text: str


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/ask")
def ask(body: Ask):
    text = body.text.strip()
    if not text:
        return {"answer": "", "tools": []}
    with _agent_lock:  # one conversation at a time
        for attempt in (1, 2):
            try:
                a = get_agent()
                since = len(a.messages)
                t0 = time.perf_counter()
                result = a(offpeak_agent.with_clock(text))
                secs = round(time.perf_counter() - t0, 1)
                tools = offpeak_agent.tool_results(a, since)
                break
            except Exception as exc:
                msg = str(exc).lower()
                lost_mcp = "MCP" in type(exc).__name__ or "client session" in msg or "mcp server" in msg
                if attempt == 1 and lost_mcp:
                    reset_mcp()  # server was restarted: reconnect and try once more
                    continue
                hint = ("I can't reach the OffPeak server. Make sure it's running."
                        if lost_mcp else "I can't reach the AI model right now. Check the model settings in .env.")
                return JSONResponse({"error": f"{type(exc).__name__}: {exc}", "answer": hint}, status_code=500)
    return {"answer": str(result).strip(), "tools": tools, "seconds": secs}


@app.get("/api/state")
def state(since: int = 0):
    """Polled by the UI: device tiles, plan, live price, and new autopilot events."""
    try:
        price = call_tool("get_live_price")
    except Exception:
        price = None
    with _events_lock:
        events = [e for e in _events if e["id"] > since]
    return {"home": home.status(), "price": price, "events": events,
            "model": offpeak_agent.model_label()}


@app.get("/api/forecast")
def forecast():
    return call_tool("get_price_forecast", {"hours": 24})


@app.post("/api/replay")
def replay():
    """Start the spike replay (the demo's 'wow' moment)."""
    return call_tool("start_spike_replay")


@app.post("/api/reset")
def reset():
    """Reset the simulated home and conversation (between demo takes)."""
    global _agent
    home.reset()
    with _agent_lock:
        _agent = None
    with _events_lock:
        _events.clear()
    return {"ok": True}


PORT = int(os.getenv("OFFPEAK_WEB_PORT", "8080"))


def main() -> None:
    uvicorn.run(app, host=os.getenv("OFFPEAK_WEB_HOST", "127.0.0.1"), port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
