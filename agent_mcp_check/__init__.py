# -*- coding: utf-8 -*-
"""agent-mcp-check — public surface."""

from .core import (
    CheckReport,
    McpProbeClient,
    ProbeResult,
    _build_probes,
    run_checks,
    render_markdown,
)
from .cli import main

__version__ = "0.1.0"

__all__ = [
    "CheckReport",
    "McpProbeClient",
    "ProbeResult",
    "run_checks",
    "render_markdown",
    "main",
    "__version__",
]