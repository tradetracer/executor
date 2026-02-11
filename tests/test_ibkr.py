"""
Tests for IBKR adapter.

Uses mocks since we can't connect to real TWS/Gateway in tests.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestIBKRAdapter:
    """Tests for IBKRAdapter."""

    @pytest.fixture
    def mock_ib(self):
        """Create a mock IB instance."""
        mock = MagicMock()
        mock.isConnected.return_value = True
        mock.connect.return_value = None
        return mock

    @pytest.fixture
    def adapter(self, mock_ib):
        """Create IBKR adapter with mocked IB."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import IBKRAdapter

            adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=1)
            adapter._ib = mock_ib
            return adapter

    def test_config_fields(self):
        """Config fields have required structure."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import IBKRAdapter

            fields = IBKRAdapter.get_config_fields()

            names = [f["name"] for f in fields]
            assert "host" in names
            assert "port" in names
            assert "client_id" in names

    def test_init_defaults(self):
        """Default values are set correctly."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import IBKRAdapter

            adapter = IBKRAdapter()

            assert adapter.host == "127.0.0.1"
            assert adapter.port == 7497
            assert adapter.client_id == 1

    def test_init_custom_values(self):
        """Custom values are set correctly."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import IBKRAdapter

            adapter = IBKRAdapter(host="192.168.1.100", port=7496, client_id=5)

            assert adapter.host == "192.168.1.100"
            assert adapter.port == 7496
            assert adapter.client_id == 5

    def test_connect_success(self):
        """Connect returns True on success."""
        mock_ib_class = MagicMock()
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_class.return_value = mock_ib_instance

        mock_module = MagicMock()
        mock_module.IB = mock_ib_class

        with patch.dict("sys.modules", {"ib_insync": mock_module}):
            from adapters.ibkr import IBKRAdapter

            adapter = IBKRAdapter()
            result = adapter.connect()

            assert result is True
            mock_ib_instance.connect.assert_called_once()

    def test_connect_failure(self):
        """Connect returns False on failure."""
        mock_ib_class = MagicMock()
        mock_ib_instance = MagicMock()
        mock_ib_instance.connect.side_effect = Exception("Connection refused")
        mock_ib_class.return_value = mock_ib_instance

        mock_module = MagicMock()
        mock_module.IB = mock_ib_class

        with patch.dict("sys.modules", {"ib_insync": mock_module}):
            from adapters.ibkr import IBKRAdapter

            adapter = IBKRAdapter()
            result = adapter.connect()

            assert result is False

    def test_disconnect(self, adapter, mock_ib):
        """Disconnect closes connection."""
        adapter.disconnect()

        mock_ib.disconnect.assert_called_once()
        assert adapter._ib is None

    def test_execute_buy_success(self, adapter, mock_ib):
        """Successful buy returns fill details."""
        # Mock trade
        mock_trade = MagicMock()
        mock_trade.isDone.return_value = True
        mock_trade.orderStatus.status = "Filled"
        mock_trade.orderStatus.avgFillPrice = 186.52
        mock_trade.orderStatus.filled = 10
        mock_trade.fills = []

        mock_ib.placeOrder.return_value = mock_trade

        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            result = adapter.execute_buy("AAPL", 10, 186.50)

        assert result["success"] is True
        assert result["fill_price"] == 186.52
        assert result["fill_shares"] == 10

    def test_execute_buy_not_connected(self):
        """Buy fails when not connected."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import IBKRAdapter

            adapter = IBKRAdapter()
            adapter._ib = None

            result = adapter.execute_buy("AAPL", 10, 186.50)

            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_execute_sell_success(self, adapter, mock_ib):
        """Successful sell returns fill details."""
        mock_trade = MagicMock()
        mock_trade.isDone.return_value = True
        mock_trade.orderStatus.status = "Filled"
        mock_trade.orderStatus.avgFillPrice = 187.00
        mock_trade.orderStatus.filled = 5
        mock_trade.fills = []

        mock_ib.placeOrder.return_value = mock_trade

        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            result = adapter.execute_sell("AAPL", 5, 187.00)

        assert result["success"] is True
        assert result["fill_price"] == 187.00
        assert result["fill_shares"] == 5

    def test_fetch_quote_success(self, adapter, mock_ib):
        """fetch_quote returns price data from broker."""
        mock_ticker = MagicMock()
        mock_ticker.open = 185.00
        mock_ticker.high = 187.50
        mock_ticker.low = 184.25
        mock_ticker.last = 186.50
        mock_ticker.volume = 1000000
        mock_ticker.bid = 186.45
        mock_ticker.ask = 186.55

        mock_ib.reqMktData.return_value = mock_ticker
        mock_ib.qualifyContracts.return_value = None

        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            result = adapter.fetch_quote("AAPL", 185.0)

        assert result is not None
        assert result["close"] == 186.50
        assert result["bid"] == 186.45
        assert result["ask"] == 186.55

    def test_fetch_quote_not_connected(self):
        """fetch_quote returns None when not connected."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import IBKRAdapter

            adapter = IBKRAdapter()
            adapter._ib = None

            result = adapter.fetch_quote("AAPL", 185.0)

            assert result is None



class TestHelperFunctions:
    """Tests for helper functions."""

    def test_is_valid_none(self):
        """None is not valid."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import _is_valid

            assert _is_valid(None) is False

    def test_is_valid_nan(self):
        """NaN is not valid."""
        import math

        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import _is_valid

            assert _is_valid(float("nan")) is False
            assert _is_valid(math.nan) is False

    def test_is_valid_number(self):
        """Numbers are valid."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import _is_valid

            assert _is_valid(0) is True
            assert _is_valid(186.50) is True
            assert _is_valid(-10) is True

    def test_safe_float(self):
        """safe_float handles valid and invalid values."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import _safe_float

            assert _safe_float(186.50) == 186.50
            assert _safe_float(None) is None
            assert _safe_float(float("nan")) is None

    def test_safe_int(self):
        """safe_int handles valid and invalid values."""
        with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
            from adapters.ibkr import _safe_int

            assert _safe_int(100) == 100
            assert _safe_int(100.5) == 100
            assert _safe_int(None) is None
