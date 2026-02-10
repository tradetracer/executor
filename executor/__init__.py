"""
TradeTracer Executor core module.

This module contains the main executor loop and supporting utilities
for configuration and transaction management.
"""

from .config import Config
from .transactions import TransactionStore

__all__ = ["Config", "TransactionStore"]
