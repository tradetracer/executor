"""
Pending transaction storage for TradeTracer Executor.

Transactions (order fills) are stored locally until they're
successfully reported to TradeTracer on the next tick.

This provides resilience against network failures - if a tick fails,
the transactions aren't lost and will be reported on the next attempt.

Example:
    ```python
    from executor.transactions import TransactionStore

    store = TransactionStore("/data")

    # Add transactions after executing orders
    store.add([
        {
            "order_id": "abc-123",
            "symbol": "AAPL",
            "action": "buy",
            "volume": 10,
            "price": 186.50,
            "commission": 1.00,
            "time": 1707500000,
        }
    ])

    # Get pending transactions to report
    pending = store.get_pending()

    # Clear after successful report
    store.clear()
    ```
"""

import json
from pathlib import Path
from typing import Any


class TransactionStore:
    """
    Stores pending transactions in a JSON file.

    Transactions are order fills that need to be reported to TradeTracer.
    They're stored locally to survive restarts and network failures.

    Attributes:
        file_path: Path to the pending transactions JSON file.
    """

    def __init__(self, data_path: str | Path):
        """
        Initialize transaction store.

        Args:
            data_path: Path to data directory.
        """
        self.file_path = Path(data_path) / "pending_tx.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create file with empty array if it doesn't exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]")

    def get_pending(self) -> list[dict[str, Any]]:
        """
        Get all pending transactions.

        Returns:
            List of transaction dicts to report to TradeTracer.

        Example:
            ```python
            pending = store.get_pending()
            # [{"order_id": "abc", "symbol": "AAPL", ...}]
            ```
        """
        try:
            return json.loads(self.file_path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def add(self, transactions: list[dict[str, Any]]) -> None:
        """
        Add transactions to pending list.

        Args:
            transactions: List of transaction dicts with keys:
                - order_id: ID of the original order
                - symbol: Stock symbol
                - action: "buy" or "sell"
                - volume: Number of shares filled
                - price: Fill price
                - commission: Broker commission
                - time: Unix timestamp of fill

        Example:
            ```python
            store.add([{
                "order_id": "abc-123",
                "symbol": "AAPL",
                "action": "buy",
                "volume": 10,
                "price": 186.50,
                "commission": 1.00,
                "time": 1707500000,
            }])
            ```
        """
        if not transactions:
            return

        current = self.get_pending()
        current.extend(transactions)
        self.file_path.write_text(json.dumps(current, indent=2))

    def clear(self) -> None:
        """
        Clear all pending transactions.

        Call this after successfully reporting transactions to TradeTracer.

        Example:
            ```python
            pending = store.get_pending()
            if report_to_tradetracer(pending):
                store.clear()
            ```
        """
        self.file_path.write_text("[]")

    def count(self) -> int:
        """
        Get number of pending transactions.

        Returns:
            Count of pending transactions.
        """
        return len(self.get_pending())
