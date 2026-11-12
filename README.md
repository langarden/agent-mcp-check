# agent-mcp-check

> **你的 MCP Server 敢过一遍安全体检吗？**  
> One-shot black-box security check for MCP servers — 6 probes, PASS/FAIL/WARN, hash-chained trail.

`agent-mcp-check` launches your MCP server (stdio transport) and throws a battery of malformed and hostile JSON-RPC messages at it. A well-behaved server rejects them all with proper JSON-RPC errors. A sloppy server crashes, hangs, or — worst case — *executes a tool it should never have run*. Part of the **Verifiable-agent family**.

## Why

MCP is the new Unix pipe for AI agents. Everyone is shipping MCP servers fast, and most of them were never pushed with `{"method": "tools/call", "params": null}`. This tool turns "is my MCP server fail-closed?" into one command.

**What you get:**

- **6 black-box probes**: malformed params, unknown method, missing tool name, notification without id, unknown tool, missing arguments.
- **PASS / FAIL / WARN** grading per probe, with the exact sent/received pairs.
- **Hash-chained probe trail**: every probe verdict is recorded in a verifiable JSONL trail.
- Zero dependencies — pure Python 3.9+ stdlib, launches any stdio MCP server.

## Install

```bash
pip install agent-mcp-check
```

## Quick start

```bash
# Probe an MCP server that starts as `python -m my_server` (stdio transport)
agent-mcp-check run --command python --args -m my_server

# Append a hash-chained trail
agent-mcp-check run --command npx --args mcp-server-filesystem --trail ./probe.trail.jsonl
```

## Proof of life

```
$ agent-mcp-check run --command python --args tests/mock_mcp_server.py
# MCP Server Security Check

- **Server**: `python tests/mock_mcp_server.py`
- **Grade**: **PASS**
- **Passed / Failed / Warned**: 6 / 0 / 0

| Probe | Description | Status | Note |
|:--|:--|:--|:--|
| P-01 | malformed JSON must yield an error, not a crash | PASS | server answered with a JSON-RPC error |
| P-02 | unknown method must answer method-not-found | PASS | server answered with a JSON-RPC error |
| P-03 | tools/call without a name must be rejected | PASS | server answered with a JSON-RPC error |
| P-04 | tools/call notification (no id) must not execute | PASS | notification sent, no unexpected execution |
| P-05 | unknown tool must answer an error | PASS | server answered with a JSON-RPC error |
| P-06 | tools/call missing arguments must be protocol-rejected | PASS | server answered with a JSON-RPC error |
```

A failing server shows `FAIL` entries with the received payload, so you can
see exactly where it misbehaves.

## Probes

| ID | Probe | Why it matters |
|:--|:--|:--|
| P-01 | `tools/call` with `params: null` | fail-closed servers reject; weak ones crash |
| P-02 | unknown method | must answer -32601, never silently succeed |
| P-03 | `tools/call` missing tool name | protocol error, must not fall through |
| P-04 | notification without `id` | a server must never execute a tool for it |
| P-05 | unknown tool | must answer an error, not pretend success |
| P-06 | `tools/call` missing `arguments` | protocol error |

## Invariants

| # | Invariant | Enforced by |
|:--|:--|:--|
| 1 | Every malformed call expects a JSON-RPC error | `_run_probe` |
| 2 | No response / crash / hang → FAIL | `_run_probe` |
| 3 | Trail is a hash chain (prev_hash + entry_hash) | `run_checks` trail writer |
| 4 | Synthetic data only — probes never persist real payloads | `_build_probes` |
| 5 | Server is launched fresh per run | `McpProbeClient.start` |

## License

MIT. [中文版](docs/README.zh-CN.md)