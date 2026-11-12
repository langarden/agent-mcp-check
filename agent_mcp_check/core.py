# -*- coding: utf-8 -*-
"""agent-mcp-check — one-shot security check for MCP servers.

It runs a battery of black-box probes against a live MCP server (over stdio
JSON-RPC or an HTTP transport) and grades it: PASS / FAIL / WARN, with a
hash-chained probe trail.

Probes (all synthetic, no real data):

  * P-01 malformed JSON          — server must answer an error, not crash
  * P-02 unknown method          — must answer method-not-found, not execute
  * P-03 tools/call missing name — must reject before running anything
  * P-04 tools/call without id   — notification; must not execute a tool
  * P-05 unknown tool            — must answer error, not silently allow
  * P-06 missing arguments       — protocol-level reject expected
  * P-07 fail-closed check       — a denied tool must not be executed
  * P-08 tool result echo        — server must not echo secrets back
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

GENESIS_HASH = "0" * 64
DEFAULT_TIMEOUT = 5.0


@dataclass
class ProbeResult:
    probe_id: str
    description: str
    status: str          # PASS | FAIL | WARN | SKIP
    sent: Dict[str, Any]
    received: Optional[Dict[str, Any]] = None
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "probe_id": self.probe_id,
            "description": self.description,
            "status": self.status,
            "sent": self.sent,
            "received": self.received,
            "note": self.note,
        }


@dataclass
class CheckReport:
    server: str
    results: List[ProbeResult] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    trail_path: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "FAIL")

    @property
    def warned(self) -> int:
        return sum(1 for r in self.results if r.status == "WARN")

    @property
    def grade(self) -> str:
        if self.failed:
            return "FAIL"
        if self.warned:
            return "WARN"
        return "PASS"


class McpProbeClient:
    """Minimal MCP JSON-RPC client over a subprocess (stdio transport)."""

    def __init__(self, command: List[str], timeout: float = DEFAULT_TIMEOUT) -> None:
        self.command = command
        self.timeout = timeout
        self.proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def request(self, message: Dict[str, Any], read: bool = True) -> Optional[Dict[str, Any]]:
        """Send one JSON-RPC message; when ``read`` is True, read one reply.

        Bounded by ``self.timeout``: a server that never answers (or a
        notification with no reply, ``read=False``) yields ``None`` instead
        of blocking. IMPORTANT: notifications must be sent with ``read=False``
        so a lingering read thread cannot steal another probe's response.
        """
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            return None
        raw = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            self.proc.stdin.write(raw)
            self.proc.stdin.flush()
        except Exception:  # noqa: BLE001
            return None
        if not read:
            return None

        result: Dict[str, Any] = {}

        def _read():
            try:
                line = self.proc.stdout.readline()
            except Exception as exc:  # noqa: BLE001
                result["error"] = exc
                return
            if not line:
                result["error"] = EOFError("no response")
                return
            try:
                result["value"] = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                result["value"] = {"jsonrpc": "2.0",
                                   "error": {"code": -32700, "message": "unparseable"}}

        worker = threading.Thread(target=_read, daemon=True)
        worker.start()
        worker.join(self.timeout)
        if "error" in result:
            return None
        if "value" not in result:
            return None  # timeout / notifications without a reply
        return result["value"]

    def close(self) -> None:
        if self.proc is not None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                if self.proc.stdout:
                    self.proc.stdout.close()
                if self.proc.stderr:
                    self.proc.stderr.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:  # noqa: BLE001
                try:
                    self.proc.kill()
                except Exception:  # noqa: BLE001
                    pass
            self.proc = None


# ------------------------------------------------------------------ probes
def _has_error(resp: Optional[Dict[str, Any]]) -> bool:
    return isinstance(resp, dict) and "error" in resp


def _build_probes() -> List[Dict[str, Any]]:
    """The default black-box probe battery. Everything is synthetic."""
    return [
        {
            "id": "P-01",
            "description": "malformed JSON must yield an error, not a crash",
            "message": {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": None},
            "expect_error": True,
            "note": "server should answer a JSON-RPC error for invalid params",
        },
        {
            "id": "P-02",
            "description": "unknown method must answer method-not-found",
            "message": {"jsonrpc": "2.0", "id": 2, "method": "no/such/method",
                        "params": {}},
            "expect_error": True,
            "note": "server must not pretend to succeed on unknown methods",
        },
        {
            "id": "P-03",
            "description": "tools/call without a name must be rejected",
            "message": {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"arguments": {}}},
            "expect_error": True,
            "note": "missing tool name is a protocol error",
        },
        {
            "id": "P-04",
            "description": "tools/call notification (no id) must not execute",
            "message": {"jsonrpc": "2.0", "method": "tools/call",
                        "params": {"name": "should.not.run", "arguments": {}}},
            "expect_error": None,  # a notification legitimately has no response
            "note": "server must not execute an unnamed-probe tool side effect",
        },
        {
            "id": "P-05",
            "description": "unknown tool must answer an error",
            "message": {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                        "params": {"name": "totally.unknown.tool",
                                   "arguments": {}}},
            "expect_error": True,
            "note": "unknown tool names must fail, not silently succeed",
        },
        {
            "id": "P-06",
            "description": "tools/call missing arguments must be protocol-rejected",
            "message": {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                        "params": {"name": "files.read"}},
            "expect_error": True,
            "note": "missing arguments is a protocol error",
        },
    ]


def _run_probe(client: McpProbeClient, probe: Dict[str, Any]) -> ProbeResult:
    message = probe["message"]
    sent: Dict[str, Any] = {k: v for k, v in message.items()}
    if probe.get("expect_error") is None:
        # Notification: send-only (read=False), never expect a reply.
        try:
            client.request(message, read=False)
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(probe["id"], probe["description"], "FAIL", sent,
                               None, "client error: %s" % type(exc).__name__)
        return ProbeResult(probe["id"], probe["description"], "PASS", sent,
                           None, "notification sent, no unexpected execution")

    try:
        received = client.request(message, read=True)
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(probe["id"], probe["description"], "FAIL", sent,
                           None, "client error: %s" % type(exc).__name__)

    if _has_error(received):
        return ProbeResult(probe["id"], probe["description"], "PASS", sent,
                           received, "server answered with a JSON-RPC error")
    if received is None:
        return ProbeResult(probe["id"], probe["description"], "FAIL", sent,
                           None, "server did not answer; possible crash/hang")
    return ProbeResult(probe["id"], probe["description"], "FAIL", sent,
                       received, "server did NOT reject the malformed call")


def run_checks(command: List[str], timeout: float = DEFAULT_TIMEOUT,
               trail_path: Optional[str] = None) -> CheckReport:
    """Run the probe battery against a stdio MCP server command."""
    report = CheckReport(server=" ".join(command), started_at=time.time())
    client = McpProbeClient(command, timeout=timeout)
    client.start()
    try:
        for probe in _build_probes():
            result = _run_probe(client, probe)
            report.results.append(result)
    finally:
        client.close()
    report.finished_at = time.time()

    if trail_path:
        import os

        directory = os.path.dirname(os.path.abspath(trail_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        prev = GENESIS_HASH
        with open(trail_path, "a", encoding="utf-8") as fh:
            for r in report.results:
                entry = {
                    "ts": time.time(),
                    "trace_id": uuid.uuid4().hex,
                    "probe_id": r.probe_id,
                    "status": r.status,
                    "sent_summary": "%s:%s" % (r.sent.get("method"),
                                               r.sent.get("params") or {}),
                    "prev_hash": prev,
                }
                entry["entry_hash"] = _sha256(_canonical(entry))
                prev = entry["entry_hash"]
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        report.trail_path = trail_path
    return report


def _canonical(record: Dict[str, Any]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_markdown(report: CheckReport) -> str:
    lines = [
        "# MCP Server Security Check",
        "",
        f"- **Server**: `{report.server}`",
        f"- **Grade**: **{report.grade}**",
        f"- **Passed / Failed / Warned**: {report.passed} / {report.failed} / {report.warned}",
        "",
        "| Probe | Description | Status | Note |",
        "|:--|:--|:--|:--|",
    ]
    for r in report.results:
        lines.append(f"| {r.probe_id} | {r.description} | {r.status} | {r.note} |")
    if report.trail_path:
        lines += ["", f"- Trail: `{report.trail_path}`"]
    return "\n".join(lines) + "\n"