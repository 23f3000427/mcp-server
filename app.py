import hashlib
import json

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

EMAIL = "23f3000427@ds.study.iitm.ac.in".strip().lower()
DEFAULT_PROTOCOL = "2025-03-26"

TOOL = {
    "name": "solve_challenge",
    "description": "Returns the exam answer for the challenge sent in the X-Exam-Challenge header.",
    "inputSchema": {"type": "object", "properties": {}},
}


def answer_for(challenge: str) -> str:
    return hashlib.sha256(f"{challenge}:{EMAIL}".encode()).hexdigest()[:16]


def handle(msg: dict, request: Request):
    """Return a JSON-RPC response dict, or None for notifications."""
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}

    if mid is None:  # notification (e.g. notifications/initialized)
        return None

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "exam-mcp", "version": "1.0.0"},
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        if params.get("name") != "solve_challenge":
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": "Unknown tool"}}
        challenge = (request.headers.get("x-exam-challenge") or "").strip()
        if not challenge:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": "missing X-Exam-Challenge header"}],
                "isError": True}}
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": answer_for(challenge)}],
            "isError": False}}
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


async def mcp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return Response(
            json.dumps({"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}}),
            media_type="application/json", status_code=400)

    if isinstance(body, list):
        out = [r for r in (handle(m, request) for m in body) if r is not None]
        payload = out if out else None
    else:
        payload = handle(body, request)

    if payload is None:
        return Response(status_code=202)

    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept and "application/json" not in accept:
        return Response(f"event: message\ndata: {json.dumps(payload)}\n\n",
                        media_type="text/event-stream")
    return Response(json.dumps(payload), media_type="application/json")


app.add_api_route("/mcp", mcp, methods=["POST"])
app.add_api_route("/mcp/", mcp, methods=["POST"])


@app.get("/mcp")
@app.get("/mcp/")
async def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})


@app.get("/")
async def root():
    return {"status": "ok", "endpoint": "/mcp"}
