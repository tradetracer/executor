"""
Tests for broker adapters.
"""

import pytest

from adapters import (
    BaseAdapter,
    SandboxAdapter,
    get_adapter,
    get_adapter_fields,
    list_adapters,
)


class TestAdapterRegistry:
    """Tests for adapter registry functions."""

    def test_list_adapters_includes_sandbox(self):
        """Sandbox adapter is always available."""
        adapters = list_adapters()
        assert "sandbox" in adapters

    def test_get_adapter_sandbox(self):
        """Can create sandbox adapter via registry."""
        adapter = get_adapter("sandbox", {})
        assert isinstance(adapter, SandboxAdapter)

    def test_get_adapter_unknown_raises(self):
        """Unknown adapter type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown adapter"):
            get_adapter("nonexistent", {})

    def test_get_adapter_fields_sandbox(self):
        """Sandbox adapter returns config fields."""
        fields = get_adapter_fields("sandbox")
        assert isinstance(fields, list)

    def test_get_adapter_fields_unknown_returns_empty(self):
        """Unknown adapter returns empty field list."""
        fields = get_adapter_fields("nonexistent")
        assert fields == []


class TestSandboxAdapter:
    """Tests for SandboxAdapter."""

    @pytest.fixture
    def adapter(self) -> SandboxAdapter:
        """Create a sandbox adapter."""
        adapter = SandboxAdapter()
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_connect_returns_true(self):
        """Connect always succeeds."""
        adapter = SandboxAdapter()
        assert adapter.connect() is True

    def test_execute_buy_always_fills(self, adapter: SandboxAdapter):
        """Buy order always fills at given price."""
        result = adapter.execute_buy("AAPL", 10, 186.50)

        assert result["success"] is True
        assert result["fill_price"] == 186.50
        assert result["fill_shares"] == 10
        assert result["commission"] == 0.0

    def test_execute_sell_always_fills(self, adapter: SandboxAdapter):
        """Sell order always fills at given price."""
        result = adapter.execute_sell("AAPL", 5, 190.00)

        assert result["success"] is True
        assert result["fill_price"] == 190.00
        assert result["fill_shares"] == 5
        assert result["commission"] == 0.0

    def test_execute_order_buy(self, adapter: SandboxAdapter):
        """execute_order dispatches buy correctly."""
        result = adapter.execute_order({
            "action": "buy",
            "symbol": "AAPL",
            "volume": 10,
            "price": 100.0,
            "order_id": "test-123",
        })
        assert result["success"] is True
        assert result["fill_shares"] == 10

    def test_execute_order_sell(self, adapter: SandboxAdapter):
        """execute_order dispatches sell correctly."""
        result = adapter.execute_order({
            "action": "sell",
            "symbol": "AAPL",
            "volume": 5,
            "price": 120.0,
            "order_id": "test-456",
        })
        assert result["success"] is True
        assert result["fill_shares"] == 5

    def test_fetch_quote_returns_none_without_eod(self, adapter: SandboxAdapter):
        """Sandbox returns None when no EOD price available."""
        assert adapter.fetch_quote("AAPL", None) is None

    def test_fetch_quote_simulates_from_eod(self, adapter: SandboxAdapter):
        """Sandbox simulates intraday price within 0.5% of EOD."""
        quote = adapter.fetch_quote("AAPL", 100.0)
        assert 99.5 <= quote["close"] <= 100.5
        assert quote["bid"] < quote["close"] < quote["ask"]

    def test_fetch_quote_spread_scales_with_price(self, adapter: SandboxAdapter):
        """Spread is proportional to price."""
        cheap = adapter.fetch_quote("PENNY", 1.0)
        expensive = adapter.fetch_quote("EXPEN", 500.0)

        cheap_spread = cheap["ask"] - cheap["bid"]
        expensive_spread = expensive["ask"] - expensive["bid"]

        assert cheap_spread <= 0.03
        assert expensive_spread > cheap_spread

    def test_fetch_quote_random_walk(self, adapter: SandboxAdapter):
        """Subsequent calls walk from previous close, not EOD."""
        q1 = adapter.fetch_quote("AAPL", 100.0)
        q2 = adapter.fetch_quote("AAPL", 100.0)

        # q2 should be within 0.5% of q1, not of EOD
        assert abs(q2["close"] - q1["close"]) / q1["close"] <= 0.005

    def test_fetch_quote_resets_on_disconnect(self, adapter: SandboxAdapter):
        """Disconnect clears last prices."""
        adapter.fetch_quote("AAPL", 100.0)
        adapter.disconnect()
        assert adapter._last_prices == {}


class TestBaseAdapter:
    """Tests for BaseAdapter abstract class."""

    def test_cannot_instantiate(self):
        """Cannot instantiate abstract class directly."""
        with pytest.raises(TypeError):
            BaseAdapter()

    def test_subclass_must_implement_methods(self):
        """Subclass must implement all abstract methods."""

        class IncompleteAdapter(BaseAdapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()
