"""
Tests for main executor loop.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from executor.main import Executor
from executor.config import Config


class TestExecutor:
    """Tests for Executor class."""

    @pytest.fixture
    def config_path(self, tmp_path: Path) -> Path:
        """Create a valid config file."""
        data_path = tmp_path / "data"
        data_path.mkdir()
        config = Config(
            api_key="test-api-key",
            adapter="sandbox",
            adapter_config={
                "db_path": str(data_path / "sandbox.db"),
                "initial_cash": 10000,
            },
            data_path=str(data_path),
        )
        config_file = tmp_path / "config.json"
        config.save(config_file)
        return config_file

    @pytest.fixture
    def executor(self, config_path: Path) -> Executor:
        """Create an executor instance."""
        return Executor(config_path)

    def test_init_loads_config(self, executor: Executor):
        """Executor loads config on init."""
        assert executor.config.api_key == "test-api-key"

    def test_init_creates_transactions(self, executor: Executor):
        """Executor creates transaction store."""
        assert executor.transactions is not None

    def test_start_with_valid_config(self, executor: Executor):
        """Start succeeds with valid config."""
        result = executor.start()
        assert result is True
        assert executor.running is True
        assert executor.adapter is not None
        executor.stop()

    def test_start_with_invalid_config(self, tmp_path: Path):
        """Start fails with missing api_key."""
        data_path = tmp_path / "data"
        data_path.mkdir()
        config = Config(
            data_path=str(data_path),  # No api_key
        )
        config_file = tmp_path / "config.json"
        config.save(config_file)

        executor = Executor(config_file)
        result = executor.start()

        assert result is False
        assert executor.running is False

    def test_stop_disconnects_adapter(self, executor: Executor):
        """Stop disconnects from adapter."""
        executor.start()
        executor.stop()

        assert executor.running is False

    def test_get_status(self, executor: Executor):
        """get_status returns correct info."""
        status = executor.get_status()

        assert status["running"] is False
        assert status["tick_count"] == 0
        assert status["config_valid"] is True
        assert status["adapter"] == "sandbox"

    @patch("executor.main.requests.post")
    def test_tick_success(self, mock_post: Mock, executor: Executor):
        """Successful tick cycle."""
        # Mock TradeTracer response
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(
                return_value={
                    "orders": [
                        {
                            "order_id": "order-1",
                            "action": "buy",
                            "symbol": "AAPL",
                            "volume": 10,
                            "price": 100.0,
                        }
                    ]
                }
            ),
        )

        executor.start()
        result = executor.tick()
        executor.stop()

        assert result["success"] is True
        assert result["orders_received"] == 1
        assert result["orders_filled"] == 1
        assert executor.tick_count == 1

    @patch("executor.main.requests.post")
    def test_tick_reports_transactions(self, mock_post: Mock, executor: Executor):
        """Tick sends pending transactions."""
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(return_value={"orders": []}),
        )

        # Add a pending transaction
        executor.start()
        executor.transactions.add(
            [
                {
                    "order_id": "prev-order",
                    "symbol": "AAPL",
                    "action": "buy",
                    "volume": 5,
                    "price": 99.0,
                    "commission": 0,
                    "time": 1234567890,
                }
            ]
        )

        executor.tick()
        executor.stop()

        # Check that transaction was sent
        call_args = mock_post.call_args
        sent_data = call_args.kwargs["json"]
        assert len(sent_data["transactions"]) == 1
        assert sent_data["transactions"][0]["order_id"] == "prev-order"

    @patch("executor.main.requests.post")
    def test_tick_clears_transactions_after_success(
        self, mock_post: Mock, executor: Executor
    ):
        """Pending transactions cleared after successful tick."""
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(return_value={"orders": []}),
        )

        executor.start()
        executor.transactions.add(
            [
                {
                    "order_id": "prev-order",
                    "symbol": "AAPL",
                    "action": "buy",
                    "volume": 5,
                    "price": 99.0,
                    "commission": 0,
                    "time": 1234567890,
                }
            ]
        )

        executor.tick()
        executor.stop()

        assert executor.transactions.count() == 0

    @patch("executor.main.requests.post")
    def test_tick_stores_new_fills(self, mock_post: Mock, executor: Executor):
        """New fills stored for next tick."""
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(
                return_value={
                    "orders": [
                        {
                            "order_id": "new-order",
                            "action": "buy",
                            "symbol": "AAPL",
                            "volume": 10,
                            "price": 100.0,
                        }
                    ]
                }
            ),
        )

        executor.start()
        executor.tick()
        executor.stop()

        # New fill should be pending
        pending = executor.transactions.get_pending()
        assert len(pending) == 1
        assert pending[0]["order_id"] == "new-order"
        assert pending[0]["volume"] == 10

    @patch("executor.main.requests.post")
    def test_tick_handles_failed_order(self, mock_post: Mock, executor: Executor):
        """Handles order execution failure gracefully."""
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(
                return_value={
                    "orders": [
                        {
                            "order_id": "fail-order",
                            "action": "buy",
                            "symbol": "AAPL",
                            "volume": 10,
                            "price": 100.0,
                        }
                    ]
                }
            ),
        )

        executor.start()
        # Mock adapter to return failure
        executor.adapter.execute_order = Mock(
            return_value={"success": False, "error": "Broker rejected"}
        )
        result = executor.tick()
        executor.stop()

        assert result["success"] is True
        assert result["orders_received"] == 1
        assert result["orders_filled"] == 0

    @patch("executor.main.requests.post")
    def test_tick_handles_network_error(self, mock_post: Mock, executor: Executor):
        """Handles network errors gracefully."""
        import requests

        mock_post.side_effect = requests.RequestException("Connection failed")

        executor.start()
        result = executor.tick()
        executor.stop()

        assert result["success"] is False
        assert "Connection failed" in result["error"]

    @patch("executor.main.requests.post")
    def test_tick_handles_api_error(self, mock_post: Mock, executor: Executor):
        """Handles API errors gracefully."""
        mock_post.return_value = Mock(
            ok=False,
            status_code=401,
            text="Unauthorized",
        )

        executor.start()
        result = executor.tick()
        executor.stop()

        assert result["success"] is False

    @patch("executor.main.requests.post")
    def test_tick_sends_prices_in_api_format(self, mock_post: Mock, executor: Executor):
        """Tick maps adapter quotes to API ohlcv format."""
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(return_value={"orders": [], "prices": {"AAPL": 186.5}}),
        )

        executor.start()
        executor.symbols = ["AAPL"]
        executor.eod_prices = {"AAPL": 186.5}
        executor.adapter.fetch_quote = Mock(
            return_value={
                "open": 185.0,
                "high": 187.5,
                "low": 184.25,
                "close": 186.5,
                "volume": 1234567,
                "bid": 186.45,
                "ask": 186.55,
            }
        )

        executor.tick()
        executor.stop()

        sent_data = mock_post.call_args.kwargs["json"]
        price = sent_data["prices"]["AAPL"]
        assert price["ohlcv"] == {
            "o": 185.0,
            "h": 187.5,
            "l": 184.25,
            "c": 186.5,
            "v": 1234567,
        }
        assert price["bid"] == 186.45
        assert price["ask"] == 186.55
        assert "time" in price

    @patch("executor.main.requests.post")
    def test_tick_skips_symbols_with_no_quote(self, mock_post: Mock, executor: Executor):
        """Tick skips symbols where adapter returns None."""
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(return_value={"orders": [], "prices": {"AAPL": 186.5}}),
        )

        executor.start()
        executor.symbols = ["AAPL"]
        executor.adapter.fetch_quote = Mock(return_value=None)

        executor.tick()
        executor.stop()

        sent_data = mock_post.call_args.kwargs["json"]
        assert sent_data["prices"] == {}

    @patch("executor.main.requests.post")
    def test_tick_updates_symbols_from_response(self, mock_post: Mock, executor: Executor):
        """Tick updates tracked symbols from prices in API response."""
        mock_post.return_value = Mock(
            ok=True,
            json=Mock(return_value={"orders": [], "prices": {"AAPL": 186.5, "TSLA": 250.0}}),
        )

        executor.start()
        executor.tick()
        executor.stop()

        assert set(executor.symbols) == {"AAPL", "TSLA"}

    def test_tick_increments_counter(self, executor: Executor):
        """Each tick increments counter."""
        with patch("executor.main.requests.post") as mock_post:
            mock_post.return_value = Mock(
                ok=True,
                json=Mock(return_value={"orders": []}),
            )

            executor.start()
            executor.tick()
            executor.tick()
            executor.tick()
            executor.stop()

            assert executor.tick_count == 3
