# -*- coding: utf-8 -*-
"""agent-mcp-check CLI entry."""

from __future__ import annotations

import argparse
import json
import sys

from .core import run_checks, render_markdown


def cmd_run(args: argparse.Namespace) -> int:
    command = [args.command] + (args.args or [])
    report = run_checks(command, timeout=args.timeout, trail_path=args.trail)
    if args.json:
        print(json.dumps(
            {
                "server": report.server,
                "grade": report.grade,
                "passed": report.passed,
                "failed": report.failed,
                "warned": report.warned,
                "results": [r.as_dict() for r in report.results],
                "trail_path": report.trail_path,
            },
            ensure_ascii=False, indent=2,
        ))
        return 0
    print(render_markdown(report))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-mcp-check",
        description="One-shot security check for MCP servers (black-box probes).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the security probe battery")
    run.add_argument("--command", required=True,
                     help="MCP server binary/command to launch (stdio transport)")
    run.add_argument("--args", nargs="*", default=[],
                     help="extra args passed to the server (e.g. --args -m my_server)")
    run.add_argument("--timeout", type=float, default=5.0,
                     help="per-probe timeout in seconds (default 5.0)")
    run.add_argument("--trail", default="",
                     help="append a hash-chained probe trail JSONL to this path")
    run.add_argument("--json", action="store_true", help="output JSON")
    run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())