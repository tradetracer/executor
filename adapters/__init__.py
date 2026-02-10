"""
Broker adapters for TradeTracer Executor.

This module provides the adapter registry and factory functions
for creating broker adapter instances.

Available Adapters:
    - `sandbox`: Paper trading with SQLite (always available)
    - `ibkr`: Interactive Brokers via TWS/Gateway (requires ib_insync)

Example:
    ```python
    from adapters import get_adapter, list_adapters

    # See available adapters
    print(list_adapters())  # ["sandbox", "ibkr"]

    # Create an adapter
    adapter = get_adapter("sandbox", {"initial_cash": 100000})
    adapter.connect()

    # Execute an order
    result = adapter.execute_order({
        "action": "buy",
        "symbol": "AAPL",
        "volume": 10,
        "price": 186.50
    })
    ```
"""

from typing import Any

from .base import BaseAdapter, ConfigField, FillResult, Order, Quote
from .sandbox import SandboxAdapter

# Adapter registry
ADAPTERS: dict[str, type[BaseAdapter]] = {
    "sandbox": SandboxAdapter,
}

# Optional IBKR adapter (requires ib_insync)
try:
    from .ibkr import IBKRAdapter

    ADAPTERS["ibkr"] = IBKRAdapter
except ImportError:
    pass


def get_adapter(adapter_type: str, config: dict[str, Any]) -> BaseAdapter:
    """
    Create an adapter instance by type.

    Args:
        adapter_type: Adapter identifier (e.g., "sandbox", "ibkr").
        config: Adapter-specific configuration dict.

    Returns:
        Configured adapter instance.

    Raises:
        ValueError: If adapter_type is unknown.

    Example:
        ```python
        adapter = get_adapter("sandbox", {"initial_cash": 50000})
        ```
    """
    adapter_class = ADAPTERS.get(adapter_type)
    if not adapter_class:
        available = ", ".join(ADAPTERS.keys())
        raise ValueError(f"Unknown adapter: {adapter_type}. Available: {available}")
    return adapter_class(**config)


def get_adapter_fields(adapter_type: str) -> list[dict[str, Any]]:
    """
    Get configuration fields for an adapter's web UI.

    Args:
        adapter_type: Adapter identifier.

    Returns:
        List of field configuration dicts, or empty list if unknown.

    Example:
        ```python
        fields = get_adapter_fields("sandbox")
        # [{"name": "initial_cash", "type": "number", ...}]
        ```
    """
    adapter_class = ADAPTERS.get(adapter_type)
    if not adapter_class:
        return []
    return adapter_class.get_config_fields()


def list_adapters() -> list[str]:
    """
    List available adapter types.

    Returns:
        List of adapter identifiers.

    Example:
        ```python
        adapters = list_adapters()
        # ["sandbox", "ibkr"]
        ```
    """
    return list(ADAPTERS.keys())


__all__ = [
    "BaseAdapter",
    "ConfigField",
    "FillResult",
    "Order",
    "Quote",
    "SandboxAdapter",
    "get_adapter",
    "get_adapter_fields",
    "list_adapters",
]
