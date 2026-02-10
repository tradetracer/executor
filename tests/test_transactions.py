"""
Tests for transaction storage.
"""

from pathlib import Path

import pytest

from executor.transactions import TransactionStore


class TestTransactionStore:
    """Tests for TransactionStore."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> TransactionStore:
        """Create a transaction store with temp directory."""
        return TransactionStore(tmp_path)

    def test_init_creates_file(self, tmp_path: Path):
        """Initializing store creates pending_tx.json."""
        TransactionStore(tmp_path)  # Side effect: creates file
        assert (tmp_path / "pending_tx.json").exists()

    def test_init_creates_parent_dirs(self, tmp_path: Path):
        """Store creates parent directories if needed."""
        data_path = tmp_path / "nested" / "dir"
        TransactionStore(data_path)  # Side effect: creates directories
        assert (data_path / "pending_tx.json").exists()

    def test_get_pending_empty(self, store: TransactionStore):
        """New store has no pending transactions."""
        assert store.get_pending() == []

    def test_add_single_transaction(self, store: TransactionStore):
        """Can add a single transaction."""
        tx = {
            "order_id": "abc-123",
            "symbol": "AAPL",
            "action": "buy",
            "volume": 10,
            "price": 186.50,
            "commission": 1.00,
            "time": 1707500000,
        }
        store.add([tx])

        pending = store.get_pending()
        assert len(pending) == 1
        assert pending[0] == tx

    def test_add_multiple_transactions(self, store: TransactionStore):
        """Can add multiple transactions at once."""
        txs = [
            {
                "order_id": "1",
                "symbol": "AAPL",
                "action": "buy",
                "volume": 10,
                "price": 100,
                "commission": 0,
                "time": 1,
            },
            {
                "order_id": "2",
                "symbol": "TSLA",
                "action": "sell",
                "volume": 5,
                "price": 200,
                "commission": 0,
                "time": 2,
            },
        ]
        store.add(txs)

        pending = store.get_pending()
        assert len(pending) == 2

    def test_add_accumulates(self, store: TransactionStore):
        """Multiple add calls accumulate transactions."""
        store.add(
            [
                {
                    "order_id": "1",
                    "symbol": "AAPL",
                    "action": "buy",
                    "volume": 10,
                    "price": 100,
                    "commission": 0,
                    "time": 1,
                }
            ]
        )
        store.add(
            [
                {
                    "order_id": "2",
                    "symbol": "TSLA",
                    "action": "buy",
                    "volume": 5,
                    "price": 200,
                    "commission": 0,
                    "time": 2,
                }
            ]
        )

        pending = store.get_pending()
        assert len(pending) == 2

    def test_add_empty_list_does_nothing(self, store: TransactionStore):
        """Adding empty list doesn't modify file."""
        store.add(
            [
                {
                    "order_id": "1",
                    "symbol": "AAPL",
                    "action": "buy",
                    "volume": 10,
                    "price": 100,
                    "commission": 0,
                    "time": 1,
                }
            ]
        )
        store.add([])

        assert store.count() == 1

    def test_clear_removes_all(self, store: TransactionStore):
        """Clear removes all pending transactions."""
        store.add(
            [
                {
                    "order_id": "1",
                    "symbol": "AAPL",
                    "action": "buy",
                    "volume": 10,
                    "price": 100,
                    "commission": 0,
                    "time": 1,
                },
                {
                    "order_id": "2",
                    "symbol": "TSLA",
                    "action": "buy",
                    "volume": 5,
                    "price": 200,
                    "commission": 0,
                    "time": 2,
                },
            ]
        )
        store.clear()

        assert store.get_pending() == []
        assert store.count() == 0

    def test_count(self, store: TransactionStore):
        """Count returns number of pending transactions."""
        assert store.count() == 0

        store.add(
            [
                {
                    "order_id": "1",
                    "symbol": "AAPL",
                    "action": "buy",
                    "volume": 10,
                    "price": 100,
                    "commission": 0,
                    "time": 1,
                }
            ]
        )
        assert store.count() == 1

        store.add(
            [
                {
                    "order_id": "2",
                    "symbol": "TSLA",
                    "action": "buy",
                    "volume": 5,
                    "price": 200,
                    "commission": 0,
                    "time": 2,
                }
            ]
        )
        assert store.count() == 2

    def test_persistence(self, tmp_path: Path):
        """Transactions persist across store instances."""
        store1 = TransactionStore(tmp_path)
        store1.add(
            [
                {
                    "order_id": "1",
                    "symbol": "AAPL",
                    "action": "buy",
                    "volume": 10,
                    "price": 100,
                    "commission": 0,
                    "time": 1,
                }
            ]
        )

        store2 = TransactionStore(tmp_path)
        assert store2.count() == 1
        assert store2.get_pending()[0]["order_id"] == "1"

    def test_handles_corrupted_file(self, tmp_path: Path):
        """Gracefully handles corrupted JSON file."""
        file_path = tmp_path / "pending_tx.json"
        file_path.write_text("not valid json")

        store = TransactionStore(tmp_path)
        assert store.get_pending() == []

    def test_handles_missing_file(self, tmp_path: Path):
        """Gracefully handles deleted file."""
        store = TransactionStore(tmp_path)
        (tmp_path / "pending_tx.json").unlink()

        assert store.get_pending() == []
