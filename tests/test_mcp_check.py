# -*- coding: utf-8 -*-
"""agent-mcp-check tests — probe battery against a mock MCP server."""

import json
import os
import sys
import tempfile
import unittest

from agent_mcp_check import (
    McpProbeClient,
    ProbeResult,
    _build_probes,
    run_checks,
    render_markdown,
)
from agent_mcp_check.core import _canonical, _sha256, GENESIS_HASH


def _server_command():
    here = os.path.dirname(os.path.abspath(__file__))
    return [sys.executable, os.path.join(here, "mock_mcp_server.py")]


class MockServerTest(unittest.TestCase):
    def test_well_behaved_server_passes_all_probes(self):
        report = run_checks(_server_command())
        self.assertEqual(report.passed, 6, "well-behaved server should pass all probes")
        self.assertEqual(report.failed, 0)
        self.assertEqual(report.grade, "PASS")

    def test_trail_is_hash_chained(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "probe.trail.jsonl")
            report = run_checks(_server_command(), trail_path=path)
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as fh:
                entries = [json.loads(line) for line in fh if line.strip()]
            self.assertEqual(len(entries), report.passed)
            prev = GENESIS_HASH
            for entry in entries:
                body = {k: v for k, v in entry.items() if k != "entry_hash"}
                self.assertEqual(body["prev_hash"], prev)
                self.assertEqual(_sha256(_canonical(body)), entry["entry_hash"])
                prev = entry["entry_hash"]

    def test_markdown_render(self):
        report = run_checks(_server_command())
        md = render_markdown(report)
        self.assertIn("# MCP Server Security Check", md)
        self.assertIn("PASS", md)


class ProbeClientTest(unittest.TestCase):
    def test_probe_client_request(self):
        client = McpProbeClient(_server_command())
        client.start()
        try:
            resp = client.request({"jsonrpc": "2.0", "id": 1, "method": "ping",
                                   "params": {}})
            self.assertIsNotNone(resp)
            self.assertIn("result", resp)
        finally:
            client.close()

    def test_probe_battery_shapes(self):
        probes = _build_probes()
        self.assertEqual(len(probes), 6)
        ids = {p["id"] for p in probes}
        self.assertEqual(ids, {"P-01", "P-02", "P-03", "P-04", "P-05", "P-06"})


class ResultTest(unittest.TestCase):
    def test_probe_result_as_dict(self):
        r = ProbeResult("P-01", "desc", "PASS", {"method": "x"}, {"error": {}})
        d = r.as_dict()
        self.assertEqual(d["probe_id"], "P-01")
        self.assertEqual(d["status"], "PASS")

    def test_report_grade(self):
        from agent_mcp_check import CheckReport

        report = CheckReport(server="s")
        report.results.append(ProbeResult("P-01", "", "PASS", {}))
        self.assertEqual(report.grade, "PASS")
        report.results.append(ProbeResult("P-02", "", "FAIL", {}))
        self.assertEqual(report.grade, "FAIL")


if __name__ == "__main__":
    unittest.main()