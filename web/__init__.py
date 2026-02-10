"""
Web UI for TradeTracer Executor.

Provides a simple Flask-based configuration interface.
"""

from .app import create_app

__all__ = ["create_app"]
