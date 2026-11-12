# -*- coding: utf-8 -*-
"""A tiny, well-behaved MCP JSON-RPC server used in tests.

It rejects malformed tool calls with JSON-RPC errors and supports one real
tool ('files.read') so probe P-05/P-06 have a well-defined target. This is a
*mock* for tests only — never used in production.
"""

import json
import sys

KNOWN_METHODS = {"tools/list", "tools/call", "ping"}
KNOWN_TOOLS = {"files.read"}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(line: str):
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "parse error"}}
    if not isinstance(msg, dict):
        return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "invalid request"}}

    method = msg.get("method")
    req_id = msg.get("id")

    if method not in KNOWN_METHODS:
        if req_id is None:
            return None  # notification we ignore
        return _error(req_id, -32601, "method not found")

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id,
                "result": {"tools": [{"name": "files.read", "description": "read a file"}]}}

    # tools/call
    params = msg.get("params")
    if not isinstance(params, dict):
        if req_id is None:
            return None
        return _error(req_id, -32602, "invalid params")
    name = params.get("name")
    if not isinstance(name, str) or not name:
        if req_id is None:
            return None
        return _error(req_id, -32602, "missing tool name")
    if name not in KNOWN_TOOLS:
        if req_id is None:
            return None  # notifications must never be answered
        return _error(req_id, -32602, "unknown tool")
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        return _error(req_id, -32602, "missing arguments")
    # well-behaved server never executes a tool for a notification with a name arg
    if req_id is None:
        return None
    return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [], "isError": False}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        resp = handle(line)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()